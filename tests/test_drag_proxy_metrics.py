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
        self.v7_best_gene = {
            "L": 2.828806591985072,
            "W_max": 0.5341212363598906,
            "H_top_max": 0.8507129826582426,
            "H_bot_max": 0.2607630635524523,
            "N1": 0.8995455328544454,
            "N2_top": 0.9819192231873867,
            "N2_bot": 0.7907158655805717,
            "X_max_pos": 0.3643890987737485,
            "X_offset": 0.6078884129880086,
            "M_top": 2.0021852058203873,
            "N_top": 2.028808871553711,
            "M_bot": 2.007321105470481,
            "N_bot": 2.021742493504909,
            "tail_rise": 0.10934525233257308,
            "blend_start": 0.6538349048599497,
            "blend_power": 1.9011250655299892,
            "w0": 0.1503535786702696,
            "w1": 0.44702560862028085,
            "w2": 0.35787314040559176,
            "w3": 0.050755819931282656,
        }
        self.v8_best_gene = {
            "L": 2.9399018072622938,
            "W_max": 0.541544387581185,
            "H_top_max": 0.8500811510703054,
            "H_bot_max": 0.26096983513480354,
            "N1": 0.8972443103846243,
            "N2_top": 0.7601539888927857,
            "N2_bot": 0.9440911069578535,
            "X_max_pos": 0.33804717404485163,
            "X_offset": 0.6195244152510936,
            "M_top": 2.0356087082719094,
            "N_top": 2.1075076473942826,
            "M_bot": 2.015632226617622,
            "N_bot": 2.460222924039834,
            "tail_rise": 0.10549525917730586,
            "blend_start": 0.6625835716376283,
            "blend_power": 1.7458441736757573,
            "w0": 0.1557907894557326,
            "w1": 0.4432825353288791,
            "w2": 0.38336454427625105,
            "w3": 0.06367026794813055,
        }

    def test_proxy_penalizes_aft_peak_and_reports_lower_laminar_fraction(self):
        proxy = FairingDragProxy(model_version="v5")

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
        self.assertGreater(aft_peak["Quality"]["pressure_risk"], baseline["Quality"]["pressure_risk"])

    def test_proxy_flags_high_pressure_risk_for_steep_tail_case(self):
        proxy = FairingDragProxy(model_version="v5")
        steep_tail_gene = {
            **self.base_gene,
            "L": 2.463576995012689,
            "W_max": 0.5401448192294462,
            "H_top_max": 0.9688933779766921,
            "H_bot_max": 0.4969736180688764,
            "X_max_pos": 0.4750946075323426,
            "tail_rise": 0.15199121805064983,
            "M_top": 3.9805360794379796,
            "N_top": 2.633820962361373,
            "M_bot": 3.6288991654137503,
            "N_bot": 2.9131356487487867,
        }

        result = proxy.evaluate_curves(
            CST_Modeler.generate_asymmetric_fairing(steep_tail_gene, num_sections=160)
        )

        self.assertEqual(result["Model"], "fast_drag_proxy_v5")
        self.assertGreater(result["Cd_pressure"], 0.015)
        self.assertGreater(result["Quality"]["pressure_risk"], 0.65)
        self.assertIn("TransitionFraction", result)
        self.assertAlmostEqual(result["TransitionFraction"], result["LaminarFraction"], places=8)

    def test_proxy_best_gene_stays_near_boundary_layer_su2_scale(self):
        proxy = FairingDragProxy(model_version="v7")
        best_gene = {
            "L": 2.463576995012689,
            "W_max": 0.5401448192294462,
            "H_top_max": 0.9688933779766921,
            "H_bot_max": 0.4969736180688764,
            "N1": 0.8046174873474908,
            "N2_top": 0.719789404087345,
            "N2_bot": 0.7560220834250201,
            "X_max_pos": 0.4750946075323426,
            "X_offset": 0.6875715657863976,
            "M_top": 3.9805360794379796,
            "N_top": 2.633820962361373,
            "M_bot": 3.6288991654137503,
            "N_bot": 2.9131356487487867,
            "tail_rise": 0.15199121805064983,
            "blend_start": 0.8173829309961446,
            "blend_power": 1.9435394606842078,
            "w0": 0.3026334562712985,
            "w1": 0.3464006669710251,
            "w2": 0.3013001624596976,
            "w3": 0.11976273259867327,
        }

        result = proxy.evaluate_curves(
            CST_Modeler.generate_asymmetric_fairing(best_gene, num_sections=160)
        )

        su2_boundary_layer_cd = 0.04955419767
        relative_error = abs(result["Cd"] - su2_boundary_layer_cd) / su2_boundary_layer_cd

        self.assertEqual(result["Model"], "fast_drag_proxy_v7")
        self.assertLess(result["Cd"], 0.08)
        self.assertLess(relative_error, 0.45)

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

    def test_proxy_uses_distinct_superellipse_m_and_n_instead_of_only_their_average(self):
        proxy = FairingDragProxy(model_version="v7")
        top_flat_side_round = {
            **self.base_gene,
            "M_top": 4.0,
            "N_top": 2.0,
        }
        top_round_side_flat = {
            **self.base_gene,
            "M_top": 2.0,
            "N_top": 4.0,
        }

        result_a = proxy.evaluate_curves(CST_Modeler.generate_asymmetric_fairing(top_flat_side_round, num_sections=160))
        result_b = proxy.evaluate_curves(CST_Modeler.generate_asymmetric_fairing(top_round_side_flat, num_sections=160))

        self.assertNotAlmostEqual(result_a["Swet"], result_b["Swet"], places=6)
        self.assertNotAlmostEqual(result_a["Cd"], result_b["Cd"], places=6)

    def test_tail_aggressiveness_primarily_changes_pressure_terms_not_transition_surrogate(self):
        proxy = FairingDragProxy(model_version="v5")
        aggressive_tail = {
            **self.base_gene,
            "L": 2.3,
            "W_max": 0.57,
            "H_top_max": 0.95,
            "H_bot_max": 0.33,
            "X_max_pos": 0.34,
            "tail_rise": 0.18,
            "blend_start": 0.84,
            "blend_power": 2.8,
            "M_top": 3.7,
            "M_bot": 3.5,
            "N_top": 2.2,
            "N_bot": 2.2,
            "w0": 0.16,
            "w1": 0.25,
            "w2": 0.39,
            "w3": 0.19,
        }

        baseline = proxy.evaluate_curves(CST_Modeler.generate_asymmetric_fairing(self.base_gene, num_sections=160))
        aggressive = proxy.evaluate_curves(
            CST_Modeler.generate_asymmetric_fairing(aggressive_tail, num_sections=160)
        )

        self.assertLess(abs(aggressive["TransitionFraction"] - baseline["TransitionFraction"]), 0.05)
        self.assertGreater(aggressive["Cd_pressure"], baseline["Cd_pressure"])
        self.assertGreater(aggressive["Quality"]["pressure_risk"], baseline["Quality"]["pressure_risk"])

    def test_default_proxy_is_v7_but_v6_and_v5_are_still_selectable(self):
        curves = CST_Modeler.generate_asymmetric_fairing(self.base_gene, num_sections=160)

        default_result = FairingDragProxy().evaluate_curves(curves)
        v6_result = FairingDragProxy(model_version="v6").evaluate_curves(curves)
        v8_result = FairingDragProxy(model_version="v8").evaluate_curves(curves)
        v9_result = FairingDragProxy(model_version="v9").evaluate_curves(curves)
        legacy_result = FairingDragProxy(model_version="v5").evaluate_curves(curves)

        self.assertEqual(default_result["Model"], "fast_drag_proxy_v7")
        self.assertEqual(v6_result["Model"], "fast_drag_proxy_v6")
        self.assertEqual(v8_result["Model"], "fast_drag_proxy_v8")
        self.assertEqual(v9_result["Model"], "fast_drag_proxy_v9")
        self.assertEqual(legacy_result["Model"], "fast_drag_proxy_v5")
        self.assertNotAlmostEqual(default_result["Cd_pressure"], v6_result["Cd_pressure"], places=8)
        self.assertNotAlmostEqual(v6_result["Cd_pressure"], legacy_result["Cd_pressure"], places=8)
        self.assertNotAlmostEqual(default_result["Cd"], v8_result["Cd"], places=8)
        self.assertNotAlmostEqual(default_result["Cd"], v9_result["Cd"], places=8)

    def test_v7_transition_surrogate_ignores_operating_conditions_when_unspecified(self):
        curves = CST_Modeler.generate_asymmetric_fairing(self.base_gene, num_sections=160)

        default_result = FairingDragProxy(model_version="v7").evaluate_curves(curves)
        explicit_refs_result = FairingDragProxy(
            model_version="v7",
            turbulence_intensity=0.005,
            roughness_height=1e-5,
        ).evaluate_curves(curves)

        self.assertAlmostEqual(
            default_result["TransitionFraction"],
            explicit_refs_result["TransitionFraction"],
            places=8,
        )

    def test_v7_reports_surface_weighted_laminar_fraction(self):
        curves = CST_Modeler.generate_asymmetric_fairing(self.base_gene, num_sections=160)
        result = FairingDragProxy(model_version="v7").evaluate_curves(curves)

        self.assertIn("LaminarAreaFraction", result)
        self.assertGreater(result["LaminarAreaFraction"], 0.0)
        self.assertLessEqual(result["LaminarAreaFraction"], 1.0)
        self.assertLessEqual(result["LaminarAreaFraction"], result["TransitionFraction"])

    def test_v7_keeps_nonzero_attached_flow_cost_for_smooth_shape(self):
        curves = CST_Modeler.generate_asymmetric_fairing(self.base_gene, num_sections=160)
        v6_result = FairingDragProxy(model_version="v6").evaluate_curves(curves)
        v7_result = FairingDragProxy(model_version="v7").evaluate_curves(curves)

        self.assertGreater(v7_result["Cd_pressure"], 0.0)
        self.assertGreater(v7_result["Cd_viscous"], v6_result["Cd_viscous"])
        self.assertGreater(v7_result["Cd"], v6_result["Cd"])

    def test_v8_trust_region_moves_current_best_toward_converged_su2(self):
        curves = CST_Modeler.generate_asymmetric_fairing(self.v7_best_gene, num_sections=160)
        su2_cd = 0.02197176052

        v7_result = FairingDragProxy(model_version="v7").evaluate_curves(curves)
        v8_result = FairingDragProxy(model_version="v8").evaluate_curves(curves)

        v7_error = abs(v7_result["Cd"] - su2_cd) / su2_cd
        v8_error = abs(v8_result["Cd"] - su2_cd) / su2_cd

        self.assertGreater(v8_result["Calibration"]["factor"], 1.0)
        self.assertGreater(v8_result["Calibration"]["blend"], 0.5)
        self.assertLess(v8_error, v7_error)

    def test_v8_trust_region_stays_inactive_for_far_aggressive_shape(self):
        aggressive_tail = {
            **self.base_gene,
            "L": 1.80,
            "W_max": 0.65,
            "H_top_max": 1.12,
            "H_bot_max": 0.49,
            "X_max_pos": 0.48,
            "tail_rise": 0.19,
            "blend_start": 0.84,
            "blend_power": 2.9,
            "M_top": 3.9,
            "M_bot": 3.8,
            "N_top": 2.2,
            "N_bot": 2.2,
            "w0": 0.16,
            "w1": 0.26,
            "w2": 0.38,
            "w3": 0.20,
        }
        curves = CST_Modeler.generate_asymmetric_fairing(aggressive_tail, num_sections=160)

        v7_result = FairingDragProxy(model_version="v7").evaluate_curves(curves)
        v8_result = FairingDragProxy(model_version="v8").evaluate_curves(curves)

        self.assertLess(v8_result["Calibration"]["blend"], 1e-6)
        self.assertAlmostEqual(v8_result["Calibration"]["factor"], 1.0, places=8)
        self.assertAlmostEqual(v8_result["Cd"], v7_result["Cd"], places=8)

    def test_v9_tail_closure_anchor_moves_current_v8_best_toward_su2(self):
        curves = CST_Modeler.generate_asymmetric_fairing(self.v8_best_gene, num_sections=160)
        su2_cd = 0.02699590694

        v7_result = FairingDragProxy(model_version="v7").evaluate_curves(curves)
        v8_result = FairingDragProxy(model_version="v8").evaluate_curves(curves)
        v9_result = FairingDragProxy(model_version="v9").evaluate_curves(curves)

        v7_error = abs(v7_result["Cd"] - su2_cd) / su2_cd
        v8_error = abs(v8_result["Cd"] - su2_cd) / su2_cd
        v9_error = abs(v9_result["Cd"] - su2_cd) / su2_cd

        self.assertGreater(v9_result["Calibration"]["factor"], 1.20)
        self.assertLess(v9_error, v7_error)
        self.assertLess(v9_error, v8_error)

    def test_v9_tail_floor_stays_inactive_for_far_aggressive_shape(self):
        aggressive_tail = {
            **self.base_gene,
            "L": 1.80,
            "W_max": 0.65,
            "H_top_max": 1.12,
            "H_bot_max": 0.49,
            "X_max_pos": 0.48,
            "tail_rise": 0.19,
            "blend_start": 0.84,
            "blend_power": 2.9,
            "M_top": 3.9,
            "M_bot": 3.8,
            "N_top": 2.2,
            "N_bot": 2.2,
            "w0": 0.16,
            "w1": 0.26,
            "w2": 0.38,
            "w3": 0.20,
        }
        curves = CST_Modeler.generate_asymmetric_fairing(aggressive_tail, num_sections=160)

        v7_result = FairingDragProxy(model_version="v7").evaluate_curves(curves)
        v9_result = FairingDragProxy(model_version="v9").evaluate_curves(curves)

        self.assertFalse(v9_result["Calibration"]["tail_floor_applied"])
        self.assertLess(v9_result["Calibration"]["blend"], 1e-6)
        self.assertAlmostEqual(v9_result["Calibration"]["factor"], 1.0, places=8)
        self.assertAlmostEqual(v9_result["Cd"], v7_result["Cd"], places=8)

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
