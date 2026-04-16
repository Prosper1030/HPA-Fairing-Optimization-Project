import os
import sys
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))

from analysis.design_evaluator import evaluate_design_gene
from analysis.fairing_drag_proxy import FairingDragProxy
from optimization.hpa_asymmetric_optimizer import CST_Modeler
from run_one_case import evaluate_gene


class TestDragProxyMetrics(unittest.TestCase):
    def setUp(self):
        self.base_gene = {
            "L": 2.5,
            "W_max": 0.60,
            "H_top_max": 0.95,
            "H_bot_max": 0.35,
            "N1": 0.5,
            "N2_top": 0.75,
            "N2_bot": 0.80,
            "X_max_pos": 0.32,
            "X_offset": 0.7,
            "M_top": 2.5,
            "N_top": 2.5,
            "M_bot": 2.5,
            "N_bot": 2.5,
            "tail_rise": 0.08,
            "blend_start": 0.80,
            "blend_power": 2.2,
            "w0": 0.25,
            "w1": 0.35,
            "w2": 0.30,
            "w3": 0.10,
        }

    def test_proxy_penalizes_aft_peak_and_reports_lower_laminar_fraction(self):
        proxy = FairingDragProxy()

        baseline = proxy.evaluate_curves(CST_Modeler.generate_asymmetric_fairing(self.base_gene, num_sections=160))
        aft_peak = proxy.evaluate_curves(
            CST_Modeler.generate_asymmetric_fairing(
                {**self.base_gene, "X_max_pos": 0.46},
                num_sections=160,
            )
        )

        self.assertLess(aft_peak["LaminarFraction"], baseline["LaminarFraction"])
        self.assertGreater(aft_peak["Cd_pressure"], baseline["Cd_pressure"])
        self.assertGreater(aft_peak["Cd"], baseline["Cd"])

    def test_evaluate_gene_proxy_details_are_self_consistent(self):
        result = evaluate_gene(
            self.base_gene,
            "proxy_detail_test",
            W_area_penalty=0.1,
            analysis_mode="proxy",
            return_details=True,
        )

        self.assertTrue(result["Valid"])
        self.assertIn("LaminarFraction", result)
        self.assertAlmostEqual(result["Score"], result["Drag"] + 0.1 * result["Swet"], places=6)

    def test_run_one_case_wrapper_matches_shared_evaluator(self):
        wrapped = evaluate_gene(
            self.base_gene,
            "proxy_wrapper_test",
            W_area_penalty=0.1,
            analysis_mode="proxy",
            return_details=True,
        )
        shared = evaluate_design_gene(
            self.base_gene,
            "proxy_wrapper_test",
            area_penalty=0.1,
            analysis_mode="proxy",
            return_details=True,
        )

        self.assertAlmostEqual(wrapped["Score"], shared["Score"], places=8)
        self.assertAlmostEqual(wrapped["Drag"], shared["Drag"], places=8)
        self.assertAlmostEqual(wrapped["Cd"], shared["Cd"], places=8)


if __name__ == "__main__":
    unittest.main()
