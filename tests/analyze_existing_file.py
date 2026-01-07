"""直接用DragAnalyzer分析現有的fairing_final_complete.vsp3"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from analysis.drag_analysis import DragAnalyzer

print("="*80)
print("使用DragAnalyzer分析 fairing_final_complete.vsp3")
print("="*80)

vsp_file = "output/current/fairing_final_complete.vsp3"

analyzer = DragAnalyzer(output_dir="output/results")

# 使用標準條件
velocity = 6.5  # m/s
rho = 1.225  # kg/m³
mu = 1.7894e-5  # kg/(m·s)

print(f"\n分析檔案: {vsp_file}")
print(f"速度: {velocity} m/s")
print(f"密度: {rho} kg/m³")

result = analyzer.run_analysis(vsp_file, velocity, rho, mu)

if result:
    print(f"\n{'='*80}")
    print("結果")
    print(f"{'='*80}")
    print(f"\nCd: {result.get('Cd', 'N/A')}")
    print(f"CdA: {result.get('CdA', 'N/A')} m²")
    print(f"Swet: {result.get('Swet', 'N/A')} m²")
    print(f"Drag: {result.get('Drag', 'N/A')} N")

    # 與GUI對比
    gui_cd = 0.04121  # 從您的截圖
    api_cd = result.get('Cd', 0)

    print(f"\n與GUI對比：")
    print(f"  GUI CD: {gui_cd}")
    print(f"  API CD: {api_cd}")
    if api_cd > 0:
        diff_pct = abs(api_cd - gui_cd) / gui_cd * 100
        print(f"  差異: {diff_pct:.2f}%")

        if diff_pct < 5:
            print(f"\n  ✅ 成功！")
        else:
            print(f"\n  ⚠️  仍有差異")
else:
    print("\n❌ 分析失敗")

print(f"\n{'='*80}")
