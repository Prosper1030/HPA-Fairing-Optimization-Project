"""
使用正確的方法（已驗證）生成最終非對稱整流罩並計算阻力
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入
for module in list(sys.modules.keys()):
    if 'optimization' in module or 'geometry' in module or 'analysis' in module:
        if module in sys.modules:
            del sys.modules[module]

from optimization.hpa_asymmetric_optimizer import CST_Modeler
from analysis.drag_analysis import DragAnalyzer
import openvsp as vsp
import numpy as np

print("="*80)
print("最終版本 - 使用已驗證的方法")
print("="*80)

# 基因定義
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

# 生成曲線
print("\n生成CST曲線...")
curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)
print(f"✅ 生成 40 個截面")

# 手動創建VSP模型（使用與 cst_geometry_math_driven.py 相同的邏輯）
print("\n創建VSP模型...")
vsp.ClearVSPModel()

fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetGeomName(fuse_id, "HPA_Fairing_FINAL")

xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

# 調整截面數量
current_num = vsp.GetNumXSec(xsec_surf)
while current_num < 40:
    vsp.InsertXSec(fuse_id, current_num - 1, vsp.XS_SUPER_ELLIPSE)
    current_num = vsp.GetNumXSec(xsec_surf)

vsp.Update()

# 設置截面
weights_fixed = [0.25, 0.35, 0.30, 0.10]

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

    z_loc_parm = vsp.GetXSecParm(xsec, "ZLocPercent")
    if z_loc_parm:
        z_loc_normalized = z_loc_value / curves['L']
        vsp.SetParmVal(z_loc_parm, z_loc_normalized)

    if not (is_nose or is_tail):
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), total_width)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), total_height)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), 2.5)

        # 切線角度
        from math.cst_derivatives import CSTDerivatives

        asymmetric_angles = CSTDerivatives.compute_asymmetric_tangent_angles(
            curves['x'], curves['z_upper'], curves['z_lower'], i
        )

        N1 = curves['N1']
        N2_avg = curves['N2_avg']
        tangent_lr = CSTDerivatives.compute_tangent_angles_for_section(
            psi, N1, N2_avg, weights_fixed, weights_fixed, curves['L']
        )

        vsp.SetXSecContinuity(xsec, 1)
        vsp.SetXSecTanAngles(
            xsec, vsp.XSEC_BOTH_SIDES,
            asymmetric_angles['top'], tangent_lr['right'],
            asymmetric_angles['bottom'], tangent_lr['left']
        )

        strength = 0.85
        if psi < 0.3:
            strength = 0.6
        elif psi > 0.7:
            strength = 1.1

        vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES, strength, strength, strength, strength)
        vsp.SetXSecTanSlews(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)

    elif is_nose:
        nose_angles = CSTDerivatives.compute_asymmetric_tangent_angles(
            curves['x'], curves['z_upper'], curves['z_lower'], i
        )
        angle_lr = nose_angles['top']

        vsp.SetXSecContinuity(xsec, 1)
        vsp.SetXSecTanAngles(
            xsec, vsp.XSEC_BOTH_SIDES,
            nose_angles['top'], angle_lr, nose_angles['bottom'], angle_lr
        )
        vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES, 0.75, 0.75, 0.75, 0.75)
        vsp.SetXSecTanSlews(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)

vsp.Update()

# ========== 關鍵：使用與 cst_geometry_math_driven.py 完全相同的ParasiteDrag設置 ==========
print("\n設置ParasiteDrag參數（直接保存到檔案）...")
pd_container = vsp.FindContainer("ParasiteDragSettings", 0)

if pd_container:
    params = [
        ("LengthUnit", 2.0),
        ("Sref", 1.0),
        ("Alt", 0.0),
        ("AltLengthUnit", 1.0),
        ("Vinf", 6.5),
        ("VinfUnitType", 1.0),
        ("Temp", 15.0),
        ("TempUnit", 1.0),
        ("DeltaTemp", 0.0),
        ("LamCfEqnType", 0.0),
        ("TurbCfEqnType", 7.0),
        ("RefFlag", 0.0),
        ("Set", 0.0),
    ]

    for parm_name, value in params:
        parm = vsp.FindParm(pd_container, parm_name, "ParasiteDrag")
        if parm:
            vsp.SetParmVal(parm, value)

    vsp.Update()
    print("✅ ParasiteDrag參數已設置")

# 保存檔案
output_file = "output/HPA_Fairing_FINAL_CORRECT.vsp3"
os.makedirs(os.path.dirname(output_file), exist_ok=True)
vsp.WriteVSPFile(output_file)
print(f"✅ 已保存: {output_file}")

# 使用 DragAnalyzer（已驗證的方法）計算阻力
print("\n" + "="*80)
print("執行阻力分析（使用DragAnalyzer）")
print("="*80)

analyzer = DragAnalyzer(output_dir="output")

velocity = 6.5  # m/s
rho = 1.225  # kg/m³
mu = 1.7894e-5  # kg/(m·s)

result = analyzer.run_analysis(output_file, velocity, rho, mu)

if result:
    print(f"\n✅ 分析成功！")
    print(f"\n   Cd: {result.get('Cd', 'N/A')}")
    print(f"   CdA: {result.get('CdA', 'N/A')} m²")
    print(f"   Swet: {result.get('Swet', 'N/A')} m²")
    print(f"   Drag: {result.get('Drag', 'N/A')} N")

    # 計算投影面積
    max_width = np.max(curves['width'])
    max_height_total = np.max(curves['z_upper']) - np.min(curves['z_lower'])
    projected_area = np.pi * (max_width / 2) * (max_height_total / 2)

    print(f"\n   投影面積（橢圓近似）: {projected_area:.6f} m²")

    # 基於投影面積的Cd
    cda = result.get('CdA', 0)
    cd_proj = cda / projected_area if projected_area > 0 else 0
    print(f"   Cd（基於投影面積）: {cd_proj:.6f}")
    print(f"   阻力計數: {cd_proj*10000:.1f} counts")

print("\n" + "="*80)
print("✅ 完成！")
print("="*80)
