"""對最終完整版本執行阻力分析"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from analysis.parasite_drag_analyzer import ParasiteDragAnalyzer
import numpy as np
import openvsp as vsp

# 分析最終版本檔案
vsp_file = "output/current/fairing_final_complete.vsp3"

# 先用 VSP API 計算投影面積
vsp.ClearVSPModel()
vsp.ReadVSPFile(vsp_file)
vsp.Update()

# 執行 CompGeom 獲取幾何信息
vsp.SetAnalysisInputDefaults("CompGeom")
comp_res_id = vsp.ExecAnalysis("CompGeom")

# 獲取濕面積
wetted_areas = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)
if len(wetted_areas) > 0:
    swet_compgeom = wetted_areas[0]
    print(f"CompGeom 濕面積: {swet_compgeom:.6f} m²")

# 手動計算投影面積（基於之前的基因）
gene = {
    'W_max': 0.60,
    'H_top_max': 0.95,
    'H_bot_max': 0.35,
}

max_width = 0.601  # m (實際)
max_height_total = 1.303  # m (實際)
projected_area = np.pi * (max_width / 2) * (max_height_total / 2)

print(f"計算的投影面積: {projected_area:.6f} m²")

# 流體條件
flow_conditions = {
    'velocity': 15.0,                   # m/s
    'density': 1.204,                   # kg/m³ (20°C, 1 atm)
    'temperature': 293.15,              # K (20°C)
    'pressure': 101325.0,               # Pa (1 atm)
    'kinematic_viscosity': 1.516e-5     # m²/s (空氣 at 20°C)
}

print("\n" + "="*80)
print("執行 ParasiteDrag 分析")
print("="*80)

analyzer = ParasiteDragAnalyzer()

results = analyzer.analyze(
    vsp_file_path=vsp_file,
    flow_conditions=flow_conditions,
    projected_area=projected_area,
    verbose=True
)

if "error" not in results:
    cda = results['CdA_equivalent']
    wetted_area = results['wetted_area_m2']
    cd = results['drag_coefficient']
    drag_force = results['drag_force_N']

    cd_proj = cda / projected_area
    drag_counts = cd_proj * 10000

    print("\n" + "="*80)
    print("最終結果")
    print("="*80)
    print(f"\n幾何：")
    print(f"  投影面積：{projected_area:.6f} m²")
    print(f"  濕潤表面積：{wetted_area:.6f} m²")

    print(f"\n阻力：")
    print(f"  阻力面積 CdA：{cda:.6f} m²")
    print(f"  阻力係數 Cd：{cd_proj:.6f}")
    print(f"  阻力計數：{drag_counts:.1f} counts")
    print(f"  阻力力量：{drag_force:.4f} N @ 15 m/s")

    print("\n" + "="*80)

else:
    print(f"❌ 分析失敗: {results['error']}")
