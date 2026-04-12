"""Quick smoke test for the persistent GA process pool worker path."""

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(project_root, "scripts"))

from run_ga import call_worker


GENE = {
    "L": 2.5,
    "W_max": 0.60,
    "H_top_max": 0.95,
    "H_bot_max": 0.35,
    "N1": 0.5,
    "N2_top": 0.7,
    "N2_bot": 0.8,
    "X_max_pos": 0.25,
    "X_offset": 0.7,
    "M_top": 2.5,
    "N_top": 2.5,
    "M_bot": 2.5,
    "N_bot": 2.5,
    "tail_rise": 0.10,
    "blend_start": 0.75,
    "blend_power": 2.0,
    "w0": 0.25,
    "w1": 0.35,
    "w2": 0.30,
    "w3": 0.10,
}


def main():
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(call_worker, GENE, f"pool_{i}", 0.1) for i in range(2)]
        for future in as_completed(futures):
            print(future.result())


if __name__ == "__main__":
    main()
