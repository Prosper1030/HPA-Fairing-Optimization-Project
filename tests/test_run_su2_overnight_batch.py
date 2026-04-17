import json
import os
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_ROOT = os.path.join(PROJECT_ROOT, "scripts")


class TestRunSU2OvernightBatch(unittest.TestCase):
    def test_dry_run_writes_manifest_for_anchor_batch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = os.path.join(temp_dir, "overnight")
            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "run_su2_overnight_batch.py"),
                    "--out",
                    out_dir,
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("SU2 overnight batch dry-run 已準備完成", proc.stdout)

            manifest_path = os.path.join(out_dir, "overnight_manifest.json")
            self.assertTrue(os.path.exists(manifest_path))

            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)

            self.assertEqual(manifest["CaseSet"], "anchor3")
            self.assertEqual(manifest["Profiles"], ["baseline"])
            self.assertFalse("representative-study" in manifest["MeshStudyCommand"])
            self.assertIn("slender_forward_conservative.json", manifest["MeshStudyCommand"])
            self.assertIn("mid_pack_example.json", manifest["MeshStudyCommand"])
            self.assertIn("shortfat_aft_aggressive.json", manifest["MeshStudyCommand"])

    def test_dry_run_can_plan_full_representative_batch(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = os.path.join(temp_dir, "overnight")
            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "run_su2_overnight_batch.py"),
                    "--out",
                    out_dir,
                    "--dry-run",
                    "--case-set",
                    "representative7",
                    "--profile",
                    "baseline",
                    "--profile",
                    "fine",
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            manifest_path = os.path.join(out_dir, "overnight_manifest.json")
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)

            self.assertEqual(manifest["CaseSet"], "representative7")
            self.assertEqual(manifest["Profiles"], ["baseline", "fine"])
            self.assertIn("--batch-summary", manifest["MeshStudyCommand"])
            self.assertIn("--representative-study", manifest["MeshStudyCommand"])
            self.assertIn("--representative-limit 7", manifest["MeshStudyCommand"])


if __name__ == "__main__":
    unittest.main()
