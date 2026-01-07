"""調試尾部混合邏輯"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import numpy as np

# 模擬混合過程
psi = np.array([0.8743, 0.8997, 0.9226, 0.9427, 0.9600, 0.9743, 0.9855, 0.9935, 0.9984, 1.0000])
z_upper_cst = np.array([0.2254, 0.1727, 0.1348, 0.1105, 0.0976, 0.0929, 0.0933, 0.0960, 0.0988, 0.1])
tail_rise = 0.1
blend_start = 0.75

# 計算混合因子
blend_factor = np.zeros_like(psi)
mask = psi >= blend_start
psi_blend = (psi[mask] - blend_start) / (1.0 - blend_start)
blend_factor[mask] = psi_blend**2.0

# 初始混合
z_upper_target = z_upper_cst * (1 - blend_factor) + tail_rise * blend_factor
z_upper = np.copy(z_upper_target)

print("="*80)
print("尾部混合邏輯調試")
print("="*80)

print("\n步驟1：初始混合結果")
for i, p in enumerate(psi):
    print(f"psi={p:.4f}, z_cst={z_upper_cst[i]:.4f}, blend={blend_factor[i]:.4f}, z_target={z_upper_target[i]:.4f}")

# 找最低點
blend_indices = np.where(mask)[0]
min_idx = None
min_val = float('inf')
for i, idx in enumerate(blend_indices):
    if z_upper[idx] < min_val:
        min_val = z_upper[idx]
        min_idx = i

print(f"\n步驟2：找到最低點")
print(f"最低點在 blend_indices[{min_idx}] = 截面索引 {blend_indices[min_idx]}, psi={psi[blend_indices[min_idx]]:.4f}, z={z_upper[blend_indices[min_idx]]:.4f}")

# 從最低點後強制線性插值
if min_idx is not None and min_idx < len(blend_indices) - 1:
    start_idx = blend_indices[min_idx]
    start_z = z_upper[start_idx]
    start_psi = psi[start_idx]

    print(f"\n步驟3：從最低點開始線性插值到 tail_rise={tail_rise}")
    print(f"起點：idx={start_idx}, psi={start_psi:.4f}, z={start_z:.4f}")

    for i in range(min_idx + 1, len(blend_indices)):
        idx = blend_indices[i]
        t = (psi[idx] - start_psi) / (1.0 - start_psi)
        z_upper[idx] = start_z + (tail_rise - start_z) * t
        print(f"  idx={idx}, psi={psi[idx]:.4f}, t={t:.4f}, z_new={z_upper[idx]:.4f}")

print("\n步驟4：最終結果")
for i, p in enumerate(psi):
    direction = "↑" if i > 0 and z_upper[i] > z_upper[i-1] else ("↓" if i > 0 and z_upper[i] < z_upper[i-1] else "=")
    print(f"截面{i+30}: psi={p:.4f}, z_upper={z_upper[i]:.4f} {direction}")

print("\n單調性檢查：")
monotonic = True
for i in range(1, len(z_upper)):
    if z_upper[i] > z_upper[i-1]:
        print(f"  ⚠️ 截面{i+30}上升！")
        monotonic = False

if monotonic:
    print("  ✅ 完全單調收斂！")

print("="*80)
