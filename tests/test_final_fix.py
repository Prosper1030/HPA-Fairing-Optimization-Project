"""
最終測試：使用修改後的幾何生成器（直接設置 Parm）
"""
import sys
sys.path.append('src')

from geometry.cst_geometry_math_driven import CSTGeometryMathDriven
from analysis.drag_analysis import DragAnalyzer

print("="*80)
print("🧪 最終測試：直接設置 ParasiteDrag Parm 到文件")
print("="*80)

# ========== 生成幾何 ==========
design_params = {
    "name": "Final_Fixed_Test",
    "length": 2.5,
    "n_nose": 0.5,
    "n_tail": 1.0,
    "width_weights": [0.25, 0.35, 0.30, 0.10],
    "height_weights": [0.30, 0.45, 0.35, 0.10],
    "super_m": 2.5,
    "super_n": 2.5,
}

generator = CSTGeometryMathDriven(output_dir="output")

print(f"\n生成幾何中...")
filepath_result = generator.generate_fuselage(design_params, verbose=True)

# 提取文件路徑
if isinstance(filepath_result, dict):
    filepath = filepath_result.get('filepath')
else:
    filepath = filepath_result

if not filepath:
    print(f"\n❌ 幾何生成失敗")
    exit(1)

print(f"\n✅ 幾何生成成功")
print(f"   文件: {filepath}")

# ========== 執行簡單分析 ==========
print(f"\n{'='*80}")
print("執行 ParasiteDrag 分析")
print(f"{'='*80}")

analyzer = DragAnalyzer(output_dir="output")

velocity = 6.5  # m/s
rho = 1.225  # kg/m³
mu = 1.7894e-5  # kg/(m·s)

result = analyzer.run_analysis(filepath, velocity, rho, mu)

if result:
    print(f"\n✅ 分析成功！")
    print(f"\n   Cd: {result.get('Cd', 'N/A')}")
    print(f"   CdA: {result.get('CdA', 'N/A')}")
    print(f"   Swet: {result.get('Swet', 'N/A')}")

    # 關鍵檢查：Cd 數量級
    cd = result.get('Cd', 0)
    if cd > 0.005:
        print(f"\n💡 Cd 數量級正確！(> 0.005)")
        print(f"   這表示使用了正確的 Sref（1.0 m²，不是 100 ft²）")

        # 與 GUI 對比
        gui_cd = 0.02045
        diff_pct = abs(cd - gui_cd) / gui_cd * 100
        print(f"\n   GUI CD: {gui_cd}")
        print(f"   API CD: {cd}")
        print(f"   差異: {diff_pct:.2f}%")

        if diff_pct < 10.0:
            print(f"\n   ✅✅✅ 成功！問題解決！")
    else:
        print(f"\n   ❌ Cd 仍然過小，Sref 仍然錯誤")

print(f"\n{'='*80}")
