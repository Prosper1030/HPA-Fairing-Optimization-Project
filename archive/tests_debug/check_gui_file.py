"""檢查GUI中使用的檔案"""
import openvsp as vsp

# 載入檔案
vsp.ClearVSPModel()
vsp.ReadVSPFile("output/current/fairing_final_complete.vsp3")
vsp.Update()

print("="*80)
print("檢查 fairing_final_complete.vsp3")
print("="*80)

# 獲取幾何信息
geoms = vsp.FindGeoms()
print(f"\n幾何物件數量: {len(geoms)}")

for i, geom_id in enumerate(geoms):
    name = vsp.GetGeomName(geom_id)
    geom_type = vsp.GetGeomTypeName(geom_id)

    # 檢查幾何所屬的集合
    sets = []
    for set_idx in range(20):  # 檢查前20個集合
        if vsp.GetSetFlag(geom_id, set_idx):
            sets.append(set_idx)

    print(f"\n幾何 {i+1}:")
    print(f"  名稱: {name}")
    print(f"  類型: {geom_type}")
    print(f"  所屬集合: {sets}")
    print(f"  vsp.SET_ALL = {vsp.SET_ALL}")
    print(f"  在 SET_ALL 中? {vsp.GetSetFlag(geom_id, vsp.SET_ALL)}")

# 執行CompGeom
print(f"\n執行CompGeom (SET_ALL)...")
vsp.SetAnalysisInputDefaults("CompGeom")
vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])
comp_res_id = vsp.ExecAnalysis("CompGeom")

if comp_res_id:
    wetted_areas = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)
    if len(wetted_areas) > 0:
        print(f"✅ CompGeom 濕面積: {wetted_areas[0]:.6f} m²")

# 執行ParasiteDrag
print(f"\n執行ParasiteDrag (使用檔案設置 + 強制GeomSet=SET_ALL)...")
vsp.SetAnalysisInputDefaults("ParasiteDrag")

# 手動設置參考面積為1.0（如同GUI）
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", [1.0])

# 強制設置GeomSet
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])

# 檢查設置
print(f"\n當前ParasiteDrag設置:")
print(f"  GeomSet: {vsp.SET_ALL}")
print(f"  Sref: 1.0 m²")

drag_res_id = vsp.ExecAnalysis("ParasiteDrag")

if drag_res_id:
    try:
        cd_total = vsp.GetDoubleResults(drag_res_id, "Total_CD_Total", 0)[0]
        comp_swet_list = vsp.GetDoubleResults(drag_res_id, "Comp_Swet", 0)

        print(f"\n✅ ParasiteDrag結果:")
        print(f"   CD_total: {cd_total:.6f}")
        if len(comp_swet_list) > 0:
            print(f"   Swet (各組件總和): {sum(comp_swet_list):.6f} m²")
            print(f"   組件數量: {len(comp_swet_list)}")
            for idx, swet in enumerate(comp_swet_list):
                print(f"     組件 {idx}: {swet:.6f} m²")

        # 檢查警告
        print(f"\n檢查是否有'not included'警告...")

    except Exception as e:
        print(f"❌ 提取結果失敗: {e}")

print("\n" + "="*80)
