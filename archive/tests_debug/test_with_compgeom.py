"""
按照 Gemini 建議：先執行 CompGeom 再執行 ParasiteDrag
"""
import openvsp as vsp

print("="*80)
print("🧪 CompGeom + ParasiteDrag 測試")
print("="*80)

# 載入模型
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

geom_ids = vsp.FindGeoms()
print(f"\n📁 模型: {test_file}")
print(f"📦 幾何數量: {len(geom_ids)}")

# ========== 步驟 0: 強制啟用幾何組件的阻力計算 (Gemini 的關鍵修正!) ==========
print(f"\n🔧 步驟 0: 強制啟用幾何組件的阻力計算參數...")

for geom_id in geom_ids:
    geom_name = vsp.GetGeomName(geom_id)

    # 1. 強制開啟 "Include in Parasite Drag"
    vsp.SetParmVal(geom_id, "Parasite_Drag", "ParasiteDrag", 1.0)

    # 2. 強制設定形狀因數方程式為 Hoerner Streamlined Body (3.0)
    vsp.SetParmVal(geom_id, "EqnType", "ParasiteDrag", 3.0)

    print(f"   ✅ {geom_name}: Parasite_Drag=1.0, EqnType=3.0")

vsp.Update()

# ========== 步驟 1: 執行 CompGeom ==========
print(f"\n📐 步驟 1: 執行 CompGeom...")

vsp.SetAnalysisInputDefaults("CompGeom")
vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])
vsp.SetIntAnalysisInput("CompGeom", "HalfMesh", [0])
vsp.SetIntAnalysisInput("CompGeom", "Subsurfs", [1])

print(f"   執行 CompGeom.ExecAnalysis()...")
comp_res_id = vsp.ExecAnalysis("CompGeom")

# 獲取濕面積
wetted_area = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)[0]
print(f"   ✅ CompGeom 完成")
print(f"   濕面積: {wetted_area:.4f} m²")

# ========== 步驟 2: 執行 ParasiteDrag ==========
print(f"\n⚙️  步驟 2: 設置並執行 ParasiteDrag...")

vsp.SetAnalysisInputDefaults("ParasiteDrag")

# 明確設置 GeomSet
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])
print(f"   GeomSet: SET_ALL ({vsp.SET_ALL})")

# 參考面積 = 1.0 m² (與 GUI 一致)
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
print(f"   Sref: 1.0 m²")

# 大氣模型
vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
print(f"   AtmosType: US_STANDARD_1976")

# 流場條件
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "DeltaTemp", [0.0])
print(f"   Vinf: 6.5 m/s, Altitude: 0.0 m")

# 單位
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])

# 摩擦係數方程式
vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])
print(f"   LamCf: Blasius, TurbCf: Power Law Prandtl Low Re")

# 形狀因數 (Hoerner Streambody = 3)
try:
    vsp.SetIntAnalysisInput("ParasiteDrag", "FFBodyEqnType", [3])
    print(f"   FFBodyEqn: Hoerner Streambody (3)")
except:
    print(f"   ⚠️ FFBodyEqnType 無法設置")

# 更新
vsp.UpdateParasiteDrag()
print(f"   UpdateParasiteDrag() 完成")

# 執行分析
print(f"\n🚀 執行 ParasiteDrag 分析...")
pd_res_id = vsp.ExecAnalysis("ParasiteDrag")

# 提取結果
print(f"\n📊 提取結果...")
try:
    cd_total = vsp.GetDoubleResults(pd_res_id, "Total_CD_Total", 0)[0]

    # 嘗試獲取更多細節
    try:
        swet_result = vsp.GetDoubleResults(pd_res_id, "Comp_Swet", 0)[0]
        print(f"   濕面積（從 ParasiteDrag 結果）: {swet_result:.4f} m²")
    except:
        pass

    print(f"\n✅ 分析完成！")
    print(f"   CD: {cd_total:.6f}")

    # 與 GUI 比較
    print(f"\n💡 與 GUI 結果對比：")
    print(f"   GUI CD (Sref=1.0): 0.02045")
    print(f"   API CD (Sref=1.0): {cd_total:.6f}")

    diff = abs(cd_total - 0.02045)
    diff_pct = (diff / 0.02045) * 100
    print(f"   絕對差異: {diff:.6f}")
    print(f"   相對差異: {diff_pct:.2f}%")

    if diff_pct < 2.0:
        print(f"\n   ✅✅✅ 差異 < 2%，完美匹配！")
    elif diff_pct < 5.0:
        print(f"\n   ✅ 差異 < 5%，設置正確！")
    elif diff_pct < 10.0:
        print(f"\n   ⚠️  差異在 5-10% 之間")
    else:
        print(f"\n   ⚠️  差異 > 10%，仍有問題")

except Exception as e:
    print(f"\n❌ 提取結果失敗: {e}")

print("\n" + "="*80)
