"""
測試：使用修改後的幾何生成器生成 VSP 文件，並測試 ParasiteDrag 分析
"""
import sys
sys.path.append('src')

from geometry.cst_geometry_math_driven import CSTGeometryMathDriven
from analysis.drag_analysis import DragAnalyzer

print("="*80)
print("🧪 測試：修改後的幾何生成器 + ParasiteDrag 分析")
print("="*80)

# ========== STEP 1: 生成幾何 ==========
print(f"\n{'='*80}")
print("STEP 1: 生成幾何（使用修改後的生成器）")
print(f"{'='*80}")

design_params = {
    "name": "Test_Fixed_ParasiteDrag",
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
filepath = generator.generate_fuselage(
    design_params,
    verbose=True
)

# 構造result字典以保持一致性
result = {
    'success': filepath is not None,
    'filepath': filepath if filepath else None
}

if result['success']:
    print(f"\n✅ 幾何生成成功！")
    print(f"   文件: {result['filepath']}")
else:
    print(f"\n❌ 幾何生成失敗")
    exit(1)

# ========== STEP 2: 執行 ParasiteDrag 分析 ==========
print(f"\n{'='*80}")
print("STEP 2: 執行 ParasiteDrag 分析（使用簡單 API）")
print(f"{'='*80}")

analyzer = DragAnalyzer(output_dir="output")

velocity = 6.5  # m/s
rho = 1.225  # kg/m³
mu = 1.7894e-5  # kg/(m·s)

print(f"\n分析參數:")
print(f"   Velocity: {velocity} m/s")
print(f"   Rho: {rho} kg/m³")
print(f"   Mu: {mu} kg/(m·s)")

print(f"\n執行分析...")
drag_result = analyzer.run_analysis(
    result['filepath'],
    velocity,
    rho,
    mu
)

# ========== STEP 3: 驗證結果 ==========
print(f"\n{'='*80}")
print("STEP 3: 驗證結果")
print(f"{'='*80}")

if drag_result:
    print(f"\n✅ 分析成功！")
    print(f"\n   CdA: {drag_result.get('CdA', 'N/A')}")
    print(f"   Cd: {drag_result.get('Cd', 'N/A')}")
    print(f"   Swet: {drag_result.get('Swet', 'N/A')} m²")
    print(f"   Drag: {drag_result.get('Drag', 'N/A')} N")

    # 檢查單位
    cd = drag_result.get('Cd', 0)
    if cd > 0.001:
        print(f"\n💡 Cd 值檢查:")
        print(f"   Cd = {cd:.6f}")
        print(f"   數量級正確（> 0.001），使用正確的 Sref！")

        # 與預期對比
        expected_cd = 0.02045  # GUI 參考值
        diff_pct = abs(cd - expected_cd) / expected_cd * 100
        print(f"\n   預期 CD（GUI 參考）: {expected_cd}")
        print(f"   實際 CD: {cd:.6f}")
        print(f"   差異: {diff_pct:.2f}%")

        if diff_pct < 10.0:
            print(f"\n   ✅✅✅ 成功！單位和設置都正確！")
        elif diff_pct < 30.0:
            print(f"\n   ✅ 差異合理，可能是幾何或流場條件略有不同")
        else:
            print(f"\n   ⚠️  差異較大，可能還有其他問題")
    else:
        print(f"\n   ❌ Cd 值過小 ({cd})，仍然使用錯誤的 Sref！")

else:
    print(f"\n❌ 分析失敗：未生成 CSV")

print(f"\n{'='*80}")
