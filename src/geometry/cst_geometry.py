"""
Compatibility wrapper for older geometry entry points.

The project's main optimization logic now lives elsewhere, but several legacy
scripts still import `src.geometry.CSTGeometryGenerator`. This adapter keeps
those entry points working and also exposes a `design_to_gene` helper for code
that wants to bridge into the newer asymmetric optimizer.
"""

import math
import os
from typing import Dict, Iterable, List


class CSTGeometryGenerator:
    """Backwards-compatible wrapper around the current geometry pipeline."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    @staticmethod
    def cst_class_function(psi: float, n1: float, n2: float) -> float:
        """Classic CST class function."""
        return (psi ** n1) * ((1.0 - psi) ** n2)

    @staticmethod
    def cst_shape_function(psi: float, weights: Iterable[float]) -> float:
        """Classic Bernstein polynomial shape function."""
        weight_list = list(weights)
        order = len(weight_list) - 1
        shape_value = 0.0

        for index, weight in enumerate(weight_list):
            bernstein = math.comb(order, index) * (psi ** index) * ((1.0 - psi) ** (order - index))
            shape_value += weight * bernstein

        return shape_value

    @classmethod
    def calculate_cst_radius(
        cls,
        psi: float,
        n1: float,
        n2: float,
        weights: Iterable[float],
        length: float,
    ) -> float:
        """Approximate the old symmetric radius definition."""
        if psi <= 0.0 or psi >= 1.0:
            return 0.0

        return cls.cst_class_function(psi, n1, n2) * cls.cst_shape_function(psi, weights) * length

    @staticmethod
    def _validate_weights(name: str, weights: Iterable[float]) -> List[float]:
        weight_list = list(weights)
        if len(weight_list) != 4:
            raise ValueError(f"{name} must contain exactly 4 CST weights, got {len(weight_list)}")
        return weight_list

    @classmethod
    def design_to_gene(cls, design_params: Dict) -> Dict:
        """
        Convert the older symmetric `design_params` format into the newer
        asymmetric optimization gene dictionary.
        """
        length = float(design_params["length"])
        n_nose = float(design_params["n_nose"])
        n_tail = float(design_params["n_tail"])

        width_weights = cls._validate_weights("width_weights", design_params["width_weights"])
        height_weights = cls._validate_weights("height_weights", design_params["height_weights"])

        sample_points = [index / 200.0 for index in range(201)]
        width_radii = [
            cls.calculate_cst_radius(psi, n_nose, n_tail, width_weights, length)
            for psi in sample_points
        ]
        height_radii = [
            cls.calculate_cst_radius(psi, n_nose, n_tail, height_weights, length)
            for psi in sample_points
        ]

        max_width_index = max(range(len(width_radii)), key=width_radii.__getitem__)
        x_max_pos = sample_points[max_width_index]

        return {
            "L": length,
            "W_max": max(width_radii) * 2.0,
            "H_top_max": max(height_radii),
            "H_bot_max": max(height_radii),
            "N1": n_nose,
            "N2_top": n_tail,
            "N2_bot": n_tail,
            "X_max_pos": x_max_pos if 0.0 < x_max_pos < 1.0 else 0.25,
            # The legacy generator did not expose this directly. 0.7 m matches
            # the current default and keeps downstream checks in a valid range.
            "X_offset": float(design_params.get("x_offset", 0.7)),
            "M_top": float(design_params.get("super_m", 2.5)),
            "N_top": float(design_params.get("super_n", 2.5)),
            "M_bot": float(design_params.get("super_m", 2.5)),
            "N_bot": float(design_params.get("super_n", 2.5)),
            "tail_rise": float(design_params.get("tail_rise", 0.0)),
            "blend_start": float(design_params.get("blend_start", 0.75)),
            "blend_power": float(design_params.get("blend_power", 2.0)),
            "w0": width_weights[0],
            "w1": width_weights[1],
            "w2": width_weights[2],
            "w3": width_weights[3],
        }

    def generate_fuselage(self, design_params: Dict) -> str:
        """Generate a `.vsp3` file using the legacy symmetric CST interface."""
        import openvsp as vsp

        name = design_params["name"]
        length = float(design_params["length"])
        n_nose = float(design_params["n_nose"])
        n_tail = float(design_params["n_tail"])
        width_weights = self._validate_weights("width_weights", design_params["width_weights"])
        height_weights = self._validate_weights("height_weights", design_params["height_weights"])
        super_m = float(design_params.get("super_m", 2.5))
        super_n = float(design_params.get("super_n", 2.5))
        num_sections = int(design_params.get("num_sections", 40))

        vsp.ClearVSPModel()

        fuse_id = vsp.AddGeom("FUSELAGE")
        vsp.SetGeomName(fuse_id, name)
        vsp.SetParmVal(fuse_id, "Length", "Design", length)

        xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
        current_sections = vsp.GetNumXSec(xsec_surf)
        needed_inserts = max(0, num_sections - current_sections)

        for index in range(needed_inserts):
            vsp.InsertXSec(fuse_id, 1 + index, vsp.XS_SUPER_ELLIPSE)

        vsp.Update()

        final_count = vsp.GetNumXSec(xsec_surf)
        for index in range(final_count):
            psi = index / (final_count - 1)
            is_tip = index == 0 or index == final_count - 1

            if is_tip:
                vsp.ChangeXSecShape(xsec_surf, index, vsp.XS_POINT)
            else:
                vsp.ChangeXSecShape(xsec_surf, index, vsp.XS_SUPER_ELLIPSE)

            xsec = vsp.GetXSec(xsec_surf, index)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

            if not is_tip:
                width_radius = self.calculate_cst_radius(psi, n_nose, n_tail, width_weights, length)
                height_radius = self.calculate_cst_radius(psi, n_nose, n_tail, height_weights, length)

                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), max(width_radius * 2.0, 0.001))
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), max(height_radius * 2.0, 0.001))
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), super_m)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), super_n)

        vsp.Update()

        filepath = os.path.join(self.output_dir, f"{name}.vsp3")
        vsp.WriteVSPFile(filepath)
        return filepath
