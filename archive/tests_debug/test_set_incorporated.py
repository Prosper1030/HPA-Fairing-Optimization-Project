"""
測試：設置 IncorporatedGen = 1.0
"""
import openvsp as vsp

print("="*80)
print("🧪 測試：設置 IncorporatedGen = 1.0")
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
print(f"📦 幾何: {geom_name}")

# 檢查當前值
print(f"\n🔍 當前參數值:")
incorporated_parm_id = vsp.FindParm(geom_id, "IncorporatedGen", geom_id)
if incorporated_parm_id:
    old_val = vsp.GetParmVal(incorporated_parm_id)
    print(f"   IncorporatedGen: {old_val}")

    # 設置為 1.0
    print(f"\n🔧 設置 IncorporatedGen = 1.0...")
    vsp.SetParmVal(incorporated_parm_id, 1.0)
    new_val = vsp.GetParmVal(incorporated_parm_id)
    print(f"   IncorporatedGen: {old_val} → {new_val}")
else:
    print(f"   ❌ 無法找到 IncorporatedGen 參數")

vsp.Update()

# ========== 執行 CompGeom ==========
print(f"\n📐 執行 CompGeom...")
vsp.SetAnalysisInputDefaults("CompGeom")
vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])
comp_res_id = vsp.ExecAnalysis("CompGeom")
wetted_area = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)[0]
print(f"   濕面積: {wetted_area:.4f} m²")

# ========== 執行 ParasiteDrag ==========
print(f"\n🚀 執行 ParasiteDrag...")

vsp.SetAnalysisInputDefaults("ParasiteDrag")
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])
vsp.SetIntAnalysisInput("ParasiteDrag", "RefFlag", [0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "DeltaTemp", [0.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])
vsp.SetIntAnalysisInput("ParasiteDrag", "RecomputeGeom", [True])

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
        print(f"\n🎉🎉🎉 問題解決！IncorporatedGen 就是關鍵！")
    elif diff_pct < 5.0:
        print(f"\n   ✅ 差異 < 5%，設置正確！")
    else:
        print(f"\n   ⚠️  仍有差異 ({diff_pct:.2f}%)")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
