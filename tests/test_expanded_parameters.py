"""測試擴展後的基因參數"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from optimization.hpa_asymmetric_optimizer import (
    CST_Modeler, VSPModelGenerator, HPA_Optimizer, ConstraintChecker
)
import numpy as np

print("="*80)
print("測試擴展後的基因參數 (9 -> 18 個參數)")
print("="*80)

# 測試案例（更新：上下分開的M/N）
test_cases = [
    {
        "name": "預設值（上下對稱 M=N=2.5）",
        "gene": {
            'L': 2.5, 'W_max': 0.60, 'H_top_max': 0.95, 'H_bot_max': 0.35,
            'N1': 0.5, 'N2_top': 0.7, 'N2_bot': 0.8,
            'X_max_pos': 0.25, 'X_offset': 0.7,
            'M_top': 2.5, 'N_top': 2.5, 'M_bot': 2.5, 'N_bot': 2.5,
            'tail_rise': 0.10, 'blend_start': 0.75, 'blend_power': 2.0,
            'w0': 0.25, 'w1': 0.35, 'w2': 0.30, 'w3': 0.10,
        }
    },
    {
        "name": "上下非對稱（上圓潤2.5，下方形3.5）",
        "gene": {
            'L': 2.5, 'W_max': 0.60, 'H_top_max': 0.95, 'H_bot_max': 0.35,
            'N1': 0.5, 'N2_top': 0.7, 'N2_bot': 0.8,
            'X_max_pos': 0.25, 'X_offset': 0.7,
            'M_top': 2.5, 'N_top': 2.5, 'M_bot': 3.5, 'N_bot': 3.5,  # 下方更方形
            'tail_rise': 0.10, 'blend_start': 0.75, 'blend_power': 2.0,
            'w0': 0.25, 'w1': 0.35, 'w2': 0.30, 'w3': 0.10,
        }
    },
    {
        "name": "全方形化（M=N=3.5）",
        "gene": {
            'L': 2.5, 'W_max': 0.60, 'H_top_max': 0.95, 'H_bot_max': 0.35,
            'N1': 0.5, 'N2_top': 0.7, 'N2_bot': 0.8,
            'X_max_pos': 0.25, 'X_offset': 0.7,
            'M_top': 3.5, 'N_top': 3.5, 'M_bot': 3.5, 'N_bot': 3.5,
            'tail_rise': 0.10, 'blend_start': 0.75, 'blend_power': 2.0,
            'w0': 0.25, 'w1': 0.35, 'w2': 0.30, 'w3': 0.10,
        }
    },
    {
        "name": "高尾部上升 + 平滑過渡",
        "gene": {
            'L': 2.5, 'W_max': 0.60, 'H_top_max': 0.95, 'H_bot_max': 0.35,
            'N1': 0.5, 'N2_top': 0.7, 'N2_bot': 0.8,
            'X_max_pos': 0.25, 'X_offset': 0.7,
            'M_top': 2.5, 'N_top': 2.5, 'M_bot': 2.5, 'N_bot': 2.5,
            'tail_rise': 0.15, 'blend_start': 0.70, 'blend_power': 1.5,  # 更平滑過渡
            'w0': 0.25, 'w1': 0.35, 'w2': 0.30, 'w3': 0.10,
        }
    },
]

# 測試曲線生成
print("\n--- 測試曲線生成 ---\n")

for case in test_cases:
    print(f"\n[{case['name']}]")
    gene = case['gene']

    # 生成曲線
    curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

    # 驗證關鍵數值
    print(f"  L: {curves['L']:.2f} m")
    print(f"  M_top: {curves['M_top']}, N_top: {curves['N_top']}")
    print(f"  M_bot: {curves['M_bot']}, N_bot: {curves['N_bot']}")
    print(f"  weights: {curves['weights']}")
    print(f"  z_upper max: {np.max(curves['z_upper']):.4f} m")
    print(f"  z_lower min: {np.min(curves['z_lower']):.4f} m")
    print(f"  width max: {np.max(curves['width']):.4f} m")

    # 檢查約束
    passed, results = ConstraintChecker.check_all_constraints(gene, curves)
    print(f"  約束檢查: {'PASS' if passed else 'FAIL'}")

    if not passed:
        for name, result in results.items():
            if not result['pass']:
                print(f"    - {name}: {result['value']:.3f} < {result.get('required', 'N/A')}")

# 測試VSP模型生成
print("\n--- 測試VSP模型生成 ---\n")

import openvsp as vsp

output_dir = "output/test_expanded_params"
os.makedirs(output_dir, exist_ok=True)

for i, case in enumerate(test_cases):
    print(f"\n[{i+1}] {case['name']}")
    gene = case['gene']

    # 生成曲線
    curves = CST_Modeler.generate_asymmetric_fairing(gene)

    # 生成VSP模型
    name = f"test_param_{i+1}"
    filepath = os.path.join(output_dir, f"{name}.vsp3")

    try:
        VSPModelGenerator.create_fuselage(curves, name, filepath)

        # 驗證檔案存在
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath) / 1024
            print(f"  VSP檔案已生成: {filepath}")
            print(f"  檔案大小: {file_size:.1f} KB")

            # 讀取並驗證Super_M/N參數
            vsp.ClearVSPModel()
            vsp.ReadVSPFile(filepath)

            geom_ids = vsp.FindGeomsWithName(name)
            if geom_ids:
                fuse_id = geom_ids[0]
                xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

                # 檢查第10個截面的上下M/N
                xsec = vsp.GetXSec(xsec_surf, 10)

                # 上半部 M/N
                m_top_parm = vsp.GetXSecParm(xsec, "Super_M")
                n_top_parm = vsp.GetXSecParm(xsec, "Super_N")
                # 下半部 M/N（注意：API名稱是小寫 bot）
                m_bot_parm = vsp.GetXSecParm(xsec, "Super_M_bot")
                n_bot_parm = vsp.GetXSecParm(xsec, "Super_N_bot")

                if m_top_parm and n_top_parm:
                    actual_m_top = vsp.GetParmVal(m_top_parm)
                    actual_n_top = vsp.GetParmVal(n_top_parm)
                    expected_m_top = gene['M_top']
                    expected_n_top = gene['N_top']

                    m_top_ok = abs(actual_m_top - expected_m_top) < 0.01
                    n_top_ok = abs(actual_n_top - expected_n_top) < 0.01

                    print(f"  M_top: 期望={expected_m_top}, 實際={actual_m_top:.2f} {'OK' if m_top_ok else 'MISMATCH'}")
                    print(f"  N_top: 期望={expected_n_top}, 實際={actual_n_top:.2f} {'OK' if n_top_ok else 'MISMATCH'}")

                if m_bot_parm and n_bot_parm:
                    actual_m_bot = vsp.GetParmVal(m_bot_parm)
                    actual_n_bot = vsp.GetParmVal(n_bot_parm)
                    expected_m_bot = gene['M_bot']
                    expected_n_bot = gene['N_bot']

                    m_bot_ok = abs(actual_m_bot - expected_m_bot) < 0.01
                    n_bot_ok = abs(actual_n_bot - expected_n_bot) < 0.01

                    print(f"  M_bot: 期望={expected_m_bot}, 實際={actual_m_bot:.2f} {'OK' if m_bot_ok else 'MISMATCH'}")
                    print(f"  N_bot: 期望={expected_n_bot}, 實際={actual_n_bot:.2f} {'OK' if n_bot_ok else 'MISMATCH'}")
                else:
                    print(f"  WARNING: 無法找到 M_bot/N_bot 參數（可能 VSP API 名稱不同）")
        else:
            print(f"  ERROR: 檔案未生成")

    except Exception as e:
        print(f"  ERROR: {e}")

# 測試基因陣列轉換
print("\n--- 測試基因陣列轉換 ---\n")

print("GENE_BOUNDS 定義:")
for key, bounds in HPA_Optimizer.GENE_BOUNDS.items():
    print(f"  {key}: {bounds}")

print(f"\n總計: {len(HPA_Optimizer.GENE_BOUNDS)} 個基因參數")

# 測試陣列轉換
from optimization.hpa_asymmetric_optimizer import ProjectManager

pm = ProjectManager(base_output_dir="output/test_expanded_params")
optimizer = HPA_Optimizer(pm)

# 使用預設基因
default_gene = test_cases[0]['gene']
gene_array = optimizer.gene_to_array(default_gene)
print(f"\n基因向量長度: {len(gene_array)}")
print(f"基因向量: {gene_array}")

# 反向轉換
recovered_gene = optimizer.array_to_gene(gene_array)
print(f"\n反向轉換驗證:")
all_match = True
for key in default_gene:
    if key in recovered_gene:
        match = abs(default_gene[key] - recovered_gene[key]) < 1e-6
        if not match:
            print(f"  MISMATCH: {key}")
            all_match = False

if all_match:
    print("  所有參數轉換正確!")

print("\n" + "="*80)
print("測試完成!")
print("="*80)
