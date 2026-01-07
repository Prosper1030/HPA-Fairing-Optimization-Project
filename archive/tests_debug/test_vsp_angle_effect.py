"""測試VSP中top/bottom角度的效果"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*60)
print("測試VSP角度效果")
print("="*60)

# 創建3個測試模型
test_cases = [
    {
        'name': 'angle_test_same',
        'desc': '上下角度相同',
        'angle_top': -80.0,
        'angle_bot': -80.0
    },
    {
        'name': 'angle_test_diff',
        'desc': '上下角度不同（模擬當前）',
        'angle_top': -79.8,
        'angle_bot': -72.6
    },
    {
        'name': 'angle_test_avg',
        'desc': '使用平均角度',
        'angle_top': -76.2,  # (-79.8 + -72.6) / 2
        'angle_bot': -76.2
    }
]

for test in test_cases:
    print(f"\n{'='*60}")
    print(f"測試: {test['desc']}")
    print(f"{'='*60}")

    vsp.ClearVSPModel()
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetParmVal(fuse_id, "Length", "Design", 2.5)

    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

    # 3個截面：機頭、中間、機尾
    # 刪除多餘的截面
    while vsp.GetNumXSec(xsec_surf) > 2:
        vsp.CutXSec(xsec_surf, 2)

    # 插入中間截面
    vsp.InsertXSec(fuse_id, 1, vsp.XS_SUPER_ELLIPSE)
    vsp.Update()

    # 設置機頭（截面0）
    xsec_0 = vsp.GetXSec(xsec_surf, 0)
    vsp.ChangeXSecShape(xsec_surf, 0, vsp.XS_POINT)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_0, "XLocPercent"), 0.0)

    # 設置中間截面（截面1）
    xsec_1 = vsp.GetXSec(xsec_surf, 1)
    vsp.ChangeXSecShape(xsec_surf, 1, vsp.XS_SUPER_ELLIPSE)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "XLocPercent"), 0.5)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "Super_Width"), 0.6)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_1, "Super_Height"), 1.3)
    # 設置Z偏移
    z_loc_parm = vsp.GetXSecParm(xsec_1, "ZLocPercent")
    if z_loc_parm:
        vsp.SetParmVal(z_loc_parm, 0.3)

    # 設置機尾（截面2）
    xsec_2 = vsp.GetXSec(xsec_surf, 2)
    vsp.ChangeXSecShape(xsec_surf, 2, vsp.XS_POINT)
    vsp.SetParmVal(vsp.GetXSecParm(xsec_2, "XLocPercent"), 1.0)
    # 機尾Z位置
    z_tail_parm = vsp.GetXSecParm(xsec_2, "ZLocPercent")
    if z_tail_parm:
        vsp.SetParmVal(z_tail_parm, 0.1)

    # 關鍵：設置機尾的切線角度
    vsp.SetXSecContinuity(xsec_2, 1)
    vsp.SetXSecTanAngles(
        xsec_2, vsp.XSEC_BOTH_SIDES,
        test['angle_top'],   # 上
        -80.0,               # 右
        test['angle_bot'],   # 下
        -80.0                # 左
    )

    vsp.Update()

    # 保存
    filename = f"output/{test['name']}.vsp3"
    vsp.WriteVSPFile(filename)

    print(f"   angle_top: {test['angle_top']:.1f}°")
    print(f"   angle_bot: {test['angle_bot']:.1f}°")
    print(f"   差異: {abs(test['angle_top'] - test['angle_bot']):.1f}°")
    print(f"   ✅ 保存: {filename}")

print(f"\n{'='*60}")
print("請在VSP GUI中對比這3個文件：")
print("1. angle_test_same.vsp3 - 上下角度相同")
print("2. angle_test_diff.vsp3 - 上下角度不同（7.2°差異）")
print("3. angle_test_avg.vsp3 - 使用平均角度")
print("")
print("對比側視圖和3D視圖，看哪個的機尾skinning最平滑")
print("="*60)
