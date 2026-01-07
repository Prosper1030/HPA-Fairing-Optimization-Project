"""診斷Skinning角度問題"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from optimization.hpa_asymmetric_optimizer import CST_Modeler, CSTDerivatives
import numpy as np

print("="*60)
print("Skinning角度診斷")
print("="*60)

# 使用相同的測試基因
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

# 生成曲線
curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

# 固定權重
weights_fixed = np.array([1.0, 1.0])

print("\n📊 檢查關鍵截面的切線角度:")
print("-" * 80)
print(f"{'截面':^6} {'psi':^8} {'Z上界':^10} {'Z下界':^10} {'Z中心':^10} {'角度上':^10} {'角度下':^10}")
print("-" * 80)

for i in [0, 5, 10, 15, 20, 25, 30, 35, 39]:
    if i >= len(curves['psi']):
        continue

    psi = curves['psi'][i]
    z_upper = curves['z_upper'][i]
    z_lower = curves['z_lower'][i]
    z_loc = curves['z_loc'][i]

    # 計算上下切線角度
    tangent_top = CSTDerivatives.compute_tangent_angles_for_section(
        psi, gene['N1'], gene['N2_top'], weights_fixed, weights_fixed, gene['L']
    )

    tangent_bot = CSTDerivatives.compute_tangent_angles_for_section(
        psi, gene['N1'], gene['N2_bot'], weights_fixed, weights_fixed, gene['L']
    )

    angle_top = tangent_top['top']
    angle_bot = tangent_bot['bottom']

    print(f"{i:^6} {psi:^8.3f} {z_upper:^10.3f} {z_lower:^10.3f} {z_loc:^10.3f} {angle_top:^10.1f} {angle_bot:^10.1f}")

print("\n" + "="*60)
print("🔍 分析:")
print("="*60)

# 檢查幾個關鍵點
print("\n1. 機頭（截面0）:")
print(f"   psi = {curves['psi'][0]:.3f}")
print(f"   z_upper = {curves['z_upper'][0]:.3f} m")
print(f"   z_lower = {curves['z_lower'][0]:.3f} m")
tangent_0_top = CSTDerivatives.compute_tangent_angles_for_section(
    curves['psi'][0], gene['N1'], gene['N2_top'], weights_fixed, weights_fixed, gene['L']
)
tangent_0_bot = CSTDerivatives.compute_tangent_angles_for_section(
    curves['psi'][0], gene['N1'], gene['N2_bot'], weights_fixed, weights_fixed, gene['L']
)
print(f"   角度上: {tangent_0_top['top']:.1f}°")
print(f"   角度下: {tangent_0_bot['bottom']:.1f}°")
print(f"   ⚠️ 預期: 機頭應該對稱，上下角度應該相等（~90°）")

print("\n2. 最大高度處（截面20）:")
idx_20 = 20
print(f"   psi = {curves['psi'][idx_20]:.3f}")
print(f"   z_upper = {curves['z_upper'][idx_20]:.3f} m")
print(f"   z_lower = {curves['z_lower'][idx_20]:.3f} m")
print(f"   z_loc = {curves['z_loc'][idx_20]:.3f} m (截面中心)")
tangent_20_top = CSTDerivatives.compute_tangent_angles_for_section(
    curves['psi'][idx_20], gene['N1'], gene['N2_top'], weights_fixed, weights_fixed, gene['L']
)
tangent_20_bot = CSTDerivatives.compute_tangent_angles_for_section(
    curves['psi'][idx_20], gene['N1'], gene['N2_bot'], weights_fixed, weights_fixed, gene['L']
)
print(f"   角度上: {tangent_20_top['top']:.1f}°")
print(f"   角度下: {tangent_20_bot['bottom']:.1f}°")
print(f"   ⚠️ 問題: 角度計算時是否考慮了Z偏移?")
print(f"         截面中心在 z_loc={curves['z_loc'][idx_20]:.3f}m，而非Z=0")

print("\n3. 機尾（截面39）:")
idx_39 = 39
print(f"   psi = {curves['psi'][idx_39]:.3f}")
print(f"   z_upper = {curves['z_upper'][idx_39]:.3f} m")
print(f"   z_lower = {curves['z_lower'][idx_39]:.3f} m")
tangent_39_top = CSTDerivatives.compute_tangent_angles_for_section(
    curves['psi'][idx_39], gene['N1'], gene['N2_top'], weights_fixed, weights_fixed, gene['L']
)
tangent_39_bot = CSTDerivatives.compute_tangent_angles_for_section(
    curves['psi'][idx_39], gene['N1'], gene['N2_bot'], weights_fixed, weights_fixed, gene['L']
)
print(f"   角度上: {tangent_39_top['top']:.1f}°")
print(f"   角度下: {tangent_39_bot['bottom']:.1f}°")
print(f"   ⚠️ 預期: 機尾應該對稱，上下角度應該相等（~90°）")

print("\n" + "="*60)
print("🔧 可能的問題:")
print("="*60)
print("1. ❓ compute_tangent_angles_for_section() 是否假設截面中心在 Z=0?")
print("   如果是，則當 z_loc≠0 時，上下切線角度可能不正確")
print("")
print("2. ❓ 角度的符號是否正確?")
print("   上邊界應該是正角度（向上），下邊界應該是負角度（向下）?")
print("")
print("3. ❓ VSP的SetXSecTanAngles()如何解釋這些角度?")
print("   需要確認VSP期望的角度方向定義")
print("\n" + "="*60)
