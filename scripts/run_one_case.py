"""
HPA 整流罩單一個體評估腳本（獨立進程）

這是一個完全獨立的腳本，由 GA 主程式透過 subprocess 呼叫。
每次執行都是全新的進程，避免 OpenVSP DLL 衝突。

使用方法：
    python run_one_case.py --gene '{"L": 2.5, ...}' --name gen000_ind000
    python run_one_case.py --gene path/to/gene.json --analysis-mode proxy

輸出（stdout）：
    成功: "SCORE:1.5283"
    失敗: "SCORE:1000000"
"""

import sys
import os
import json
import argparse

from _bootstrap import ensure_src_path


ensure_src_path()

from analysis.design_evaluator import evaluate_design_gene


def evaluate_gene(
    gene: dict,
    name: str,
    W_area_penalty: float = 0.1,
    analysis_mode: str = "openvsp",
    flow_conditions: dict | None = None,
    return_details: bool = False,
) -> float | dict:
    """
    評估單一基因組。

    Returns:
        score (float): 適應度分數，越小越好
        或在 return_details=True 時返回詳細結果字典
    """
    return evaluate_design_gene(
        gene,
        name,
        area_penalty=W_area_penalty,
        analysis_mode=analysis_mode,
        flow_conditions=flow_conditions,
        return_details=return_details,
        logger=lambda message: print(message, file=sys.stderr),
    )


def main():
    parser = argparse.ArgumentParser(description='HPA 整流罩單一個體評估')
    parser.add_argument('--gene', type=str, required=True,
                        help='基因 JSON 字串或檔案路徑')
    parser.add_argument('--name', type=str, default='unnamed',
                        help='個體名稱（用於日誌）')
    parser.add_argument('--penalty', type=float, default=0.1,
                        help='面積懲罰因子 (N/m²)')
    parser.add_argument('--analysis-mode', choices=['openvsp', 'proxy'], default='openvsp',
                        help='阻力評估模式')

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
    score = evaluate_gene(gene, args.name, args.penalty, analysis_mode=args.analysis_mode)

    # 輸出分數到 stdout（這是主程式要讀取的）
    print(f"SCORE:{score}")


if __name__ == "__main__":
    main()
