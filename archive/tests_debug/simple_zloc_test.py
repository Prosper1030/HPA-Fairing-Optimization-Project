"""簡化的ZLocPercent測試"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*60)
print("簡化ZLocPercent測試")
print("="*60)

test_cases = [
    ("Test_ZLoc_ZERO", 0.0),
    ("Test_ZLoc_0.3", 0.3),
]

for name, z_val in test_cases:
    vsp.ClearVSPModel()
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetParmVal(fuse_id, "Length", "Design", 2.5)

    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

    # 修改第1個截面（默認是第二個點）
    xsec_1 = vsp.GetXSec(xsec_surf, 1)
    vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_SUPER_ELLIPSE)
    xsec_1 = vsp.GetXSec(xsec_surf, 1)  # 重新獲取

    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "XLocPercent"), 0.5)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "Super_Width"), 0.6)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "Super_Height"), 1.3)

    # 設置Z偏移
    z_parm = vsp.GetXSecParm(xsec_1, "ZLocPercent")
    if z_parm:
        vsp.SetParmVal(z_parm, z_val)

    vsp.Update()
    filename = f"output/{name}.vsp3"
    vsp.WriteVSPFile(filename)

    print(f"\n{name}:")
    print(f"   ZLocPercent = {z_val}")
    print(f"   保存: {filename}")
    if z_val == 0.0:
        print(f"   預期: 對稱, 頂部+0.65m, 底部-0.65m")
    else:
        print(f"   預期: 頂部={z_val+0.65:.2f}m, 底部={z_val-0.65:.2f}m")

print(f"\n{'='*60}")
print("請在VSP中打開並對比側視圖!")
print("如果Test_ZLoc_0.3的底部在-0.35m，說明ZLocPercent是絕對值")
print("="*60)
