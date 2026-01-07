"""驗證生成的 VSP 模型"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp

print("="*60)
print("驗證 VSP 模型")
print("="*60)

vsp_file = "output/test_hpa_fixed_params.vsp3"

if not os.path.exists(vsp_file):
    print(f"\n❌ 檔案不存在: {vsp_file}")
    sys.exit(1)

print(f"\n檔案: {vsp_file}")
print(f"大小: {os.path.getsize(vsp_file) / 1024:.1f} KB")

# 清空當前模型
vsp.ClearVSPModel()

# 嘗試讀取
try:
    vsp.ReadVSPFile(vsp_file)
    print("\n✅ 模型讀取成功!")

    # 獲取所有幾何
    geoms = vsp.FindGeoms()
    print(f"\n幾何數量: {len(geoms)}")

    for geom_id in geoms:
        name = vsp.GetGeomName(geom_id)
        type_name = vsp.GetGeomTypeName(geom_id)
        print(f"   - {name} ({type_name})")

        if type_name == "Fuselage":
            # 獲取截面信息
            xsec_surf = vsp.GetXSecSurf(geom_id, 0)
            num_xsec = vsp.GetNumXSec(xsec_surf)
            print(f"     截面數量: {num_xsec}")

            # 獲取長度
            length_parm = vsp.FindParm(geom_id, "Length", "Design")
            if length_parm:
                length = vsp.GetParmVal(length_parm)
                print(f"     總長度: {length:.3f} m")

    # 執行 CompGeom 獲取濕面積
    print("\n執行 CompGeom...")
    vsp.SetAnalysisInputDefaults("CompGeom")
    vsp.Update()
    res_id = vsp.ExecAnalysis("CompGeom")

    # 獲取結果
    wetted_area = vsp.GetDoubleResults(res_id, "Wet_Area", 0)
    if wetted_area:
        print(f"✅ 濕面積: {wetted_area[0]:.3f} m²")

except Exception as e:
    print(f"\n❌ 模型讀取失敗: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
