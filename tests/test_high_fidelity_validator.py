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

from analysis import (
    get_example_gene,
    prepare_shortlist_validation_package,
    run_prepared_su2_case,
    run_shortlist_su2_cases,
)


class TestHighFidelityValidator(unittest.TestCase):
    def setUp(self):
        self.example_gene = get_example_gene()

    def test_prepare_shortlist_validation_package_creates_su2_bundle(self):
        partial_gene = {
            "L": 2.45,
            "W_max": 0.57,
            "X_max_pos": 0.38,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [
                    {"name": "alpha", "gene": self.example_gene},
                    {"name": "beta", "gene": partial_gene},
                ],
                output_dir=temp_dir,
                fill_missing_from_example=True,
            )

            self.assertEqual(manifest["Status"], "prepared")
            self.assertEqual(manifest["CaseCount"], 2)
            self.assertTrue(os.path.exists(manifest["ManifestFiles"]["json"]))
            self.assertTrue(os.path.exists(manifest["ManifestFiles"]["markdown"]))
            self.assertTrue(os.path.exists(manifest["ShortlistReportFiles"]["json"]))
            self.assertTrue(os.path.exists(manifest["ShortlistReportFiles"]["markdown"]))
            self.assertTrue(os.path.exists(manifest["RunScript"]))

            with open(manifest["ManifestFiles"]["json"], "r", encoding="utf-8") as handle:
                saved_manifest = json.load(handle)

            self.assertIn("ManifestFiles", saved_manifest)
            self.assertIn("ShortlistReportFiles", saved_manifest)
            self.assertEqual(saved_manifest["CaseCount"], 2)

            case_entry = saved_manifest["Cases"][0]
            case_dir = case_entry["CaseDir"]
            self.assertTrue(os.path.exists(os.path.join(case_dir, "gene.json")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "summary.json")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "summary.md")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "fairing_geometry.csv")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "su2_case.cfg")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "su2_runtime.cfg")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "README.md")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "PUT_MESH_HERE.txt")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "geometry_preview.html")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "fairing_surface.obj")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "fairing_surface.stl")))
            with open(os.path.join(case_dir, "geometry_preview.html"), "r", encoding="utf-8") as handle:
                preview_html = handle.read()
            self.assertIn('"side": {"yaw": -1.5707963267948966, "pitch": 0.0, "roll": 0.0, "zoom": 0.82}', preview_html)
            self.assertIn('"top": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0, "zoom": 0.82}', preview_html)
            self.assertIn('"front": {"yaw": -1.5707963267948966, "pitch": -1.5707963267948966, "roll": 0.0, "zoom": 0.82}', preview_html)

            with open(os.path.join(case_dir, "su2_case.cfg"), "r", encoding="utf-8") as handle:
                config_text = handle.read()
            self.assertIn("SOLVER= INC_NAVIER_STOKES", config_text)
            self.assertIn("CONV_NUM_METHOD_FLOW= FDS", config_text)
            self.assertIn("LINEAR_SOLVER= FGMRES", config_text)
            self.assertIn("LINEAR_SOLVER_PREC= ILU", config_text)
            self.assertIn("MARKER_FAR= ( farfield )", config_text)

            beta_entry = next(entry for entry in saved_manifest["Cases"] if entry["CaseName"] == "beta")
            self.assertIn("H_top_max", beta_entry["FilledFields"])
            self.assertTrue(beta_entry["Recommendations"])

    def test_cli_can_prepare_shortlist_from_batch_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_dir = os.path.join(temp_dir, "genes")
            output_dir = os.path.join(temp_dir, "su2_shortlist")
            os.makedirs(gene_dir, exist_ok=True)

            gene_a_path = os.path.join(gene_dir, "gene_a.json")
            gene_b_path = os.path.join(gene_dir, "gene_b.json")
            with open(gene_a_path, "w", encoding="utf-8") as handle:
                json.dump(self.example_gene, handle)
            with open(gene_b_path, "w", encoding="utf-8") as handle:
                json.dump({"L": 2.4, "W_max": 0.56, "X_max_pos": 0.41}, handle)

            batch_summary_path = os.path.join(temp_dir, "batch_summary.json")
            with open(batch_summary_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "RankedCases": [
                            {"Rank": 1, "CaseName": "gene_a", "GeneFile": gene_a_path, "Drag": 1.0, "Cd": 0.12},
                            {"Rank": 2, "CaseName": "gene_b", "GeneFile": gene_b_path, "Drag": 1.1, "Cd": 0.13},
                        ]
                    },
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "prepare_su2_shortlist.py"),
                    "--batch-summary",
                    batch_summary_path,
                    "--top",
                    "1",
                    "--out",
                    output_dir,
                    "--fill-missing-from-example",
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("SU2 shortlist 工作包準備完成", proc.stdout)
            self.assertIn("geometry_preview.html:", proc.stdout)
            self.assertIn("fairing_surface.obj:", proc.stdout)
            self.assertIn("fairing_surface.stl:", proc.stdout)
            self.assertTrue(os.path.exists(os.path.join(output_dir, "validation_manifest.json")))
            self.assertTrue(os.path.exists(os.path.join(output_dir, "shortlist_report.json")))
            self.assertTrue(os.path.exists(os.path.join(output_dir, "run_all_su2_cases.sh")))

            with open(os.path.join(output_dir, "validation_manifest.json"), "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertEqual(payload["CaseCount"], 1)
            self.assertEqual(payload["Cases"][0]["CaseName"], "gene_a")
            self.assertTrue(os.path.exists(os.path.join(payload["Cases"][0]["CaseDir"], "geometry_preview.html")))

    def test_run_prepared_su2_case_parses_history_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "alpha", "gene": self.example_gene}],
                output_dir=temp_dir,
            )
            case_dir = manifest["Cases"][0]["CaseDir"]
            mesh_path = os.path.join(case_dir, "fairing_mesh.su2")
            with open(mesh_path, "w", encoding="utf-8") as handle:
                handle.write("NDIME= 3\nNELEM= 0\nNPOIN= 0\nNMARK= 0\n")

            solver_path = os.path.join(temp_dir, "fake_su2.sh")
            with open(solver_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "#!/bin/sh\n"
                    "cat > history.csv <<'EOF'\n"
                    "\"ITER\",\"DRAG\",\"FORCE_X\",\"Cauchy[CD]\"\n"
                    "1,0.031000,-0.031000,2.0e-04\n"
                    "EOF\n"
                    "cat > stdout.log <<'EOF'\n"
                    "Maximum number of iterations reached (ITER = 1) before convergence.\n"
                    "+-----------------------------------------------------------------------+\n"
                    "|      Convergence Field     |     Value    |   Criterion  |  Converged |\n"
                    "+-----------------------------------------------------------------------+\n"
                    "|                  Cauchy[CD]|       0.0002|       < 1e-05|          No|\n"
                    "+-----------------------------------------------------------------------+\n"
                    "EOF\n"
                    "cat stdout.log\n"
                )
            os.chmod(solver_path, 0o755)

            result = run_prepared_su2_case(case_dir, solver_command=solver_path)

            self.assertEqual(result["Status"], "completed")
            self.assertAlmostEqual(result["Cd"], 0.031, places=6)
            self.assertAlmostEqual(result["Drag"], 0.802221875, places=6)
            self.assertFalse(result["Converged"])
            self.assertFalse(result["BuiltInConverged"])
            self.assertFalse(result["EngineeringStable"])
            self.assertEqual(result["ConvergenceSource"], "stdout_table")
            self.assertEqual(result["TerminationReason"], "max_iterations_before_convergence")
            self.assertAlmostEqual(result["LastCauchyCd"], 2.0e-4, places=9)
            self.assertTrue(os.path.exists(os.path.join(case_dir, "su2_result.json")))
            self.assertTrue(os.path.exists(os.path.join(case_dir, "su2_result.md")))

    def test_run_prepared_su2_case_uses_configured_cauchy_criterion_when_stdout_is_silent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "alpha", "gene": self.example_gene}],
                output_dir=temp_dir,
            )
            case_dir = manifest["Cases"][0]["CaseDir"]
            mesh_path = os.path.join(case_dir, "fairing_mesh.su2")
            with open(mesh_path, "w", encoding="utf-8") as handle:
                handle.write("NDIME= 3\nNELEM= 0\nNPOIN= 0\nNMARK= 0\n")

            history_path = os.path.join(case_dir, "history.csv")
            with open(history_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "\"ITER\",\"DRAG\",\"FORCE_X\",\"Cauchy[CD]\"\n"
                    "45,0.028100,-0.028100,8.0e-07\n"
                )

            solver_path = os.path.join(temp_dir, "fake_su2_silent.sh")
            with open(solver_path, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\nexit 0\n")
            os.chmod(solver_path, 0o755)

            result = run_prepared_su2_case(case_dir, solver_command=solver_path)

            self.assertTrue(result["Converged"])
            self.assertTrue(result["BuiltInConverged"])
            self.assertTrue(result["EngineeringStable"])
            self.assertEqual(result["ConvergenceSource"], "history_vs_config")
            self.assertAlmostEqual(result["ConvergenceCriterion"], 1.0e-06, places=12)

    def test_run_prepared_su2_case_parses_real_su2_uppercase_history_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "alpha", "gene": self.example_gene}],
                output_dir=temp_dir,
            )
            case_dir = manifest["Cases"][0]["CaseDir"]
            mesh_path = os.path.join(case_dir, "fairing_mesh.su2")
            with open(mesh_path, "w", encoding="utf-8") as handle:
                handle.write("NDIME= 3\nNELEM= 0\nNPOIN= 0\nNMARK= 0\n")

            history_path = os.path.join(case_dir, "history.csv")
            with open(history_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "\"Time_Iter\",\"Outer_Iter\",\"Inner_Iter\",     \"rms[P]\"     ,     \"rms[U]\"     ,     \"rms[V]\"     ,    \"RefForce\"    ,       \"CD\"       ,       \"CL\"       ,       \"CSF\"      ,       \"CMx\"      ,       \"CMy\"      ,       \"CMz\"      ,       \"CFx\"      ,       \"CFy\"      ,       \"CFz\"      ,      \"CEff\"      \n"
                    "0,0,49,-4.024284,-1.764546,-2.547058,25.878125,0.172186,0.753189,0,0,0,0.402861,0.172186,0.753189,0,4.374266\n"
                )

            solver_path = os.path.join(temp_dir, "fake_su2_uppercase.sh")
            with open(solver_path, "w", encoding="utf-8") as handle:
                handle.write("#!/bin/sh\nexit 0\n")
            os.chmod(solver_path, 0o755)

            result = run_prepared_su2_case(case_dir, solver_command=solver_path)

            self.assertEqual(result["Status"], "completed")
            self.assertAlmostEqual(result["Cd"], 0.172186, places=6)
            self.assertAlmostEqual(result["ForceX"], 0.172186, places=6)
            self.assertAlmostEqual(result["Drag"], 4.45585083125, places=6)
            self.assertAlmostEqual(result["ResidualPressure"], -4.024284, places=6)

    def test_run_prepared_su2_case_accepts_solver_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="su2 solver test ") as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "alpha", "gene": self.example_gene}],
                output_dir=temp_dir,
            )
            case_dir = manifest["Cases"][0]["CaseDir"]
            mesh_path = os.path.join(case_dir, "fairing_mesh.su2")
            with open(mesh_path, "w", encoding="utf-8") as handle:
                handle.write("NDIME= 3\nNELEM= 0\nNPOIN= 0\nNMARK= 0\n")

            solver_path = os.path.join(temp_dir, "fake solver.sh")
            with open(solver_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "#!/bin/sh\n"
                    "cat > history.csv <<'EOF'\n"
                    "\"ITER\",\"DRAG\"\n"
                    "1,0.030000\n"
                    "EOF\n"
                )
            os.chmod(solver_path, 0o755)

            result = run_prepared_su2_case(case_dir, solver_command=solver_path)

            self.assertEqual(result["Status"], "completed")
            self.assertTrue(result["SolverCommand"].endswith("fake solver.sh su2_runtime.cfg"))

    def test_run_prepared_su2_case_dry_run_does_not_require_installed_solver(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "alpha", "gene": self.example_gene}],
                output_dir=temp_dir,
            )
            case_dir = manifest["Cases"][0]["CaseDir"]
            with open(os.path.join(case_dir, "fairing_mesh.su2"), "w", encoding="utf-8") as handle:
                handle.write("NDIME= 3\nNELEM= 0\nNPOIN= 0\nNMARK= 0\n")

            result = run_prepared_su2_case(case_dir, solver_command="SU2_CFD", dry_run=True)

            self.assertEqual(result["Status"], "dry_run")
            self.assertIn("SU2_CFD", result["SolverCommand"])
            self.assertTrue(result["RuntimeConfig"].endswith("su2_runtime.cfg"))

    def test_run_shortlist_su2_cases_writes_root_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "alpha", "gene": self.example_gene}],
                output_dir=temp_dir,
            )
            case_dir = manifest["Cases"][0]["CaseDir"]
            mesh_path = os.path.join(case_dir, "fairing_mesh.su2")
            with open(mesh_path, "w", encoding="utf-8") as handle:
                handle.write("NDIME= 3\nNELEM= 0\nNPOIN= 0\nNMARK= 0\n")

            solver_path = os.path.join(temp_dir, "fake_su2.sh")
            with open(solver_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "#!/bin/sh\n"
                    "cat > history.csv <<'EOF'\n"
                    "\"ITER\",\"DRAG\"\n"
                    "1,0.029000\n"
                    "EOF\n"
                )
            os.chmod(solver_path, 0o755)

            summary = run_shortlist_su2_cases(temp_dir, solver_command=solver_path)

            self.assertEqual(summary["SuccessfulCases"], 1)
            self.assertTrue(os.path.exists(summary["SummaryFiles"]["json"]))
            self.assertTrue(os.path.exists(summary["SummaryFiles"]["markdown"]))
            self.assertIn("Converged", summary["Cases"][0])

    def test_run_shortlist_su2_cases_writes_summary_on_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prepare_shortlist_validation_package(
                [{"name": "alpha", "gene": self.example_gene}],
                output_dir=temp_dir,
            )

            with self.assertRaises(RuntimeError):
                run_shortlist_su2_cases(temp_dir, solver_command="missing_su2_binary")

            self.assertTrue(os.path.exists(os.path.join(temp_dir, "su2_run_summary.json")))
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "su2_run_summary.md")))

    def test_cli_can_run_shortlist_with_fake_solver(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "alpha", "gene": self.example_gene}],
                output_dir=temp_dir,
            )
            case_dir = manifest["Cases"][0]["CaseDir"]
            with open(os.path.join(case_dir, "fairing_mesh.su2"), "w", encoding="utf-8") as handle:
                handle.write("NDIME= 3\nNELEM= 0\nNPOIN= 0\nNMARK= 0\n")

            solver_path = os.path.join(temp_dir, "fake_su2.sh")
            with open(solver_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "#!/bin/sh\n"
                    "cat > history.csv <<'EOF'\n"
                    "\"ITER\",\"DRAG\"\n"
                    "1,0.028500\n"
                    "EOF\n"
                )
            os.chmod(solver_path, 0o755)

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "run_su2_shortlist.py"),
                    "--shortlist-dir",
                    temp_dir,
                    "--solver-cmd",
                    solver_path,
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("SU2 shortlist 執行完成", proc.stdout)
            self.assertTrue(os.path.exists(os.path.join(temp_dir, "su2_run_summary.json")))


if __name__ == "__main__":
    unittest.main()
