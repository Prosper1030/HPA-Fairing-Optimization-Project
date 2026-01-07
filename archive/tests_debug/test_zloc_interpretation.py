"""測試ZLocPercent的正確解釋"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*60)
print("測試ZLocPercent的解釋")
print("="*60)

# 創建簡單測試
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetParmVal(fuse_id, "Length", "Design", 2.5)

xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

# 改變第1個截面為SUPER_ELLIPSE
vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_SUPER_ELLIPSE)
xsec = vsp.GetXSec(xsec_surf, 1)

# 設置截面參數
vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), 0.5)  # 50%位置
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), 0.6)
vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), 1.3)

print(f"\n📊 測試設置:")
print(f"   機身長度: 2.5 m")
print(f"   截面位置: 50% (X=1.25m)")
print(f"   寬度: 0.6 m")
print(f"   高度: 1.3 m")

# 測試1：設置絕對Z值
print(f"\n🧪 測試1：設置絕對Z值 = 0.3m")
z_loc_parm = vsp.GetXSecParm(xsec, "ZLocPercent")
if z_loc_parm:
    vsp.SetParmVal(z_loc_parm, 0.3)
    vsp.Update()
    actual = vsp.GetParmVal(z_loc_parm)
    print(f"   設置: 0.3")
    print(f"   讀回: {actual:.6f}")

# 測試2：設置相對值（z_loc / L）
print(f"\n🧪 測試2：設置相對值 = 0.3/2.5 = 0.12")
if z_loc_parm:
    vsp.SetParmVal(z_loc_parm, 0.3 / 2.5)
    vsp.Update()
    actual = vsp.GetParmVal(z_loc_parm)
    print(f"   設置: {0.3/2.5:.6f}")
    print(f"   讀回: {actual:.6f}")

# 測試3：讀取Example.vsp3中的值並對比
print(f"\n🔍 對比Example.vsp3:")
vsp.ClearVSPModel()
vsp.ReadVSPFile("output/Example.vsp3")

geoms = vsp.FindGeoms()
if geoms:
    ex_fuse = geoms[0]
    ex_xsec_surf = vsp.GetXSecSurf(ex_fuse, 0)

    # 獲取機身長度
    length_parm = vsp.FindParm(ex_fuse, "Length", "Design")
    if length_parm:
        ex_length = vsp.GetParmVal(length_parm)
        print(f"   Example機身長度: {ex_length:.3f} m")

    # 檢查幾個截面
    for i in [1, 3, 7]:
        ex_xsec = vsp.GetXSec(ex_xsec_surf, i)
        z_parm = vsp.GetXSecParm(ex_xsec, "ZLocPercent")
        if z_parm:
            z_val = vsp.GetParmVal(z_parm)
            print(f"   截面 {i}: ZLocPercent = {z_val:.6f}")
            if ex_length > 0:
                print(f"           => 絕對值 ≈ {z_val * ex_length:.6f} m")

print("\n" + "="*60)
