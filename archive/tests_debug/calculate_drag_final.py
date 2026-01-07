"""計算最終版本的阻力和投影面積"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入
for module in ['optimization.hpa_asymmetric_optimizer', 'analysis.drag_analysis']:
    if module in sys.modules:
        del sys.modules[module]

from optimization.hpa_asymmetric_optimizer import CST_Modeler, VSPModelGenerator
from analysis.drag_analysis import DragAnalyzer
import openvsp as vsp

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

print("="*80)
print("最終版本 - 阻力和投影面積計算")
print("="*80)

# 生成曲線
curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

# 計算理論投影面積（從幾何定義）
import numpy as np

# 找到最大寬度和上下最大高度
max_width = np.max(curves['width'])  # 全寬
max_height_top = np.max(curves['z_upper'])
min_height_bot = np.min(curves['z_lower'])
max_height_total = max_height_top - min_height_bot

print(f"\n幾何參數：")
print(f"  長度 L = {gene['L']:.3f} m")
print(f"  最大寬度（理論）= {gene['W_max']:.3f} m")
print(f"  最大寬度（實際）= {max_width:.3f} m")
print(f"  上半部最大高度（理論）= {gene['H_top_max']:.3f} m")
print(f"  上半部最大高度（實際）= {max_height_top:.3f} m")
print(f"  下半部最大高度（理論）= {gene['H_bot_max']:.3f} m")
print(f"  下半部最大高度（實際）= {abs(min_height_bot):.3f} m")
print(f"  總高度 = {max_height_total:.3f} m")

# 理論投影面積（近似為橢圓）
projected_area_approx = np.pi * (max_width / 2) * (max_height_total / 2)
print(f"\n投影面積（橢圓近似）= {projected_area_approx:.6f} m²")

# 生成 VSP 模型
output_file = "output/current/fairing_final_for_drag.vsp3"
print(f"\n生成VSP模型: {output_file}")

VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_Final_Drag",
    filepath=output_file
)

print(f"✅ VSP模型已生成")

# 計算投影面積（使用 CompGeom）
print(f"\n計算投影面積（CompGeom）...")
try:
    vsp.ReadVSPFile(output_file)
    vsp.Update()

    # 設置 CompGeom
    geom_set = vsp.GetStringAnalysisInput("CompGeom", "Set")
    vsp.SetStringAnalysisInput("CompGeom", "Set", [str(vsp.SET_ALL)])

    # 執行 CompGeom
    comp_res_id = vsp.ExecAnalysis("CompGeom")

    if comp_res_id:
        # 獲取投影面積（X方向投影 = 正面投影面積）
        proj_areas = vsp.GetDoubleResults(comp_res_id, "Proj_Area", 0)

        if len(proj_areas) > 0:
            # proj_areas[0] = X投影, [1] = Y投影, [2] = Z投影
            projected_area_vsp = proj_areas[0]  # X方向投影（正面）
            print(f"✅ VSP投影面積（X方向）= {projected_area_vsp:.6f} m²")
            print(f"   差異 = {abs(projected_area_vsp - projected_area_approx):.6f} m² ({abs(projected_area_vsp - projected_area_approx)/projected_area_approx*100:.2f}%)")
        else:
            print("⚠️ 無法獲取投影面積數據")
            projected_area_vsp = projected_area_approx
    else:
        print("⚠️ CompGeom執行失敗")
        projected_area_vsp = projected_area_approx

except Exception as e:
    print(f"⚠️ CompGeom錯誤: {e}")
    projected_area_vsp = projected_area_approx

# 計算阻力（使用 DragAnalyzer）
print(f"\n計算寄生阻力（ParasiteDrag）...")
try:
    # 大氣參數（20°C, 1 atm）
    rho = 1.204      # kg/m³
    mu = 1.825e-5    # kg/m·s (動力黏度)
    velocity = 15.0  # m/s

    # 使用 DragAnalyzer 類別
    analyzer = DragAnalyzer(output_dir="output/results")
    result = analyzer.run_analysis(output_file, velocity, rho, mu)

    if result:
        print(f"\n✅ 阻力分析完成！")
        print(f"\n摘要：")
        print(f"  投影面積（橢圓近似）：{projected_area_approx:.6f} m²")
        print(f"  濕潤表面積 Swet：{result['Swet']:.6f} m²")
        print(f"  阻力面積 CdA：{result['CdA']:.6f} m²")
        print(f"  阻力係數 Cd：{result['Cd']:.6f} (Sref = Swet)")
        print(f"  阻力力量 D：{result['Drag']:.4f} N @ {velocity} m/s")

        # 如果使用投影面積作為參考，重新計算 Cd
        if projected_area_approx > 0:
            cd_proj = result['CdA'] / projected_area_approx
            print(f"\n  阻力係數 Cd：{cd_proj:.6f} (Sref = 投影面積)")
            drag_counts = cd_proj * 10000
            print(f"  阻力計數：{drag_counts:.1f} counts")

    else:
        print("⚠️ ParasiteDrag分析失敗")

except Exception as e:
    print(f"⚠️ ParasiteDrag錯誤: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("✅ 計算完成！")
print("="*80)
