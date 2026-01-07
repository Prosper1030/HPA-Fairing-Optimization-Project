"""
HPA 整流罩 GA 優化運行腳本

使用方法：
    python scripts/run_ga.py --gen 50 --pop 20
    python scripts/run_ga.py --config config/ga_config.json
"""

import sys
import os
import json
import argparse
import numpy as np
from datetime import datetime
from pathlib import Path

# 添加專案路徑
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

from optimization.hpa_asymmetric_optimizer import (
    HPA_Optimizer, ProjectManager, CST_Modeler,
    VSPModelGenerator, ConstraintChecker
)


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


def plot_parameter_distribution(population: list, gene_names: list, output_path: str):
    """繪製參數分布"""
    try:
        import matplotlib.pyplot as plt

        n_params = len(gene_names)
        n_cols = 4
        n_rows = (n_params + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, n_rows * 3))
        axes = axes.flatten()

        for i, name in enumerate(gene_names):
            values = [ind[name] for ind in population]
            axes[i].hist(values, bins=15, edgecolor='black', alpha=0.7)
            axes[i].set_title(name)
            axes[i].set_xlabel('Value')
            axes[i].set_ylabel('Count')

        # 隱藏多餘的子圖
        for i in range(n_params, len(axes)):
            axes[i].set_visible(False)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150)
        plt.close()

        print(f"參數分布圖已保存: {output_path}")

    except ImportError:
        print("Warning: matplotlib 未安裝，跳過參數分布圖繪製")


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

    print(f"\n{'='*60}")
    print(f"HPA 整流罩 GA 優化")
    print(f"{'='*60}")
    print(f"代數: {n_gen}")
    print(f"族群大小: {pop_size}")
    print(f"隨機種子: {seed}")
    print(f"{'='*60}\n")

    # 檢查 pymoo
    try:
        from pymoo.core.problem import Problem
        from pymoo.algorithms.soo.nonconvex.ga import GA
        from pymoo.optimize import minimize
        from pymoo.operators.sampling.rnd import FloatRandomSampling
        from pymoo.operators.crossover.sbx import SBX
        from pymoo.operators.mutation.pm import PM
    except ImportError:
        print("錯誤: 需要安裝 pymoo")
        print("請執行: pip install pymoo")
        return None

    # 創建專案管理器
    pm = ProjectManager(base_output_dir="output")
    pm.log(f"開始 GA 優化: {n_gen} 代, 族群大小 {pop_size}")

    # 保存配置
    with open(pm.log_dir / 'config_used.json', 'w', encoding='utf-8') as f:
        json.dump({
            'ga_config': config,
            'fluid_conditions': fluid,
            'cli_args': vars(args)
        }, f, indent=2, ensure_ascii=False)

    # 創建優化器
    optimizer = HPA_Optimizer(pm)

    # 收斂歷史
    convergence_history = []

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
            self.generation = 0
            self.individual_counter = 0
            self.gen_fitness = []

        def _evaluate(self, X, out, *args, **kwargs):
            fitness = []
            for i, x in enumerate(X):
                f = optimizer.evaluate_individual(x, self.generation, self.individual_counter)
                fitness.append(f)
                self.gen_fitness.append(f)
                self.individual_counter += 1

            out["F"] = np.array(fitness).reshape(-1, 1)

            # 每代結束後記錄
            if self.individual_counter >= pop_size:
                valid_fitness = [f for f in self.gen_fitness if f < 1e5]
                if valid_fitness:
                    convergence_history.append({
                        'generation': self.generation,
                        'best_fitness': min(valid_fitness),
                        'avg_fitness': sum(valid_fitness) / len(valid_fitness),
                        'feasible_count': len(valid_fitness)
                    })
                    pm.log(f"Gen {self.generation}: Best={min(valid_fitness):.4f}N, "
                           f"Avg={sum(valid_fitness)/len(valid_fitness):.4f}N, "
                           f"Feasible={len(valid_fitness)}/{pop_size}")

                self.generation += 1
                self.individual_counter = 0
                self.gen_fitness = []

    # 創建問題實例
    problem = HPAProblem()

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
        verbose=True,
        seed=seed
    )

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    # 保存結果
    best_gene = optimizer.array_to_gene(res.X)
    best_fitness = float(res.F[0])

    pm.save_best_gene(best_gene, best_fitness, n_gen)

    # 保存收斂歷史
    with open(pm.log_dir / 'convergence_history.json', 'w', encoding='utf-8') as f:
        json.dump(convergence_history, f, indent=2)

    # 繪製收斂曲線
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
    pm.log(f"總耗時: {elapsed:.1f} 秒")
    pm.log(f"最佳適應度: {best_fitness:.4f} N")
    pm.log(f"最佳基因:")
    for key, value in best_gene.items():
        pm.log(f"  {key}: {value:.4f}")
    pm.log(f"")
    pm.log(f"輸出目錄: {pm.run_dir}")
    pm.log(f"最佳模型: {best_vsp_path}")
    pm.log(f"{'='*60}")

    return res, pm, convergence_history


def main():
    parser = argparse.ArgumentParser(description='HPA 整流罩 GA 優化')
    parser.add_argument('--gen', type=int, help='GA 代數')
    parser.add_argument('--pop', type=int, help='族群大小')
    parser.add_argument('--seed', type=int, help='隨機種子')
    parser.add_argument('--config', type=str, help='GA 配置檔案路徑')
    parser.add_argument('--fluid', type=str, help='流體條件配置檔案路徑')

    args = parser.parse_args()

    result = run_optimization(args)

    if result:
        res, pm, history = result
        print(f"\n完成！結果保存於: {pm.run_dir}")


if __name__ == "__main__":
    main()
