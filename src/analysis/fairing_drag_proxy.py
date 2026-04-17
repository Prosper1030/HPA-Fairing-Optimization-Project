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


class FairingDragProxy:
    """
    Fast preliminary drag proxy for the HPA fairing geometry.

    References reflected in the structure of this proxy:
    - conceptual drag build-up methods such as OpenVSP / FRICTION
    - streamlined-body form factor based on fineness ratio
    - low-drag streamliner practice that explicitly designs for laminar flow
      retention and gentle Stratford-style pressure recovery
    """

    def __init__(self, velocity=6.5, rho=1.225, mu=1.7894e-5, s_ref=1.0):
        self.velocity = float(velocity)
        self.rho = float(rho)
        self.mu = float(mu)
        self.s_ref = float(s_ref)
        self.q = 0.5 * self.rho * (self.velocity ** 2)

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
    def _tri_area(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> float:
        return 0.5 * float(np.linalg.norm(np.cross(p1 - p0, p2 - p0)))

    @classmethod
    def _loft_wetted_area(cls, section_points: list[np.ndarray]) -> float:
        total_area = 0.0
        n_points = len(section_points[0])

        for i in range(len(section_points) - 1):
            sec_a = section_points[i]
            sec_b = section_points[i + 1]
            for j in range(n_points):
                j_next = (j + 1) % n_points
                p0 = sec_a[j]
                p1 = sec_a[j_next]
                p2 = sec_b[j_next]
                p3 = sec_b[j]
                total_area += cls._tri_area(p0, p1, p2)
                total_area += cls._tri_area(p0, p2, p3)

        return total_area

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
        swet = self._loft_wetted_area(section_points)

        max_area_index = int(np.argmax(section_areas))
        max_area = float(section_areas[max_area_index])
        eq_diameter = 2.0 * np.sqrt(max(max_area, 1e-12) / pi)
        fineness_ratio = body_length / max(eq_diameter, 1e-9)
        reynolds_number = self.rho * self.velocity * body_length / max(self.mu, 1e-12)
        x_dimless = x_coords / max(body_length, 1e-9)
        width_norm = width_half / max(eq_diameter, 1e-9)
        z_upper_norm = z_upper / max(eq_diameter, 1e-9)
        z_lower_norm = z_lower / max(eq_diameter, 1e-9)

        significance_mask = section_areas >= (0.08 * max(max_area, 1e-12))
        if int(np.count_nonzero(significance_mask)) < 6:
            significance_mask = section_areas >= (0.03 * max(max_area, 1e-12))

        nose_mask = (x_coords <= min(x_coords[max_area_index], 0.25 * body_length)) & significance_mask
        aft_mask = (x_coords >= x_coords[max_area_index]) & significance_mask

        if int(np.count_nonzero(nose_mask)) < 3:
            nose_mask = (x_coords <= min(x_coords[max_area_index], 0.30 * body_length))
        if int(np.count_nonzero(aft_mask)) < 4:
            aft_mask = x_coords >= x_coords[max_area_index]

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

        area_norm = section_areas / max(max_area, 1e-12)
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

    def estimate_laminar_fraction(self, metrics: ProxyMetrics) -> float:
        # Interpret "laminar fraction" as a transition-location surrogate:
        # the approximate fraction of body length that can remain laminar before
        # transition, driven mainly by forebody loading and smoothness rather
        # than by aft-body separation features.
        x_t_min = 0.05
        x_t_max = 0.70
        x_peak_ref = 0.35
        low_fineness = max(0.0, 2.8 - metrics.fineness_ratio)
        peak_alignment = np.exp(-((metrics.x_peak_area_frac - x_peak_ref) / 0.12) ** 2)

        transition_argument = (
            0.15
            + 2.20 * peak_alignment
            - 0.55 * metrics.forebody_burden
            - 0.02 * metrics.forebody_curvature
            - 0.25 * low_fineness
        )
        laminar_fraction = x_t_min + (x_t_max - x_t_min) * self._sigmoid(transition_argument)
        return float(np.clip(laminar_fraction, x_t_min, x_t_max))

    def estimate_skin_friction_cf(self, metrics: ProxyMetrics, laminar_fraction: float) -> float:
        re_total = metrics.reynolds_number
        re_lam = max(re_total * laminar_fraction, 1.0)

        cf_turb_total = self._cf_turbulent(re_total)
        cf_turb_partial = self._cf_turbulent(re_lam)
        cf_lam_partial = self._cf_laminar(re_lam)

        # Same conceptual mixed-flow idea used in OpenVSP's partial laminar model.
        cf_mix = cf_turb_total - laminar_fraction * cf_turb_partial + laminar_fraction * cf_lam_partial
        return float(max(cf_mix, 1e-6))

    @staticmethod
    def estimate_form_factor(metrics: ProxyMetrics) -> float:
        # Hoerner streamlined body form factor, matching a common preliminary
        # design choice and OpenVSP's default body model.
        fr = max(metrics.fineness_ratio, 1.0)
        return float(1.0 + 1.5 / (fr ** 1.5) + 7.0 / (fr ** 3.0))

    def estimate_pressure_cd(self, metrics: ProxyMetrics, laminar_fraction: float) -> tuple[float, float]:
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
        return pressure_cd, float(pressure_risk)

    def evaluate_curves(self, curves: dict) -> dict:
        metrics = self.extract_metrics(curves)
        laminar_fraction = self.estimate_laminar_fraction(metrics)
        cf_mix = self.estimate_skin_friction_cf(metrics, laminar_fraction)
        form_factor = self.estimate_form_factor(metrics)
        cd_viscous = metrics.swet * cf_mix * form_factor / self.s_ref
        cd_pressure, pressure_risk = self.estimate_pressure_cd(metrics, laminar_fraction)
        cd_total = cd_viscous + cd_pressure
        drag_force = self.q * cd_total * self.s_ref

        return {
            "Cd": float(cd_total),
            "Cd_viscous": float(cd_viscous),
            "Cd_pressure": float(cd_pressure),
            "Drag": float(drag_force),
            "Swet": float(metrics.swet),
            "Cf": float(cf_mix),
            "FF": float(form_factor),
            "LaminarFraction": float(laminar_fraction),
            "TransitionFraction": float(laminar_fraction),
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
                "pressure_risk": float(pressure_risk),
            },
            "Model": "fast_drag_proxy_v5",
        }
