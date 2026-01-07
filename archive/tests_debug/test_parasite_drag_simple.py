"""
最簡單的 ParasiteDrag 測試
完全按照 GUI 的方式設置
"""
import openvsp as vsp

print("="*80)
print("🧪 簡單 ParasiteDrag 測試")
print("="*80)

# 載入模型
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

# 確保幾何顯示
geom_ids = vsp.FindGeoms()
for geom_id in geom_ids:
    vsp.SetSetFlag(geom_id, vsp.SET_SHOWN, True)
vsp.Update()

print(f"\n📁 模型: {test_file}")
print(f"📦 幾何數量: {len(geom_ids)}")

# 設置默認值
vsp.SetAnalysisInputDefaults("ParasiteDrag")

# 按照 GUI 的設置
print(f"\n⚙️  設置參數...")

# 1. 參考面積 = 1.0 m²
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
print(f"   Sref: 1.0 m²")

# 2. US Standard Atmosphere 1976
vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
print(f"   AtmosType: US_STANDARD_1976 ({vsp.ATMOS_TYPE_US_STANDARD_1976})")

# 3. 速度 = 6.5 m/s
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
print(f"   Vinf: 6.5 m/s")

# 4. 高度 = 0 m
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
print(f"   Altitude: 0.0 m")

# 5. 溫度偏移 = 0
vsp.SetDoubleAnalysisInput("ParasiteDrag", "DeltaTemp", [0.0])
print(f"   DeltaTemp: 0.0")

# 6. 單位 = 米
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
print(f"   LengthUnit: LEN_M ({vsp.LEN_M})")

# 7. 層流摩擦係數：Blasius
vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
print(f"   LamCfEqnType: CF_LAM_BLASIUS ({vsp.CF_LAM_BLASIUS})")

# 8. 紊流摩擦係數：Power Law Prandtl Low Re
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])
print(f"   TurbCfEqnType: CF_TURB_POWER_LAW_PRANDTL_LOW_RE ({vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE})")

# 9. 幾何集 = SET_ALL
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])
print(f"   GeomSet: SET_ALL ({vsp.SET_ALL})")

# 更新
vsp.UpdateParasiteDrag()
print(f"\n🔄 UpdateParasiteDrag() 完成")

# 執行分析
print(f"\n🚀 執行分析...")
result_id = vsp.ExecAnalysis("ParasiteDrag")

# 提取結果
print(f"\n📊 提取結果...")
try:
    cd_total = vsp.GetDoubleResults(result_id, "Total_CD_Total", 0)[0]

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

    if diff_pct < 5.0:
        print(f"\n   ✅ 差異 < 5%，設置正確！")
    else:
        print(f"\n   ⚠️  差異 > 5%，可能還有其他設置問題")

except Exception as e:
    print(f"\n❌ 提取結果失敗: {e}")

print("\n" + "="*80)
