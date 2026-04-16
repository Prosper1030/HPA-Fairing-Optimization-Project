import json
import os
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
SCRIPTS_ROOT = os.path.join(PROJECT_ROOT, "scripts")

sys.path.insert(0, SRC_ROOT)

from analysis.fairing_analysis import analyze_gene, get_example_gene, write_analysis_report_bundle


class TestFairingAnalysis(unittest.TestCase):
    def setUp(self):
        self.gene = {
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

    def test_presets_keep_aero_same_but_change_constraint_report(self):
        result_none = analyze_gene(self.gene, preset="none", include_geometry=True)
        result_hpa = analyze_gene(self.gene, preset="hpa", include_geometry=True)

        self.assertAlmostEqual(result_none["Drag"], result_hpa["Drag"], places=8)
        self.assertAlmostEqual(result_none["Cd"], result_hpa["Cd"], places=8)
        self.assertEqual(result_none["ConstraintReport"], {})
        self.assertIn("checks", result_hpa["ConstraintReport"])

    def test_report_bundle_creates_expected_files(self):
        analysis = analyze_gene(self.gene, preset="none", include_geometry=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            report_files = write_analysis_report_bundle(temp_dir, self.gene, analysis)
            for path in report_files.values():
                self.assertTrue(os.path.exists(path), msg=f"Missing report file: {path}")

            with open(report_files["summary_json"], "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["Analysis"]["Backend"], "fast_proxy")
            self.assertTrue(payload["Analysis"]["Recommendations"])

    def test_example_gene_is_complete_and_analyzable(self):
        example_gene = get_example_gene()
        analysis = analyze_gene(example_gene, preset="none")

        self.assertIn("Drag", analysis)
        self.assertIn("Cd", analysis)

    def test_cli_smoke_creates_report_bundle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_path = os.path.join(temp_dir, "gene.json")
            out_dir = os.path.join(temp_dir, "report")
            with open(gene_path, "w", encoding="utf-8") as handle:
                json.dump(self.gene, handle)

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "analyze_fairing.py"),
                    "--gene",
                    gene_path,
                    "--out",
                    out_dir,
                    "--preset",
                    "hpa",
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("低速整流罩分析完成", proc.stdout)
            self.assertTrue(os.path.exists(os.path.join(out_dir, "summary.json")))
            self.assertTrue(os.path.exists(os.path.join(out_dir, "summary.md")))

    def test_cli_reports_missing_gene_fields_cleanly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bad_gene_path = os.path.join(temp_dir, "bad_gene.json")
            with open(bad_gene_path, "w", encoding="utf-8") as handle:
                json.dump({"L": 2.5}, handle)

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "analyze_fairing.py"),
                    "--gene",
                    bad_gene_path,
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("缺少必要欄位", proc.stderr)
            self.assertIn("--write-example-gene", proc.stderr)

    def test_cli_can_write_example_gene(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_path = os.path.join(temp_dir, "example_gene.json")

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "analyze_fairing.py"),
                    "--write-example-gene",
                    gene_path,
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertTrue(os.path.exists(gene_path))
            with open(gene_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["X_max_pos"], get_example_gene()["X_max_pos"])

    def test_cli_can_list_required_fields(self):
        proc = subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS_ROOT, "analyze_fairing.py"),
                "--show-required-fields",
            ],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )

        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("必填 gene 欄位與建議範圍", proc.stdout)
        self.assertIn("X_max_pos", proc.stdout)


if __name__ == "__main__":
    unittest.main()
