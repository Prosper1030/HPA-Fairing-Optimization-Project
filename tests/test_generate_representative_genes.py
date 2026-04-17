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

from analysis.fairing_analysis import get_representative_gene_cases


class TestGenerateRepresentativeGenes(unittest.TestCase):
    def test_representative_gene_cases_cover_all_expected_tags(self):
        expected_tags = {
            "slender",
            "short_fat",
            "peak_forward",
            "peak_aft",
            "tail_aggressive",
            "tail_conservative",
            "mid_pack",
        }

        covered_tags = set()
        for case in get_representative_gene_cases():
            covered_tags.update(case["TargetTags"])
            self.assertIsInstance(case["Gene"], dict)
            self.assertIn("CaseName", case)

        self.assertEqual(covered_tags, expected_tags)

    def test_cli_writes_batch_summary_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = os.path.join(temp_dir, "representative_cases")
            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "generate_representative_genes.py"),
                    "--out",
                    out_dir,
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("代表性整流罩 gene 批次已產生", proc.stdout)

            batch_summary_path = os.path.join(out_dir, "batch_summary.json")
            manifest_path = os.path.join(out_dir, "representative_manifest.json")
            self.assertTrue(os.path.exists(batch_summary_path))
            self.assertTrue(os.path.exists(manifest_path))

            with open(batch_summary_path, "r", encoding="utf-8") as handle:
                batch_summary = json.load(handle)
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)

            self.assertEqual(batch_summary["SuccessfulCases"], len(get_representative_gene_cases()))
            covered_tags = set()
            for entry in batch_summary["RankedCases"]:
                covered_tags.update(entry["RepresentativeTags"])

            self.assertTrue({"slender", "short_fat", "peak_forward", "peak_aft", "tail_aggressive", "tail_conservative", "mid_pack"}.issubset(covered_tags))
            self.assertEqual(manifest["TotalCases"], len(get_representative_gene_cases()))


if __name__ == "__main__":
    unittest.main()
