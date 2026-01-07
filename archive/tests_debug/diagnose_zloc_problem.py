"""診斷Z位置問題"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
import numpy as np

print("="*60)
print("診斷Z位置問題")
print("="*60)

# 讀取我們生成的模型
vsp.ClearVSPModel()
vsp.ReadVSPFile("output/test_new_geometry.vsp3")

geoms = vsp.FindGeoms()
if not geoms:
    print("❌ 找不到幾何體")
    sys.exit(1)

fuse_id = geoms[0]
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_xsec = vsp.GetNumXSec(xsec_surf)

print(f"\n📋 截面參數分析:")
print(f"{'截面':^6} {'X%':^8} {'Width':^8} {'Height':^8} {'Z值':^10} {'計算頂部':^10} {'計算底部':^10}")
print("-" * 70)

for i in [0, 10, 20, 30, 39]:
    if i >= num_xsec:
        continue

    xsec = vsp.GetXSec(xsec_surf, i)
    shape = vsp.GetXSecShape(xsec)

    x_parm = vsp.GetXSecParm(xsec, "XLocPercent")
    x_loc = vsp.GetParmVal(x_parm) if x_parm else 0

    if shape == vsp.XS_SUPER_ELLIPSE:
        w_parm = vsp.GetXSecParm(xsec, "Super_Width")
        h_parm = vsp.GetXSecParm(xsec, "Super_Height")
        z_parm = vsp.GetXSecParm(xsec, "ZLocPercent")

        width = vsp.GetParmVal(w_parm) if w_parm else 0
        height = vsp.GetParmVal(h_parm) if h_parm else 0
        z_loc = vsp.GetParmVal(z_parm) if z_parm else 0

        # 計算實際頂部和底部位置
        calc_top = z_loc + height/2
        calc_bot = z_loc - height/2

        print(f"{i:^6} {x_loc:^8.3f} {width:^8.3f} {height:^8.3f} {z_loc:^10.3f} {calc_top:^10.3f} {calc_bot:^10.3f}")
    else:
        type_name = "POINT" if shape == vsp.XS_POINT else "OTHER"
        print(f"{i:^6} {x_loc:^8.3f} {type_name:^8} {'-':^8} {'-':^10} {'-':^10} {'-':^10}")

# 對比期望值
print(f"\n🎯 期望值:")
print(f"   上邊界最大值: 0.953 m（應該在psi≈0.42處）")
print(f"   下邊界最小值: -0.350 m（應該在psi≈0.50處）")

# 檢查截面20（大約中間位置）
print(f"\n🔍 截面20詳細檢查:")
xsec_20 = vsp.GetXSec(xsec_surf, 20)
z_parm_20 = vsp.GetXSecParm(xsec_20, "ZLocPercent")
h_parm_20 = vsp.GetXSecParm(xsec_20, "Super_Height")

if z_parm_20 and h_parm_20:
    z_20 = vsp.GetParmVal(z_parm_20)
    h_20 = vsp.GetParmVal(h_parm_20)

    print(f"   ZLocPercent: {z_20:.6f} m")
    print(f"   Super_Height: {h_20:.6f} m")
    print(f"   計算頂部: {z_20 + h_20/2:.6f} m")
    print(f"   計算底部: {z_20 - h_20/2:.6f} m")

    # 檢查這是否符合我們的設計
    print(f"\n   ⚠️ 分析:")
    if z_20 > 0.2:
        print(f"   ZLocPercent = {z_20:.3f}m 看起來太大了!")
        print(f"   這會導致整個截面向上偏移{z_20:.3f}m")
        print(f"   ")
        print(f"   🔧 可能的問題:")
        print(f"   - ZLocPercent應該相對於機身長度標準化?")
        print(f"   - 或者ZLocPercent的含義與我們理解的不同?")

print("\n" + "="*60)

# 創建一個對比測試
print(f"\n🧪 創建對比測試（ZLocPercent = 0）...")

vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetParmVal(fuse_id, "Length", "Design", 2.5)

xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
vsp.InsertXSec(fuse_id, 1, vsp.XS_SUPER_ELLIPSE)
vsp.Update()

# 設置中間截面
xsec_test = vsp.GetXSec(xsec_surf, 1)
vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_SUPER_ELLIPSE)
xsec_test = vsp.GetXSec(xsec_surf, 1)

vsp.SetParmVal(vsp.GetXSecParm(xsec_test, "XLocPercent"), 0.5)
vsp.SetParmVal(vsp.GetXSecParm(xsec_test, "Super_Width"), 0.6)
vsp.SetParmVal(vsp.GetXSecParm(xsec_test, "Super_Height"), 1.3)

# 設置ZLocPercent = 0
z_test_parm = vsp.GetXSecParm(xsec_test, "ZLocPercent")
if z_test_parm:
    vsp.SetParmVal(z_test_parm, 0.0)

vsp.Update()
vsp.WriteVSPFile("output/test_zloc_zero.vsp3")

print(f"   ✅ 保存至: output/test_zloc_zero.vsp3")
print(f"   請在GUI中對比此文件與test_new_geometry.vsp3")

print("\n" + "="*60)
