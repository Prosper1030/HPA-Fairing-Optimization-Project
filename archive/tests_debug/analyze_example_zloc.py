"""詳細分析Example.vsp3的ZLoc使用方式"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*80)
print("分析Example.vsp3的ZLoc使用方式")
print("="*80)

vsp.ClearVSPModel()
vsp.ReadVSPFile("output/current/Example.vsp3")

geoms = vsp.FindGeoms()
fuse_id = geoms[0]

# 獲取機身長度
length_parm = vsp.FindParm(fuse_id, "Length", "Design")
if length_parm:
    length = vsp.GetParmVal(length_parm)
    print(f"\n機身長度: {length:.3f} m")

xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_xsec = vsp.GetNumXSec(xsec_surf)

print(f"截面數量: {num_xsec}")
print("\n" + "-"*80)
print(f"{'截面':^6} {'XLocPercent':^15} {'ZLocPercent':^15} {'X實際位置':^15} {'Z可能含義':^20}")
print("-"*80)

for i in range(num_xsec):
    xsec = vsp.GetXSec(xsec_surf, i)

    x_parm = vsp.GetXSecParm(xsec, "XLocPercent")
    z_parm = vsp.GetXSecParm(xsec, "ZLocPercent")

    x_percent = vsp.GetParmVal(x_parm) if x_parm else 0
    z_percent = vsp.GetParmVal(z_parm) if z_parm else 0

    x_actual = x_percent * length if x_parm else 0

    # ZLocPercent可能的含義
    if abs(z_percent) < 0.1:
        z_meaning = f"{z_percent:.6f} (可能是絕對值)"
    else:
        z_meaning = f"{z_percent:.6f}"

    print(f"{i:^6} {x_percent:^15.6f} {z_percent:^15.6f} {x_actual:^15.3f} {z_meaning:^20}")

print("-"*80)
print("\n🔍 關鍵觀察:")
print("   1. XLocPercent: 明確是百分比 (0.0 - 1.0)")
print("   2. ZLocPercent: 需要確定是絕對值還是百分比")
print("   3. 如果Example工作正常，我們應該使用相同的方式")
print("="*80)
