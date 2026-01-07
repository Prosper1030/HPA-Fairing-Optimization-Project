"""
測試：用 API 載入 GUI 保存的檔案，看看是否能正確分析
"""
import openvsp as vsp

print("="*80)
print("🧪 測試：API 載入 GUI 檔案")
print("="*80)

# 載入 GUI 保存的檔案
gui_file = "output/Fixed_Angles_Test_GUI_Setup.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(gui_file)
vsp.Update()

print(f"\n📁 載入檔案: {gui_file}")

geom_ids = vsp.FindGeoms()
print(f"📦 幾何數量: {len(geom_ids)}")

# ========== 執行 CompGeom ==========
print(f"\n📐 執行 CompGeom...")
vsp.SetAnalysisInputDefaults("CompGeom")
vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])
comp_res_id = vsp.ExecAnalysis("CompGeom")
wetted_area = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)[0]
print(f"   濕面積: {wetted_area:.4f} m²")

# ========== 執行 ParasiteDrag（使用檔案中保存的設定）==========
print(f"\n🚀 執行 ParasiteDrag（使用檔案保存的設定）...")

# 方案 A: 只載入預設值，不覆蓋任何設定
print(f"\n方案 A: 使用檔案中保存的設定")
vsp.SetAnalysisInputDefaults("ParasiteDrag")
# 不調用任何 SetAnalysisInput，直接執行
pd_res_id_a = vsp.ExecAnalysis("ParasiteDrag")

try:
    cd_a = vsp.GetDoubleResults(pd_res_id_a, "Total_CD_Total", 0)[0]
    swet_a = vsp.GetDoubleResults(pd_res_id_a, "Comp_Swet", 0)[0]
    print(f"   CD: {cd_a:.6f}")
    print(f"   濕面積: {swet_a:.4f} m²")

    diff_pct = abs(cd_a - 0.02045) / 0.02045 * 100
    if diff_pct < 2.0:
        print(f"   ✅ 與 GUI (0.02045) 差異 < 2%")
    else:
        print(f"   ⚠️  與 GUI (0.02045) 差異 {diff_pct:.2f}%")
except Exception as e:
    print(f"   ❌ 錯誤: {e}")

# ========== 方案 B: 明確設定所有參數 ==========
print(f"\n方案 B: 明確設定所有參數")
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
pd_res_id_b = vsp.ExecAnalysis("ParasiteDrag")

try:
    cd_b = vsp.GetDoubleResults(pd_res_id_b, "Total_CD_Total", 0)[0]
    swet_b = vsp.GetDoubleResults(pd_res_id_b, "Comp_Swet", 0)[0]
    print(f"   CD: {cd_b:.6f}")
    print(f"   濕面積: {swet_b:.4f} m²")

    diff_pct = abs(cd_b - 0.02045) / 0.02045 * 100
    if diff_pct < 2.0:
        print(f"   ✅ 與 GUI (0.02045) 差異 < 2%")
    else:
        print(f"   ⚠️  與 GUI (0.02045) 差異 {diff_pct:.2f}%")
except Exception as e:
    print(f"   ❌ 錯誤: {e}")

print("\n" + "="*80)
