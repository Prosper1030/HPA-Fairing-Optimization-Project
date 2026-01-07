"""
測試：使用 parasitedrag_sweep 函數（高階 API）
"""
import openvsp as vsp
from openvsp.parasite_drag import parasitedrag_sweep

print("="*80)
print("🧪 測試：使用 parasitedrag_sweep 高階 API")
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

# ========== 使用 parasitedrag_sweep 函數 ==========
print(f"\n🚀 使用 parasitedrag_sweep 函數...")

try:
    # 單個速度和高度點
    speeds = [6.5]  # m/s
    alts_ft = [0.0]  # feet (海平面)

    print(f"   參數:")
    print(f"     speeds: {speeds} m/s")
    print(f"     altitudes: {alts_ft} ft")
    print(f"     sref: 1.0 m²")
    print(f"     length_unit: vsp.LEN_M")
    print(f"     speed_unit: vsp.V_UNIT_M_S")
    print(f"     set: vsp.SET_ALL")

    results = parasitedrag_sweep(
        speeds=speeds,
        alts_ft=alts_ft,
        sref=1.0,
        length_unit=vsp.LEN_M,
        speed_unit=vsp.V_UNIT_M_S,  # m/s
        set=vsp.SET_ALL
    )

    print(f"\n✅ 分析完成！")
    print(f"\n結果類型: {type(results)}")
    print(f"結果: {results}")

    # 嘗試訪問結果屬性
    if hasattr(results, 'CD'):
        cd = results.CD[0]
        print(f"\n   CD: {cd:.6f}")

        diff_pct = abs(cd - 0.02045) / 0.02045 * 100
        print(f"\n💡 與 GUI 對比:")
        print(f"   GUI CD: 0.02045")
        print(f"   API CD: {cd:.6f}")
        print(f"   差異: {diff_pct:.2f}%")

        if diff_pct < 2.0:
            print(f"\n   ✅✅✅ 成功！差異 < 2%")
        elif diff_pct < 5.0:
            print(f"\n   ✅ 差異 < 5%")
        else:
            print(f"\n   ⚠️  仍有差異")

except Exception as e:
    print(f"   ❌ 錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
