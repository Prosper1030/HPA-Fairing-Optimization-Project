"""直接測試VSP的ZLocPercent行為"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*60)
print("理解VSP的ZLocPercent")
print("="*60)

# 創建3個測試模型來對比
test_cases = [
    {"name": "Test_ZLoc_0", "z_loc": 0.0, "desc": "無偏移（對稱）"},
    {"name": "Test_ZLoc_0.3", "z_loc": 0.3, "desc": "絕對偏移0.3m"},
    {"name": "Test_ZLoc_0.12", "z_loc": 0.12, "desc": "相對偏移0.12(=0.3/2.5)"},
]

for test in test_cases:
    print(f"\n{'='*60}")
    print(f"測試: {test['desc']}")
    print(f"{'='*60}")

    vsp.ClearVSPModel()
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetParmVal(fuse_id, "Length", "Design", 2.5)

    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

    # 只保留3個截面：機頭、中間、機尾
    vsp.CutXSec(xsec_surf, 2)  # 刪除多餘的
    vsp.InsertXSec(fuse_id, 1, vsp.XS_SUPER_ELLIPSE)
    vsp.Update()

    # 設置機頭（截面0）- POINT
    xsec_0 = vsp.GetXSec(xsec_surf, 0)
    vsp.ChangeXSecShape(xsec_surf, 0, vsp.XS_POINT)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_0, "XLocPercent"), 0.0)

    # 設置中間截面（截面1）- SUPER_ELLIPSE
    xsec_1 = vsp.GetXSec(xsec_surf, 1)
    vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_SUPER_ELLIPSE)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "XLocPercent"), 0.5)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "Super_Width"), 0.6)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "Super_Height"), 1.3)  # 上0.65m, 下-0.65m
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "Super_M"), 2.5)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "Super_N"), 2.5)

    # 關鍵：設置ZLocPercent
    z_loc_parm = vsp.GetXSecParm(xsec_1, "ZLocPercent")
    if z_loc_parm:
        vsp.SetParmVal(z_loc_parm, test['z_loc'])
        print(f"   設置ZLocPercent = {test['z_loc']}")

    # 設置機尾（截面2）- POINT
    xsec_2 = vsp.GetXSec(xsec_surf, 2)
    vsp.ChangeXSecShape(xsec_surf, 2, vsp.XS_POINT)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_2, "XLocPercent"), 1.0)

    vsp.Update()

    # 保存
    filename = f"output/{test['name']}.vsp3"
    vsp.WriteVSPFile(filename)
    print(f"   ✅ 保存: {filename}")

    # 預測結果
    if test['z_loc'] == 0.0:
        print(f"   預期: 截面中心在Z=0, 頂部+0.65m, 底部-0.65m（對稱）")
    else:
        print(f"   如果是絕對偏移: 中心在Z={test['z_loc']}, 頂部={test['z_loc']+0.65:.2f}m, 底部={test['z_loc']-0.65:.2f}m")

print(f"\n{'='*60}")
print("請在VSP GUI中打開這3個文件對比：")
print("1. Test_ZLoc_0.vsp3 - 對稱基準")
print("2. Test_ZLoc_0.3.vsp3 - 測試絕對偏移")
print("3. Test_ZLoc_0.12.vsp3 - 測試相對偏移")
print("")
print("對比側視圖，看哪個的位置符合預期：")
print("- 如果0.3版本的底部在Z=-0.35m，說明是絕對值")
print("- 如果0.12版本的底部在Z=-0.35m，說明需要除以L")
print("="*60)
