"""診斷完整角度修復後的結果"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from optimization.hpa_asymmetric_optimizer import CST_Modeler, CSTDerivatives
import numpy as np

gene = {
    'L': 2.5,
    'W_max': 0.60,
    'H_top_max': 0.95,
    'H_bot_max': 0.35,
    'N1': 0.5,
    'N2_top': 0.7,
    'N2_bot': 0.8,
    'X_max_pos': 0.25,
    'X_offset': 0.7,
}

curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

print("="*80)
print("完整角度診斷報告")
print("="*80)
print("\n使用新的非對稱角度計算法：compute_asymmetric_tangent_angles")
print("直接從z_upper和z_lower曲線計算斜率\n")

# 檢查關鍵截面
key_sections = [0, 1, 10, 20, 30, 38, 39]

print(f"{'截面':<6} {'psi':<8} {'z_upper':<10} {'z_lower':<10} {'對稱?':<8} {'Top角度':<12} {'Bot角度':<12} {'差異':<10}")
print("-"*80)

for i in key_sections:
    psi = curves['psi'][i]
    z_upper = curves['z_upper'][i]
    z_lower = curves['z_lower'][i]

    is_symmetric = abs(z_upper - z_lower) < 0.02

    # 使用新方法計算角度
    angles = CSTDerivatives.compute_asymmetric_tangent_angles(
        curves['x'], curves['z_upper'], curves['z_lower'], i
    )

    angle_top = angles['top']
    angle_bot = angles['bottom']
    diff = abs(angle_top - angle_bot)

    sym_str = "對稱" if is_symmetric else "非對稱"

    print(f"{i:<6} {psi:<8.3f} {z_upper:<10.4f} {z_lower:<10.4f} {sym_str:<8} {angle_top:<12.2f} {angle_bot:<12.2f} {diff:<10.2f}")

print("\n" + "="*80)
print("關鍵觀察:")
print("="*80)
print("1. 機頭（截面0）：")
print(f"   - z_upper ≈ z_lower ≈ 0 (對稱)")
print(f"   - Top和Bottom角度應該接近（因為幾何對稱）")
print(f"   - 但使用新方法，會根據實際斜率計算")

print("\n2. 機尾（截面39）：")
print(f"   - z_upper ≈ z_lower ≈ 0 (對稱)")
print(f"   - Top和Bottom角度應該接近（因為幾何對稱）")

print("\n3. 中間非對稱截面：")
print(f"   - z_upper ≠ z_lower")
print(f"   - Top和Bottom角度可以不同（反映真實幾何）")

print("\n4. Bottom角度符號：")
print(f"   - 已加入負號修正 (angle_bottom = -math.degrees(math.atan(dz_lower_dx)))")
print(f"   - 符合VSP skinning定義")

print("\n✅ 所有截面使用統一的角度計算方法（有限差分法）")
print("="*80)
