import importlib.util
import json
import os
import sys
import tempfile
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")

sys.path.insert(0, SRC_ROOT)

from analysis import get_example_gene, prepare_shortlist_validation_package


GMSH_AVAILABLE = importlib.util.find_spec("gmsh") is not None


@unittest.skipUnless(GMSH_AVAILABLE, "gmsh not installed")
class TestSU2Gmsh3DMesh(unittest.TestCase):
    def setUp(self):
        self.example_gene = get_example_gene()
        self.mesh_options = {
            "section_points": 16,
            "body_section_count": 12,
            "near_body_size_factor": 0.050,
            "farfield_size_factor": 0.25,
            "wake_size_factor": 0.080,
        }

    def test_prepare_shortlist_can_generate_gmsh_3d_mesh(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "gmsh_case", "gene": self.example_gene}],
                output_dir=temp_dir,
                mesh_mode="gmsh_3d",
                mesh_options=self.mesh_options,
            )

            self.assertEqual(manifest["MeshMode"], "gmsh_3d")
            case_dir = manifest["Cases"][0]["CaseDir"]
            mesh_path = os.path.join(case_dir, "fairing_mesh.su2")
            msh_path = os.path.join(case_dir, "fairing_mesh.msh")
            metadata_path = os.path.join(case_dir, "mesh_metadata.json")
            cfg_path = os.path.join(case_dir, "su2_case.cfg")

            self.assertTrue(os.path.exists(mesh_path))
            self.assertTrue(os.path.exists(msh_path))
            self.assertTrue(os.path.exists(metadata_path))
            self.assertTrue(os.path.exists(cfg_path))

            with open(mesh_path, "r", encoding="utf-8") as handle:
                mesh_text = handle.read()
            self.assertIn("NDIME= 3", mesh_text)
            self.assertIn("MARKER_TAG= fairing", mesh_text)
            self.assertIn("MARKER_TAG= farfield", mesh_text)

            with open(cfg_path, "r", encoding="utf-8") as handle:
                cfg_text = handle.read()
            self.assertIn("AXISYMMETRIC= NO", cfg_text)
            self.assertIn("CFL_ADAPT= YES", cfg_text)
            self.assertIn("LINEAR_SOLVER= FGMRES", cfg_text)
            self.assertNotIn("MARKER_SYM= ( axis )", cfg_text)

            with open(metadata_path, "r", encoding="utf-8") as handle:
                metadata = json.load(handle)
            self.assertEqual(metadata["MeshMode"], "gmsh_3d")
            self.assertGreater(metadata["Nodes"], 0)
            self.assertGreater(metadata["VolumeElements"], 0)
            self.assertGreater(metadata["FairingSurfaceCount"], 0)
            self.assertGreater(metadata["FarfieldSurfaceCount"], 0)

    def test_prepare_shortlist_can_generate_boundary_layer_mesh(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = prepare_shortlist_validation_package(
                [{"name": "gmsh_bl_case", "gene": self.example_gene}],
                output_dir=temp_dir,
                mesh_mode="gmsh_3d",
                mesh_options={
                    "section_points": 12,
                    "body_section_count": 10,
                    "near_body_size_factor": 0.055,
                    "farfield_size_factor": 0.26,
                    "wake_size_factor": 0.085,
                    "surface_mesh_size_factor": 0.024,
                    "use_boundary_layer_extrusion": True,
                    "boundary_layer_num_layers": 4,
                    "boundary_layer_total_thickness_factor": 0.008,
                },
            )

            case_dir = manifest["Cases"][0]["CaseDir"]
            metadata_path = os.path.join(case_dir, "mesh_metadata.json")
            with open(metadata_path, "r", encoding="utf-8") as handle:
                metadata = json.load(handle)

            self.assertTrue(metadata["BoundaryLayerInfo"]["Enabled"])
            self.assertGreater(metadata["BoundaryLayerInfo"]["BoundaryLayerVolumeCount"], 0)
            self.assertIn("13", metadata["VolumeElementTypeCounts"])
            self.assertGreater(metadata["VolumeElementTypeCounts"]["13"], 0)


if __name__ == "__main__":
    unittest.main()
