"""
最終模型生成器 - 系統化、模組化的方法
確保所有設置正確保存到VSP檔案
"""
import openvsp as vsp
import numpy as np
import os
import sys

# 添加專案路徑
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from optimization.hpa_asymmetric_optimizer import CST_Modeler


def generate_final_model(gene, output_filepath, verbose=True):
    """
    生成最終VSP模型，確保所有參數正確設置

    Parameters:
    -----------
    gene : dict
        設計基因
    output_filepath : str
        輸出檔案路徑
    verbose : bool
        是否顯示詳細信息
    """
    if verbose:
        print("="*80)
        print("最終模型生成器")
        print("="*80)
        print(f"輸出檔案: {output_filepath}")

    # 1. 生成曲線數據
    if verbose:
        print("\n步驟 1: 生成CST曲線...")

    curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

    if verbose:
        print(f"  ✅ 生成 {len(curves['psi'])} 個截面")

    # 2. 清除並創建新模型
    if verbose:
        print("\n步驟 2: 創建VSP幾何...")

    vsp.ClearVSPModel()

    # 創建機身
    fuse_id = vsp.AddGeom("FUSELAGE")
    vsp.SetGeomName(fuse_id, "HPA_Fairing")

    # 確保幾何在正確的集合中
    vsp.SetSetFlag(fuse_id, vsp.SET_ALL, True)
    vsp.SetSetFlag(fuse_id, vsp.SET_SHOWN, True)
    vsp.SetSetFlag(fuse_id, vsp.SET_NOT_SHOWN, False)

    if verbose:
        print(f"  ✅ 創建機身幾何: {fuse_id}")
        print(f"  ✅ 設置在 SET_ALL 集合中")

    # 3. 設置截面
    if verbose:
        print("\n步驟 3: 設置截面幾何...")

    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

    # 調整截面數量
    current_num = vsp.GetNumXSec(xsec_surf)
    while current_num < 40:
        vsp.InsertXSec(fuse_id, current_num - 1, vsp.XS_SUPER_ELLIPSE)
        current_num = vsp.GetNumXSec(xsec_surf)

    vsp.Update()

    # 設置每個截面
    weights_fixed = [0.25, 0.35, 0.30, 0.10]

    for i in range(40):
        psi = curves['psi'][i]
        is_nose = (i == 0)
        is_tail = (i == 39)

        total_width = curves['width_half'][i] * 2.0
        total_height = curves['super_height'][i]
        z_loc_value = curves['z_loc'][i]

        # 設置截面類型
        if is_nose or is_tail:
            vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
        else:
            vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)

        xsec = vsp.GetXSec(xsec_surf, i)

        # X位置
        vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

        # Z位置（歸一化）
        z_loc_parm = vsp.GetXSecParm(xsec, "ZLocPercent")
        if z_loc_parm:
            z_loc_normalized = z_loc_value / curves['L']
            vsp.SetParmVal(z_loc_parm, z_loc_normalized)

        # 超橢圓參數
        if not (is_nose or is_tail):
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), total_width)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), total_height)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), 2.5)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), 2.5)

            # 切線角度（使用新方法）
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
                asymmetric_angles['top'],
                tangent_lr['right'],
                asymmetric_angles['bottom'],
                tangent_lr['left']
            )

            # 強度
            strength = 0.85
            if psi < 0.3:
                strength = 0.6
            elif psi > 0.7:
                strength = 1.1

            vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES, strength, strength, strength, strength)
            vsp.SetXSecTanSlews(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)

        elif is_nose:
            # 機頭
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

    if verbose:
        print(f"  ✅ 設置 40 個截面")

    # 4. 設置ParasiteDrag參數（關鍵！）
    if verbose:
        print("\n步驟 4: 設置ParasiteDrag參數（保存到檔案）...")

    pd_container = vsp.FindContainer("ParasiteDragSettings", 0)

    if pd_container:
        params = [
            ("LengthUnit", 2.0, "長度單位 = meters"),
            ("Sref", 1.0, "參考面積 = 1.0 m²"),
            ("Alt", 0.0, "高度 = 0 m"),
            ("AltLengthUnit", 1.0, "高度單位 = meters"),
            ("Vinf", 6.5, "速度 = 6.5 m/s"),
            ("VinfUnitType", 1.0, "速度單位 = m/s"),
            ("Temp", 15.0, "溫度 = 15°C"),
            ("TempUnit", 1.0, "溫度單位 = Celsius"),
            ("LamCfEqnType", 0.0, "層流摩擦係數 = Blasius"),
            ("TurbCfEqnType", 7.0, "紊流摩擦係數 = Power Law Prandtl Low Re"),
            ("RefFlag", 0.0, "參考面積標誌 = Manual"),
            ("Set", 0.0, "幾何集 = SET_ALL"),
        ]

        for parm_name, value, description in params:
            parm = vsp.FindParm(pd_container, parm_name, "ParasiteDrag")
            if parm:
                vsp.SetParmVal(parm, value)
                if verbose:
                    print(f"  ✅ {description}")
            else:
                if verbose:
                    print(f"  ⚠️  找不到參數: {parm_name}")

        vsp.Update()
    else:
        if verbose:
            print(f"  ❌ 找不到ParasiteDragSettings容器")

    # 5. 保存檔案
    if verbose:
        print(f"\n步驟 5: 保存VSP檔案...")

    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    vsp.WriteVSPFile(output_filepath)

    if verbose:
        print(f"  ✅ 已保存: {output_filepath}")

    # 6. 驗證
    if verbose:
        print(f"\n步驟 6: 驗證設置...")

        vsp.ClearVSPModel()
        vsp.ReadVSPFile(output_filepath)
        vsp.Update()

        # 執行CompGeom
        vsp.SetAnalysisInputDefaults("CompGeom")
        vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])
        comp_res_id = vsp.ExecAnalysis("CompGeom")

        if comp_res_id:
            wetted_areas = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)
            if len(wetted_areas) > 0:
                print(f"  ✅ CompGeom 濕面積: {wetted_areas[0]:.6f} m²")

        # 執行ParasiteDrag（使用檔案設置）
        print(f"\n  執行ParasiteDrag（使用檔案設置）...")
        vsp.SetAnalysisInputDefaults("ParasiteDrag")

        # 強制GeomSet
        vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])

        drag_res_id = vsp.ExecAnalysis("ParasiteDrag")

        if drag_res_id:
            try:
                cd_total = vsp.GetDoubleResults(drag_res_id, "Total_CD_Total", 0)[0]
                comp_swet_list = vsp.GetDoubleResults(drag_res_id, "Comp_Swet", 0)

                print(f"  ✅ ParasiteDrag CD: {cd_total:.6f}")
                if len(comp_swet_list) > 0:
                    print(f"  ✅ ParasiteDrag Swet: {sum(comp_swet_list):.6f} m²")
            except Exception as e:
                print(f"  ❌ 提取結果失敗: {e}")

    if verbose:
        print("\n" + "="*80)
        print("✅ 最終模型生成完成！")
        print("="*80)

    return output_filepath


if __name__ == "__main__":
    # 測試
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

    output_file = "output/current/HPA_Fairing_FINAL.vsp3"

    generate_final_model(gene, output_file, verbose=True)
