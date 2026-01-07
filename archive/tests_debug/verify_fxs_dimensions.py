"""驗證 FILE_FUSE 截面尺寸（從 .fxs 檔案）"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
import numpy as np

# 測試基因
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

print("="*60)
print("驗證 FILE_FUSE 截面尺寸")
print("="*60)

# 讀取模型
vsp.ClearVSPModel()
vsp_file = "output/test_hpa_fixed_params.vsp3"
vsp.ReadVSPFile(vsp_file)

geoms = vsp.FindGeoms()
fuse_id = geoms[0]

print(f"\n📋 期望值:")
print(f"   W_max = {gene['W_max']:.3f} m (全寬)")
print(f"   H_top_max = {gene['H_top_max']:.3f} m")
print(f"   H_bot_max = {gene['H_bot_max']:.3f} m")
print(f"   總高 = {gene['H_top_max'] + gene['H_bot_max']:.3f} m")

# 獲取截面信息
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_xsec = vsp.GetNumXSec(xsec_surf)

print(f"\n📊 檢查 FILE_FUSE 截面:")

# 找到中間截面（應該接近最大尺寸）
target_idx = num_xsec // 2

for i in [target_idx - 1, target_idx, target_idx + 1]:
    if i < 0 or i >= num_xsec:
        continue

    xsec = vsp.GetXSec(xsec_surf, i)

    # 獲取截面類型
    psi_parm = vsp.GetXSecParm(xsec, "XLocPercent")
    if psi_parm:
        psi = vsp.GetParmVal(psi_parm)
    else:
        continue

    # 檢查截面類型
    shape_type = vsp.GetXSecShape(xsec)
    type_name = "UNKNOWN"

    if shape_type == vsp.XS_FILE_FUSE:
        type_name = "FILE_FUSE"
    elif shape_type == vsp.XS_SUPER_ELLIPSE:
        type_name = "SUPER_ELLIPSE"
    elif shape_type == vsp.XS_POINT:
        type_name = "POINT"

    print(f"\n   截面 {i} (psi={psi:.3f}):")
    print(f"      類型: {type_name}")

    # 如果是 FILE_FUSE，讀取對應的 .fxs 檔案
    if shape_type == vsp.XS_FILE_FUSE:
        fxs_file = f"output/xsec_{i:03d}.fxs"
        if os.path.exists(fxs_file):
            # 讀取 .fxs 並計算包絡
            with open(fxs_file, 'r') as f:
                ys = []
                zs = []
                for line in f:
                    parts = line.strip().split()
                    if len(parts) == 2:
                        y, z = map(float, parts)
                        ys.append(y)
                        zs.append(z)

            if ys and zs:
                width = max(ys) - min(ys)
                height_top = max(zs)
                height_bot = abs(min(zs))
                total_height = height_top + height_bot

                print(f"      寬度: {width:.3f} m (從 .fxs)")
                print(f"      上高: {height_top:.3f} m")
                print(f"      下高: {height_bot:.3f} m")
                print(f"      總高: {total_height:.3f} m")
        else:
            print(f"      ⚠️ .fxs 檔案不存在: {fxs_file}")

print(f"\n🔍 全局分析:")

# 讀取所有 .fxs 檔案並找最大值
max_width = 0
max_width_idx = 0
max_total_height = 0

for i in range(1, num_xsec - 1):  # 跳過機頭機尾
    fxs_file = f"output/xsec_{i:03d}.fxs"
    if os.path.exists(fxs_file):
        with open(fxs_file, 'r') as f:
            ys = []
            zs = []
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2:
                    y, z = map(float, parts)
                    ys.append(y)
                    zs.append(z)

        if ys and zs:
            width = max(ys) - min(ys)
            height = max(zs) - min(zs)

            if width > max_width:
                max_width = width
                max_width_idx = i

            if height > max_total_height:
                max_total_height = height

print(f"   最大寬度: {max_width:.3f} m (截面 {max_width_idx})")
print(f"   最大總高: {max_total_height:.3f} m")

# 對比
width_error = abs(max_width - gene['W_max'])
height_error = abs(max_total_height - (gene['H_top_max'] + gene['H_bot_max']))

if width_error < 0.01:
    print(f"   ✅ 寬度正確！誤差: {width_error:.4f} m")
else:
    print(f"   ❌ 寬度錯誤！誤差: {width_error:.4f} m")

if height_error < 0.01:
    print(f"   ✅ 高度正確！誤差: {height_error:.4f} m")
else:
    print(f"   ❌ 高度錯誤！誤差: {height_error:.4f} m")

print("\n" + "="*60)
