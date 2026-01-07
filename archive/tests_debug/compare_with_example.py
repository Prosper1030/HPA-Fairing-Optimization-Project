"""對比Example.vsp3和我們的模型，找出差異"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*80)
print("對比Example.vsp3和我們的模型")
print("="*80)

# 讀取Example.vsp3
print("\n📊 Example.vsp3:")
vsp.ClearVSPModel()
vsp.ReadVSPFile("output/current/Example.vsp3")

geoms = vsp.FindGeoms()
if geoms:
    fuse_id = geoms[0]
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

    print(f"   截面數量: {vsp.GetNumXSec(xsec_surf)}")

    # 檢查一個中間截面
    xsec = vsp.GetXSec(xsec_surf, 2)

    # 檢查關鍵參數
    print("\n   可用參數:")
    params_to_check = ["ZLocPercent", "Z_Offset", "ZLoc", "Z"]

    for param_name in params_to_check:
        parm = vsp.GetXSecParm(xsec, param_name)
        if parm:
            value = vsp.GetParmVal(parm)
            print(f"      {param_name}: {value:.6f}")
        else:
            print(f"      {param_name}: (不存在)")

# 讀取我們的模型
print("\n📊 fairing_zloc_fixed_v2.vsp3:")
vsp.ClearVSPModel()
vsp.ReadVSPFile("output/current/fairing_zloc_fixed_v2.vsp3")

geoms = vsp.FindGeoms()
if geoms:
    fuse_id = geoms[0]
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

    print(f"   截面數量: {vsp.GetNumXSec(xsec_surf)}")

    # 檢查截面16（對應GUI中的Xsec_16）
    xsec = vsp.GetXSec(xsec_surf, 16)

    print("\n   可用參數:")
    for param_name in params_to_check:
        parm = vsp.GetXSecParm(xsec, param_name)
        if parm:
            value = vsp.GetParmVal(parm)
            print(f"      {param_name}: {value:.6f}")
        else:
            print(f"      {param_name}: (不存在)")

    # 獲取高度
    height_parm = vsp.GetXSecParm(xsec, "Super_Height")
    if height_parm:
        height = vsp.GetParmVal(height_parm)
        print(f"\n   Super_Height: {height:.6f}")

print("\n" + "="*80)
print("🔍 分析:")
print("   如果Example.vsp3使用了不同的參數名稱，我們需要改用相同的")
print("="*80)
