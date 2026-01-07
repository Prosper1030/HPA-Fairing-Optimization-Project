"""找出最大值位置並對比期望"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from optimization.hpa_asymmetric_optimizer import CST_Modeler
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

# 找最大/最小值
max_upper_idx = np.argmax(curves['z_upper'])
min_lower_idx = np.argmin(curves['z_lower'])

print("="*60)
print("最大/最小值位置分析")
print("="*60)

print(f"\n📊 期望值:")
print(f"   H_top_max: {gene['H_top_max']:.3f} m")
print(f"   H_bot_max: {gene['H_bot_max']:.3f} m (絕對值)")
print(f"   期望下邊界最小: {-gene['H_bot_max']:.3f} m")

print(f"\n🔍 實際最大值位置:")
print(f"   截面 {max_upper_idx}:")
print(f"      psi = {curves['psi'][max_upper_idx]:.3f}")
print(f"      X = {curves['x'][max_upper_idx]:.3f} m")
print(f"      z_upper = {curves['z_upper'][max_upper_idx]:.3f} m")
print(f"      z_lower = {curves['z_lower'][max_upper_idx]:.3f} m")
print(f"      super_height = {curves['super_height'][max_upper_idx]:.3f} m")
print(f"      z_loc = {curves['z_loc'][max_upper_idx]:.3f} m")
print(f"")
print(f"   計算驗證:")
print(f"      z_loc + height/2 = {curves['z_loc'][max_upper_idx] + curves['super_height'][max_upper_idx]/2:.3f} m")
print(f"      (應等於z_upper = {curves['z_upper'][max_upper_idx]:.3f} m)")

print(f"\n🔍 實際最小值位置:")
print(f"   截面 {min_lower_idx}:")
print(f"      psi = {curves['psi'][min_lower_idx]:.3f}")
print(f"      X = {curves['x'][min_lower_idx]:.3f} m")
print(f"      z_upper = {curves['z_upper'][min_lower_idx]:.3f} m")
print(f"      z_lower = {curves['z_lower'][min_lower_idx]:.3f} m")
print(f"      super_height = {curves['super_height'][min_lower_idx]:.3f} m")
print(f"      z_loc = {curves['z_loc'][min_lower_idx]:.3f} m")
print(f"")
print(f"   計算驗證:")
print(f"      z_loc - height/2 = {curves['z_loc'][min_lower_idx] - curves['super_height'][min_lower_idx]/2:.3f} m")
print(f"      (應等於z_lower = {curves['z_lower'][min_lower_idx]:.3f} m)")

# 檢查誤差
upper_error = gene['H_top_max'] - curves['z_upper'][max_upper_idx]
lower_error = -gene['H_bot_max'] - curves['z_lower'][min_lower_idx]

print(f"\n📏 誤差分析:")
print(f"   上邊界誤差: {abs(upper_error)*1000:.1f} mm ({abs(upper_error)/gene['H_top_max']*100:.2f}%)")
print(f"   下邊界誤差: {abs(lower_error)*1000:.1f} mm ({abs(lower_error)/gene['H_bot_max']*100:.2f}%)")

if abs(upper_error) < 0.01 and abs(lower_error) < 0.01:
    print(f"   ✅ 誤差在可接受範圍內（<10mm）")
else:
    print(f"   ⚠️ 誤差較大，可能需要調整")

print("\n" + "="*60)
