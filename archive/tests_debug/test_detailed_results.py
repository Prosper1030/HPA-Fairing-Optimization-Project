"""
測試：詳細檢查 ParasiteDrag 結果，看它計算了哪些 components
"""
import openvsp as vsp

print("="*80)
print("🧪 測試：詳細檢查 ParasiteDrag 結果")
print("="*80)

# 載入檔案
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

geom_ids = vsp.FindGeoms()
geom_id = geom_ids[0]
geom_name = vsp.GetGeomName(geom_id)

print(f"\n📁 模型: {test_file}")
print(f"📦 幾何: {geom_name} (ID: {geom_id})")

# ========== 執行 CompGeom ==========
print(f"\n📐 執行 CompGeom...")
vsp.SetAnalysisInputDefaults("CompGeom")
vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])
comp_res_id = vsp.ExecAnalysis("CompGeom")
wetted_area = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)[0]
print(f"   總濕面積: {wetted_area:.4f} m²")

# ========== 執行 ParasiteDrag ==========
print(f"\n🚀 執行 ParasiteDrag...")

vsp.SetAnalysisInputDefaults("ParasiteDrag")
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])
vsp.SetIntAnalysisInput("ParasiteDrag", "RefFlag", [0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])
vsp.SetIntAnalysisInput("ParasiteDrag", "RecomputeGeom", [1])

pd_res_id = vsp.ExecAnalysis("ParasiteDrag")

# ========== 詳細提取所有結果 ==========
print(f"\n📊 詳細提取所有結果...")

# 解析結果對象
res_obj = vsp.parse_results_object(pd_res_id)

print(f"\n🔍 可用的結果鍵:")
result_names = vsp.GetAllResultsNames(pd_res_id)
for name in result_names:
    print(f"   - {name}")

print(f"\n🔍 Component 相關結果:")

try:
    # Component數量
    num_comp = res_obj.Num_Comp
    print(f"\n   Component 數量: {num_comp}")

    # Component labels
    comp_labels = res_obj.Comp_Label
    print(f"   Component 標籤: {comp_labels}")

    # Component IDs
    comp_ids = res_obj.Comp_ID
    print(f"   Component IDs: {comp_ids}")

    # Component wetted areas
    comp_swet = res_obj.Comp_Swet
    print(f"   Component 濕面積: {comp_swet}")

    # Component CDs
    comp_cd = res_obj.Comp_CD
    print(f"   Component CD: {comp_cd}")

    # 總 CD
    cd_total = res_obj.Total_CD_Total[0]
    print(f"\n   總 CD: {cd_total:.6f}")

    # 比較
    print(f"\n💡 分析:")
    print(f"   GUI 計算的濕面積: 3.3680 m²")
    print(f"   CompGeom 濕面積: {wetted_area:.4f} m²")
    if len(comp_swet) > 0:
        total_comp_swet = sum(comp_swet)
        print(f"   ParasiteDrag 計算的 Component 總濕面積: {total_comp_swet:.4f} m²")
        print(f"   濕面積比例: {total_comp_swet / wetted_area * 100:.1f}%")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
