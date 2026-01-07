"""測試4種不同的ZLoc設定方法"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
from optimization.hpa_asymmetric_optimizer import CST_Modeler
import numpy as np

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

curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

methods = [
    {
        'name': 'method1_absolute',
        'desc': '方法1: ZLoc = z_loc (絕對值，當前方法)',
        'calc': lambda i: curves['z_loc'][i]
    },
    {
        'name': 'method2_normalized_by_length',
        'desc': '方法2: ZLoc = z_loc / Length',
        'calc': lambda i: curves['z_loc'][i] / gene['L']
    },
    {
        'name': 'method3_normalized_by_height',
        'desc': '方法3: ZLoc = z_loc / H_top_max',
        'calc': lambda i: curves['z_loc'][i] / gene['H_top_max']
    },
    {
        'name': 'method4_zero',
        'desc': '方法4: ZLoc = 0 (不設定，全部在Z=0)',
        'calc': lambda i: 0.0
    },
]

print("="*80)
print("生成4種不同ZLoc設定方法的測試檔案")
print("="*80)

for method in methods:
    print(f"\n📝 {method['desc']}")

    vsp.ClearVSPModel()
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse_id, f"Test_{method['name']}")

    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

    # 調整截面數量（使用InsertXSec而不是清除重建）
    current_num = vsp.GetNumXSec(xsec_surf)
    target_num = 40

    while current_num < target_num:
        vsp.InsertXSec(fuse_id, current_num - 1, vsp.XS_SUPER_ELLIPSE)
        current_num = vsp.GetNumXSec(xsec_surf)

    vsp.Update()

    # 設置每個截面
    for i in range(40):
        psi = curves['psi'][i]
        is_nose = (i == 0)
        is_tail = (i == 39)

        total_width = curves['width_half'][i] * 2.0
        total_height = curves['super_height'][i]

        # 使用當前方法計算ZLoc
        z_loc_value = method['calc'](i)

        if is_nose or is_tail:
            vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
        else:
            vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)

        xsec = vsp.GetXSec(xsec_surf, i)

        vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

        z_loc_parm = vsp.GetXSecParm(xsec, "ZLocPercent")
        if z_loc_parm:
            vsp.SetParmVal(z_loc_parm, z_loc_value)

        if not (is_nose or is_tail):
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), total_width)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), total_height)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), 2.5)

    vsp.Update()

    # 保存
    filename = f"output/{method['name']}.vsp3"
    vsp.WriteVSPFile(filename)

    print(f"   ✅ 保存: {filename}")

    # 顯示關鍵截面的ZLoc值
    print(f"   截面16 ZLoc: {method['calc'](16):.6f}")

print("\n" + "="*80)
print("請在VSP GUI中打開這4個檔案，找出哪個位置正確:")
print("="*80)
for method in methods:
    print(f"   {method['name']}.vsp3")
print("\n正確的應該是：下邊界最低點約在Z = -0.35m")
print("="*80)
