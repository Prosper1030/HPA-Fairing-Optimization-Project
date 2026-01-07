"""直接從z_upper和z_lower曲線計算切線角度"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from optimization.hpa_asymmetric_optimizer import CST_Modeler
import numpy as np
import math

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
print("直接計算z_upper和z_lower的斜率")
print("="*80)

# 計算每個截面的切線角度（使用有限差分）
x = curves['x']
z_upper = curves['z_upper']
z_lower = curves['z_lower']

print(f"\n{'截面':^6} {'X':^10} {'dz_up/dx':^12} {'角度上':^10} {'dz_low/dx':^12} {'角度下':^10}")
print("-" * 70)

angles_top_new = []
angles_bot_new = []

for i in range(len(x)):
    # 使用中心差分計算斜率
    if i == 0:
        # 前向差分
        dz_upper_dx = (z_upper[i+1] - z_upper[i]) / (x[i+1] - x[i])
        dz_lower_dx = (z_lower[i+1] - z_lower[i]) / (x[i+1] - x[i])
    elif i == len(x) - 1:
        # 後向差分
        dz_upper_dx = (z_upper[i] - z_upper[i-1]) / (x[i] - x[i-1])
        dz_lower_dx = (z_lower[i] - z_lower[i-1]) / (x[i] - x[i-1])
    else:
        # 中心差分
        dz_upper_dx = (z_upper[i+1] - z_upper[i-1]) / (x[i+1] - x[i-1])
        dz_lower_dx = (z_lower[i+1] - z_lower[i-1]) / (x[i+1] - x[i-1])

    # 轉換為角度
    angle_top = math.degrees(math.atan(dz_upper_dx))
    angle_bot = math.degrees(math.atan(dz_lower_dx))

    angles_top_new.append(angle_top)
    angles_bot_new.append(angle_bot)

    if i in [0, 5, 10, 15, 20, 25, 30, 35, 39]:
        print(f"{i:^6} {x[i]:^10.3f} {dz_upper_dx:^12.3f} {angle_top:^10.1f} {dz_lower_dx:^12.3f} {angle_bot:^10.1f}")

print("\n" + "="*80)
print("🔍 觀察:")
print("="*80)
print("1. 這些角度是直接從z_upper(x)和z_lower(x)的斜率計算的")
print("2. 機頭（截面0）：上下角度應該非常接近（幾何對稱）")
print("3. 中間截面：上下角度可以不同（反映非對稱形狀）")
print("4. 機尾（截面39）：上下角度應該非常接近（幾何對稱）")
print("\n如果這些角度看起來更合理，我會用這個方法替換當前的角度計算")
print("="*80)
