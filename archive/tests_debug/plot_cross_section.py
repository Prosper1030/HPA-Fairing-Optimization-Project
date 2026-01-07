"""繪製截面形狀，驗證上下非對稱"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import matplotlib.pyplot as plt
import numpy as np
from optimization.hpa_asymmetric_optimizer import CST_Modeler

print("="*60)
print("繪製截面形狀 - 驗證上下非對稱")
print("="*60)

# 測試參數（應該產生上圓下平）
y_half = 0.30  # 半寬 30 cm
z_top = 0.95   # 上高 95 cm（大）
z_bot = 0.35   # 下高 35 cm（小）
exponent = 2.5

print(f"\n📊 測試參數:")
print(f"   半寬 y_half = {y_half:.2f} m")
print(f"   上高 z_top = {z_top:.2f} m (應該比下高大)")
print(f"   下高 z_bot = {z_bot:.2f} m (應該比上高小)")
print(f"   超橢圓指數 = {exponent}")

# 生成截面點
points = CST_Modeler.generate_super_ellipse_profile(
    y_half, z_top, z_bot, n_points=60, exponent=exponent
)

# 提取 Y 和 Z 座標
ys = [pt[1] for pt in points]
zs = [pt[2] for pt in points]

print(f"\n📈 生成的點:")
print(f"   總點數: {len(points)}")
print(f"   Y 範圍: [{min(ys):.3f}, {max(ys):.3f}]")
print(f"   Z 範圍: [{min(zs):.3f}, {max(zs):.3f}]")

# 分析上下高度
z_max = max(zs)  # 最大 Z（頂部）
z_min = min(zs)  # 最小 Z（底部）

print(f"\n🔍 分析:")
print(f"   頂部高度: {z_max:.3f} m (期望 ≈ {z_top:.3f} m)")
print(f"   底部高度: {abs(z_min):.3f} m (期望 ≈ {z_bot:.3f} m)")

if abs(z_max - z_top) < 0.01:
    print(f"   ✅ 頂部正確")
else:
    print(f"   ❌ 頂部錯誤！差異 {abs(z_max - z_top):.4f} m")

if abs(abs(z_min) - z_bot) < 0.01:
    print(f"   ✅ 底部正確")
else:
    print(f"   ❌ 底部錯誤！差異 {abs(abs(z_min) - z_bot):.4f} m")

# 檢查對稱性
if abs(z_max - abs(z_min)) < 0.01:
    print(f"\n⚠️⚠️⚠️ 警告：上下高度幾乎相等，沒有非對稱！")
else:
    print(f"\n✅ 上下非對稱：上下高度差 {abs(z_max - abs(z_min)):.3f} m")

# 繪製截面
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# 左圖：完整截面
ax1.plot(ys, zs, 'b-', linewidth=2, label='截面輪廓')
ax1.plot(ys[0], zs[0], 'ro', markersize=8, label='起點/終點')
ax1.axhline(y=0, color='k', linestyle='--', alpha=0.3, label='中心線')
ax1.axhline(y=z_top, color='r', linestyle='--', alpha=0.5, label=f'期望上高 {z_top:.2f}m')
ax1.axhline(y=-z_bot, color='g', linestyle='--', alpha=0.5, label=f'期望下高 {z_bot:.2f}m')
ax1.grid(True, alpha=0.3)
ax1.set_xlabel('Y (m)', fontsize=12)
ax1.set_ylabel('Z (m)', fontsize=12)
ax1.set_title('截面形狀（應該上圓下平）', fontsize=14, fontweight='bold')
ax1.legend()
ax1.set_aspect('equal')

# 右圖：上下半部分開顯示
# 分離上下半部
upper_points = [(y, z) for y, z in zip(ys, zs) if z >= 0]
lower_points = [(y, z) for y, z in zip(ys, zs) if z <= 0]

if upper_points:
    upper_y, upper_z = zip(*upper_points)
    ax2.plot(upper_y, upper_z, 'r-', linewidth=2, label=f'上半部 (max={max(upper_z):.3f}m)')

if lower_points:
    lower_y, lower_z = zip(*lower_points)
    ax2.plot(lower_y, lower_z, 'b-', linewidth=2, label=f'下半部 (min={min(lower_z):.3f}m)')

ax2.axhline(y=0, color='k', linestyle='-', alpha=0.5)
ax2.grid(True, alpha=0.3)
ax2.set_xlabel('Y (m)', fontsize=12)
ax2.set_ylabel('Z (m)', fontsize=12)
ax2.set_title('上下半部對比', fontsize=14, fontweight='bold')
ax2.legend()
ax2.set_aspect('equal')

plt.tight_layout()

# 保存圖片
output_file = "output/cross_section_plot.png"
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n💾 圖片已保存: {output_file}")

plt.show()

print("\n" + "="*60)
