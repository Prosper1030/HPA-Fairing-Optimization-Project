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
sys.path.insert(0, SCRIPTS_ROOT)

from analysis import get_example_gene
import run_su2_mesh_study


GMSH_AVAILABLE = importlib.util.find_spec("gmsh") is not None


class TestRepresentativeSelection(unittest.TestCase):
    def test_select_representative_ranked_cases_prefers_diverse_tags(self):
        ranked_cases = [
            {"Rank": 1, "CaseName": "best", "GeneFile": "/tmp/best.json", "RepresentativeTags": ["mid_pack"]},
            {"Rank": 2, "CaseName": "slender", "GeneFile": "/tmp/slender.json", "RepresentativeTags": ["slender"]},
            {"Rank": 3, "CaseName": "aft", "GeneFile": "/tmp/aft.json", "RepresentativeTags": ["peak_aft"]},
            {"Rank": 4, "CaseName": "aggressive", "GeneFile": "/tmp/aggr.json", "RepresentativeTags": ["tail_aggressive"]},
            {"Rank": 5, "CaseName": "fat", "GeneFile": "/tmp/fat.json", "RepresentativeTags": ["short_fat"]},
        ]

        selected = run_su2_mesh_study._select_representative_ranked_cases(ranked_cases, limit=4)

        self.assertEqual([entry["CaseName"] for entry in selected], ["slender", "fat", "aft", "aggressive"])
        self.assertEqual(selected[0]["RepresentativeSelectionReason"], "representative_tag:slender")
        self.assertEqual(selected[3]["RepresentativeSelectionReason"], "representative_tag:tail_aggressive")

    def test_load_batch_summary_candidates_can_use_representative_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_paths = {}
            for name in ("best", "slender", "aft", "aggressive"):
                gene_path = os.path.join(temp_dir, f"{name}.json")
                with open(gene_path, "w", encoding="utf-8") as handle:
                    json.dump(get_example_gene(), handle, indent=2, ensure_ascii=False)
                gene_paths[name] = gene_path

            batch_summary_path = os.path.join(temp_dir, "batch_summary.json")
            with open(batch_summary_path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "RankedCases": [
                            {"Rank": 1, "CaseName": "best", "GeneFile": gene_paths["best"], "RepresentativeTags": ["mid_pack"], "Drag": 1.0, "Cd": 0.10},
                            {"Rank": 2, "CaseName": "slender", "GeneFile": gene_paths["slender"], "RepresentativeTags": ["slender"], "Drag": 1.1, "Cd": 0.11},
                            {"Rank": 3, "CaseName": "aft", "GeneFile": gene_paths["aft"], "RepresentativeTags": ["peak_aft"], "Drag": 1.2, "Cd": 0.12},
                            {"Rank": 4, "CaseName": "aggressive", "GeneFile": gene_paths["aggressive"], "RepresentativeTags": ["tail_aggressive"], "Drag": 1.3, "Cd": 0.13},
                        ]
                    },
                    handle,
                    indent=2,
                    ensure_ascii=False,
                )

            candidates = run_su2_mesh_study._load_batch_summary_candidates(
                batch_summary_path,
                top=None,
                representative_study=True,
                representative_limit=3,
            )

            self.assertEqual([entry["name"] for entry in candidates], ["slender", "aft", "aggressive"])
            self.assertEqual(candidates[0]["Notes"]["representative_selection_reason"], "representative_tag:slender")

    def test_build_study_summary_tracks_selection_coverage(self):
        cases = [
            {
                "SourceCaseName": "slender_case",
                "RepresentativeTags": ["slender"],
                "RepresentativeSelectionReason": "representative_tag:slender",
                "ReferenceAssessment": {"ReferenceReady": True, "ReferenceStatus": "ReferenceReady", "FineToFinerDeltaCdPercent": 1.0},
            },
            {
                "SourceCaseName": "aft_case",
                "RepresentativeTags": ["peak_aft", "tail_aggressive"],
                "RepresentativeSelectionReason": "representative_tag:peak_aft",
                "ReferenceAssessment": {"ReferenceReady": False, "ReferenceStatus": "NotReferenceReady", "FineToFinerDeltaCdPercent": None},
            },
        ]

        summary = run_su2_mesh_study._build_study_summary(
            cases=cases,
            preset="hpa",
            flow_path="/tmp/flow.json",
            solver_command="SU2_CFD",
            selected_profiles=["fine", "finer"],
        )

        self.assertEqual(summary["ReferenceReadyCaseCount"], 1)
        self.assertEqual(summary["SelectionCoverage"]["TagCounts"]["slender"], 1)
        self.assertEqual(summary["SelectionCoverage"]["TagCounts"]["peak_aft"], 1)
        self.assertEqual(summary["SelectionCoverage"]["SelectionReasonCounts"]["representative_tag:slender"], 1)
        self.assertIn("short_fat", summary["SelectionCoverage"]["MissingTags"])


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

            self.assertEqual(payload["CaseCount"], 1)
            self.assertEqual(payload["ReferenceReadyCaseCount"], 0)
            self.assertEqual(len(payload["Profiles"]), 1)
            self.assertEqual(payload["Profiles"][0]["Profile"], "coarse")
            self.assertTrue(payload["Profiles"][0]["Converged"])
            self.assertEqual(payload["Profiles"][0]["ConvergenceSource"], "stdout_table")
            self.assertEqual(payload["Profiles"][0]["TerminationReason"], "completed")
            self.assertGreater(payload["Profiles"][0]["Nodes"], 0)
            self.assertGreater(payload["Profiles"][0]["VolumeElements"], 0)
            self.assertEqual(payload["ReferenceAssessment"]["ReferenceStatus"], "NotReferenceReady")

    def test_cli_runs_multi_case_mesh_study_and_marks_reference_ready(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_a_path = os.path.join(temp_dir, "gene_a.json")
            gene_b_path = os.path.join(temp_dir, "gene_b.json")
            output_dir = os.path.join(temp_dir, "study")
            solver_path = os.path.join(temp_dir, "fake_su2.sh")

            gene_a = get_example_gene()
            gene_b = dict(get_example_gene())
            gene_b["L"] = float(gene_b["L"]) * 1.03

            with open(gene_a_path, "w", encoding="utf-8") as handle:
                json.dump(gene_a, handle, indent=2, ensure_ascii=False)
            with open(gene_b_path, "w", encoding="utf-8") as handle:
                json.dump(gene_b, handle, indent=2, ensure_ascii=False)

            with open(solver_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "#!/bin/sh\n"
                    "cat > history.csv <<'EOF'\n"
                    "\"ITER\",\"DRAG\",\"FORCE_X\",\"Cauchy[CD]\"\n"
                    "1,0.0288,-0.0288,8.0e-05\n"
                    "2,0.0282,-0.0282,4.0e-06\n"
                    "3,0.0281,-0.0281,2.0e-06\n"
                    "4,0.0281,-0.0281,1.5e-06\n"
                    "5,0.0281,-0.0281,1.1e-06\n"
                    "6,0.0281,-0.0281,1.0e-06\n"
                    "EOF\n"
                    "cat <<'EOF'\n"
                    "All convergence criteria satisfied.\n"
                    "+-----------------------------------------------------------------------+\n"
                    "|      Convergence Field     |     Value    |   Criterion  |  Converged |\n"
                    "+-----------------------------------------------------------------------+\n"
                    "|                  Cauchy[CD]|       1.0e-06|       < 2e-06|         Yes|\n"
                    "+-----------------------------------------------------------------------+\n"
                    "EOF\n"
                )
            os.chmod(solver_path, 0o755)

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "run_su2_mesh_study.py"),
                    "--gene",
                    gene_a_path,
                    "--gene",
                    gene_b_path,
                    "--out",
                    output_dir,
                    "--profile",
                    "fine",
                    "--profile",
                    "finer",
                    "--solver-cmd",
                    solver_path,
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("Cases: 2", proc.stdout)
            self.assertIn("ReferenceReadyCases: 2", proc.stdout)

            summary_json = os.path.join(output_dir, "mesh_study_summary.json")
            with open(summary_json, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertEqual(payload["CaseCount"], 2)
            self.assertEqual(payload["ReferenceReadyCaseCount"], 2)
            self.assertEqual(payload["NotReferenceReadyCaseCount"], 0)
            self.assertEqual(payload["RequestedProfiles"], ["fine", "finer"])
            self.assertEqual(len(payload["Cases"]), 2)
            for case in payload["Cases"]:
                self.assertEqual(case["ReferenceAssessment"]["ReferenceStatus"], "ReferenceReady")
                self.assertTrue(case["ReferenceAssessment"]["ReferenceReady"])
                self.assertEqual(len(case["Profiles"]), 2)
                self.assertEqual(case["Profiles"][0]["Profile"], "fine")
                self.assertEqual(case["Profiles"][1]["Profile"], "finer")
                self.assertAlmostEqual(case["ReferenceAssessment"]["FineToFinerDeltaCdPercent"], 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
