"""
使用正確的方式設置 ParasiteDrag 參數
"""
import openvsp as vsp

print("="*80)
print("🔧 正確設置 ParasiteDrag 參數")
print("="*80)

# 載入模型
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

geom_ids = vsp.FindGeoms()
print(f"\n📁 模型: {test_file}")

# 先調用 UpdateParasiteDrag 以創建參數
print(f"\n🔄 調用 UpdateParasiteDrag() 以創建參數...")
vsp.UpdateParasiteDrag()

# 設置參數
print(f"\n🔧 設置 ParasiteDrag 參數...")

for geom_id in geom_ids:
    geom_name = vsp.GetGeomName(geom_id)
    print(f"\n  幾何: {geom_name}")

    # 方法 1: 使用 FindParm 獲取參數 ID
    print(f"    方法 1: 使用 FindParm")

    # 嘗試找到 Parasite_Drag 參數
    pd_parm_id = vsp.FindParm(geom_id, "Parasite_Drag", "ParasiteDrag")
    if pd_parm_id:
        old_val = vsp.GetParmVal(pd_parm_id)
        vsp.SetParmVal(pd_parm_id, 1.0)
        new_val = vsp.GetParmVal(pd_parm_id)
        print(f"      Parasite_Drag: {old_val} → {new_val}")
    else:
        print(f"      ❌ 無法找到 Parasite_Drag 參數")

    # 嘗試找到 EqnType 參數
    eq_parm_id = vsp.FindParm(geom_id, "EqnType", "ParasiteDrag")
    if eq_parm_id:
        old_val = vsp.GetParmVal(eq_parm_id)
        vsp.SetParmVal(eq_parm_id, 3.0)  # Hoerner Streamlined
        new_val = vsp.GetParmVal(eq_parm_id)
        print(f"      EqnType: {old_val} → {new_val}")
    else:
        print(f"      ❌ 無法找到 EqnType 參數")

vsp.Update()

# 執行 CompGeom
print(f"\n📐 執行 CompGeom...")
vsp.SetAnalysisInputDefaults("CompGeom")
vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])
comp_res_id = vsp.ExecAnalysis("CompGeom")
wetted_area = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)[0]
print(f"   濕面積: {wetted_area:.4f} m²")

# 執行 ParasiteDrag
print(f"\n🚀 執行 ParasiteDrag...")
vsp.SetAnalysisInputDefaults("ParasiteDrag")
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "DeltaTemp", [0.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])

vsp.UpdateParasiteDrag()
pd_res_id = vsp.ExecAnalysis("ParasiteDrag")

# 提取結果
print(f"\n📊 結果:")
try:
    cd_total = vsp.GetDoubleResults(pd_res_id, "Total_CD_Total", 0)[0]
    swet_result = vsp.GetDoubleResults(pd_res_id, "Comp_Swet", 0)[0]

    print(f"   CD: {cd_total:.6f}")
    print(f"   濕面積（從 ParasiteDrag）: {swet_result:.4f} m²")

    print(f"\n💡 與 GUI 對比:")
    print(f"   GUI CD: 0.02045")
    print(f"   API CD: {cd_total:.6f}")
    diff_pct = abs(cd_total - 0.02045) / 0.02045 * 100
    print(f"   差異: {diff_pct:.2f}%")

    if diff_pct < 5.0:
        print(f"\n   ✅✅✅ 成功！差異 < 5%")
    else:
        print(f"\n   ⚠️  仍有差異")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")

print("\n" + "="*80)
