"""
HPA 整流罩 GA 優化運行腳本

使用方法：
    python scripts/run_ga.py --gen 50 --pop 20
    python scripts/run_ga.py --gen 50 --pop 20 --workers 10  # 10進程平行
    python scripts/run_ga.py --resume output/hpa_run_xxx       # 從 checkpoint 續跑
    python scripts/run_ga.py --config config/ga_config.json

架構說明：
    - 主程式：負責 GA 調度與 checkpoint 管理
    - run_one_case.py：提供單個設計的評估函式
    - 平行運算：使用常駐 ProcessPoolExecutor 重用 worker 進程
"""

import sys
import os
import json
import argparse
import pickle
import numpy as np
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from _bootstrap import ensure_src_path


project_root = os.fspath(ensure_src_path())

from analysis import prepare_shortlist_validation_package

# 導入優化器模組
from optimization.hpa_asymmetric_optimizer import (
    HPA_Optimizer, ProjectManager, CST_Modeler
)
from run_one_case import evaluate_gene

def load_config(config_path: str) -> dict:
    """載入配置檔案"""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_fluid_conditions(fluid_path: str) -> dict:
    """載入流體條件"""
    with open(fluid_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def plot_convergence(history: list, output_path: str):
    """繪製收斂曲線"""
    try:
        import matplotlib.pyplot as plt

        generations = [h['generation'] for h in history]
        best_fitness = [h['best_fitness'] for h in history]
        avg_fitness = [h['avg_fitness'] for h in history]

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(generations, best_fitness, 'b-', label='Best Fitness', linewidth=2)
        ax.plot(generations, avg_fitness, 'r--', label='Average Fitness', linewidth=1)

        ax.set_xlabel('Generation')
        ax.set_ylabel('Fitness (Drag, N)')
        ax.set_title('GA Optimization Convergence')
        ax.legend()
        ax.grid(True, alpha=0.3)

        # 設置 y 軸最大值（排除懲罰值）
        valid_best = [f for f in best_fitness if f < 1e5]
        if valid_best:
            ax.set_ylim(0, max(valid_best) * 1.2)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

        print(f"收斂曲線已保存: {output_path}")

    except ImportError:
        print("Warning: matplotlib 未安裝，跳過收斂曲線繪製")


def resolve_checkpoint_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_dir():
        return path / "checkpoint.pkl"
    return path


def load_checkpoint(path_str: str) -> dict:
    checkpoint_path = resolve_checkpoint_path(path_str)
    with open(checkpoint_path, "rb") as f:
        data = pickle.load(f)
    data["checkpoint_path"] = str(checkpoint_path)
    return data


def save_checkpoint(pm, callback, algorithm, convergence_history, best_so_far,
                    generations_without_improvement, total_generations):
    checkpoint = {
        "generation": callback.n_gen,
        "population_X": algorithm.pop.get("X"),
        "population_F": algorithm.pop.get("F"),
        "convergence_history": convergence_history,
        "best_so_far": best_so_far,
        "generations_without_improvement": generations_without_improvement,
        "numpy_random_state": np.random.get_state(),
        "run_dir": str(pm.run_dir),
        "total_generations": total_generations,
        "timestamp": datetime.now().isoformat(),
    }

    checkpoint_path = pm.run_dir / "checkpoint.pkl"
    temp_path = checkpoint_path.with_suffix(".tmp")
    with open(temp_path, "wb") as f:
        pickle.dump(checkpoint, f)
    temp_path.replace(checkpoint_path)


def build_su2_shortlist_candidates(pm, top_n: int):
    if top_n <= 0:
        raise ValueError("su2 shortlist top_n 必須大於 0")

    if not pm.candidate_scores_file.exists():
        return []

    entries = []
    with open(pm.candidate_scores_file, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if float(payload.get("score", 1e6)) >= 1e5:
                continue
            gene = payload.get("gene")
            if not isinstance(gene, dict):
                continue
            entries.append(payload)

    entries.sort(
        key=lambda item: (
            float(item["score"]),
            int(item.get("generation", 0)),
            int(item.get("individual", 0)),
        )
    )

    seen_genes = set()
    candidates = []
    keys = list(HPA_Optimizer.GENE_BOUNDS.keys())
    for entry in entries:
        gene = entry["gene"]
        gene_key = tuple(round(float(gene[key]), 8) for key in keys)
        if gene_key in seen_genes:
            continue
        seen_genes.add(gene_key)
        rank = len(candidates) + 1
        candidates.append(
            {
                "name": f"rank_{rank:02d}_{entry['name']}",
                "gene": gene,
                "Notes": {
                    "score": float(entry["score"]),
                    "generation": int(entry.get("generation", 0)),
                    "individual": int(entry.get("individual", 0)),
                    "analysis_mode": entry.get("analysis_mode"),
                    "selection_source": str(pm.candidate_scores_file),
                },
            }
        )
        if len(candidates) >= top_n:
            break

    return candidates


def prepare_ga_su2_shortlist(pm, *, top_n: int, flow_conditions: dict, output_dir: str | None = None):
    candidates = build_su2_shortlist_candidates(pm, top_n)
    if not candidates:
        pm.log("沒有可用的有效候選，跳過 SU2 shortlist 工作包")
        return None

    shortlist_dir = Path(output_dir) if output_dir else pm.run_dir / "su2_shortlist"
    manifest = prepare_shortlist_validation_package(
        candidates,
        output_dir=shortlist_dir,
        flow_conditions=flow_conditions,
        preset="hpa",
    )
    pm.log(f"SU2 shortlist 工作包已建立: {manifest['ManifestFiles']['json']}")
    return {
        "prepared": True,
        "top_n_requested": top_n,
        "case_count": manifest["CaseCount"],
        "output_dir": str(shortlist_dir),
        "manifest_json": manifest["ManifestFiles"]["json"],
        "manifest_markdown": manifest["ManifestFiles"]["markdown"],
        "shortlist_report_json": manifest["ShortlistReportFiles"]["json"],
        "shortlist_report_markdown": manifest["ShortlistReportFiles"]["markdown"],
        "run_script": manifest["RunScript"],
    }


def call_worker(
    gene_dict: dict,
    name: str,
    W_area_penalty: float,
    analysis_mode: str,
    flow_conditions: dict,
) -> float:
    """直接在常駐 worker 進程中評估單一個體。"""
    try:
        return float(
            evaluate_gene(
                gene_dict,
                name,
                W_area_penalty,
                analysis_mode=analysis_mode,
                flow_conditions=flow_conditions,
            )
        )
    except Exception as e:
        raise RuntimeError(f"{name}: Worker評估失敗 - {e}") from e


def evaluate_population_parallel(
    population,
    gen,
    gene_bounds,
    W_area_penalty,
    n_workers,
    pm,
    analysis_mode,
    flow_conditions,
    optimizer=None,
    executor=None,
):
    """
    評估整個族群

    Args:
        population: 族群基因陣列 (N x D)
        gen: 當前代數
        gene_bounds: 基因邊界字典
        W_area_penalty: 面積懲罰因子
        n_workers: worker 數量
        pm: ProjectManager
        optimizer: HPA_Optimizer 實例（用於單執行緒模式）

    Returns:
        fitness: 適應度陣列
    """
    keys = list(gene_bounds.keys())
    fitness = []

    if n_workers > 1 and optimizer is None and executor is not None:
        # 平行模式：使用常駐 ProcessPoolExecutor，避免每個個體重啟 Python
        tasks = []
        for i, gene_array in enumerate(population):
            gene_dict = {k: gene_array[j] for j, k in enumerate(keys)}
            name = f"gen{gen:03d}_ind{i:03d}"
            tasks.append((gene_dict, name, W_area_penalty, analysis_mode, flow_conditions))

        ordered_fitness = [1e6] * len(tasks)
        future_to_index = {
            executor.submit(call_worker, *task): index for index, task in enumerate(tasks)
        }

        for future in as_completed(future_to_index):
            index = future_to_index[future]
            gene_dict, _, _, _, _ = tasks[index]
            try:
                ordered_fitness[index] = future.result()
            except Exception as e:
                pm.log(str(e))
                ordered_fitness[index] = 1e6
            pm.record_candidate(gene_dict, ordered_fitness[index], gen, index, analysis_mode)

        fitness.extend(ordered_fitness)
    else:
        # 單執行緒模式：使用 HPA_Optimizer（穩定版）
        for i, gene_array in enumerate(population):
            gene_dict = {k: gene_array[j] for j, k in enumerate(keys)}
            f = optimizer.evaluate_individual(gene_array, gen, i)
            pm.record_candidate(gene_dict, f, gen, i, analysis_mode)
            fitness.append(f)

    return np.array(fitness)


def run_optimization(args):
    """運行 GA 優化"""

    checkpoint = load_checkpoint(args.resume) if args.resume else None

    # 載入配置
    config_path = args.config or os.path.join(project_root, 'config', 'ga_config.json')
    fluid_path = args.fluid or os.path.join(project_root, 'config', 'fluid_conditions.json')

    if os.path.exists(config_path):
        config = load_config(config_path)
        print(f"已載入配置: {config_path}")
    else:
        config = {}
        print("使用預設配置")

    if os.path.exists(fluid_path):
        fluid = load_fluid_conditions(fluid_path)
        print(f"已載入流體條件: {fluid_path}")
    else:
        fluid = {}
        print("使用預設流體條件")

    # 優先使用命令行參數
    n_gen = args.gen or (
        checkpoint.get('total_generations') if checkpoint else None
    ) or config.get('ga_settings', {}).get('n_generations', 50)
    pop_size = args.pop or config.get('ga_settings', {}).get('population_size', 20)
    seed = args.seed or config.get('ga_settings', {}).get('seed', 42)
    convergence_tol = args.tol or 10  # 預設10代不改善就停止

    start_generation = checkpoint.get('generation', 0) if checkpoint else 0
    resume_population_data = checkpoint.get('population_X') if checkpoint else None
    if resume_population_data is not None:
        pop_size = len(resume_population_data)
    if checkpoint and start_generation >= n_gen:
        print(f"Checkpoint 已經到第 {start_generation} 代，目標代數 {n_gen} 無需繼續。")
        return None

    # 平行運算設定（預設保留2核給系統）
    max_workers = max(1, os.cpu_count() - 2)
    n_workers = args.workers if args.workers else 1
    if n_workers > max_workers:
        n_workers = max_workers
        print(f"⚠️ Workers 調整為 {n_workers}（保留2核給系統）")

    # 讀取面積懲罰因子
    W_area_penalty = config.get('fitness', {}).get('W_area_penalty', 0.1)
    analysis_mode = args.analysis_mode or config.get('fitness', {}).get('analysis_mode', 'proxy')
    prepare_su2_shortlist = bool(getattr(args, 'prepare_su2_shortlist', False))
    su2_shortlist_top = int(getattr(args, 'su2_shortlist_top', 5) or 5)
    su2_shortlist_out = getattr(args, 'su2_shortlist_out', None)
    if su2_shortlist_top <= 0:
        raise ValueError("su2 shortlist top 必須大於 0")
    flow_block = fluid.get('flow_conditions', {})
    flow_conditions = {
        'velocity': flow_block.get('velocity', {}).get('value', 6.5),
        'rho': flow_block.get('density', {}).get('value', 1.225),
        'mu': flow_block.get('viscosity', {}).get('value', 1.7894e-5),
    }

    print(f"\n{'='*60}")
    print(f"HPA 整流罩 GA 優化（外包工頭模式）")
    print(f"{'='*60}")
    print(f"代數上限: {n_gen}")
    print(f"族群大小: {pop_size}")
    print(f"隨機種子: {seed}")
    print(f"收斂容忍度: {convergence_tol} 代不改善則停止")
    print(f"面積懲罰因子: {W_area_penalty} N/m²")
    print(f"評估模式: {analysis_mode}")
    print(f"適應度公式: Score = Drag + {W_area_penalty} × Swet")
    print(f"平行運算: {n_workers} 進程" + (f"（可用上限: {max_workers}）" if n_workers > 1 else ""))
    print(f"SU2 shortlist: {'ON' if prepare_su2_shortlist else 'OFF'}" + (f"（top {su2_shortlist_top}）" if prepare_su2_shortlist else ""))
    if checkpoint:
        print(f"續跑模式: 從第 {start_generation} 代繼續到第 {n_gen} 代")
    print(f"{'='*60}\n")

    # 檢查 pymoo
    try:
        from pymoo.core.problem import Problem
        from pymoo.algorithms.soo.nonconvex.ga import GA
        from pymoo.optimize import minimize
        from pymoo.operators.sampling.rnd import FloatRandomSampling
        from pymoo.operators.crossover.sbx import SBX
        from pymoo.operators.mutation.pm import PM
        from pymoo.core.callback import Callback
    except ImportError:
        print("錯誤: 需要安裝 pymoo")
        print("請執行: pip install pymoo")
        return None

    # 創建專案管理器
    pm = ProjectManager(
        base_output_dir="output",
        existing_run_dir=checkpoint.get('run_dir') if checkpoint else None,
    )
    if checkpoint:
        pm.log(f"從 checkpoint 續跑: {checkpoint['checkpoint_path']}")
    pm.log(f"開始 GA 優化: 最多 {n_gen} 代, 族群大小 {pop_size}, {n_workers} 進程")

    # 保存配置
    if not checkpoint:
        with open(pm.log_dir / 'config_used.json', 'w', encoding='utf-8') as f:
            json.dump({
                'ga_config': config,
                'fluid_conditions': fluid,
                'cli_args': vars(args)
            }, f, indent=2, ensure_ascii=False)

    # 創建優化器（單執行緒模式使用）
    optimizer = (
        HPA_Optimizer(
            pm,
            W_area_penalty=W_area_penalty,
            analysis_mode=analysis_mode,
            flow_conditions=flow_conditions,
        )
        if n_workers == 1 else None
    )
    executor = ProcessPoolExecutor(max_workers=n_workers) if n_workers > 1 else None

    # 使用優化器的基因範圍
    GENE_BOUNDS = HPA_Optimizer.GENE_BOUNDS
    keys = list(GENE_BOUNDS.keys())
    lower = np.array([GENE_BOUNDS[k][0] for k in keys])
    upper = np.array([GENE_BOUNDS[k][1] for k in keys])

    # 收斂歷史和追蹤
    convergence_history = checkpoint.get('convergence_history', []) if checkpoint else []
    best_so_far = checkpoint.get('best_so_far', float('inf')) if checkpoint else float('inf')
    generations_without_improvement = checkpoint.get('generations_without_improvement', 0) if checkpoint else 0
    should_terminate = False

    if checkpoint and 'numpy_random_state' in checkpoint:
        np.random.set_state(checkpoint['numpy_random_state'])

    resume_population = np.array(resume_population_data) if resume_population_data is not None else None
    if resume_population is not None:
        pop_size = len(resume_population)
        pm.log(f"載入 checkpoint population: {pop_size} 個體")

    # 定義問題
    class HPAProblem(Problem):
        def __init__(self):
            super().__init__(
                n_var=len(lower),
                n_obj=1,
                n_constr=0,
                xl=lower,
                xu=upper
            )

        def _evaluate(self, X, out, *args, **kwargs):
            nonlocal best_so_far, generations_without_improvement, should_terminate

            gen = callback.n_gen

            # 評估族群（單執行緒或平行模式）
            fitness = evaluate_population_parallel(
                X,
                gen,
                GENE_BOUNDS,
                W_area_penalty,
                n_workers,
                pm,
                analysis_mode,
                flow_conditions,
                optimizer,
                executor,
            )

            out["F"] = fitness.reshape(-1, 1)

    # 定義回調函數（用於收斂檢測）
    class ConvergenceCallback(Callback):
        def __init__(self):
            super().__init__()
            self.n_gen = start_generation
            self.best_history = []

        def notify(self, algorithm):
            nonlocal best_so_far, generations_without_improvement, should_terminate

            self.n_gen += 1

            # 獲取當前最佳適應度
            current_best = algorithm.pop.get("F").min()
            valid_fitness = [f for f in algorithm.pop.get("F").flatten() if f < 1e5]

            if valid_fitness:
                current_best = min(valid_fitness)
                current_avg = sum(valid_fitness) / len(valid_fitness)
            else:
                current_best = 1e6
                current_avg = 1e6

            # 記錄收斂歷史
            convergence_history.append({
                'generation': self.n_gen,
                'best_fitness': current_best,
                'avg_fitness': current_avg,
                'feasible_count': len(valid_fitness),
                'pop_size': len(algorithm.pop)
            })

            # 檢查是否改善
            if current_best < best_so_far * 0.999:  # 0.1% 改善才算
                best_so_far = current_best
                generations_without_improvement = 0
                pm.log(f"Gen {self.n_gen}: Best={current_best:.4f}N ⬇️ (改善!)")
            else:
                generations_without_improvement += 1
                pm.log(f"Gen {self.n_gen}: Best={current_best:.4f}N "
                       f"(無改善 {generations_without_improvement}/{convergence_tol})")

            # 檢查收斂條件
            if generations_without_improvement >= convergence_tol:
                pm.log(f"\n🎯 收斂！連續 {convergence_tol} 代無改善，提前終止")
                should_terminate = True
                algorithm.termination.force_termination = True

            # 每5代保存一次收斂曲線
            if self.n_gen % 5 == 0 and convergence_history:
                plot_convergence(convergence_history, str(pm.log_dir / 'convergence.png'))

                # 保存收斂歷史
                with open(pm.log_dir / 'convergence_history.json', 'w', encoding='utf-8') as f:
                    json.dump(convergence_history, f, indent=2)

            save_checkpoint(
                pm,
                self,
                algorithm,
                convergence_history,
                best_so_far,
                generations_without_improvement,
                n_gen,
            )

    # 創建問題和回調
    problem = HPAProblem()
    callback = ConvergenceCallback()

    # 設置 GA 演算法
    algorithm = GA(
        pop_size=pop_size,
        sampling=resume_population if resume_population is not None else FloatRandomSampling(),
        crossover=SBX(
            prob=config.get('ga_settings', {}).get('crossover_probability', 0.9),
            eta=config.get('ga_settings', {}).get('crossover_eta', 15)
        ),
        mutation=PM(eta=config.get('ga_settings', {}).get('mutation_eta', 20)),
        eliminate_duplicates=config.get('ga_settings', {}).get('eliminate_duplicates', True)
    )

    remaining_generations = n_gen - start_generation

    # 續跑時應保留 checkpoint 中的 numpy RNG 狀態，避免又被 seed 重設。
    optimization_seed = None if checkpoint and 'numpy_random_state' in checkpoint else seed

    # 執行優化
    pm.log("開始 GA 演算法...")
    start_time = datetime.now()

    try:
        res = minimize(
            problem,
            algorithm,
            ('n_gen', remaining_generations),
            callback=callback,
            verbose=False,  # 使用自己的日誌
            seed=optimization_seed
        )
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=False)

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    # 保存結果
    best_gene = {k: res.X[i] for i, k in enumerate(keys)}
    best_fitness = float(res.F[0])

    best_analysis = evaluate_gene(
        best_gene,
        "best_design_summary",
        W_area_penalty,
        analysis_mode=analysis_mode,
        flow_conditions=flow_conditions,
        return_details=True,
    )
    su2_shortlist_summary = None
    if prepare_su2_shortlist:
        su2_shortlist_summary = prepare_ga_su2_shortlist(
            pm,
            top_n=su2_shortlist_top,
            flow_conditions=flow_conditions,
            output_dir=su2_shortlist_out,
        )
    pm.save_best_gene(best_gene, best_fitness, callback.n_gen, analysis=best_analysis)
    results_payload = {
        'best_gene': best_gene,
        'best_fitness': best_fitness,
        'generation': callback.n_gen,
        'analysis_mode': analysis_mode,
        'best_analysis': best_analysis,
        'elapsed_seconds': elapsed,
        'timestamp': datetime.now().isoformat(),
    }
    if su2_shortlist_summary is not None:
        results_payload['su2_shortlist'] = su2_shortlist_summary
    pm.save_results(results_payload)

    # 最終保存收斂歷史
    with open(pm.log_dir / 'convergence_history.json', 'w', encoding='utf-8') as f:
        json.dump(convergence_history, f, indent=2)

    # 繪製最終收斂曲線
    if convergence_history:
        plot_convergence(convergence_history, str(pm.log_dir / 'convergence.png'))

    export_final_vsp = bool(args.final_vsp or config.get('output', {}).get('export_final_vsp', False))
    if args.skip_final_vsp:
        export_final_vsp = False

    if not export_final_vsp:
        pm.log("跳過最終 VSP 匯出（預設關閉，可用 --final-vsp 啟用）")
    else:
        # 生成最佳模型
        pm.log("生成最佳模型...")
        best_vsp_path = str(pm.vsp_dir / 'best_design.vsp3')
        from optimization.hpa_asymmetric_optimizer import VSPModelGenerator
        curves = CST_Modeler.generate_asymmetric_fairing(best_gene)
        VSPModelGenerator.create_fuselage(curves, 'best_design', best_vsp_path)
        pm.log(f"最佳模型已生成: {best_vsp_path}")

    # 輸出結果
    pm.log(f"\n{'='*60}")
    pm.log(f"優化完成！")
    pm.log(f"{'='*60}")
    pm.log(f"實際運行代數: {callback.n_gen}")
    pm.log(f"總耗時: {elapsed:.1f} 秒")
    pm.log(f"收斂狀態: {'提前收斂' if should_terminate else '達到最大代數'}")
    pm.log(f"最佳適應度: {best_fitness:.4f} N")
    pm.log(f"最佳基因:")
    for key, value in best_gene.items():
        pm.log(f"  {key}: {value:.4f}")
    pm.log(f"")
    pm.log(f"輸出目錄: {pm.run_dir}")
    pm.log(f"最佳基因: {pm.log_dir / 'best_gene.json'}")
    pm.log(f"分析摘要: {pm.results_file}")
    pm.log(f"收斂曲線: {pm.log_dir / 'convergence.png'}")
    if su2_shortlist_summary is not None:
        pm.log(f"SU2 shortlist: {su2_shortlist_summary['manifest_json']}")
    pm.log(f"{'='*60}")

    return res, pm, convergence_history


def main():
    parser = argparse.ArgumentParser(description='HPA 整流罩 GA 優化（外包工頭模式）')
    parser.add_argument('--gen', type=int, help='GA 代數上限')
    parser.add_argument('--pop', type=int, help='族群大小')
    parser.add_argument('--seed', type=int, help='隨機種子')
    parser.add_argument('--tol', type=int, help='收斂容忍度（連續N代不改善則停止）')
    parser.add_argument('--workers', type=int, help='平行運算進程數（預設1，建議8-18）')
    parser.add_argument('--config', type=str, help='GA 配置檔案路徑')
    parser.add_argument('--fluid', type=str, help='流體條件配置檔案路徑')
    parser.add_argument('--resume', type=str, help='從 checkpoint.pkl 或其所在目錄續跑')
    parser.add_argument('--analysis-mode', choices=['openvsp', 'proxy'],
                        help='阻力評估模式（預設讀 config，否則 proxy）')
    parser.add_argument('--final-vsp', action='store_true',
                        help='完成後匯出最佳解的 .vsp3 模型（預設關閉）')
    parser.add_argument('--skip-final-vsp', action='store_true',
                        help='強制跳過最佳解的最終 .vsp3 匯出（保留舊介面）')
    parser.add_argument('--prepare-su2-shortlist', action='store_true',
                        help='完成後自動從 GA 候選建立 SU2 shortlist 工作包')
    parser.add_argument('--su2-shortlist-top', type=int, default=5,
                        help='建立 SU2 shortlist 時保留前 N 名候選（預設 5）')
    parser.add_argument('--su2-shortlist-out', type=str,
                        help='SU2 shortlist 輸出目錄（預設為 <run_dir>/su2_shortlist）')

    args = parser.parse_args()

    result = run_optimization(args)

    if result:
        res, pm, history = result
        print(f"\n完成！結果保存於: {pm.run_dir}")


if __name__ == "__main__":
    main()
