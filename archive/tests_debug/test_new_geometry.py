"""測試新的上下邊界獨立反推法"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import openvsp as vsp
from optimization.hpa_asymmetric_optimizer import CST_Modeler, VSPModelGenerator

print("="*60)
print("測試新的上下邊界獨立反推法")
print("="*60)

# 測試基因
gene = {
    'L': 2.5,
    'W_max': 0.60,
    'H_top_max': 0.95,
    'H_bot_max': 0.35,
    'N1': 0.5,
    'N2_top': 0.7,
    'N2_bot': 0.8,
    'X_max_pos': 0.25,
    'X_offset': 0.7,
}

print(f"\n📊 測試基因:")
for key, value in gene.items():
    print(f"   {key}: {value}")

# 生成曲線
print(f"\n🔧 生成非對稱曲線...")
curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

# 驗證曲線數據
print(f"\n📈 曲線數據驗證:")
print(f"   截面數量: {len(curves['psi'])}")
print(f"   上邊界範圍: [{min(curves['z_upper']):.3f}, {max(curves['z_upper']):.3f}] m")
print(f"   下邊界範圍: [{min(curves['z_lower']):.3f}, {max(curves['z_lower']):.3f}] m")
print(f"   總高度範圍: [{min(curves['super_height']):.3f}, {max(curves['super_height']):.3f}] m")
print(f"   Z位置範圍: [{min(curves['z_loc']):.3f}, {max(curves['z_loc']):.3f}] m")

# 檢查機頭和機尾
nose_gap = abs(curves['z_upper'][0] - curves['z_lower'][0])
tail_gap = abs(curves['z_upper'][-1] - curves['z_lower'][-1])

print(f"\n🔍 幾何檢查:")
if nose_gap < 0.01:
    print(f"   ✅ 機頭閉合（間隙 {nose_gap:.4f} m）")
else:
    print(f"   ❌ 機頭未閉合（間隙 {nose_gap:.4f} m）")

if tail_gap < 0.01:
    print(f"   ✅ 機尾閉合（間隙 {tail_gap:.4f} m）")
else:
    print(f"   ❌ 機尾未閉合（間隙 {tail_gap:.4f} m）")

# 生成VSP模型
print(f"\n🚀 生成VSP模型...")
output_file = "output/test_new_geometry.vsp3"

try:
    VSPModelGenerator.create_fuselage(
        curves,
        name="Test_New_Geometry",
        filepath=output_file
    )
    print(f"   ✅ 模型生成成功")
    print(f"   💾 保存至: {output_file}")
except Exception as e:
    print(f"   ❌ 生成失敗: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 讀取模型並驗證
print(f"\n🔍 驗證VSP模型...")
vsp.ClearVSPModel()
vsp.ReadVSPFile(output_file)

geoms = vsp.FindGeoms()
if geoms:
    fuse_id = geoms[0]
    print(f"   幾何體 ID: {fuse_id}")
    print(f"   名稱: {vsp.GetGeomName(fuse_id)}")

    # 獲取截面信息
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
    num_xsec = vsp.GetNumXSec(xsec_surf)
    print(f"   截面數量: {num_xsec}")

    # 檢查幾個關鍵截面
    print(f"\n📋 關鍵截面檢查:")

    # 機頭
    xsec_0 = vsp.GetXSec(xsec_surf, 0)
    shape_0 = vsp.GetXSecShape(xsec_0)
    print(f"   截面 0 (機頭): {'POINT' if shape_0 == vsp.XS_POINT else 'OTHER'}")

    # 中間截面
    mid_idx = num_xsec // 2
    xsec_mid = vsp.GetXSec(xsec_surf, mid_idx)
    shape_mid = vsp.GetXSecShape(xsec_mid)

    if shape_mid == vsp.XS_SUPER_ELLIPSE:
        print(f"   截面 {mid_idx} (中間): SUPER_ELLIPSE")

        # 獲取參數
        width_parm = vsp.GetXSecParm(xsec_mid, "Super_Width")
        height_parm = vsp.GetXSecParm(xsec_mid, "Super_Height")
        z_loc_parm = vsp.GetXSecParm(xsec_mid, "ZLocPercent")

        if width_parm and height_parm:
            width = vsp.GetParmVal(width_parm)
            height = vsp.GetParmVal(height_parm)
            print(f"      寬度: {width:.3f} m")
            print(f"      高度: {height:.3f} m")

        if z_loc_parm:
            z_loc = vsp.GetParmVal(z_loc_parm)
            print(f"      Z位置: {z_loc:.3f} m")

    # 機尾
    xsec_tail = vsp.GetXSec(xsec_surf, num_xsec - 1)
    shape_tail = vsp.GetXSecShape(xsec_tail)
    print(f"   截面 {num_xsec - 1} (機尾): {'POINT' if shape_tail == vsp.XS_POINT else 'OTHER'}")

    # 運行CompGeom
    print(f"\n🔧 運行 CompGeom...")
    try:
        vsp.Update()
        comp_geom_set = vsp.SET_ALL
        comp_geom_file_flag = vsp.COMP_GEOM_CSV_TYPE
        vsp.ComputeCompGeom(comp_geom_set, False, comp_geom_file_flag)

        results = vsp.FindLatestResultsID("Comp_Geom")
        if results:
            wetted_area = vsp.GetDoubleResults(results, "Wet_Area", 0)
            if wetted_area:
                print(f"   ✅ 濕表面積: {wetted_area[0]:.3f} m²")
        else:
            print(f"   ⚠️ 無法獲取CompGeom結果")
    except Exception as e:
        print(f"   ❌ CompGeom失敗: {e}")

print(f"\n" + "="*60)
print("測試完成！")
print("="*60)
print(f"\n💡 在 VSP GUI 中打開 {output_file} 檢查:")
print(f"   1. 側視圖：上半部應明顯比下半部大")
print(f"   2. 機頭：應該對稱指向正前方")
print(f"   3. 機尾：應該平滑收束成尖點")
print(f"   4. Skinning：表面應該平滑無扭結")
print("="*60)
