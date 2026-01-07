"""測試skinning angle修復"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入
if 'optimization.hpa_asymmetric_optimizer' in sys.modules:
    del sys.modules['optimization.hpa_asymmetric_optimizer']

from optimization.hpa_asymmetric_optimizer import CST_Modeler, VSPModelGenerator, CSTDerivatives
import numpy as np

print("="*80)
print("測試Skinning Angle修復")
print("="*80)

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
weights_fixed = np.array([1.0, 1.0])

print("\n📊 檢查角度計算（修復後）:")
print("-" * 80)
print(f"{'截面':^6} {'z_upper':^10} {'z_lower':^10} {'對稱?':^8} {'角度上':^10} {'角度下':^10} {'差異':^8}")
print("-" * 80)

for i in [0, 10, 20, 30, 38, 39]:
    if i >= len(curves['psi']):
        continue

    psi = curves['psi'][i]
    z_upper = curves['z_upper'][i]
    z_lower = curves['z_lower'][i]

    # 檢查對稱性（與code中相同的邏輯）
    is_symmetric = abs(z_upper - z_lower) < 0.02

    # 計算角度（模擬修復後的邏輯）
    N2_avg = (gene['N2_top'] + gene['N2_bot']) / 2.0

    if is_symmetric:
        # 對稱時使用平均N2
        tangent_both = CSTDerivatives.compute_tangent_angles_for_section(
            psi, gene['N1'], N2_avg, weights_fixed, weights_fixed, gene['L']
        )
        angle_top = tangent_both['top']
        angle_bot = tangent_both['bottom']
    else:
        # 非對稱時使用不同N2
        tangent_top = CSTDerivatives.compute_tangent_angles_for_section(
            psi, gene['N1'], gene['N2_top'], weights_fixed, weights_fixed, gene['L']
        )
        tangent_bot = CSTDerivatives.compute_tangent_angles_for_section(
            psi, gene['N1'], gene['N2_bot'], weights_fixed, weights_fixed, gene['L']
        )
        angle_top = tangent_top['top']
        angle_bot = tangent_bot['bottom']

    diff = abs(angle_top - angle_bot)
    sym_str = "✅" if is_symmetric else "❌"
    status = "✅" if (is_symmetric and diff < 0.1) or not is_symmetric else "⚠️"

    print(f"{i:^6} {z_upper:^10.3f} {z_lower:^10.3f} {sym_str:^8} {angle_top:^10.1f} {angle_bot:^10.1f} {diff:^8.2f} {status}")

print("\n" + "="*80)
print("🔍 預期結果:")
print("  - 截面0（機頭）: 對稱，角度應相同")
print("  - 截面39（機尾）: 對稱，角度應相同")
print("  - 截面10,20,30: 非對稱，角度可以不同")
print("="*80)

# 生成VSP模型
output_file = "output/fairing_skinning_fixed.vsp3"
print(f"\n🚀 生成VSP模型: {output_file}")

VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_Skinning_Fixed",
    filepath=output_file
)

print(f"   ✅ 模型已保存")
print(f"\n💡 請在VSP GUI中打開: {output_file}")
print("   檢查機尾（側視圖）skinning是否平滑")
print("="*80)
