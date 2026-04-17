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

from analysis.fairing_analysis import (
    analyze_gene,
    build_representative_case_metadata,
    get_example_gene,
    load_gene_file,
    write_analysis_report_bundle,
)


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

    def test_report_bundle_can_use_placeholder_plots(self):
        analysis = analyze_gene(self.gene, preset="none", include_geometry=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            report_files = write_analysis_report_bundle(
                temp_dir,
                self.gene,
                analysis,
                report_config={"use_placeholder_plots": True},
            )
            self.assertTrue(os.path.exists(report_files["side_profile"]))
            self.assertTrue(os.path.exists(report_files["drag_breakdown"]))

    def test_example_gene_is_complete_and_analyzable(self):
        example_gene = get_example_gene()
        analysis = analyze_gene(example_gene, preset="none")

        self.assertIn("Drag", analysis)
        self.assertIn("Cd", analysis)

    def test_analysis_reports_representative_tags(self):
        aggressive_gene = {
            **self.gene,
            "X_max_pos": 0.4750946075323426,
            "tail_rise": 0.15199121805064983,
            "M_top": 3.9805360794379796,
            "N_top": 2.633820962361373,
            "M_bot": 3.6288991654137503,
            "N_bot": 2.9131356487487867,
        }

        analysis = analyze_gene(aggressive_gene, preset="none")

        self.assertIn("peak_aft", analysis["RepresentativeTags"])
        self.assertIn("tail_aggressive", analysis["RepresentativeTags"])
        self.assertGreater(analysis["GeometryTraits"]["PressureRisk"], 0.65)

    def test_example_gene_now_maps_to_mid_pack_in_family_distribution(self):
        analysis = analyze_gene(get_example_gene(), preset="none")

        self.assertEqual(analysis["RepresentativeTags"], ["mid_pack"])

    def test_representative_metadata_defaults_to_mid_pack_when_no_extreme_tag(self):
        metadata = build_representative_case_metadata(
            {
                "FinenessRatio": 2.6,
                "XPeakAreaFrac": 0.33,
                "TailAngles": {"top_deg": 38.0, "bottom_deg": 18.0, "side_deg": 12.5},
                "Quality": {
                    "pressure_risk": 0.45,
                    "area_monotonicity": 0.99,
                    "recovery_curvature": 0.02,
                },
            }
        )

        self.assertEqual(metadata["RepresentativeTags"], ["mid_pack"])

    def test_representative_metadata_can_emit_slender_and_tail_conservative(self):
        metadata = build_representative_case_metadata(
            {
                "FinenessRatio": 3.1,
                "XPeakAreaFrac": 0.23,
                "TailAngles": {"top_deg": 34.0, "bottom_deg": 13.5, "side_deg": 10.5},
                "Quality": {
                    "pressure_risk": 0.28,
                    "area_monotonicity": 0.99,
                    "recovery_curvature": 0.02,
                },
            }
        )

        self.assertIn("slender", metadata["RepresentativeTags"])
        self.assertIn("peak_forward", metadata["RepresentativeTags"])
        self.assertIn("tail_conservative", metadata["RepresentativeTags"])

    def test_partial_gene_can_be_filled_from_example(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_path = os.path.join(temp_dir, "partial_gene.json")
            with open(gene_path, "w", encoding="utf-8") as handle:
                json.dump({"L": 2.6, "W_max": 0.58}, handle)

            gene, metadata = load_gene_file(
                gene_path,
                fill_missing_from_example=True,
                return_metadata=True,
            )

        self.assertEqual(gene["L"], 2.6)
        self.assertEqual(gene["W_max"], 0.58)
        self.assertIn("X_max_pos", metadata["filled_fields"])
        self.assertEqual(gene["X_max_pos"], get_example_gene()["X_max_pos"])

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

    def test_cli_can_fill_missing_fields_from_example(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_path = os.path.join(temp_dir, "partial_gene.json")
            out_dir = os.path.join(temp_dir, "report")
            with open(gene_path, "w", encoding="utf-8") as handle:
                json.dump({"L": 2.6, "W_max": 0.58}, handle)

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "analyze_fairing.py"),
                    "--gene",
                    gene_path,
                    "--out",
                    out_dir,
                    "--fill-missing-from-example",
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("FilledFields:", proc.stdout)

            with open(os.path.join(out_dir, "summary.json"), "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertIn("X_max_pos", payload["GeneMetadata"]["filled_fields"])

    def test_cli_batch_mode_creates_ranked_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_dir = os.path.join(temp_dir, "genes")
            out_dir = os.path.join(temp_dir, "batch_report")
            os.makedirs(gene_dir, exist_ok=True)

            gene_a = dict(self.gene)
            gene_b = {
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

            with open(os.path.join(gene_dir, "gene_a.json"), "w", encoding="utf-8") as handle:
                json.dump(gene_a, handle)
            with open(os.path.join(gene_dir, "gene_b.json"), "w", encoding="utf-8") as handle:
                json.dump(gene_b, handle)

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "analyze_fairing.py"),
                    "--gene-dir",
                    gene_dir,
                    "--out",
                    out_dir,
                    "--fill-missing-from-example",
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("batch 分析完成", proc.stdout)

            summary_json = os.path.join(out_dir, "batch_summary.json")
            summary_md = os.path.join(out_dir, "batch_summary.md")
            self.assertTrue(os.path.exists(summary_json))
            self.assertTrue(os.path.exists(summary_md))
            self.assertTrue(os.path.exists(os.path.join(out_dir, "gene_a", "summary.json")))
            self.assertTrue(os.path.exists(os.path.join(out_dir, "gene_b", "summary.json")))

            with open(summary_json, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertEqual(payload["SuccessfulCases"], 2)
            self.assertEqual(payload["FailedCases"], 0)
            self.assertEqual(len(payload["RankedCases"]), 2)
            self.assertEqual(payload["RankedCases"][0]["Rank"], 1)
            self.assertTrue(payload["RankedCases"][1]["FilledFields"])
            self.assertIn("RepresentativeTags", payload["RankedCases"][0])
            self.assertIn("GeometryTraits", payload["RankedCases"][0])
            self.assertIn("peak_aft", payload["RankedCases"][1]["RepresentativeTags"])


if __name__ == "__main__":
    unittest.main()
