import os
import sys
import unittest

import numpy as np


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from optimization.hpa_asymmetric_optimizer import CST_Modeler


class TestGeometryPeakPosition(unittest.TestCase):
    def test_cst_curve_preserves_target_height_after_peak_remap(self):
        psi = np.linspace(0.0, 1.0, 401)
        curve = CST_Modeler.cst_curve(
            psi,
            target_height=0.32,
            N1=0.55,
            N2=0.85,
            weights=np.array([0.25, 0.35, 0.30, 0.10]),
            peak_position=0.42,
        )

        self.assertAlmostEqual(float(np.max(curve)), 0.32, places=6)

    def test_x_max_pos_moves_peak_station_in_generated_fairing(self):
        base_gene = {
            "L": 2.5,
            "W_max": 0.60,
            "H_top_max": 0.95,
            "H_bot_max": 0.35,
            "N1": 0.5,
            "N2_top": 0.7,
            "N2_bot": 0.8,
            "X_offset": 0.7,
            "M_top": 2.5,
            "N_top": 2.5,
            "M_bot": 2.5,
            "N_bot": 2.5,
            "tail_rise": 0.10,
            "blend_start": 0.75,
            "blend_power": 2.0,
            "w0": 0.25,
            "w1": 0.35,
            "w2": 0.30,
            "w3": 0.10,
        }

        early_curves = CST_Modeler.generate_asymmetric_fairing(
            {**base_gene, "X_max_pos": 0.24},
            num_sections=160,
        )
        late_curves = CST_Modeler.generate_asymmetric_fairing(
            {**base_gene, "X_max_pos": 0.44},
            num_sections=160,
        )

        early_width_peak = early_curves["x"][int(np.argmax(early_curves["width"]))] / early_curves["L"]
        late_width_peak = late_curves["x"][int(np.argmax(late_curves["width"]))] / late_curves["L"]
        early_height_peak = early_curves["x"][int(np.argmax(early_curves["z_upper"]))] / early_curves["L"]
        late_height_peak = late_curves["x"][int(np.argmax(late_curves["z_upper"]))] / late_curves["L"]

        self.assertGreater(late_width_peak, early_width_peak + 0.08)
        self.assertGreater(late_height_peak, early_height_peak + 0.08)
        self.assertAlmostEqual(late_width_peak, 0.44, delta=0.05)
        self.assertAlmostEqual(early_width_peak, 0.24, delta=0.05)
        self.assertAlmostEqual(float(np.max(early_curves["width"])), base_gene["W_max"], delta=2e-3)
        self.assertAlmostEqual(float(np.max(late_curves["z_upper"])), base_gene["H_top_max"], delta=2e-3)

    def test_tail_conditions_are_enforced_in_thickness_and_centerline_space(self):
        gene = {
            "L": 2.5,
            "W_max": 0.60,
            "H_top_max": 0.95,
            "H_bot_max": 0.35,
            "N1": 0.5,
            "N2_top": 0.70,
            "N2_bot": 0.85,
            "X_max_pos": 0.34,
            "X_offset": 0.7,
            "M_top": 2.5,
            "N_top": 2.5,
            "M_bot": 2.5,
            "N_bot": 2.5,
            "tail_rise": 0.12,
            "blend_start": 0.82,
            "blend_power": 2.6,
            "w0": 0.22,
            "w1": 0.38,
            "w2": 0.27,
            "w3": 0.12,
        }

        curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=160)

        self.assertAlmostEqual(float(curves["super_height"][-1]), 0.0, places=8)
        self.assertAlmostEqual(float(curves["z_loc"][-1]), gene["tail_rise"], places=8)
        self.assertAlmostEqual(float(curves["z_upper"][-1]), gene["tail_rise"], places=8)
        self.assertAlmostEqual(float(curves["z_lower"][-1]), gene["tail_rise"], places=8)
        self.assertTrue(np.all(curves["super_height"] >= -1e-10))


if __name__ == "__main__":
    unittest.main()
