"""繪製側視圖曲線 - 上下邊界獨立反推法"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from optimization.hpa_asymmetric_optimizer import CST_Modeler

print("="*60)
print("繪製側視圖曲線 - 上下邊界獨立反推法")
print("="*60)

# 測試基因
gene = {
    'L': 2.5,              # 總長
    'W_max': 0.60,         # 最大全寬
    'H_top_max': 0.95,     # 上半部高度
    'H_bot_max': 0.35,     # 下半部高度
    'N1': 0.5,             # Class function N1
    'N2_top': 0.7,         # Shape function N2 (上)
    'N2_bot': 0.8,         # Shape function N2 (下)
    'X_max_pos': 0.25,     # 最大寬度/高度位置
    'X_offset': 0.7,       # 收縮開始位置
    'Tail_Rise': 0.10,     # 機尾上升高度
}

print(f"\n📊 測試參數:")
print(f"   總長 L = {gene['L']:.2f} m")
print(f"   上高 H_top_max = {gene['H_top_max']:.2f} m")
print(f"   下高 H_bot_max = {gene['H_bot_max']:.2f} m")
print(f"   機尾上升 Tail_Rise = {gene['Tail_Rise']:.2f} m")
print(f"   N1 = {gene['N1']:.2f}, N2_top = {gene['N2_top']:.2f}, N2_bot = {gene['N2_bot']:.2f}")

# 生成psi分布（0到1）
n_points = 100
psi = np.linspace(0, 1, n_points)
x = psi * gene['L']

# 固定權重
weights = np.array([0.25, 0.35, 0.30, 0.10])

print(f"\n🔧 幾何定義:")
print(f"   1. 機頭：兩條曲線都從 (0, 0) 出發")
print(f"   2. 上邊界：向上拱起至最高點 {gene['H_top_max']:.2f} m")
print(f"   3. 下邊界：向下包覆至最低點 {-gene['H_bot_max']:.2f} m")
print(f"   4. 機尾：兩條曲線在 ({gene['L']:.2f}, {gene['Tail_Rise']:.2f}) 交會")

# ==========================================
# 方法：上下邊界獨立反推法（混合法）
# ==========================================

# 關鍵思想：在機尾附近才混合到Tail_Rise
# 1. 前段（psi < blend_start）：正常的CST曲線
# 2. 後段（psi >= blend_start）：CST平滑過渡到Tail_Rise

# 混合參數
blend_start = 0.75  # 從75%位置開始混合
blend_power = 2.0   # 混合曲線的冪次

# === 上邊界曲線 ===
# 生成基礎CST曲線（從0到H_top_max）
z_upper_cst = CST_Modeler.cst_curve(
    psi, gene['H_top_max'], gene['N1'], gene['N2_top'], weights
)

# 混合因子：在blend_start之前為0，在psi=1處為1
# 使用平滑的S曲線過渡
blend_factor = np.zeros_like(psi)
mask = psi >= blend_start
if np.any(mask):
    # 標準化到[0,1]範圍
    psi_blend = (psi[mask] - blend_start) / (1.0 - blend_start)
    # 使用平滑過渡函數
    blend_factor[mask] = psi_blend**blend_power

# 目標線性趨勢：從當前CST值到Tail_Rise
# 在psi=1處，我們希望z = Tail_Rise
linear_target = gene['Tail_Rise']

# 混合：z = z_cst * (1 - blend) + target * blend
z_upper = z_upper_cst * (1 - blend_factor) + linear_target * blend_factor

# === 下邊界曲線 ===
# 為了確保機頭對稱，下邊界使用相同的N1
z_lower_cst = -CST_Modeler.cst_curve(
    psi, gene['H_bot_max'], gene['N1'], gene['N2_bot'], weights
)

# 下邊界使用相同的混合因子
z_lower = z_lower_cst * (1 - blend_factor) + linear_target * blend_factor

print(f"\n📈 生成的曲線:")
print(f"   上邊界 Z 範圍: [{min(z_upper):.3f}, {max(z_upper):.3f}] m")
print(f"   下邊界 Z 範圍: [{min(z_lower):.3f}, {max(z_lower):.3f}] m")
print(f"   機頭處: 上={z_upper[0]:.3f}, 下={z_lower[0]:.3f}")
print(f"   機尾處: 上={z_upper[-1]:.3f}, 下={z_lower[-1]:.3f}")

# 檢查機頭和機尾
nose_gap = abs(z_upper[0] - z_lower[0])
tail_gap = abs(z_upper[-1] - z_lower[-1])

if nose_gap < 0.01:
    print(f"   ✅ 機頭閉合（間隙 {nose_gap:.4f} m）")
else:
    print(f"   ⚠️ 機頭未閉合（間隙 {nose_gap:.4f} m）")

if tail_gap < 0.01:
    print(f"   ✅ 機尾閉合（間隙 {tail_gap:.4f} m）")
else:
    print(f"   ⚠️ 機尾未閉合（間隙 {tail_gap:.4f} m）")

# 計算反推的VSP參數
super_height = z_upper - z_lower  # 總厚度
z_loc = (z_upper + z_lower) / 2   # 幾何中心

print(f"\n🔄 反推的VSP參數:")
print(f"   最大Super_Height: {max(super_height):.3f} m")
print(f"   Z_Loc 範圍: [{min(z_loc):.3f}, {max(z_loc):.3f}] m")

# 繪製側視圖
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

# ===== 左上：完整側視圖 =====
ax1 = axes[0, 0]
ax1.plot(x, z_upper, 'r-', linewidth=2.5, label='上邊界')
ax1.plot(x, z_lower, 'b-', linewidth=2.5, label='下邊界')
ax1.plot([x[0], x[0]], [z_upper[0], z_lower[0]], 'go', markersize=10, label='機頭 (0,0)')
ax1.plot([x[-1], x[-1]], [z_upper[-1], z_lower[-1]], 'mo', markersize=10, label=f'機尾 ({gene["L"]:.1f}, {gene["Tail_Rise"]:.2f})')

# 標註關鍵點
ax1.axhline(y=0, color='k', linestyle='--', alpha=0.3, linewidth=1)
ax1.axhline(y=gene['H_top_max'], color='r', linestyle=':', alpha=0.5, linewidth=1, label=f'期望上高 {gene["H_top_max"]:.2f}m')
ax1.axhline(y=-gene['H_bot_max'], color='b', linestyle=':', alpha=0.5, linewidth=1, label=f'期望下高 {gene["H_bot_max"]:.2f}m')

ax1.grid(True, alpha=0.3)
ax1.set_xlabel('X (m)', fontsize=12, fontweight='bold')
ax1.set_ylabel('Z (m)', fontsize=12, fontweight='bold')
ax1.set_title('完整側視圖（上下邊界獨立）', fontsize=14, fontweight='bold')
ax1.legend(fontsize=10)
ax1.set_aspect('equal')

# ===== 右上：機頭細節 =====
ax2 = axes[0, 1]
nose_range = int(n_points * 0.15)  # 前15%
ax2.plot(x[:nose_range], z_upper[:nose_range], 'r-', linewidth=3, label='上邊界')
ax2.plot(x[:nose_range], z_lower[:nose_range], 'b-', linewidth=3, label='下邊界')
ax2.plot(x[0], z_upper[0], 'go', markersize=12)
ax2.plot(x[0], z_lower[0], 'go', markersize=12)
ax2.axhline(y=0, color='k', linestyle='--', alpha=0.5, linewidth=1.5)
ax2.grid(True, alpha=0.3)
ax2.set_xlabel('X (m)', fontsize=12, fontweight='bold')
ax2.set_ylabel('Z (m)', fontsize=12, fontweight='bold')
ax2.set_title('機頭細節（應指向正前方）', fontsize=14, fontweight='bold')
ax2.legend(fontsize=10)
ax2.set_aspect('equal')

# ===== 左下：機尾細節 =====
ax3 = axes[1, 0]
tail_range = int(n_points * 0.15)
ax3.plot(x[-tail_range:], z_upper[-tail_range:], 'r-', linewidth=3, label='上邊界')
ax3.plot(x[-tail_range:], z_lower[-tail_range:], 'b-', linewidth=3, label='下邊界')
ax3.plot(x[-1], z_upper[-1], 'mo', markersize=12)
ax3.plot(x[-1], z_lower[-1], 'mo', markersize=12)
ax3.axhline(y=gene['Tail_Rise'], color='m', linestyle='--', alpha=0.5, linewidth=1.5, label=f'機尾高度 {gene["Tail_Rise"]:.2f}m')
ax3.grid(True, alpha=0.3)
ax3.set_xlabel('X (m)', fontsize=12, fontweight='bold')
ax3.set_ylabel('Z (m)', fontsize=12, fontweight='bold')
ax3.set_title('機尾細節（應收束成尖點）', fontsize=14, fontweight='bold')
ax3.legend(fontsize=10)
ax3.set_aspect('equal')

# ===== 右下：VSP參數分布 =====
ax4 = axes[1, 1]
ax4_twin = ax4.twinx()

# Super_Height (總厚度)
line1 = ax4.plot(x, super_height, 'g-', linewidth=2.5, label='Super_Height (總厚度)')
ax4.set_xlabel('X (m)', fontsize=12, fontweight='bold')
ax4.set_ylabel('Super_Height (m)', fontsize=12, fontweight='bold', color='g')
ax4.tick_params(axis='y', labelcolor='g')
ax4.grid(True, alpha=0.3)

# Z_Loc (幾何中心)
line2 = ax4_twin.plot(x, z_loc, 'orange', linewidth=2.5, label='Z_Loc (幾何中心)', linestyle='--')
ax4_twin.set_ylabel('Z_Loc (m)', fontsize=12, fontweight='bold', color='orange')
ax4_twin.tick_params(axis='y', labelcolor='orange')
ax4_twin.axhline(y=0, color='k', linestyle='--', alpha=0.3, linewidth=1)

# 合併圖例
lines = line1 + line2
labels = [l.get_label() for l in lines]
ax4.legend(lines, labels, fontsize=10, loc='upper left')

ax4.set_title('反推的VSP參數', fontsize=14, fontweight='bold')

plt.tight_layout()

# 保存圖片
output_file = "output/side_view_curves.png"
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n💾 圖片已保存: {output_file}")

plt.show()

print("\n" + "="*60)
print("請檢查側視圖：")
print("  1. 機頭是否指向正前方（上下對稱於X軸）？")
print("  2. 上邊界是否向上拱起到期望高度？")
print("  3. 下邊界是否向下包覆然後平順上升？")
print("  4. 機尾是否完美閉合成尖點？")
print("="*60)
