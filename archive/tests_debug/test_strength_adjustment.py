"""測試不同的Strength設定來改善skinning平滑度"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
from optimization.hpa_asymmetric_optimizer import CST_Modeler, CSTDerivatives
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
weights_fixed = [0.25, 0.35, 0.30, 0.10]

print("="*80)
print("測試不同Strength設定")
print("="*80)

vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetGeomName(fuse_id, "Strength_Test")

xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

# 調整截面數量
current_num = vsp.GetNumXSec(xsec_surf)
while current_num < 40:
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
    z_loc_value = curves['z_loc'][i]

    if is_nose or is_tail:
        vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
    else:
        vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)

    xsec = vsp.GetXSec(xsec_surf, i)

    vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

    # ZLoc歸一化
    z_loc_parm = vsp.GetXSecParm(xsec, "ZLocPercent")
    if z_loc_parm:
        z_loc_normalized = z_loc_value / curves['L']
        vsp.SetParmVal(z_loc_parm, z_loc_normalized)

    if not (is_nose or is_tail):
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), total_width)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), total_height)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), 2.5)

        # 對稱檢查
        z_upper_val = curves['z_upper'][i]
        z_lower_val = curves['z_lower'][i]
        is_symmetric = abs(z_upper_val - z_lower_val) < 0.02

        N1 = curves['N1']
        N2_top = curves['N2_top']
        N2_bot = curves['N2_bot']
        N2_avg = curves['N2_avg']

        if is_symmetric:
            tangent_both = CSTDerivatives.compute_tangent_angles_for_section(
                psi, N1, N2_avg, weights_fixed, weights_fixed, curves['L']
            )
            angle_top_use = tangent_both['top']
            angle_bot_use = tangent_both['bottom']
        else:
            tangent_top = CSTDerivatives.compute_tangent_angles_for_section(
                psi, N1, N2_top, weights_fixed, weights_fixed, curves['L']
            )
            tangent_bot = CSTDerivatives.compute_tangent_angles_for_section(
                psi, N1, N2_bot, weights_fixed, weights_fixed, curves['L']
            )
            angle_top_use = tangent_top['top']
            angle_bot_use = tangent_bot['bottom']

        tangent_lr = CSTDerivatives.compute_tangent_angles_for_section(
            psi, N1, N2_avg, weights_fixed, weights_fixed, curves['L']
        )

        # 🔧 關鍵修改：根據位置調整Strength
        # 前半段（psi < 0.5）：較低strength，後半段：較高strength
        if psi < 0.3:
            strength_factor = 0.5  # 前段較低
        elif psi < 0.7:
            strength_factor = 0.85  # 中段
        else:
            strength_factor = 1.2  # 後段較高，幫助平滑

        vsp.SetXSecContinuity(xsec, 1)
        vsp.SetXSecTanAngles(
            xsec, vsp.XSEC_BOTH_SIDES,
            angle_top_use,
            tangent_lr['right'],
            angle_bot_use,
            tangent_lr['left']
        )
        vsp.SetXSecTanStrengths(
            xsec, vsp.XSEC_BOTH_SIDES,
            strength_factor, strength_factor, strength_factor, strength_factor
        )
        vsp.SetXSecTanSlews(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)
    else:
        # 機頭/機尾
        if i == 0:
            nose_angle = CSTDerivatives.tangent_angle_at_nose(
                curves['N1'], curves['N2_avg'], weights_fixed
            )
            vsp.SetXSecContinuity(xsec, 1)
            vsp.SetXSecTanAngles(
                xsec, vsp.XSEC_BOTH_SIDES,
                nose_angle, nose_angle, nose_angle, nose_angle
            )
            vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES, 0.5, 0.5, 0.5, 0.5)
            vsp.SetXSecTanSlews(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)

vsp.Update()

# 保存
filename = "output/fairing_strength_adjusted.vsp3"
vsp.WriteVSPFile(filename)

print(f"\n✅ 已生成: {filename}")
print("\n設定說明：")
print("  - 前段（psi < 0.3）：Strength = 0.5（較低，保持銳利）")
print("  - 中段（0.3 ≤ psi < 0.7）：Strength = 0.85")
print("  - 後段（psi ≥ 0.7）：Strength = 1.2（較高，增加平滑）")
print("\n請在VSP GUI中檢查skinning是否改善")
print("="*80)
