"""重新生成最終版本 - 確保ParasiteDrag設置正確"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入
for module in list(sys.modules.keys()):
    if 'optimization' in module or 'math' in module:
        del sys.modules[module]

from optimization.hpa_asymmetric_optimizer import CST_Modeler, VSPModelGenerator
import openvsp as vsp

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

print("="*80)
print("重新生成最終版本 - 確保ParasiteDrag設置正確")
print("="*80)

# 生成曲線
curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

output_file = "output/current/fairing_final_FIXED.vsp3"
print(f"\n生成: {output_file}")

# 生成VSP模型
VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_Final_FIXED",
    filepath=output_file
)

print(f"✅ VSP模型已生成")

# 重新載入並驗證ParasiteDrag設置
print(f"\n驗證ParasiteDrag設置...")
vsp.ClearVSPModel()
vsp.ReadVSPFile(output_file)
vsp.Update()

pd_container = vsp.FindContainer("ParasiteDragSettings", 0)
if pd_container:
    # 讀取所有關鍵參數
    params_to_check = [
        ("LengthUnit", "ParasiteDrag", "長度單位"),
        ("Sref", "ParasiteDrag", "參考面積"),
        ("Alt", "ParasiteDrag", "高度"),
        ("Vinf", "ParasiteDrag", "速度"),
        ("Temp", "ParasiteDrag", "溫度"),
        ("LamCfEqnType", "ParasiteDrag", "層流摩擦係數方程式"),
        ("TurbCfEqnType", "ParasiteDrag", "紊流摩擦係數方程式"),
        ("RefFlag", "ParasiteDrag", "參考面積標誌"),
        ("Set", "ParasiteDrag", "幾何集"),
    ]

    print(f"\n檔案中保存的ParasiteDrag參數：")
    for parm_name, group_name, description in params_to_check:
        parm = vsp.FindParm(pd_container, parm_name, group_name)
        if parm:
            value = vsp.GetParmVal(parm)
            print(f"  {description} ({parm_name}): {value}")
        else:
            print(f"  {description} ({parm_name}): ❌ 找不到")

# 執行CompGeom檢查濕面積
print(f"\n執行CompGeom分析...")
vsp.SetAnalysisInputDefaults("CompGeom")
comp_res_id = vsp.ExecAnalysis("CompGeom")

if comp_res_id:
    wetted_areas = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)
    if len(wetted_areas) > 0:
        swet = wetted_areas[0]
        print(f"✅ 濕潤表面積: {swet:.6f} m²")
    else:
        print(f"❌ 無法獲取濕潤表面積")
else:
    print(f"❌ CompGeom執行失敗")

# 執行ParasiteDrag分析（使用檔案中的設置）
print(f"\n執行ParasiteDrag分析（使用檔案中保存的設置）...")
vsp.SetAnalysisInputDefaults("ParasiteDrag")

# 強制設置 GeomSet = SET_ALL
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])

drag_res_id = vsp.ExecAnalysis("ParasiteDrag")

if drag_res_id:
    try:
        cd_total = vsp.GetDoubleResults(drag_res_id, "Total_CD_Total", 0)[0]
        comp_swet = vsp.GetDoubleResults(drag_res_id, "Comp_Swet", 0)

        print(f"✅ ParasiteDrag執行成功")
        print(f"   CD_total: {cd_total:.6f}")
        if len(comp_swet) > 0:
            print(f"   Swet (from ParasiteDrag): {comp_swet[0]:.6f} m²")
    except Exception as e:
        print(f"❌ 提取結果失敗: {e}")
else:
    print(f"❌ ParasiteDrag執行失敗")

print("\n" + "="*80)
print("✅ 重新生成完成！")
print(f"請在VSP GUI中開啟: {output_file}")
print("並手動檢查ParasiteDrag分析是否與API結果一致")
print("="*80)
