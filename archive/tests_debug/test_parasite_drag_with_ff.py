"""
測試添加形狀因數方程式 (Form Factor)
"""
import openvsp as vsp

print("="*80)
print("🧪 ParasiteDrag 測試 + 形狀因數")
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

print(f"\n⚙️  設置參數...")

# 基本設置
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "DeltaTemp", [0.0])
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
vsp.SetIntAnalysisInput("ParasiteDrag", "LamCfEqnType", [vsp.CF_LAM_BLASIUS])
vsp.SetIntAnalysisInput("ParasiteDrag", "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])

# 嘗試設置形狀因數方程式
print(f"\n嘗試設置形狀因數方程式:")
try:
    # 列出所有可用的 FF_B (Body Form Factor) 常量
    ff_constants = [
        ("FF_B_MANUAL", vsp.FF_B_MANUAL),
        ("FF_B_SCHEMENSKY_FUSE", vsp.FF_B_SCHEMENSKY_FUSE),
        ("FF_B_SCHEMENSKY_NACELLE", vsp.FF_B_SCHEMENSKY_NACELLE),
        ("FF_B_HOERNER_STREAMLINED", vsp.FF_B_HOERNER_STREAMLINED),
        ("FF_B_TORENBEEK", vsp.FF_B_TORENBEEK),
        ("FF_B_SHEVELL", vsp.FF_B_SHEVELL),
        ("FF_B_COVERT", vsp.FF_B_COVERT),
        ("FF_B_JENKINSON_FUSE", vsp.FF_B_JENKINSON_FUSE),
        ("FF_B_JENKINSON_WING_NACELLE", vsp.FF_B_JENKINSON_WING_NACELLE),
        ("FF_B_JENKINSON_AFT_FUSE_NACELLE", vsp.FF_B_JENKINSON_AFT_FUSE_NACELLE),
    ]

    print(f"\n  可用的機身形狀因數方程式:")
    for name, value in ff_constants:
        print(f"    {name} = {value}")

    # 設置為 Hoerner Streamlined
    vsp.SetIntAnalysisInput("ParasiteDrag", "FFBodyEqnType", [vsp.FF_B_HOERNER_STREAMLINED])
    result = vsp.GetIntAnalysisInput("ParasiteDrag", "FFBodyEqnType")
    print(f"\n  ✅ FFBodyEqnType 設置成功: {result}")
    print(f"  使用: FF_B_HOERNER_STREAMLINED ({vsp.FF_B_HOERNER_STREAMLINED})")
except Exception as e:
    print(f"  ❌ FFBodyEqnType 設置失敗: {e}")

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
    elif diff_pct < 10.0:
        print(f"\n   ⚠️  差異在 5-10% 之間，可能還有小差異")
    else:
        print(f"\n   ⚠️  差異 > 10%，可能還有其他設置問題")

except Exception as e:
    print(f"\n❌ 提取結果失敗: {e}")

print("\n" + "="*80)
