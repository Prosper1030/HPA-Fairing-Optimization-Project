"""診斷模型尺寸是否正確"""
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
print("模型尺寸診斷")
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
print(f"   X_max_pos = {gene['X_max_pos']:.3f}")

# 獲取截面信息
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_xsec = vsp.GetNumXSec(xsec_surf)

print(f"\n📊 實際截面尺寸:")

max_width = 0
max_width_psi = 0
max_height = 0

for i in range(num_xsec):
    xsec = vsp.GetXSec(xsec_surf, i)

    # 獲取位置
    psi_parm = vsp.GetXSecParm(xsec, "XLocPercent")
    if psi_parm:
        psi = vsp.GetParmVal(psi_parm)
    else:
        continue

    # 嘗試獲取寬度和高度
    width_parm = vsp.GetXSecParm(xsec, "Width")
    height_parm = vsp.GetXSecParm(xsec, "Height")

    if width_parm and height_parm:
        width = vsp.GetParmVal(width_parm)
        height = vsp.GetParmVal(height_parm)

        if width > max_width:
            max_width = width
            max_width_psi = psi

        if height > max_height:
            max_height = height

        # 在目標位置附近打印詳細信息
        if abs(psi - gene['X_max_pos']) < 0.05:
            top_str_parm = vsp.GetXSecParm(xsec, "TopStr")
            bot_str_parm = vsp.GetXSecParm(xsec, "BotStr")

            top_str = vsp.GetParmVal(top_str_parm) if top_str_parm else 0
            bot_str = vsp.GetParmVal(bot_str_parm) if bot_str_parm else 0

            print(f"   截面 {i} (psi={psi:.3f}):")
            print(f"      Width  = {width:.3f} m")
            print(f"      Height = {height:.3f} m")
            print(f"      TopStr = {top_str:.3f}")
            print(f"      BotStr = {bot_str:.3f}")

print(f"\n📈 全局最大值:")
print(f"   最大寬度: {max_width:.3f} m (psi={max_width_psi:.3f})")
print(f"   最大高度: {max_height:.3f} m")

print(f"\n🔍 對比分析:")
width_error = abs(max_width - gene['W_max'])
total_height = gene['H_top_max'] + gene['H_bot_max']
height_error = abs(max_height - total_height)

if width_error < 0.01:
    print(f"   ✅ 寬度正確！誤差: {width_error:.4f} m")
else:
    print(f"   ❌ 寬度錯誤！誤差: {width_error:.4f} m")
    print(f"      可能問題: W_max 需要除以 2 或乘以 2")

if height_error < 0.01:
    print(f"   ✅ 高度正確！誤差: {height_error:.4f} m")
else:
    print(f"   ❌ 高度錯誤！誤差: {height_error:.4f} m")

max_psi_error = abs(max_width_psi - gene['X_max_pos'])
if max_psi_error < 0.05:
    print(f"   ✅ 最大位置正確！誤差: {max_psi_error:.4f}")
else:
    print(f"   ⚠️ 最大位置偏移: 期望 {gene['X_max_pos']:.3f}, 實際 {max_width_psi:.3f}")

print("\n" + "="*60)
