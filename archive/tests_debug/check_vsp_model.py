"""檢查VSP模型是否有效"""
import openvsp as vsp

vsp_file = "output/current/fairing_final_for_drag.vsp3"

print("="*80)
print("檢查VSP模型")
print("="*80)

print(f"\n載入模型: {vsp_file}")
vsp.ClearVSPModel()
vsp.ReadVSPFile(vsp_file)
vsp.Update()

# 獲取所有幾何
geoms = vsp.FindGeoms()
print(f"\n找到 {len(geoms)} 個幾何物件：")

for i, geom_id in enumerate(geoms):
    name = vsp.GetGeomName(geom_id)
    geom_type = vsp.GetGeomTypeName(geom_id)
    print(f"  {i+1}. {name} (類型: {geom_type})")

# 檢查 CompGeom
print(f"\n執行 CompGeom 分析...")
try:
    vsp.SetAnalysisInputDefaults("CompGeom")
    comp_res_id = vsp.ExecAnalysis("CompGeom")

    if comp_res_id:
        print("✅ CompGeom 成功")

        # 列出所有可用的結果
        res_names = vsp.GetAllDataNames(comp_res_id)
        print(f"\n可用結果 ({len(res_names)})：")
        for name in res_names[:20]:  # 只顯示前20個
            print(f"  - {name}")

except Exception as e:
    print(f"❌ CompGeom 失敗: {e}")

# 檢查 ParasiteDrag
print(f"\n執行 ParasiteDrag 分析...")
try:
    vsp.SetAnalysisInputDefaults("ParasiteDrag")
    vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [15.0])
    vsp.SetDoubleAnalysisInput("ParasiteDrag", "Rho", [1.204])
    vsp.SetDoubleAnalysisInput("ParasiteDrag", "Mu", [1.825e-5])

    drag_res_id = vsp.ExecAnalysis("ParasiteDrag")

    if drag_res_id:
        print("✅ ParasiteDrag 成功")

        # 列出所有可用的結果
        res_names = vsp.GetAllDataNames(drag_res_id)
        print(f"\n可用結果 ({len(res_names)})：")
        for name in res_names[:20]:
            print(f"  - {name}")

    else:
        print("❌ ParasiteDrag 返回 None")

except Exception as e:
    print(f"❌ ParasiteDrag 失敗: {e}")
    import traceback
    traceback.print_exc()

# 檢查生成的檔案
import os
print(f"\n當前目錄檔案：")
for f in os.listdir("."):
    if f.endswith(".csv") or f.endswith(".txt"):
        print(f"  - {f}")

print("\n" + "="*80)
