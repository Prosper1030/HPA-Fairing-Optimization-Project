import argparse
import importlib.util
import json
import os
import shutil
import sys
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
SCRIPTS_ROOT = os.path.join(PROJECT_ROOT, "scripts")

sys.path.insert(0, SRC_ROOT)
sys.path.insert(0, SCRIPTS_ROOT)


RUN_GA_SPEC = importlib.util.find_spec("run_ga")
PYMOO_SPEC = importlib.util.find_spec("pymoo")

if RUN_GA_SPEC is not None:
    import run_ga
else:
    run_ga = None


@unittest.skipUnless(run_ga is not None and PYMOO_SPEC is not None, "run_ga / pymoo unavailable")
class TestRunGaProxy(unittest.TestCase):
    def test_run_ga_proxy_smoke_saves_analysis_summary(self):
        args = argparse.Namespace(
            gen=1,
            pop=4,
            seed=7,
            tol=1,
            workers=1,
            config=os.path.join(PROJECT_ROOT, "config", "ga_config.json"),
            fluid=os.path.join(PROJECT_ROOT, "config", "fluid_conditions.json"),
            resume=None,
            analysis_mode=None,
            final_vsp=False,
            skip_final_vsp=False,
            prepare_su2_shortlist=False,
            su2_shortlist_top=5,
            su2_shortlist_out=None,
        )

        result = run_ga.run_optimization(args)
        self.assertIsNotNone(result)
        _, pm, _ = result

        try:
            with open(pm.best_gene_file, "r", encoding="utf-8") as handle:
                best_gene_payload = json.load(handle)
            with open(pm.results_file, "r", encoding="utf-8") as handle:
                results_payload = json.load(handle)

            self.assertEqual(results_payload["analysis_mode"], "proxy")
            self.assertIn("best_analysis", results_payload)
            self.assertIn("Drag", results_payload["best_analysis"])
            self.assertIn("Cd", results_payload["best_analysis"])
            self.assertIn("analysis", best_gene_payload)
            self.assertEqual(best_gene_payload["analysis"]["AnalysisMode"], "proxy")
            self.assertTrue(os.path.exists(pm.candidate_scores_file))
        finally:
            shutil.rmtree(pm.run_dir, ignore_errors=True)

    def test_run_ga_proxy_can_prepare_su2_shortlist_bundle(self):
        args = argparse.Namespace(
            gen=1,
            pop=4,
            seed=11,
            tol=1,
            workers=1,
            config=os.path.join(PROJECT_ROOT, "config", "ga_config.json"),
            fluid=os.path.join(PROJECT_ROOT, "config", "fluid_conditions.json"),
            resume=None,
            analysis_mode=None,
            final_vsp=False,
            skip_final_vsp=False,
            prepare_su2_shortlist=True,
            su2_shortlist_top=2,
            su2_shortlist_out=None,
        )

        result = run_ga.run_optimization(args)
        self.assertIsNotNone(result)
        _, pm, _ = result

        try:
            with open(pm.results_file, "r", encoding="utf-8") as handle:
                results_payload = json.load(handle)

            shortlist = results_payload["su2_shortlist"]
            self.assertTrue(shortlist["prepared"])
            self.assertEqual(shortlist["top_n_requested"], 2)
            self.assertTrue(os.path.exists(shortlist["manifest_json"]))
            self.assertTrue(os.path.exists(shortlist["run_script"]))

            with open(shortlist["manifest_json"], "r", encoding="utf-8") as handle:
                manifest_payload = json.load(handle)

            self.assertGreaterEqual(manifest_payload["CaseCount"], 1)
            self.assertLessEqual(manifest_payload["CaseCount"], 2)
            self.assertEqual(manifest_payload["Preset"], "hpa")
            self.assertTrue(
                os.path.exists(
                    os.path.join(manifest_payload["Cases"][0]["CaseDir"], "su2_case.cfg")
                )
            )
        finally:
            shutil.rmtree(pm.run_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
