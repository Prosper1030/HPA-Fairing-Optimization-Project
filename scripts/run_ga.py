"""
HPA 整流罩 GA 優化運行腳本

使用方法：
    python scripts/run_ga.py --gen 50 --pop 20
    python scripts/run_ga.py --config config/ga_config.json
    python scripts/run_ga.py --gen 100 --pop 30 --tol 5  # 5代不改善就停止
    python scripts/run_ga.py --gen 50 --pop 20 --workers 4  # 4進程平行運算
"""

import sys
import os
import json
import argparse
import numpy as np
from datetime import datetime
from pathlib import Path
from multiprocessing import Pool, cpu_count

# 添加專案路徑
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

from optimization.hpa_asymmetric_optimizer import (
    HPA_Optimizer, ProjectManager, CST_Modeler,
    VSPModelGenerator, ConstraintChecker
)


# ==========================================
# 平行運算 Worker 函數（必須在模組層級）
# ==========================================
def evaluate_worker(args_tuple):
    """
    平行運算的 worker 函數
    每個 worker 進程會有自己的 OpenVSP 實例
    使用唯一臨時目錄避免檔案衝突
    """
    import tempfile
    import shutil

    gene_array, gen, ind, vsp_dir, W_area_penalty, gene_bounds = args_tuple
    name = f"gen{gen:03d}_ind{ind:03d}"

    # 創建唯一的臨時工作目錄（避免檔案衝突）
    temp_dir = tempfile.mkdtemp(prefix=f"vsp_{name}_")

    try:
        # 每個進程獨立導入 openvsp
        import openvsp as vsp

        # 轉換基因陣列為字典
        keys = list(gene_bounds.keys())
        gene = {k: gene_array[i] for i, k in enumerate(keys)}

        # 1. 生成幾何曲線
        curves = CST_Modeler.generate_asymmetric_fairing(gene)

        # 2. 檢查限制（快速篩選）
        passed, results = ConstraintChecker.check_all_constraints(gene, curves)
        if not passed:
            return 1e6, None

        # 3. 生成 VSP 模型（在臨時目錄）
        vsp_path = os.path.join(temp_dir, f"{name}.vsp3")

        try:
            VSPModelGenerator.create_fuselage(curves, name, vsp_path)
        except Exception as e:
            return 1e6, f"VSP生成失敗: {e}"

        # 4. 計算阻力
        try:
            vsp.ClearVSPModel()
            vsp.ReadVSPFile(vsp_path)

            vsp.SetAnalysisInputDefaults("ParasiteDrag")
            vsp.SetDoubleAnalysisInput("ParasiteDrag", "Rho", [1.225])
            vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
            vsp.SetDoubleAnalysisInput("ParasiteDrag", "Mu", [1.7894e-5])
            vsp.ExecAnalysis("ParasiteDrag")

            # 解析 CSV（在臨時目錄）
            csv_file = os.path.join(temp_dir, f"{name}_ParasiteBuildUp.csv")

            if os.path.exists(csv_file):
                with open(csv_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # 解析 Swet
                swet = None
                found_header = False
                for line in lines:
                    if 'Component Name' in line and 'S_wet' in line:
                        found_header = True
                        continue
                    if found_header and line.strip():
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 2:
                            try:
                                swet = float(parts[1])
                                break
                            except:
                                pass

                # 解析 Totals
                for line in lines:
                    if 'Totals:' in line:
                        parts = [p.strip() for p in line.split(',')]
                        values = [p for p in parts if p and p != 'Totals:']
                        if len(values) >= 2:
                            try:
                                cd = float(values[1])
                                q = 0.5 * 1.225 * (6.5 ** 2)
                                drag = q * 1.0 * cd

                                if swet is not None:
                                    area_penalty = W_area_penalty * swet
                                    score = drag + area_penalty
                                    msg = f"{name}: Cd={cd:.6f}, Swet={swet:.3f}m², Drag={drag:.4f}N, Penalty={area_penalty:.4f}N, Score={score:.4f}N"
                                    return score, msg
                                else:
                                    msg = f"{name}: Cd={cd:.6f}, Drag={drag:.4f}N (無Swet)"
                                    return drag, msg
                            except:
                                pass

            return 1e6, f"{name}: CSV解析失敗"

        except Exception as e:
            return 1e6, f"{name}: 阻力計算失敗 - {e}"

    except Exception as e:
        return 1e6, f"Worker錯誤: {e}"

    finally:
        # 清理臨時目錄
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


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


def run_optimization(args):
    """運行 GA 優化"""

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
    n_gen = args.gen or config.get('ga_settings', {}).get('n_generations', 50)
    pop_size = args.pop or config.get('ga_settings', {}).get('population_size', 20)
    seed = args.seed or config.get('ga_settings', {}).get('seed', 42)
    convergence_tol = args.tol or 10  # 預設10代不改善就停止

    # 平行運算設定（預設保留2核給系統）
    max_workers = max(1, cpu_count() - 2)  # 至少1個，最多 CPU-2
    n_workers = args.workers if args.workers else 1  # 預設單執行緒
    if n_workers > max_workers:
        n_workers = max_workers
        print(f"⚠️ Workers 調整為 {n_workers}（保留2核給系統）")

    # 讀取面積懲罰因子（提前讀取以便顯示）
    W_area_penalty = config.get('fitness', {}).get('W_area_penalty', 0.1)

    print(f"\n{'='*60}")
    print(f"HPA 整流罩 GA 優化")
    print(f"{'='*60}")
    print(f"代數上限: {n_gen}")
    print(f"族群大小: {pop_size}")
    print(f"隨機種子: {seed}")
    print(f"收斂容忍度: {convergence_tol} 代不改善則停止")
    print(f"面積懲罰因子: {W_area_penalty} N/m²")
    print(f"適應度公式: Score = Drag + {W_area_penalty} × Swet")
    print(f"平行運算: {n_workers} 進程" + (f"（可用: {max_workers}）" if n_workers > 1 else "（單執行緒）"))
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
    pm = ProjectManager(base_output_dir="output")
    pm.log(f"開始 GA 優化: 最多 {n_gen} 代, 族群大小 {pop_size}")

    # 保存配置
    with open(pm.log_dir / 'config_used.json', 'w', encoding='utf-8') as f:
        json.dump({
            'ga_config': config,
            'fluid_conditions': fluid,
            'cli_args': vars(args)
        }, f, indent=2, ensure_ascii=False)

    # 創建優化器（W_area_penalty 已在前面讀取）
    optimizer = HPA_Optimizer(pm, W_area_penalty=W_area_penalty)

    # 收斂歷史和追蹤
    convergence_history = []
    best_so_far = float('inf')
    generations_without_improvement = 0
    should_terminate = False

    # 定義問題
    class HPAProblem(Problem):
        def __init__(self):
            lower, upper = optimizer.get_bounds()
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
            gene_bounds = optimizer.GENE_BOUNDS

            if n_workers > 1:
                # 平行評估（每代的族群評估階段）
                args_list = [
                    (x, gen, i, str(pm.vsp_dir), W_area_penalty, gene_bounds)
                    for i, x in enumerate(X)
                ]

                with Pool(processes=n_workers) as pool:
                    results = pool.map(evaluate_worker, args_list)

                fitness = []
                for score, msg in results:
                    fitness.append(score)
                    if msg:
                        pm.log(msg)
            else:
                # 串行評估（原本方式）
                fitness = []
                for i, x in enumerate(X):
                    f = optimizer.evaluate_individual(x, gen, i)
                    fitness.append(f)

            out["F"] = np.array(fitness).reshape(-1, 1)

    # 定義回調函數（用於收斂檢測）
    class ConvergenceCallback(Callback):
        def __init__(self):
            super().__init__()
            self.n_gen = 0
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

    # 創建問題和回調
    problem = HPAProblem()
    callback = ConvergenceCallback()

    # 設置 GA 演算法
    algorithm = GA(
        pop_size=pop_size,
        sampling=FloatRandomSampling(),
        crossover=SBX(
            prob=config.get('ga_settings', {}).get('crossover_probability', 0.9),
            eta=config.get('ga_settings', {}).get('crossover_eta', 15)
        ),
        mutation=PM(eta=config.get('ga_settings', {}).get('mutation_eta', 20)),
        eliminate_duplicates=config.get('ga_settings', {}).get('eliminate_duplicates', True)
    )

    # 執行優化
    pm.log("開始 GA 演算法...")
    start_time = datetime.now()

    res = minimize(
        problem,
        algorithm,
        ('n_gen', n_gen),
        callback=callback,
        verbose=False,  # 使用自己的日誌
        seed=seed
    )

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    # 保存結果
    best_gene = optimizer.array_to_gene(res.X)
    best_fitness = float(res.F[0])

    pm.save_best_gene(best_gene, best_fitness, callback.n_gen)

    # 最終保存收斂歷史
    with open(pm.log_dir / 'convergence_history.json', 'w', encoding='utf-8') as f:
        json.dump(convergence_history, f, indent=2)

    # 繪製最終收斂曲線
    if convergence_history:
        plot_convergence(convergence_history, str(pm.log_dir / 'convergence.png'))

    # 生成最佳模型
    pm.log("生成最佳模型...")
    curves = CST_Modeler.generate_asymmetric_fairing(best_gene)
    best_vsp_path = str(pm.vsp_dir / 'best_design.vsp3')
    VSPModelGenerator.create_fuselage(curves, 'best_design', best_vsp_path)

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
    pm.log(f"最佳模型: {best_vsp_path}")
    pm.log(f"收斂曲線: {pm.log_dir / 'convergence.png'}")
    pm.log(f"{'='*60}")

    return res, pm, convergence_history


def main():
    parser = argparse.ArgumentParser(description='HPA 整流罩 GA 優化')
    parser.add_argument('--gen', type=int, help='GA 代數上限')
    parser.add_argument('--pop', type=int, help='族群大小')
    parser.add_argument('--seed', type=int, help='隨機種子')
    parser.add_argument('--tol', type=int, help='收斂容忍度（連續N代不改善則停止）')
    parser.add_argument('--workers', type=int, help=f'平行運算進程數（預設1，最多{cpu_count()-2}）')
    parser.add_argument('--config', type=str, help='GA 配置檔案路徑')
    parser.add_argument('--fluid', type=str, help='流體條件配置檔案路徑')

    args = parser.parse_args()

    result = run_optimization(args)

    if result:
        res, pm, history = result
        print(f"\n完成！結果保存於: {pm.run_dir}")


if __name__ == "__main__":
    main()
