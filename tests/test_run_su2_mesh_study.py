import importlib.util
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

from analysis import get_example_gene


GMSH_AVAILABLE = importlib.util.find_spec("gmsh") is not None


@unittest.skipUnless(GMSH_AVAILABLE, "gmsh not installed")
class TestRunSU2MeshStudy(unittest.TestCase):
    def test_cli_runs_single_profile_mesh_study_with_fake_solver(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_path = os.path.join(temp_dir, "gene.json")
            output_dir = os.path.join(temp_dir, "study")
            solver_path = os.path.join(temp_dir, "fake_su2.sh")

            with open(gene_path, "w", encoding="utf-8") as handle:
                json.dump(get_example_gene(), handle, indent=2, ensure_ascii=False)

            with open(solver_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "#!/bin/sh\n"
                    "cat > history.csv <<'EOF'\n"
                    "\"ITER\",\"DRAG\",\"FORCE_X\",\"Cauchy[CD]\"\n"
                    "1,0.0288,-0.0288,8.0e-05\n"
                    "2,0.0282,-0.0282,4.0e-06\n"
                    "3,0.0281,-0.0281,2.0e-06\n"
                    "EOF\n"
                    "cat <<'EOF'\n"
                    "All convergence criteria satisfied.\n"
                    "+-----------------------------------------------------------------------+\n"
                    "|      Convergence Field     |     Value    |   Criterion  |  Converged |\n"
                    "+-----------------------------------------------------------------------+\n"
                    "|                  Cauchy[CD]|       2.0e-06|       < 3e-06|         Yes|\n"
                    "+-----------------------------------------------------------------------+\n"
                    "EOF\n"
                )
            os.chmod(solver_path, 0o755)

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "run_su2_mesh_study.py"),
                    "--gene",
                    gene_path,
                    "--out",
                    output_dir,
                    "--profile",
                    "coarse",
                    "--solver-cmd",
                    solver_path,
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("SU2 mesh study 執行完成", proc.stdout)

            summary_json = os.path.join(output_dir, "mesh_study_summary.json")
            summary_md = os.path.join(output_dir, "mesh_study_summary.md")
            self.assertTrue(os.path.exists(summary_json))
            self.assertTrue(os.path.exists(summary_md))

            with open(summary_json, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertEqual(len(payload["Profiles"]), 1)
            self.assertEqual(payload["Profiles"][0]["Profile"], "coarse")
            self.assertTrue(payload["Profiles"][0]["Converged"])
            self.assertEqual(payload["Profiles"][0]["ConvergenceSource"], "stdout_table")
            self.assertEqual(payload["Profiles"][0]["TerminationReason"], "completed")
            self.assertGreater(payload["Profiles"][0]["Nodes"], 0)
            self.assertGreater(payload["Profiles"][0]["VolumeElements"], 0)


if __name__ == "__main__":
    unittest.main()
