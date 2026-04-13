"""
Benchmark the fast drag proxy against the current OpenVSP evaluator.

This is intentionally an experimental script:
- it samples feasible fairing genes,
- compares proxy scores with OpenVSP scores,
- reports correlation and rough top-k agreement,
- highlights the wall-time savings of dropping VSP from the inner loop.
"""

import argparse
import os
import sys
import time

import numpy as np
from scipy.stats import kendalltau, pearsonr, spearmanr

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, os.path.join(project_root, 'scripts'))

from optimization.hpa_asymmetric_optimizer import HPA_Optimizer, CST_Modeler, ConstraintChecker
from run_one_case import evaluate_gene


def sample_feasible_genes(sample_count: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    bounds = HPA_Optimizer.GENE_BOUNDS
    keys = list(bounds.keys())
    lower = np.array([bounds[k][0] for k in keys], dtype=float)
    upper = np.array([bounds[k][1] for k in keys], dtype=float)

    genes = []
    trials = 0
    max_trials = sample_count * 200

    while len(genes) < sample_count and trials < max_trials:
        trials += 1
        arr = lower + rng.random(len(keys)) * (upper - lower)
        gene = {k: float(arr[i]) for i, k in enumerate(keys)}
        curves = CST_Modeler.generate_asymmetric_fairing(gene)
        passed, _ = ConstraintChecker.check_all_constraints(gene, curves)
        if passed:
            genes.append(gene)

    if len(genes) < sample_count:
        raise RuntimeError(f"只取到 {len(genes)} 個可行樣本，少於要求的 {sample_count}")

    return genes


def top_k_overlap(proxy_scores: list[float], vsp_scores: list[float], k: int) -> float:
    proxy_top = set(np.argsort(proxy_scores)[:k].tolist())
    vsp_top = set(np.argsort(vsp_scores)[:k].tolist())
    return len(proxy_top & vsp_top) / max(k, 1)


def main():
    parser = argparse.ArgumentParser(description="Compare fast proxy ranking against OpenVSP.")
    parser.add_argument('--samples', type=int, default=6, help='可行樣本數')
    parser.add_argument('--seed', type=int, default=42, help='隨機種子')
    parser.add_argument('--penalty', type=float, default=0.1, help='面積懲罰因子')
    parser.add_argument('--skip-vsp', action='store_true', help='只量 proxy 速度，不跑 OpenVSP 對照')
    args = parser.parse_args()

    genes = sample_feasible_genes(args.samples, args.seed)
    proxy_scores = []
    proxy_times = []
    vsp_scores = []
    vsp_times = []

    print(f"抽樣完成: {len(genes)} 個可行設計")

    for idx, gene in enumerate(genes):
        name = f"bench_{idx:03d}"

        t0 = time.perf_counter()
        proxy_score = evaluate_gene(gene, name, args.penalty, analysis_mode='proxy')
        proxy_times.append(time.perf_counter() - t0)
        proxy_scores.append(proxy_score)

        print(f"[{idx + 1}/{len(genes)}] proxy={proxy_score:.6f}", flush=True)

        if not args.skip_vsp:
            t1 = time.perf_counter()
            vsp_score = evaluate_gene(gene, name, args.penalty, analysis_mode='openvsp')
            vsp_times.append(time.perf_counter() - t1)
            vsp_scores.append(vsp_score)
            print(f"             vsp={vsp_score:.6f}", flush=True)

    print("\n=== Speed ===")
    print(f"proxy avg: {np.mean(proxy_times):.4f}s")
    if not args.skip_vsp:
        print(f"vsp avg:   {np.mean(vsp_times):.4f}s")
        print(f"speedup:   {np.mean(vsp_times) / max(np.mean(proxy_times), 1e-9):.1f}x")

    if args.skip_vsp:
        return

    print("\n=== Rank Quality ===")
    pearson_val = pearsonr(proxy_scores, vsp_scores)[0]
    spearman_val = spearmanr(proxy_scores, vsp_scores)[0]
    kendall_val = kendalltau(proxy_scores, vsp_scores)[0]
    print(f"pearson : {pearson_val:.4f}")
    print(f"spearman: {spearman_val:.4f}")
    print(f"kendall : {kendall_val:.4f}")

    top_k = min(3, len(proxy_scores))
    overlap = top_k_overlap(proxy_scores, vsp_scores, top_k)
    print(f"top-{top_k} overlap: {overlap:.2f}")


if __name__ == "__main__":
    main()
