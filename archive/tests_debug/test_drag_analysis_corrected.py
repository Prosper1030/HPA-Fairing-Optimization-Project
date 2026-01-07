"""
測試修正後的阻力分析
驗證：
1. 投影面積計算是否正確
2. 摩擦係數方程式設定（Blasius + Power Law Prandtl Low Re）
3. 阻力結果是否合理
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 設置路徑
current_dir = os.path.dirname(__file__)
analysis_dir = os.path.join(current_dir, '..', 'src', 'analysis')
sys.path.insert(0, analysis_dir)

from parasite_drag_analyzer import ParasiteDragAnalyzer

print("="*80)
print("🧪 測試修正後的阻力分析")
print("="*80)

# 測試文件
test_file = "output/Fixed_Angles_Test.vsp3"

if not os.path.exists(test_file):
    print(f"\n❌ 測試文件不存在: {test_file}")
    print("請先運行 test_fixed_angles.py 生成測試文件")
    sys.exit(1)

# 設計參數（用於計算投影面積）
design_params = {
    "length": 2.5,
    "n_nose": 0.5,
    "n_tail": 1.0,
    "width_weights": [0.25, 0.35, 0.30, 0.10],
    "height_weights": [0.30, 0.45, 0.35, 0.10],
    "super_m": 2.5,
    "super_n": 2.5,
}

# 標準大氣條件（海平面，15°C）
flow_conditions = {
    'velocity': 6.5,                    # m/s
    'density': 1.225,                   # kg/m³ (標準大氣)
    'temperature': 288.15,              # K (15°C)
    'pressure': 101325.0,               # Pa (1 atm)
    'kinematic_viscosity': 1.4607e-5    # m²/s (空氣 at 15°C)
}

print(f"\n📋 測試配置：")
print(f"   模型: {test_file}")
print(f"   流速: {flow_conditions['velocity']} m/s")
print(f"   密度: {flow_conditions['density']} kg/m³")
print(f"   溫度: {flow_conditions['temperature']} K (15°C)")

# 先計算投影面積
print(f"\n📐 計算投影面積...")
projected_area = ParasiteDragAnalyzer.calculate_projected_area(design_params)
print(f"   投影面積: {projected_area:.6f} m²")

# 創建分析器
analyzer = ParasiteDragAnalyzer()

# 執行分析
print(f"\n🚀 執行阻力分析（使用 Blasius + Power Law Prandtl Low Re）...")
results = analyzer.analyze(test_file, flow_conditions, design_params=design_params, verbose=True)

# 檢查結果
if "error" in results:
    print(f"\n❌ 分析失敗: {results['error']}")
else:
    print("\n" + "="*80)
    print("📊 分析結果摘要")
    print("="*80)
    print(f"\n   阻力結果：")
    print(f"      阻力力: {results['drag_force_N']:.4f} N")
    print(f"      阻力係數 (CD): {results['drag_coefficient']:.6f}")
    print(f"      Cd·A: {results['CdA_equivalent']:.6f} m²")

    print(f"\n   幾何參數：")
    print(f"      濕面積: {results['wetted_area_m2']:.4f} m²")
    print(f"      投影面積 (Sref): {results['projected_area_m2']:.6f} m²")
    print(f"      雷諾數: {results['reynolds_number']:.0f}")

    print(f"\n   流場參數：")
    print(f"      動壓: {results['dynamic_pressure_Pa']:.4f} Pa")
    print(f"      速度: {results['flow_conditions']['velocity_ms']:.2f} m/s")
    print(f"      密度: {results['flow_conditions']['density_kgm3']:.3f} kg/m³")

    print(f"\n💡 與 GUI 結果對比：")
    print(f"   GUI CD (Sref=1.0): 0.02045")
    print(f"   API CD (Sref={results['projected_area_m2']:.6f}): {results['drag_coefficient']:.6f}")

    # 換算到相同的參考面積
    cd_normalized = results['drag_coefficient'] * results['projected_area_m2'] / 1.0
    print(f"   API CD (換算到 Sref=1.0): {cd_normalized:.6f}")

    diff_pct = abs(cd_normalized - 0.02045) / 0.02045 * 100
    print(f"   差異: {diff_pct:.2f}%")

    if diff_pct < 5.0:
        print(f"\n   ✅ 差異 < 5%，阻力分析設定正確！")
    else:
        print(f"\n   ⚠️  差異 > 5%，可能需要檢查其他設定")

print("\n" + "="*80)
print("✅ 測試完成！")
print("="*80)
