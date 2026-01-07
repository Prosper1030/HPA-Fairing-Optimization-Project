"""檢查archive中舊版本的ZLoc值"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*80)
print("檢查archive中的test_new_geometry.vsp3")
print("="*80)

vsp.ClearVSPModel()
vsp.ReadVSPFile("output/archive/test_new_geometry.vsp3")

geoms = vsp.FindGeoms()
if not geoms:
    print("找不到幾何體")
else:
    fuse_id = geoms[0]
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

    print(f"\n檢查關鍵截面的ZLocPercent值:")
    print("-" * 60)
    print(f"{'截面':^6} {'ZLocPercent':^15}")
    print("-" * 60)

    for i in [0, 10, 16, 20, 30, 39]:
        if i >= vsp.GetNumXSec(xsec_surf):
            continue

        xsec = vsp.GetXSec(xsec_surf, i)
        z_parm = vsp.GetXSecParm(xsec, "ZLocPercent")

        if z_parm:
            z_val = vsp.GetParmVal(z_parm)
            print(f"{i:^6} {z_val:^15.6f}")

    print("-" * 60)
    print("\n如果這些值很小（<0.1），可能問題出在我們需要歸一化")
    print("="*80)
