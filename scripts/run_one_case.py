"""
HPA 整流罩單一個體評估腳本（獨立進程）

這是一個完全獨立的腳本，由 GA 主程式透過 subprocess 呼叫。
每次執行都是全新的進程，避免 OpenVSP DLL 衝突。

使用方法：
    python run_one_case.py --gene '{"L": 2.5, ...}' --name gen000_ind000 --output_dir /path/to/dir

輸出（stdout）：
    成功: "SCORE:1.5283"
    失敗: "SCORE:1000000"
"""

import sys
import os
import json
import argparse

# 添加專案路徑
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

from optimization.hpa_asymmetric_optimizer import (
    CST_Modeler, VSPModelGenerator, ConstraintChecker
)
from analysis.drag_analysis import DragAnalyzer


def evaluate_gene(gene: dict, name: str, W_area_penalty: float = 0.1) -> float:
    """
    評估單一基因組

    Returns:
        score (float): 適應度分數，越小越好
    """
    try:
        # 1. 生成幾何曲線
        curves = CST_Modeler.generate_asymmetric_fairing(gene)

        # 2. 檢查限制（快速篩選）
        passed, results = ConstraintChecker.check_all_constraints(gene, curves)
        if not passed:
            return 1e6

        # 3. 生成 VSP 模型（直接保留在記憶體中）
        try:
            VSPModelGenerator.create_fuselage(curves, name, filepath=None)
        except Exception as e:
            print(f"VSP生成失敗: {e}", file=sys.stderr)
            return 1e6

        # 4. 計算阻力（直接分析當前記憶體中的 OpenVSP 模型）
        try:
            analyzer = DragAnalyzer()
            result = analyzer.run_analysis_current_model(name, velocity=6.5, rho=1.225, mu=1.7894e-5)
            if not result:
                print(f"{name}: 分析失敗", file=sys.stderr)
                return 1e6

            drag = result["Drag"]
            swet = result.get("Swet")
            cd = result["Cd"]

            if swet is not None:
                area_penalty = W_area_penalty * swet
                score = drag + area_penalty
                print(
                    f"{name}: Cd={cd:.6f}, Swet={swet:.3f}m², "
                    f"Drag={drag:.4f}N, Penalty={area_penalty:.4f}N, "
                    f"Score={score:.4f}N",
                    file=sys.stderr,
                )
                return score

            print(f"{name}: Cd={cd:.6f}, Drag={drag:.4f}N (無Swet)", file=sys.stderr)
            return drag

        except Exception as e:
            print(f"{name}: 阻力計算失敗 - {e}", file=sys.stderr)
            return 1e6

    except Exception as e:
        print(f"Worker錯誤: {e}", file=sys.stderr)
        return 1e6


def main():
    parser = argparse.ArgumentParser(description='HPA 整流罩單一個體評估')
    parser.add_argument('--gene', type=str, required=True,
                        help='基因 JSON 字串或檔案路徑')
    parser.add_argument('--name', type=str, default='unnamed',
                        help='個體名稱（用於日誌）')
    parser.add_argument('--penalty', type=float, default=0.1,
                        help='面積懲罰因子 (N/m²)')

    args = parser.parse_args()

    # 解析基因
    if os.path.exists(args.gene):
        # 從檔案讀取
        with open(args.gene, 'r', encoding='utf-8') as f:
            gene = json.load(f)
    else:
        # 直接解析 JSON 字串
        gene = json.loads(args.gene)

    # 評估
    score = evaluate_gene(gene, args.name, args.penalty)

    # 輸出分數到 stdout（這是主程式要讀取的）
    print(f"SCORE:{score}")


if __name__ == "__main__":
    main()
