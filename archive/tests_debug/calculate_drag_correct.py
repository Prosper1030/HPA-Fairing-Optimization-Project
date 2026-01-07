"""使用已驗證的 ParasiteDragAnalyzer 計算阻力"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# 強制重新載入
for module in ['optimization.hpa_asymmetric_optimizer', 'analysis.parasite_drag_analyzer']:
    if module in sys.modules:
        del sys.modules[module]

from optimization.hpa_asymmetric_optimizer import CST_Modeler, VSPModelGenerator
from analysis.parasite_drag_analyzer import ParasiteDragAnalyzer
import numpy as np

# 基因定義
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
print("使用已驗證的 ParasiteDragAnalyzer 計算阻力")
print("="*80)

# 生成曲線
curves = CST_Modeler.generate_asymmetric_fairing(gene, num_sections=40)

# 生成 VSP 模型
output_file = "output/current/fairing_drag_correct.vsp3"
print(f"\n生成VSP模型: {output_file}")

VSPModelGenerator.create_fuselage(
    curves,
    name="Fairing_Drag_Test",
    filepath=output_file
)

print(f"✅ VSP模型已生成")

# 準備設計參數（用於計算投影面積）
# 注意：ParasiteDragAnalyzer 需要對稱幾何的參數格式
# 對於非對稱幾何，我們需要使用平均值或手動計算投影面積

# 計算理論投影面積
max_width = np.max(curves['width'])
max_height_top = np.max(curves['z_upper'])
min_height_bot = np.min(curves['z_lower'])
max_height_total = max_height_top - min_height_bot

projected_area = np.pi * (max_width / 2) * (max_height_total / 2)

print(f"\n幾何參數：")
print(f"  長度 L = {gene['L']:.3f} m")
print(f"  最大寬度 = {max_width:.3f} m")
print(f"  總高度 = {max_height_total:.3f} m")
print(f"  投影面積（橢圓近似）= {projected_area:.6f} m²")

# 設置流體條件（標準條件）
flow_conditions = {
    'velocity': 15.0,                   # m/s
    'density': 1.204,                   # kg/m³ (20°C, 1 atm)
    'temperature': 293.15,              # K (20°C)
    'pressure': 101325.0,               # Pa (1 atm)
    'kinematic_viscosity': 1.516e-5     # m²/s (空氣 at 20°C)
}

print(f"\n流體條件：")
print(f"  速度：{flow_conditions['velocity']} m/s")
print(f"  溫度：{flow_conditions['temperature']} K ({flow_conditions['temperature']-273.15:.1f}°C)")
print(f"  密度：{flow_conditions['density']} kg/m³")
print(f"  壓力：{flow_conditions['pressure']} Pa")

# 創建分析器並執行
print(f"\n執行 ParasiteDrag 分析...")
print("="*80)

analyzer = ParasiteDragAnalyzer()

# 使用修改後的 analyze 函數，直接傳入投影面積
results = analyzer.analyze(
    vsp_file_path=output_file,
    flow_conditions=flow_conditions,
    design_params=None,
    projected_area=projected_area,  # 直接指定投影面積
    verbose=True
)

# 顯示結果
if "error" not in results:
    cda_value = results['CdA_equivalent']
    wetted_area = results['wetted_area_m2']
    cd_value = results['drag_coefficient']
    drag_force = results['drag_force_N']

    # 基於投影面積重新計算 Cd（因為 VSP 用 Sref 計算 CD）
    cd_projected = cda_value / projected_area
    drag_counts = cd_projected * 10000

    print(f"\n幾何：")
    print(f"  投影面積（橢圓近似）：{projected_area:.6f} m²")
    print(f"  濕潤表面積：{wetted_area:.6f} m²")

    print(f"\n阻力結果：")
    print(f"  阻力面積 CdA：{cda_value:.6f} m²")
    print(f"  阻力係數 Cd：{cd_projected:.6f} (基於投影面積)")
    print(f"  阻力計數：{drag_counts:.1f} counts")
    print(f"  阻力力量：{drag_force:.4f} N @ {flow_conditions['velocity']} m/s")

    print(f"\n摘要：")
    print(f"  ┌{'─'*60}┐")
    print(f"  │ 投影面積：{projected_area:.6f} m²{' '*(37-len(f'{projected_area:.6f}'))}│")
    print(f"  │ 濕潤表面積：{wetted_area:.6f} m²{' '*(35-len(f'{wetted_area:.6f}'))}│")
    print(f"  │ 阻力面積 CdA：{cda_value:.6f} m²{' '*(34-len(f'{cda_value:.6f}'))}│")
    print(f"  │ 阻力係數 Cd：{cd_projected:.6f} (基於投影面積){' '*(18-len(f'{cd_projected:.6f}'))}│")
    print(f"  │ 阻力計數：{drag_counts:.1f} counts{' '*(39-len(f'{drag_counts:.1f}'))}│")
    print(f"  │ 阻力力量：{drag_force:.4f} N @ {flow_conditions['velocity']} m/s{' '*(27-len(f'{drag_force:.4f}'))}│")
    print(f"  └{'─'*60}┘")

else:
    print(f"\n❌ 分析失敗: {results['error']}")

print("\n" + "="*80)
print("✅ 計算完成！")
print("="*80)
