import json
import os
import shutil
import sys
import unittest

import numpy as np


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")

sys.path.insert(0, SRC_ROOT)

from optimization.hpa_asymmetric_optimizer import ProjectManager


class TestProjectManagerSerialization(unittest.TestCase):
    def test_save_best_gene_accepts_numpy_bool_analysis_fields(self):
        pm = ProjectManager(base_output_dir=os.path.join(PROJECT_ROOT, "output"))
        try:
            pm.save_best_gene(
                {"L": 2.5},
                1.23,
                4,
                analysis={
                    "AnalysisMode": "proxy",
                    "Valid": np.bool_(True),
                    "ConstraintReport": {
                        "enabled": np.bool_(True),
                    },
                },
            )

            with open(pm.best_gene_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertIs(payload["analysis"]["Valid"], True)
            self.assertIs(payload["analysis"]["ConstraintReport"]["enabled"], True)
        finally:
            shutil.rmtree(pm.run_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
