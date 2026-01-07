"""
測試：使用 RecomputeGeom 參數
"""
import openvsp as vsp

print("="*80)
print("🧪 測試：RecomputeGeom 參數")
print("="*80)

# 載入檔案
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

print(f"\n📁 載入檔案: {test_file}")

geom_ids = vsp.FindGeoms()
print(f"📦 幾何數量: {len(geom_ids)}")

# ========== 執行 CompGeom ==========
print(f"\n📐 執行 CompGeom...")
vsp.SetAnalysisInputDefaults("CompGeom")
vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])
comp_res_id = vsp.ExecAnalysis("CompGeom")
wetted_area = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)[0]
print(f"   濕面積: {wetted_area:.4f} m²")

# ========== 執行 ParasiteDrag（添加 RecomputeGeom）==========
print(f"\n🚀 執行 ParasiteDrag（添加 RecomputeGeom=True）...")

vsp.SetAnalysisInputDefaults("ParasiteDrag")

# 設置參數
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "DeltaTemp", [0.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])

# ⭐⭐⭐ 關鍵：設置 RecomputeGeom=True
vsp.SetIntAnalysisInput("ParasiteDrag", "RecomputeGeom", [True])
print(f"   ✅ 設置 RecomputeGeom=True")

# 執行分析
pd_res_id = vsp.ExecAnalysis("ParasiteDrag")

# 提取結果
print(f"\n📊 提取結果...")
try:
    cd_total = vsp.GetDoubleResults(pd_res_id, "Total_CD_Total", 0)[0]
    swet_result = vsp.GetDoubleResults(pd_res_id, "Comp_Swet", 0)[0]

    print(f"   CD: {cd_total:.6f}")
    print(f"   濕面積（從 ParasiteDrag）: {swet_result:.4f} m²")

    print(f"\n💡 與 GUI 對比：")
    print(f"   GUI CD: 0.02045")
    print(f"   API CD: {cd_total:.6f}")

    diff = abs(cd_total - 0.02045)
    diff_pct = (diff / 0.02045) * 100
    print(f"   絕對差異: {diff:.6f}")
    print(f"   相對差異: {diff_pct:.2f}%")

    if diff_pct < 2.0:
        print(f"\n   ✅✅✅ 完美匹配！差異 < 2%")
    elif diff_pct < 5.0:
        print(f"\n   ✅ 差異 < 5%，設置正確！")
    else:
        print(f"\n   ⚠️  仍有差異 ({diff_pct:.2f}%)")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
