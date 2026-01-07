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
import tempfile
import shutil

# 添加專案路徑
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(project_root, 'src'))

from optimization.hpa_asymmetric_optimizer import (
    CST_Modeler, VSPModelGenerator, ConstraintChecker
)


def evaluate_gene(gene: dict, name: str, W_area_penalty: float = 0.1) -> float:
    """
    評估單一基因組

    Returns:
        score (float): 適應度分數，越小越好
    """
    # 創建唯一臨時目錄
    temp_dir = tempfile.mkdtemp(prefix=f"vsp_{name}_")
    original_cwd = os.getcwd()

    try:
        # 切換到臨時目錄（避免檔案衝突）
        os.chdir(temp_dir)

        # 1. 生成幾何曲線
        curves = CST_Modeler.generate_asymmetric_fairing(gene)

        # 2. 檢查限制（快速篩選）
        passed, results = ConstraintChecker.check_all_constraints(gene, curves)
        if not passed:
            return 1e6

        # 3. 生成 VSP 模型
        vsp_path = os.path.join(temp_dir, f"{name}.vsp3")

        try:
            VSPModelGenerator.create_fuselage(curves, name, vsp_path)
        except Exception as e:
            print(f"VSP生成失敗: {e}", file=sys.stderr)
            return 1e6

        # 4. 在這裡才導入 openvsp（每個進程獨立）
        import openvsp as vsp

        # 5. 計算阻力
        try:
            vsp.ClearVSPModel()
            vsp.ReadVSPFile(vsp_path)

            vsp.SetAnalysisInputDefaults("ParasiteDrag")
            vsp.SetDoubleAnalysisInput("ParasiteDrag", "Rho", [1.225])
            vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
            vsp.SetDoubleAnalysisInput("ParasiteDrag", "Mu", [1.7894e-5])
            vsp.ExecAnalysis("ParasiteDrag")

            # 解析 CSV
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
                                    # 輸出詳細資訊到 stderr（不影響 score 解析）
                                    print(f"{name}: Cd={cd:.6f}, Swet={swet:.3f}m², "
                                          f"Drag={drag:.4f}N, Penalty={area_penalty:.4f}N, "
                                          f"Score={score:.4f}N", file=sys.stderr)
                                    return score
                                else:
                                    print(f"{name}: Cd={cd:.6f}, Drag={drag:.4f}N (無Swet)",
                                          file=sys.stderr)
                                    return drag
                            except:
                                pass

            print(f"{name}: CSV解析失敗", file=sys.stderr)
            return 1e6

        except Exception as e:
            print(f"{name}: 阻力計算失敗 - {e}", file=sys.stderr)
            return 1e6

    except Exception as e:
        print(f"Worker錯誤: {e}", file=sys.stderr)
        return 1e6

    finally:
        # 恢復原始工作目錄
        try:
            os.chdir(original_cwd)
        except:
            pass
        # 清理臨時目錄
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


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
