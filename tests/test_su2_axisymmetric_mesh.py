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

from analysis import get_example_gene, prepare_shortlist_validation_package


TRIANGLE_AVAILABLE = importlib.util.find_spec("triangle") is not None


@unittest.skipUnless(TRIANGLE_AVAILABLE, "triangle not installed")
class TestSU2AxisymmetricMesh(unittest.TestCase):
    def setUp(self):
        self.example_gene = get_example_gene()

    def test_prepare_shortlist_can_generate_axisymmetric_mesh(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "axis_case", "gene": self.example_gene}],
                output_dir=temp_dir,
                mesh_mode="axisymmetric_2d",
            )

            self.assertEqual(manifest["MeshMode"], "axisymmetric_2d")
            case_dir = manifest["Cases"][0]["CaseDir"]
            mesh_path = os.path.join(case_dir, "fairing_mesh.su2")
            metadata_path = os.path.join(case_dir, "mesh_metadata.json")
            cfg_path = os.path.join(case_dir, "su2_case.cfg")

            self.assertTrue(os.path.exists(mesh_path))
            self.assertTrue(os.path.exists(metadata_path))
            self.assertTrue(os.path.exists(cfg_path))

            with open(mesh_path, "r", encoding="utf-8") as handle:
                mesh_text = handle.read()
            self.assertIn("NDIME= 2", mesh_text)
            self.assertIn("MARKER_TAG= axis", mesh_text)
            self.assertIn("MARKER_TAG= fairing", mesh_text)
            self.assertIn("MARKER_TAG= farfield", mesh_text)

            with open(cfg_path, "r", encoding="utf-8") as handle:
                cfg_text = handle.read()
            self.assertIn("AXISYMMETRIC= YES", cfg_text)
            self.assertIn("MARKER_SYM= ( axis )", cfg_text)
            self.assertIn("INNER_ITER= 400", cfg_text)
            self.assertIn("CONV_CAUCHY_ELEMS= 25", cfg_text)

            with open(metadata_path, "r", encoding="utf-8") as handle:
                metadata = json.load(handle)
            self.assertEqual(metadata["MeshMode"], "axisymmetric_2d")
            self.assertGreater(metadata["Nodes"], 0)
            self.assertGreater(metadata["Elements"], 0)
            self.assertGreater(metadata["InteriorSeedPoints"], 0)
            self.assertGreaterEqual(metadata["BodyStations"], 120)

    def test_prepare_shortlist_cli_supports_axisymmetric_mesh_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            gene_path = os.path.join(temp_dir, "gene.json")
            output_dir = os.path.join(temp_dir, "shortlist")
            with open(gene_path, "w", encoding="utf-8") as handle:
                json.dump(self.example_gene, handle)

            proc = subprocess.run(
                [
                    sys.executable,
                    os.path.join(SCRIPTS_ROOT, "prepare_su2_shortlist.py"),
                    "--gene",
                    gene_path,
                    "--out",
                    output_dir,
                    "--mesh-mode",
                    "axisymmetric_2d",
                ],
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
            )

            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertIn("MeshMode: axisymmetric_2d", proc.stdout)

            manifest_path = os.path.join(output_dir, "validation_manifest.json")
            self.assertTrue(os.path.exists(manifest_path))
            with open(manifest_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["MeshMode"], "axisymmetric_2d")
            mesh_path = os.path.join(payload["Cases"][0]["CaseDir"], "fairing_mesh.su2")
            self.assertTrue(os.path.exists(mesh_path))


if __name__ == "__main__":
    unittest.main()
