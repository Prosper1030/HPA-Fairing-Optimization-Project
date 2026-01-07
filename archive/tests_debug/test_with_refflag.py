"""
測試：添加 RefFlag=0 參數
"""
import openvsp as vsp

print("="*80)
print("🧪 測試：添加 RefFlag=0")
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

# ========== 執行 ParasiteDrag（完全按照 parasitedrag_sweep 的方式）==========
print(f"\n🚀 執行 ParasiteDrag（完全按照 parasitedrag_sweep）...")

vsp.SetAnalysisInputDefaults("ParasiteDrag")

# 按照 parasitedrag_sweep 的順序設置
vsp.SetIntAnalysisInput("ParasiteDrag", "VelocityUnit", [vsp.V_UNIT_M_S])
print(f"   ✅ VelocityUnit: V_UNIT_M_S")

vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
print(f"   ✅ LengthUnit: LEN_M")

vsp.SetStringAnalysisInput("ParasiteDrag", "FileName", ["/dev/null"])
print(f"   ✅ FileName: /dev/null")

vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])
print(f"   ✅ GeomSet: SET_ALL")

# ⭐⭐⭐ 關鍵：先設置 RefFlag=0，再設置 Sref
vsp.SetIntAnalysisInput("ParasiteDrag", "RefFlag", [0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
print(f"   ✅ RefFlag: 0, Sref: 1.0")

vsp.SetVSP3FileName('/dev/null')
print(f"   ✅ SetVSP3FileName: /dev/null")

# 設置流場條件
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
print(f"   ✅ Vinf: 6.5 m/s, Altitude: 0.0 m")

# 設置摩擦係數方程式（這個 parasitedrag_sweep 沒有設置，使用預設值）
vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])
print(f"   ✅ LamCfEqn: Blasius, TurbCfEqn: Power Law Prandtl Low Re")

# RecomputeGeom（從 parasitedrag_sweep 學到的）
vsp.SetIntAnalysisInput("ParasiteDrag", "RecomputeGeom", [True])
print(f"   ✅ RecomputeGeom: True")

# 執行分析
print(f"\n🚀 執行分析...")
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
        print(f"\n🎉🎉🎉 問題解決！")
    elif diff_pct < 5.0:
        print(f"\n   ✅ 差異 < 5%，設置正確！")
    else:
        print(f"\n   ⚠️  仍有差異 ({diff_pct:.2f}%)")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
