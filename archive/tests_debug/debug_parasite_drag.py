"""調試ParasiteDrag執行"""
import openvsp as vsp

print("="*80)
print("調試 ParasiteDrag")
print("="*80)

# 載入檔案
vsp.ClearVSPModel()
vsp.ReadVSPFile("output/current/fairing_final_FIXED_DRAG.vsp3")
vsp.Update()

# 檢查幾何
geoms = vsp.FindGeoms()
print(f"\n幾何數量: {len(geoms)}")
for geom_id in geoms:
    name = vsp.GetGeomName(geom_id)
    print(f"  - {name}")

# 執行CompGeom
print(f"\n執行 CompGeom...")
vsp.SetAnalysisInputDefaults("CompGeom")
comp_res_id = vsp.ExecAnalysis("CompGeom")

if comp_res_id:
    wetted_areas = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)
    if len(wetted_areas) > 0:
        print(f"✅ CompGeom 成功，濕面積: {wetted_areas[0]:.6f} m²")
else:
    print(f"❌ CompGeom 失敗")

# 執行ParasiteDrag
print(f"\n執行 ParasiteDrag...")
vsp.SetAnalysisInputDefaults("ParasiteDrag")

# 只設置這3個參數（與DragAnalyzer相同）
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Rho", [1.225])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Mu", [1.7894e-5])

print(f"\n開始執行...")
try:
    drag_res_id = vsp.ExecAnalysis("ParasiteDrag")

    if drag_res_id:
        print(f"✅ ParasiteDrag 執行成功")

        # 嘗試提取結果
        try:
            cd_total = vsp.GetDoubleResults(drag_res_id, "Total_CD_Total", 0)
            if len(cd_total) > 0:
                print(f"   CD_total: {cd_total[0]:.6f}")
        except Exception as e:
            print(f"   ⚠️  無法提取CD: {e}")

        # 檢查所有可用的結果名稱
        result_names = vsp.GetAllDataNames(drag_res_id)
        print(f"\n   可用結果數量: {len(result_names)}")
        if len(result_names) > 0:
            print(f"   前10個結果名稱:")
            for name in result_names[:10]:
                print(f"     - {name}")
    else:
        print(f"❌ ParasiteDrag 返回 None")

except Exception as e:
    print(f"❌ 執行錯誤: {e}")
    import traceback
    traceback.print_exc()

# 檢查生成的檔案
import os
print(f"\n檢查當前目錄的CSV檔案...")
csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
print(f"找到 {len(csv_files)} 個CSV檔案:")
for f in csv_files:
    print(f"  - {f}")

print(f"\n{'='*80}")
