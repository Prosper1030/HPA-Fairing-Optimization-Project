"""診斷尾部扭曲問題"""
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
print("尾部診斷報告")
print("="*80)

# 檢查最後10個截面
tail_sections = range(30, 40)

print(f"\n{'截面':<6} {'psi':<8} {'X':<10} {'z_upper':<10} {'z_lower':<10} {'寬度':<10} {'高度':<10} {'Top角':<10} {'Bot角':<10}")
print("-"*100)

for i in tail_sections:
    psi = curves['psi'][i]
    x = curves['x'][i]
    z_upper = curves['z_upper'][i]
    z_lower = curves['z_lower'][i]
    width = curves['width_half'][i] * 2.0
    height = curves['super_height'][i]

    if i < 39:  # 不是最後一個點截面
        angles = CSTDerivatives.compute_asymmetric_tangent_angles(
            curves['x'], curves['z_upper'], curves['z_lower'], i
        )
        angle_top = angles['top']
        angle_bot = angles['bottom']
    else:
        angle_top = angle_bot = "Point"

    print(f"{i:<6} {psi:<8.4f} {x:<10.4f} {z_upper:<10.4f} {z_lower:<10.4f} {width:<10.4f} {height:<10.4f} {str(angle_top):<10} {str(angle_bot):<10}")

print("\n" + "="*80)
print("關鍵觀察:")
print("="*80)
print("\n1. 尾部收縮檢查：")
print(f"   - 截面30 (psi=0.874): 寬度={curves['width_half'][30]*2:.4f}, 高度={curves['super_height'][30]:.4f}")
print(f"   - 截面35 (psi=0.961): 寬度={curves['width_half'][35]*2:.4f}, 高度={curves['super_height'][35]:.4f}")
print(f"   - 截面38 (psi=0.998): 寬度={curves['width_half'][38]*2:.4f}, 高度={curves['super_height'][38]:.4f}")
print(f"   - 截面39 (psi=1.000): Point截面")

print("\n2. Z位置檢查：")
print(f"   - Tail_Rise = {curves.get('Tail_Rise', 0.1):.4f}m")
print(f"   - 截面38: z_upper={curves['z_upper'][38]:.4f}, z_lower={curves['z_lower'][38]:.4f}")
print(f"   - 截面39: z_upper={curves['z_upper'][39]:.4f}, z_lower={curves['z_lower'][39]:.4f}")

print("\n3. 角度變化：")
for i in range(35, 39):
    angles = CSTDerivatives.compute_asymmetric_tangent_angles(
        curves['x'], curves['z_upper'], curves['z_lower'], i
    )
    diff = abs(angles['top'] - angles['bottom'])
    print(f"   - 截面{i}: Top={angles['top']:.2f}°, Bot={angles['bottom']:.2f}°, 差={diff:.2f}°")

print("\n可能問題：")
print("   1. 尾部截面太接近時，角度計算可能不穩定")
print("   2. 最後幾個截面的Strength可能需要調整")
print("   3. 尾部Point截面的角度設置可能需要改進")
print("="*80)
