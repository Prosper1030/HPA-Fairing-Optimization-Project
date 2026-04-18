"""
Fast fairing drag proxy for preliminary design work.

This module follows the same broad workflow used in conceptual/preliminary
aerodynamic design:
1. estimate wetted area from geometry,
2. use a drag build-up model (Cf * FF * Swet),
3. add a pressure-recovery / separation risk term so we do not rank obviously
   "bad tails" as acceptable streamlined bodies.

The goal is not CFD-level absolute accuracy. The goal is to preserve ranking
quality far better than a plain fineness-ratio-only model while staying fast
enough for the inner loop of an optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi

import numpy as np


_V8_TRUST_REGION_ANCHORS = (
    {
        "name": "v5_best_reinterpreted_with_v7",
        "fineness_ratio": 3.6946282161783834,
        "x_peak_area_frac": 0.3226975564787321,
        "pressure_risk": 0.23096765281312692,
        "cd_ratio": 0.9360992354310164,
    },
    {
        "name": "v6_best_reinterpreted_with_v7",
        "fineness_ratio": 3.6787417269431812,
        "x_peak_area_frac": 0.2856537192984729,
        "pressure_risk": 0.1849781445507167,
        "cd_ratio": 1.071909999013221,
    },
    {
        "name": "v7_best_converged_su2",
        "fineness_ratio": 3.669185987689221,
        "x_peak_area_frac": 0.3226975564787321,
        "pressure_risk": 0.33281944146160747,
        "cd_ratio": 1.1221868586072885,
    },
    {
        "name": "mid_pack_example_baseline_su2",
        "fineness_ratio": 2.7303431053477443,
        "x_peak_area_frac": 0.2856537192984729,
        "pressure_risk": 0.2873774242159004,
        "cd_ratio": 0.9661997866636765,
    },
)

_V8_TRUST_REGION_FEATURE_SCALE = np.array([0.15, 0.04, 0.10], dtype=float)
_V8_TRUST_REGION_KERNEL_WIDTH = 0.50
_V8_TRUST_REGION_RATIO_MIN = 0.90
_V8_TRUST_REGION_RATIO_MAX = 1.18

_V9_TRUST_REGION_ANCHORS = (
    {
        "name": "v5_best_reinterpreted_with_v7",
        "fineness_ratio": 3.6946282161783834,
        "x_peak_area_frac": 0.3226975564787321,
        "pressure_risk": 0.23096765281312692,
        "terminal_area_log10": -3.8103413034999696,
        "cd_ratio": 0.9360992354310164,
    },
    {
        "name": "v6_best_reinterpreted_with_v7",
        "fineness_ratio": 3.6787417269431812,
        "x_peak_area_frac": 0.2856537192984729,
        "pressure_risk": 0.1849781445507167,
        "terminal_area_log10": -4.048876007628542,
        "cd_ratio": 1.071909999013221,
    },
    {
        "name": "v7_best_converged_su2",
        "fineness_ratio": 3.669185987689221,
        "x_peak_area_frac": 0.3226975564787321,
        "pressure_risk": 0.33281944146160747,
        "terminal_area_log10": -4.469119555445397,
        "cd_ratio": 1.1221868586072885,
    },
    {
        "name": "v8_best_baseline_su2",
        "fineness_ratio": 3.7500602457809493,
        "x_peak_area_frac": 0.3226975564787321,
        "pressure_risk": 0.2669728796404066,
        "terminal_area_log10": -4.5888500886164965,
        "cd_ratio": 1.3928037935740187,
    },
    {
        "name": "mid_pack_example_baseline_su2",
        "fineness_ratio": 2.7303431053477443,
        "x_peak_area_frac": 0.2856537192984729,
        "pressure_risk": 0.2873774242159004,
        "terminal_area_log10": -3.7923590591173558,
        "cd_ratio": 0.9661997866636765,
    },
)

_V9_TRUST_REGION_FEATURE_SCALE = np.array([0.15, 0.04, 0.10, 0.20], dtype=float)
_V9_TRUST_REGION_KERNEL_WIDTH = 0.65
_V9_TRUST_REGION_RATIO_MIN = 0.90
_V9_TRUST_REGION_RATIO_MAX = 1.45
_V9_LOW_DRAG_TAIL_RATIO_FLOOR = 1.3928037935740187
_V9_LOW_DRAG_TERMINAL_LOG10_MIN = -4.5888500886164965


def _clip01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


@dataclass(slots=True)
class ProxyMetrics:
    swet: float
    max_area: float
    equivalent_diameter: float
    fineness_ratio: float
    reynolds_number: float
    x_peak_area_frac: float
    recovery_length_ratio: float
    nose_angle_deg: float
    top_tail_angle_deg: float
    bottom_tail_angle_deg: float
    side_tail_angle_deg: float
    area_non_monotonicity: float
    forebody_burden: float
    forebody_curvature: float
    recovery_burden: float
    recovery_curvature: float
    forebody_burden_full: float
    forebody_curvature_full: float
    recovery_burden_smooth: float
    recovery_burden_excess: float
    recovery_curvature_full: float
    perimeter_efficiency: float
    forebody_perimeter_efficiency: float
    terminal_area_ratio: float
    x_dimless: np.ndarray
    cumulative_wetted_area_fraction: np.ndarray


class FairingDragProxy:
    """
    Fast preliminary drag proxy for the HPA fairing geometry.

    References reflected in the structure of this proxy:
    - conceptual drag build-up methods such as OpenVSP / FRICTION
    - streamlined-body form factor based on fineness ratio
    - low-drag streamliner practice that explicitly designs for laminar flow
      retention and gentle Stratford-style pressure recovery
    """

    def __init__(
        self,
        velocity=6.5,
        rho=1.225,
        mu=1.7894e-5,
        s_ref=1.0,
        model_version: str = "v7",
        turbulence_intensity: float | None = None,
        roughness_height: float | None = None,
        turbulence_intensity_ref: float = 0.005,
        roughness_height_ref: float = 1e-5,
    ):
        self.velocity = float(velocity)
        self.rho = float(rho)
        self.mu = float(mu)
        self.s_ref = float(s_ref)
        self.q = 0.5 * self.rho * (self.velocity ** 2)
        normalized_version = str(model_version).strip().lower()
        if normalized_version not in {"v5", "v6", "v7", "v8", "v9"}:
            raise ValueError(f"Unsupported proxy model_version: {model_version}")
        self.model_version = normalized_version
        self.turbulence_intensity = (
            None if turbulence_intensity is None else max(float(turbulence_intensity), 1e-6)
        )
        self.roughness_height = (
            None if roughness_height is None else max(float(roughness_height), 1e-9)
        )
        self.turbulence_intensity_ref = max(float(turbulence_intensity_ref), 1e-6)
        self.roughness_height_ref = max(float(roughness_height_ref), 1e-9)

    @staticmethod
    def _section_exponents(curves: dict) -> tuple[float, float, float, float]:
        return (
            max(float(curves.get("M_top", 2.5)), 1.2),
            max(float(curves.get("N_top", 2.5)), 1.2),
            max(float(curves.get("M_bot", 2.5)), 1.2),
            max(float(curves.get("N_bot", 2.5)), 1.2),
        )

    @staticmethod
    def _build_section_points(
        x_value: float,
        width_half: float,
        total_height: float,
        z_center: float,
        top_y_exp: float,
        top_z_exp: float,
        bot_y_exp: float,
        bot_z_exp: float,
        n_points: int,
    ) -> np.ndarray:
        if width_half <= 1e-9 or total_height <= 1e-9:
            point = np.array([[x_value, 0.0, z_center]], dtype=float)
            return np.repeat(point, n_points, axis=0)

        points = np.zeros((n_points, 3), dtype=float)
        half_height = total_height * 0.5

        for idx in range(n_points):
            theta = (2.0 * pi * idx) / n_points
            cos_val = np.cos(theta)
            sin_val = np.sin(theta)

            # Use the upper-half exponent on the nose-top side and the
            # lower-half exponent on the underside. This keeps the proxy
            # aligned with how the current geometry exposes shape control.
            if 0.0 <= theta <= pi:
                y_value = width_half * np.sign(cos_val) * (abs(cos_val) ** (2.0 / top_y_exp))
                z_local = half_height * (abs(sin_val) ** (2.0 / top_z_exp))
            else:
                y_value = width_half * np.sign(cos_val) * (abs(cos_val) ** (2.0 / bot_y_exp))
                z_local = -half_height * (abs(sin_val) ** (2.0 / bot_z_exp))

            points[idx] = [x_value, y_value, z_center + z_local]

        return points

    @staticmethod
    def _polygon_area_yz(points: np.ndarray) -> float:
        y_coords = points[:, 1]
        z_coords = points[:, 2]
        return 0.5 * abs(
            np.dot(y_coords, np.roll(z_coords, -1)) - np.dot(z_coords, np.roll(y_coords, -1))
        )

    @staticmethod
    def _polygon_perimeter_yz(points: np.ndarray) -> float:
        yz_points = points[:, 1:3]
        diffs = np.roll(yz_points, -1, axis=0) - yz_points
        return float(np.sum(np.linalg.norm(diffs, axis=1)))

    @staticmethod
    def _tri_area(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> float:
        return 0.5 * float(np.linalg.norm(np.cross(p1 - p0, p2 - p0)))

    @classmethod
    def _loft_strip_areas(cls, section_points: list[np.ndarray]) -> np.ndarray:
        n_sections = len(section_points)
        if n_sections < 2:
            return np.zeros(0, dtype=float)

        n_points = len(section_points[0])
        strip_areas = np.zeros(n_sections - 1, dtype=float)

        for i in range(n_sections - 1):
            sec_a = section_points[i]
            sec_b = section_points[i + 1]
            strip_area = 0.0
            for j in range(n_points):
                j_next = (j + 1) % n_points
                p0 = sec_a[j]
                p1 = sec_a[j_next]
                p2 = sec_b[j_next]
                p3 = sec_b[j]
                strip_area += cls._tri_area(p0, p1, p2)
                strip_area += cls._tri_area(p0, p2, p3)
            strip_areas[i] = strip_area
        return strip_areas

    @classmethod
    def _loft_wetted_area(cls, section_points: list[np.ndarray]) -> float:
        return float(np.sum(cls._loft_strip_areas(section_points)))

    @staticmethod
    def _positive_percentile(values: np.ndarray, percentile: float = 90.0) -> float:
        positive = values[values > 0.0]
        if positive.size == 0:
            return 0.0
        return float(np.percentile(np.degrees(np.arctan(positive)), percentile))

    @staticmethod
    def _normalized_interval_average(
        x_dimless: np.ndarray,
        values: np.ndarray,
    ) -> float:
        if len(x_dimless) < 2:
            return 0.0
        span = float(x_dimless[-1] - x_dimless[0])
        if span <= 1e-12:
            return float(np.mean(values))
        return float(np.trapezoid(values, x_dimless) / span)

    @classmethod
    def _area_weighted_average(
        cls,
        x_dimless: np.ndarray,
        values: np.ndarray,
        area_weights: np.ndarray,
    ) -> float:
        if len(x_dimless) < 2:
            if len(values) == 0:
                return 0.0
            return float(values[-1])

        weighted_area = np.maximum(area_weights, 0.0)
        denominator = float(np.trapezoid(weighted_area, x_dimless))
        if denominator <= 1e-12:
            return float(np.mean(values))
        numerator = float(np.trapezoid(values * weighted_area, x_dimless))
        return numerator / denominator

    @classmethod
    def _slope_exceedance_burden(
        cls,
        x_dimless: np.ndarray,
        slope_components: list[np.ndarray],
        angle_refs_deg: list[float],
        weights: list[float],
    ) -> float:
        if len(x_dimless) < 2:
            return 0.0

        burden = np.zeros_like(x_dimless, dtype=float)
        for slopes, angle_ref_deg, weight in zip(slope_components, angle_refs_deg, weights):
            tan_ref = max(np.tan(np.radians(angle_ref_deg)), 1e-9)
            exceedance = np.maximum(slopes / tan_ref - 1.0, 0.0) ** 2
            burden += float(weight) * exceedance
        return cls._normalized_interval_average(x_dimless, burden)

    @classmethod
    def _slope_reference_burden(
        cls,
        x_dimless: np.ndarray,
        slope_components: list[np.ndarray],
        angle_refs_deg: list[float],
        weights: list[float],
    ) -> float:
        if len(x_dimless) < 2:
            return 0.0

        burden = np.zeros_like(x_dimless, dtype=float)
        for slopes, angle_ref_deg, weight in zip(slope_components, angle_refs_deg, weights):
            tan_ref = max(np.tan(np.radians(angle_ref_deg)), 1e-9)
            burden += float(weight) * (slopes / tan_ref) ** 2
        return cls._normalized_interval_average(x_dimless, burden)

    @classmethod
    def _curvature_burden(
        cls,
        x_dimless: np.ndarray,
        width_norm: np.ndarray,
        z_upper_norm: np.ndarray,
        z_lower_norm: np.ndarray,
        mask: np.ndarray,
    ) -> float:
        x_masked = x_dimless[mask]
        if len(x_masked) < 4:
            return 0.0

        side_ddx = np.gradient(np.gradient(width_norm[mask], x_masked), x_masked)
        top_ddx = np.gradient(np.gradient(z_upper_norm[mask], x_masked), x_masked)
        bot_ddx = np.gradient(np.gradient(z_lower_norm[mask], x_masked), x_masked)
        curvature_load = np.abs(side_ddx) + np.abs(top_ddx) + np.abs(bot_ddx)
        return cls._normalized_interval_average(x_masked, curvature_load)

    @classmethod
    def _area_regrowth_burden(
        cls,
        x_dimless: np.ndarray,
        area_norm: np.ndarray,
        start_index: int,
    ) -> float:
        x_aft = x_dimless[start_index:]
        area_aft = area_norm[start_index:]
        if len(x_aft) < 3:
            return 0.0
        darea_dx = np.gradient(area_aft, x_aft)
        return float(
            np.trapezoid(np.maximum(darea_dx, 0.0), x_aft)
        )

    @staticmethod
    def _tail_terminal_area_ratio(
        x_dimless: np.ndarray,
        area_norm: np.ndarray,
        start: float = 0.98,
        end: float = 1.0,
    ) -> float:
        xi_start = max(float(start), float(x_dimless[0]))
        xi_end = min(float(end), float(x_dimless[-1]))
        if xi_end <= xi_start + 1e-9:
            return 0.0
        sample_x = np.linspace(xi_start, xi_end, 21)
        sample_area = np.interp(sample_x, x_dimless, area_norm)
        return float(50.0 * np.trapezoid(sample_area, sample_x))

    def extract_metrics(self, curves: dict, profile_points: int = 72) -> ProxyMetrics:
        x_coords = np.asarray(curves["x"], dtype=float)
        width_half = np.asarray(curves["width_half"], dtype=float)
        total_height = np.asarray(curves["super_height"], dtype=float)
        z_center = np.asarray(curves["z_loc"], dtype=float)
        z_upper = np.asarray(curves["z_upper"], dtype=float)
        z_lower = np.asarray(curves["z_lower"], dtype=float)
        body_length = float(curves["L"])

        top_y_exp, top_z_exp, bot_y_exp, bot_z_exp = self._section_exponents(curves)

        section_points = [
            self._build_section_points(
                x_coords[i],
                width_half[i],
                total_height[i],
                z_center[i],
                top_y_exp,
                top_z_exp,
                bot_y_exp,
                bot_z_exp,
                profile_points,
            )
            for i in range(len(x_coords))
        ]

        section_areas = np.array([self._polygon_area_yz(points) for points in section_points], dtype=float)
        section_perimeters = np.array(
            [self._polygon_perimeter_yz(points) for points in section_points],
            dtype=float,
        )
        strip_areas = self._loft_strip_areas(section_points)
        swet = float(np.sum(strip_areas))
        cumulative_wetted_area = np.concatenate(([0.0], np.cumsum(strip_areas)))

        max_area_index = int(np.argmax(section_areas))
        max_area = float(section_areas[max_area_index])
        eq_diameter = 2.0 * np.sqrt(max(max_area, 1e-12) / pi)
        fineness_ratio = body_length / max(eq_diameter, 1e-9)
        reynolds_number = self.rho * self.velocity * body_length / max(self.mu, 1e-12)
        x_dimless = x_coords / max(body_length, 1e-9)
        width_norm = width_half / max(eq_diameter, 1e-9)
        z_upper_norm = z_upper / max(eq_diameter, 1e-9)
        z_lower_norm = z_lower / max(eq_diameter, 1e-9)
        area_norm = section_areas / max(max_area, 1e-12)
        cumulative_wetted_area_fraction = (
            cumulative_wetted_area / max(swet, 1e-12)
            if swet > 1e-12
            else np.zeros_like(cumulative_wetted_area)
        )

        significance_mask = section_areas >= (0.08 * max(max_area, 1e-12))
        if int(np.count_nonzero(significance_mask)) < 6:
            significance_mask = section_areas >= (0.03 * max(max_area, 1e-12))

        nose_mask = (x_coords <= min(x_coords[max_area_index], 0.25 * body_length)) & significance_mask
        aft_mask = (x_coords >= x_coords[max_area_index]) & significance_mask
        forebody_full_mask = x_coords <= x_coords[max_area_index]
        aft_full_mask = x_coords >= x_coords[max_area_index]

        if int(np.count_nonzero(nose_mask)) < 3:
            nose_mask = (x_coords <= min(x_coords[max_area_index], 0.30 * body_length))
        if int(np.count_nonzero(aft_mask)) < 4:
            aft_mask = x_coords >= x_coords[max_area_index]
        if int(np.count_nonzero(forebody_full_mask)) < 3:
            forebody_full_mask = x_coords <= min(x_coords[max_area_index], 0.30 * body_length)
        if int(np.count_nonzero(aft_full_mask)) < 4:
            aft_full_mask = x_coords >= x_coords[max_area_index]

        dwidth_dx = np.gradient(width_half, x_coords)
        dz_upper_dx = np.gradient(z_upper, x_coords)
        dz_lower_dx = np.gradient(z_lower, x_coords)

        nose_angle_deg = max(
            self._positive_percentile(dwidth_dx[nose_mask]),
            self._positive_percentile(dz_upper_dx[nose_mask]),
            self._positive_percentile(-dz_lower_dx[nose_mask]),
        )

        top_tail_angle_deg = self._positive_percentile(-dz_upper_dx[aft_mask])
        bottom_tail_angle_deg = self._positive_percentile(dz_lower_dx[aft_mask])
        side_tail_angle_deg = self._positive_percentile(-dwidth_dx[aft_mask])

        area_non_monotonicity = self._area_regrowth_burden(
            x_dimless,
            area_norm,
            max_area_index,
        )

        forebody_burden = self._slope_exceedance_burden(
            x_dimless[nose_mask],
            [
                np.maximum(dwidth_dx[nose_mask], 0.0),
                np.maximum(dz_upper_dx[nose_mask], 0.0),
                np.maximum(-dz_lower_dx[nose_mask], 0.0),
            ],
            [30.0, 30.0, 30.0],
            [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0],
        )
        forebody_burden_full = self._slope_exceedance_burden(
            x_dimless[forebody_full_mask],
            [
                np.maximum(dwidth_dx[forebody_full_mask], 0.0),
                np.maximum(dz_upper_dx[forebody_full_mask], 0.0),
                np.maximum(-dz_lower_dx[forebody_full_mask], 0.0),
            ],
            [30.0, 30.0, 30.0],
            [1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0],
        )
        recovery_burden = self._slope_exceedance_burden(
            x_dimless[aft_mask],
            [
                np.maximum(-dz_upper_dx[aft_mask], 0.0),
                np.maximum(dz_lower_dx[aft_mask], 0.0),
                np.maximum(-dwidth_dx[aft_mask], 0.0),
            ],
            [18.0, 14.0, 13.0],
            [0.40, 0.35, 0.25],
        )
        recovery_burden_excess = self._slope_exceedance_burden(
            x_dimless[aft_full_mask],
            [
                np.maximum(-dz_upper_dx[aft_full_mask], 0.0),
                np.maximum(dz_lower_dx[aft_full_mask], 0.0),
                np.maximum(-dwidth_dx[aft_full_mask], 0.0),
            ],
            [18.0, 14.0, 13.0],
            [0.40, 0.35, 0.25],
        )
        recovery_burden_smooth = self._slope_reference_burden(
            x_dimless[aft_full_mask],
            [
                np.maximum(-dz_upper_dx[aft_full_mask], 0.0),
                np.maximum(dz_lower_dx[aft_full_mask], 0.0),
                np.maximum(-dwidth_dx[aft_full_mask], 0.0),
            ],
            [18.0, 14.0, 13.0],
            [0.40, 0.35, 0.25],
        )
        forebody_curvature = self._curvature_burden(
            x_dimless,
            width_norm,
            z_upper_norm,
            z_lower_norm,
            nose_mask,
        )
        recovery_curvature = self._curvature_burden(
            x_dimless,
            width_norm,
            z_upper_norm,
            z_lower_norm,
            aft_mask,
        )
        forebody_curvature_full = self._curvature_burden(
            x_dimless,
            width_norm,
            z_upper_norm,
            z_lower_norm,
            forebody_full_mask,
        )
        recovery_curvature_full = self._curvature_burden(
            x_dimless,
            width_norm,
            z_upper_norm,
            z_lower_norm,
            aft_full_mask,
        )

        perimeter_efficiency_profile = section_perimeters / np.maximum(
            2.0 * np.sqrt(pi * np.maximum(section_areas, 1e-12)),
            1e-12,
        )
        perimeter_efficiency = self._area_weighted_average(
            x_dimless,
            perimeter_efficiency_profile,
            area_norm,
        )
        forebody_perimeter_efficiency = self._area_weighted_average(
            x_dimless[forebody_full_mask],
            perimeter_efficiency_profile[forebody_full_mask],
            area_norm[forebody_full_mask],
        )
        terminal_area_ratio = self._tail_terminal_area_ratio(x_dimless, area_norm)

        return ProxyMetrics(
            swet=float(swet),
            max_area=max_area,
            equivalent_diameter=eq_diameter,
            fineness_ratio=float(fineness_ratio),
            reynolds_number=float(reynolds_number),
            x_peak_area_frac=float(x_coords[max_area_index] / max(body_length, 1e-9)),
            recovery_length_ratio=float((body_length - x_coords[max_area_index]) / max(body_length, 1e-9)),
            nose_angle_deg=float(nose_angle_deg),
            top_tail_angle_deg=float(top_tail_angle_deg),
            bottom_tail_angle_deg=float(bottom_tail_angle_deg),
            side_tail_angle_deg=float(side_tail_angle_deg),
            area_non_monotonicity=float(area_non_monotonicity),
            forebody_burden=float(forebody_burden),
            forebody_curvature=float(forebody_curvature),
            recovery_burden=float(recovery_burden),
            recovery_curvature=float(recovery_curvature),
            forebody_burden_full=float(forebody_burden_full),
            forebody_curvature_full=float(forebody_curvature_full),
            recovery_burden_smooth=float(recovery_burden_smooth),
            recovery_burden_excess=float(recovery_burden_excess),
            recovery_curvature_full=float(recovery_curvature_full),
            perimeter_efficiency=float(perimeter_efficiency),
            forebody_perimeter_efficiency=float(forebody_perimeter_efficiency),
            terminal_area_ratio=float(terminal_area_ratio),
            x_dimless=np.asarray(x_dimless, dtype=float),
            cumulative_wetted_area_fraction=np.asarray(cumulative_wetted_area_fraction, dtype=float),
        )

    @staticmethod
    def _cf_laminar(reynolds_number: float) -> float:
        return 1.32824 / np.sqrt(max(reynolds_number, 1.0))

    @staticmethod
    def _cf_turbulent(reynolds_number: float) -> float:
        return 0.074 / (max(reynolds_number, 1.0) ** 0.2)

    @staticmethod
    def _sigmoid(value: float) -> float:
        return float(1.0 / (1.0 + np.exp(-value)))

    @staticmethod
    def _log_ratio(value: float | None, reference: float) -> float:
        if value is None:
            return 0.0
        return float(np.log(max(value, 1e-12) / max(reference, 1e-12)))

    def _estimate_transition_fraction_v5(self, metrics: ProxyMetrics) -> float:
        # Interpret "laminar fraction" as a transition-location surrogate:
        # the approximate fraction of body length that can remain laminar before
        # transition, driven mainly by forebody loading and smoothness rather
        # than by aft-body separation features.
        x_t_min = 0.05
        x_t_max = 0.70
        x_peak_ref = 0.35
        low_fineness = max(0.0, 2.8 - metrics.fineness_ratio)
        peak_alignment = np.exp(-((metrics.x_peak_area_frac - x_peak_ref) / 0.12) ** 2)
        aft_peak_penalty = max(0.0, metrics.x_peak_area_frac - 0.33)

        transition_argument = (
            0.15
            + 2.20 * peak_alignment
            - 0.55 * metrics.forebody_burden
            - 0.02 * metrics.forebody_curvature
            - 0.25 * low_fineness
            - 4.50 * aft_peak_penalty
        )
        laminar_fraction = x_t_min + (x_t_max - x_t_min) * self._sigmoid(transition_argument)
        return float(np.clip(laminar_fraction, x_t_min, x_t_max))

    def _estimate_transition_fraction_v6(self, metrics: ProxyMetrics) -> float:
        x_t_min = 0.05
        x_t_max = 0.70
        x_peak_ref = 0.35
        beta_0 = 1.40
        beta_1 = 1.50
        beta_2 = 0.55
        beta_3 = 0.020
        beta_4 = 0.18
        beta_5 = 0.10

        chi_ti = self._log_ratio(self.turbulence_intensity, self.turbulence_intensity_ref)
        chi_k = self._log_ratio(self.roughness_height, self.roughness_height_ref)

        transition_argument = (
            beta_0
            + beta_1 * (metrics.x_peak_area_frac - x_peak_ref)
            - beta_2 * metrics.forebody_burden
            - beta_3 * metrics.forebody_curvature
            - beta_4 * chi_ti
            - beta_5 * chi_k
        )
        transition_fraction = x_t_min + (x_t_max - x_t_min) * self._sigmoid(transition_argument)
        return float(np.clip(transition_fraction, x_t_min, x_t_max))

    def _estimate_transition_fraction_v7(self, metrics: ProxyMetrics) -> float:
        x_t_min = 0.05
        x_t_max = 0.65
        x_peak_ref = 0.35
        beta_0 = 1.40
        beta_1 = 1.50
        beta_2 = 0.55
        beta_3 = 0.020
        beta_4 = 0.18
        beta_5 = 0.10
        beta_6 = 1.00

        chi_ti = self._log_ratio(self.turbulence_intensity, self.turbulence_intensity_ref)
        chi_k = self._log_ratio(self.roughness_height, self.roughness_height_ref)

        transition_argument = (
            beta_0
            + beta_1 * (metrics.x_peak_area_frac - x_peak_ref)
            - beta_2 * metrics.forebody_burden_full
            - beta_3 * metrics.forebody_curvature_full
            - beta_4 * chi_ti
            - beta_5 * chi_k
            - beta_6 * max(0.0, metrics.forebody_perimeter_efficiency - 1.0)
        )
        transition_fraction = x_t_min + (x_t_max - x_t_min) * self._sigmoid(transition_argument)
        return float(np.clip(transition_fraction, x_t_min, x_t_max))

    def estimate_laminar_fraction(self, metrics: ProxyMetrics) -> float:
        if self.model_version == "v5":
            return self._estimate_transition_fraction_v5(metrics)
        if self.model_version == "v6":
            return self._estimate_transition_fraction_v6(metrics)
        if self.model_version in {"v7", "v8", "v9"}:
            return self._estimate_transition_fraction_v7(metrics)
        return self._estimate_transition_fraction_v7(metrics)

    @staticmethod
    def estimate_laminar_area_fraction(metrics: ProxyMetrics, transition_fraction: float) -> float:
        x_t_star = float(np.clip(transition_fraction, 0.0, 1.0))
        return float(
            np.clip(
                np.interp(
                    x_t_star,
                    metrics.x_dimless,
                    metrics.cumulative_wetted_area_fraction,
                ),
                0.0,
                1.0,
            )
        )

    def estimate_skin_friction_cf(
        self,
        metrics: ProxyMetrics,
        laminar_fraction: float,
        laminar_area_fraction: float | None = None,
    ) -> float:
        re_total = metrics.reynolds_number
        if self.model_version in {"v7", "v8", "v9"}:
            x_t_star = float(np.clip(laminar_fraction, 1e-4, 0.999999))
            phi_s = float(
                np.clip(
                    laminar_area_fraction if laminar_area_fraction is not None else laminar_fraction,
                    0.0,
                    1.0,
                )
            )
            re_t = max(re_total * x_t_star, 1.0)
            cf_lam_avg = self._cf_laminar(re_t)
            cf_turb_avg = 0.074 * (max(re_total, 1.0) ** -0.2) * (
                (1.0 - x_t_star ** 0.8) / max(1.0 - x_t_star, 1e-6)
            )
            cf_mix = phi_s * cf_lam_avg + (1.0 - phi_s) * cf_turb_avg
            return float(max(cf_mix, 1e-6))

        re_lam = max(re_total * laminar_fraction, 1.0)

        cf_turb_total = self._cf_turbulent(re_total)
        cf_turb_partial = self._cf_turbulent(re_lam)
        cf_lam_partial = self._cf_laminar(re_lam)

        # Same conceptual mixed-flow idea used in OpenVSP's partial laminar model.
        cf_mix = cf_turb_total - laminar_fraction * cf_turb_partial + laminar_fraction * cf_lam_partial
        return float(max(cf_mix, 1e-6))

    def estimate_form_factor(self, metrics: ProxyMetrics) -> float:
        # Hoerner streamlined body form factor, matching a common preliminary
        # design choice and OpenVSP's default body model.
        fr = max(metrics.fineness_ratio, 1.0)
        if self.model_version not in {"v7", "v8", "v9"}:
            return float(1.0 + 1.5 / (fr ** 1.5) + 7.0 / (fr ** 3.0))

        a_1 = 1.5
        a_2 = 7.0
        a_3 = 0.85
        a_4 = 0.22
        return float(
            1.0
            + a_1 / (fr ** 1.5)
            + a_2 / (fr ** 3.0)
            + a_3 * max(0.0, metrics.perimeter_efficiency - 1.0)
            + a_4 * np.log1p(max(metrics.recovery_burden_smooth, 0.0))
        )

    def _estimate_pressure_cd_v5(self, metrics: ProxyMetrics, laminar_fraction: float) -> tuple[float, float, float]:
        peak_shift = max(0.0, metrics.x_peak_area_frac - 0.50) + max(0.0, 0.18 - metrics.x_peak_area_frac)
        low_fineness = max(0.0, 2.8 - metrics.fineness_ratio)
        curvature_excess = max(0.0, metrics.recovery_curvature - 18.0)
        recovery_span = max(metrics.recovery_length_ratio, 1e-6)
        transition_into_tail = max(0.0, (laminar_fraction - metrics.x_peak_area_frac) / recovery_span)
        tail_transition_multiplier = 1.0 + 0.85 * transition_into_tail

        pressure_load = (
            0.0200 * tail_transition_multiplier * metrics.recovery_burden
            + 0.0250 * metrics.area_non_monotonicity
            + 0.0012 * curvature_excess
            + 0.0050 * (peak_shift ** 2)
            + 0.0030 * (low_fineness ** 2)
        )

        pressure_cd = float(pressure_load * (metrics.max_area / max(self.s_ref, 1e-9)))
        risk_load = (
            1.6 * tail_transition_multiplier * metrics.recovery_burden
            + 6.0 * metrics.area_non_monotonicity
            + 0.12 * curvature_excess
            + 1.2 * peak_shift
            + 0.8 * low_fineness
        )
        pressure_risk = _clip01(1.0 - np.exp(-risk_load))
        return pressure_cd, float(pressure_risk), float(tail_transition_multiplier)

    def _estimate_pressure_cd_v6(self, metrics: ProxyMetrics, transition_fraction: float) -> tuple[float, float, float]:
        eta_a = max(metrics.area_non_monotonicity, 0.0)
        eta_c = max(metrics.recovery_curvature, 0.0)
        psi_rec = max(metrics.recovery_burden, 0.0)
        x_peak = metrics.x_peak_area_frac
        recovery_span = max(1.0 - x_peak, 1e-6)

        k_r = 0.025
        k_a = 0.028
        k_c = 0.0012
        k_t = 0.85
        eta_c0 = 18.0

        transition_tail_overlap = max(0.0, (transition_fraction - x_peak) / recovery_span)
        transition_multiplier = 1.0 + k_t * transition_tail_overlap
        curvature_excess = max(0.0, eta_c - eta_c0)

        pressure_load = (
            k_r * transition_multiplier * psi_rec
            + k_a * eta_a
            + k_c * curvature_excess
        )
        pressure_cd = float(pressure_load * (metrics.max_area / max(self.s_ref, 1e-9)))
        pressure_risk = _clip01(
            1.0
            - np.exp(
                -(
                    1.5 * transition_multiplier * psi_rec
                    + 5.0 * eta_a
                    + 0.12 * curvature_excess
                )
            )
        )
        return pressure_cd, float(pressure_risk), float(transition_multiplier)

    def _estimate_pressure_cd_v7(self, metrics: ProxyMetrics, transition_fraction: float) -> tuple[float, float, float]:
        x_peak = float(np.clip(metrics.x_peak_area_frac, 1e-6, 1.0 - 1e-6))
        omega_plus = max(0.0, (transition_fraction - x_peak) / max(1.0 - x_peak, 1e-6))
        omega_minus = max(0.0, (x_peak - transition_fraction) / max(x_peak, 1e-6))

        k_plus = 0.85
        k_minus = 0.55
        tail_state_factor = float(np.exp(k_plus * omega_plus - k_minus * omega_minus))

        eta_a = max(metrics.area_non_monotonicity, 0.0)
        eta_c0 = 18.0
        curvature_excess = max(0.0, metrics.recovery_curvature_full - eta_c0)
        psi_rec_excess = max(metrics.recovery_burden_excess, 0.0)
        tau_b = max(metrics.terminal_area_ratio, 0.0)

        b_1 = 0.014
        b_2 = 0.020
        b_3 = 0.0010
        b_4 = 0.075

        pressure_load = (
            b_1 * tail_state_factor * psi_rec_excess
            + b_2 * eta_a
            + b_3 * curvature_excess
            + b_4 * tau_b
        )
        pressure_cd = float(pressure_load * (metrics.max_area / max(self.s_ref, 1e-9)))
        pressure_risk = _clip01(
            1.0
            - np.exp(
                -(
                    1.8 * tail_state_factor * psi_rec_excess
                    + 4.0 * eta_a
                    + 0.10 * curvature_excess
                    + 3.0 * tau_b
                )
            )
        )
        return pressure_cd, float(pressure_risk), float(tail_state_factor)

    def _estimate_v8_calibration(
        self,
        metrics: ProxyMetrics,
        pressure_risk: float,
    ) -> dict[str, float | list[str]]:
        anchor_feature_matrix = np.array(
            [
                [
                    anchor["fineness_ratio"],
                    anchor["x_peak_area_frac"],
                    anchor["pressure_risk"],
                ]
                for anchor in _V8_TRUST_REGION_ANCHORS
            ],
            dtype=float,
        )
        anchor_residuals = np.array(
            [float(anchor["cd_ratio"]) - 1.0 for anchor in _V8_TRUST_REGION_ANCHORS],
            dtype=float,
        )
        feature_vector = np.array(
            [
                float(metrics.fineness_ratio),
                float(metrics.x_peak_area_frac),
                float(pressure_risk),
            ],
            dtype=float,
        )

        normalized_delta = (anchor_feature_matrix - feature_vector) / _V8_TRUST_REGION_FEATURE_SCALE
        distances = np.linalg.norm(normalized_delta, axis=1)
        weights = np.exp(-((distances / _V8_TRUST_REGION_KERNEL_WIDTH) ** 2))
        total_weight = float(np.sum(weights))
        if total_weight <= 1e-12:
            return {
                "factor": 1.0,
                "blend": 0.0,
                "min_distance": float(np.min(distances)),
                "weighted_residual": 0.0,
                "anchor_names": [str(anchor["name"]) for anchor in _V8_TRUST_REGION_ANCHORS],
            }

        weighted_residual = float(np.dot(weights, anchor_residuals) / total_weight)
        blend = float(min(1.0, total_weight))
        factor = float(
            np.clip(
                1.0 + blend * weighted_residual,
                _V8_TRUST_REGION_RATIO_MIN,
                _V8_TRUST_REGION_RATIO_MAX,
            )
        )
        return {
            "factor": factor,
            "blend": blend,
            "min_distance": float(np.min(distances)),
            "weighted_residual": weighted_residual,
            "anchor_names": [str(anchor["name"]) for anchor in _V8_TRUST_REGION_ANCHORS],
        }

    def _estimate_v9_calibration(
        self,
        metrics: ProxyMetrics,
        pressure_risk: float,
    ) -> dict[str, float | bool | list[str]]:
        anchor_feature_matrix = np.array(
            [
                [
                    anchor["fineness_ratio"],
                    anchor["x_peak_area_frac"],
                    anchor["pressure_risk"],
                    anchor["terminal_area_log10"],
                ]
                for anchor in _V9_TRUST_REGION_ANCHORS
            ],
            dtype=float,
        )
        anchor_residuals = np.array(
            [float(anchor["cd_ratio"]) - 1.0 for anchor in _V9_TRUST_REGION_ANCHORS],
            dtype=float,
        )
        terminal_area_log10 = float(np.log10(max(metrics.terminal_area_ratio, 1e-8)))
        feature_vector = np.array(
            [
                float(metrics.fineness_ratio),
                float(metrics.x_peak_area_frac),
                float(pressure_risk),
                terminal_area_log10,
            ],
            dtype=float,
        )

        normalized_delta = (anchor_feature_matrix - feature_vector) / _V9_TRUST_REGION_FEATURE_SCALE
        distances = np.linalg.norm(normalized_delta, axis=1)
        weights = np.exp(-((distances / _V9_TRUST_REGION_KERNEL_WIDTH) ** 2))
        total_weight = float(np.sum(weights))
        if total_weight <= 1e-12:
            return {
                "factor": 1.0,
                "blend": 0.0,
                "min_distance": float(np.min(distances)),
                "weighted_residual": 0.0,
                "terminal_area_log10": terminal_area_log10,
                "tail_floor_applied": False,
                "anchor_names": [str(anchor["name"]) for anchor in _V9_TRUST_REGION_ANCHORS],
            }

        weighted_residual = float(np.dot(weights, anchor_residuals) / total_weight)
        blend = float(min(1.0, total_weight))
        factor = float(
            np.clip(
                1.0 + blend * weighted_residual,
                _V9_TRUST_REGION_RATIO_MIN,
                _V9_TRUST_REGION_RATIO_MAX,
            )
        )

        tail_floor_applied = False
        if (
            metrics.fineness_ratio >= 3.55
            and 0.27 <= metrics.x_peak_area_frac <= 0.34
            and pressure_risk <= 0.36
            and terminal_area_log10 <= _V9_LOW_DRAG_TERMINAL_LOG10_MIN
        ):
            factor = max(factor, _V9_LOW_DRAG_TAIL_RATIO_FLOOR)
            tail_floor_applied = True

        return {
            "factor": factor,
            "blend": blend,
            "min_distance": float(np.min(distances)),
            "weighted_residual": weighted_residual,
            "terminal_area_log10": terminal_area_log10,
            "tail_floor_applied": tail_floor_applied,
            "anchor_names": [str(anchor["name"]) for anchor in _V9_TRUST_REGION_ANCHORS],
        }

    def estimate_pressure_cd(self, metrics: ProxyMetrics, laminar_fraction: float) -> tuple[float, float, float]:
        if self.model_version == "v5":
            return self._estimate_pressure_cd_v5(metrics, laminar_fraction)
        if self.model_version == "v6":
            return self._estimate_pressure_cd_v6(metrics, laminar_fraction)
        if self.model_version in {"v7", "v8", "v9"}:
            return self._estimate_pressure_cd_v7(metrics, laminar_fraction)
        return self._estimate_pressure_cd_v7(metrics, laminar_fraction)

    def evaluate_curves(self, curves: dict) -> dict:
        metrics = self.extract_metrics(curves)
        transition_fraction = self.estimate_laminar_fraction(metrics)
        laminar_area_fraction = (
            self.estimate_laminar_area_fraction(metrics, transition_fraction)
            if self.model_version in {"v7", "v8", "v9"}
            else transition_fraction
        )
        cf_mix = self.estimate_skin_friction_cf(metrics, transition_fraction, laminar_area_fraction)
        form_factor = self.estimate_form_factor(metrics)
        cd_viscous = metrics.swet * cf_mix * form_factor / self.s_ref
        cd_pressure, pressure_risk, transition_multiplier = self.estimate_pressure_cd(metrics, transition_fraction)
        calibration_factor = 1.0
        calibration_blend = 0.0
        calibration_min_distance = 0.0
        calibration_weighted_residual = 0.0
        calibration_terminal_area_log10 = 0.0
        calibration_tail_floor_applied = False
        calibration_anchor_names: list[str] = []
        if self.model_version == "v8":
            calibration = self._estimate_v8_calibration(metrics, pressure_risk)
            calibration_factor = float(calibration["factor"])
            calibration_blend = float(calibration["blend"])
            calibration_min_distance = float(calibration["min_distance"])
            calibration_weighted_residual = float(calibration["weighted_residual"])
            calibration_anchor_names = list(calibration["anchor_names"])
            cd_viscous *= calibration_factor
            cd_pressure *= calibration_factor
        elif self.model_version == "v9":
            calibration = self._estimate_v9_calibration(metrics, pressure_risk)
            calibration_factor = float(calibration["factor"])
            calibration_blend = float(calibration["blend"])
            calibration_min_distance = float(calibration["min_distance"])
            calibration_weighted_residual = float(calibration["weighted_residual"])
            calibration_terminal_area_log10 = float(calibration["terminal_area_log10"])
            calibration_tail_floor_applied = bool(calibration["tail_floor_applied"])
            calibration_anchor_names = list(calibration["anchor_names"])
            cd_viscous *= calibration_factor
            cd_pressure *= calibration_factor
        cd_total = cd_viscous + cd_pressure
        drag_force = self.q * cd_total * self.s_ref
        model_name = f"fast_drag_proxy_{self.model_version}"

        return {
            "Cd": float(cd_total),
            "Cd_viscous": float(cd_viscous),
            "Cd_pressure": float(cd_pressure),
            "Drag": float(drag_force),
            "Swet": float(metrics.swet),
            "Cf": float(cf_mix),
            "FF": float(form_factor),
            "LaminarFraction": float(transition_fraction),
            "TransitionFraction": float(transition_fraction),
            "TransitionLocationFraction": float(transition_fraction),
            "LaminarAreaFraction": float(laminar_area_fraction),
            "TransitionTailMultiplier": float(transition_multiplier),
            "Calibration": {
                "mode": (
                    "local_trust_region_v8"
                    if self.model_version == "v8"
                    else "local_trust_region_v9"
                    if self.model_version == "v9"
                    else "none"
                ),
                "factor": float(calibration_factor),
                "blend": float(calibration_blend),
                "min_distance": float(calibration_min_distance),
                "weighted_residual": float(calibration_weighted_residual),
                "terminal_area_log10": float(calibration_terminal_area_log10),
                "tail_floor_applied": bool(calibration_tail_floor_applied),
                "anchor_names": calibration_anchor_names,
            },
            "FinenessRatio": float(metrics.fineness_ratio),
            "XPeakAreaFrac": float(metrics.x_peak_area_frac),
            "TailAngles": {
                "top_deg": float(metrics.top_tail_angle_deg),
                "bottom_deg": float(metrics.bottom_tail_angle_deg),
                "side_deg": float(metrics.side_tail_angle_deg),
            },
            "Quality": {
                "area_monotonicity": float(1.0 - _clip01(metrics.area_non_monotonicity)),
                "forebody_burden": float(metrics.forebody_burden),
                "forebody_curvature": float(metrics.forebody_curvature),
                "recovery_burden": float(metrics.recovery_burden),
                "recovery_curvature": float(metrics.recovery_curvature),
                "smooth_recovery_burden": float(metrics.recovery_burden_smooth),
                "perimeter_efficiency": float(metrics.perimeter_efficiency),
                "terminal_area_ratio": float(metrics.terminal_area_ratio),
                "pressure_risk": float(pressure_risk),
            },
            "Model": model_name,
        }
