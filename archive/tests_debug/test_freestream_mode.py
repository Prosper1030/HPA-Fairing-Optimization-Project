"""
測試 FreestreamPropChoice 的正確值
0 = ?
1 = ?
"""
import openvsp as vsp

print("="*80)
print("🔍 測試 FreestreamPropChoice 模式")
print("="*80)

# 載入模型
test_file = "output/Fixed_Angles_Test.vsp3"
vsp.ClearVSPModel()
vsp.ReadVSPFile(test_file)
vsp.Update()

print("\n測試不同的 FreestreamPropChoice 值:\n")

for mode in [0, 1]:
    print(f"  FreestreamPropChoice = {mode}:")

    # 重置並設置
    vsp.SetAnalysisInputDefaults("ParasiteDrag")
    vsp.SetIntAnalysisInput("ParasiteDrag", "FreestreamPropChoice", [mode])

    # 設置速度和高度
    vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
    vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", [0.0])
    vsp.SetDoubleAnalysisInput("ParasiteDrag", "DeltaTemp", [0.0])

    # 讀取結果
    try:
        density = vsp.GetDoubleAnalysisInput("ParasiteDrag", "Density")[0]
        temp = vsp.GetDoubleAnalysisInput("ParasiteDrag", "Temperature")[0]
        pres = vsp.GetDoubleAnalysisInput("ParasiteDrag", "Pressure")[0]

        print(f"    Density: {density:.6f} kg/m³")
        print(f"    Temperature: {temp:.2f} K or °C")
        print(f"    Pressure: {pres:.2f} Pa")

        # 檢查密度是否接近海平面標準大氣 (1.225 kg/m³)
        if abs(density - 1.225) < 0.01:
            print(f"    ✅ 密度接近標準大氣 (1.225 kg/m³) → 可能是大氣模式")
        else:
            print(f"    ⚠️  密度與標準大氣差異較大")
    except Exception as e:
        print(f"    ❌ 錯誤: {e}")

    print()

# 測試：嘗試使用 AtmosType
print("\n測試設置 AtmosType:")
try:
    # ATMOS_TYPE_US_STANDARD_1976 = 0
    vsp.SetIntAnalysisInput("ParasiteDrag", "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])
    result = vsp.GetIntAnalysisInput("ParasiteDrag", "AtmosType")
    print(f"  AtmosType 設置成功: {result}")
except Exception as e:
    print(f"  ❌ AtmosType 設置失敗: {e}")

print("\n" + "="*80)
