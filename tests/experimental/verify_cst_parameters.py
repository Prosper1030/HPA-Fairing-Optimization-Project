"""
CST Parameter Verification Test
生成多個測試設計，輸出 VSP 檔案和視覺化圖，供人工檢查
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.geometry import CSTGeometryGenerator
from src.utils.cst_visualizer import CSTVisualizer
import matplotlib.pyplot as plt

print("=" * 80)
print("🧪 CST Parameter Verification Test")
print("=" * 80)

# Initialize
geometry = CSTGeometryGenerator(output_dir="output")
visualizer = CSTVisualizer()

# Define test cases with different parameter combinations
test_designs = [
    {
        "name": "Test_1_Baseline",
        "description": "基準設計：中等長度、標準橢圓",
        "length": 2.5,
        "n_nose": 0.5,
        "n_tail": 1.0,
        "width_weights": [0.15, 0.20, 0.20, 0.05],
        "height_weights": [0.20, 0.35, 0.25, 0.05],
        "super_m": 2.0,  # 標準橢圓
        "super_n": 2.0,
        "num_sections": 40
    },
    {
        "name": "Test_2_SuperEllipse",
        "description": "超橢圓測試：方形化以容納肩膀",
        "length": 2.5,
        "n_nose": 0.5,
        "n_tail": 1.0,
        "width_weights": [0.15, 0.20, 0.20, 0.05],
        "height_weights": [0.20, 0.35, 0.25, 0.05],
        "super_m": 2.8,  # 明顯方形
        "super_n": 2.8,
        "num_sections": 40
    },
    {
        "name": "Test_3_SharpNose",
        "description": "尖鼻測試：N1=0.3（更尖銳）",
        "length": 2.5,
        "n_nose": 0.3,  # 更尖
        "n_tail": 1.0,
        "width_weights": [0.10, 0.18, 0.18, 0.05],
        "height_weights": [0.15, 0.30, 0.20, 0.05],
        "super_m": 2.5,
        "super_n": 2.5,
        "num_sections": 40
    },
    {
        "name": "Test_4_BluntNose",
        "description": "鈍鼻測試：N1=0.7（更圓潤）",
        "length": 2.5,
        "n_nose": 0.7,  # 更鈍
        "n_tail": 0.8,  # 尾部也較鈍
        "width_weights": [0.20, 0.25, 0.22, 0.08],
        "height_weights": [0.25, 0.38, 0.28, 0.08],
        "super_m": 2.5,
        "super_n": 2.5,
        "num_sections": 40
    },
    {
        "name": "Test_5_HighWeights",
        "description": "高權重測試：座艙區域明顯隆起",
        "length": 2.5,
        "n_nose": 0.5,
        "n_tail": 1.0,
        "width_weights": [0.25, 0.35, 0.30, 0.10],  # 高權重
        "height_weights": [0.30, 0.45, 0.35, 0.10],  # 高權重
        "super_m": 2.5,
        "super_n": 2.5,
        "num_sections": 40
    },
]

print(f"\n📋 Total test cases: {len(test_designs)}\n")

# Process each design
results = []
for i, design in enumerate(test_designs, 1):
    print(f"[{i}/{len(test_designs)}] Processing: {design['name']}")
    print(f"   📝 {design['description']}")

    # Generate VSP file
    try:
        vsp_file = geometry.generate_fuselage(design)
        print(f"   ✅ VSP file: {vsp_file}")
    except Exception as e:
        print(f"   ❌ VSP generation failed: {e}")
        continue

    # Generate 2D profile plot
    fig_2d = visualizer.plot_2d_profile(
        design,
        save_path=f"output/{design['name']}_2D_Profile.png"
    )
    plt.close(fig_2d)

    # Generate 3D shape plot
    fig_3d = visualizer.plot_3d_shape(
        design,
        num_sections=design['num_sections'],
        save_path=f"output/{design['name']}_3D_Shape.png"
    )
    plt.close(fig_3d)

    # Calculate shoulder width for reference
    psi_shoulder = 0.4
    shoulder_width = visualizer.calculate_cst_radius(
        psi_shoulder,
        design["n_nose"],
        design["n_tail"],
        design["width_weights"],
        design["length"]
    ) * 2

    results.append({
        "name": design["name"],
        "vsp_file": vsp_file,
        "shoulder_width": shoulder_width,
        "description": design["description"]
    })

    print(f"   📐 Shoulder width (40% position): {shoulder_width:.3f} m")
    print("-" * 80)

# Create comparison plot
print("\n📊 Creating comparison plot...")
fig_compare = visualizer.create_comparison_plot(
    test_designs,
    save_path="output/Test_Comparison_All.png"
)
plt.close(fig_compare)

# Summary
print("\n" + "=" * 80)
print("📊 TEST SUMMARY")
print("=" * 80)

header = f"{'Test Name':<25} | {'Shoulder Width (m)':<20} | {'Status':<10}"
print(header)
print("-" * 80)

for res in results:
    status = "✅ PASS" if res["shoulder_width"] >= 0.45 else "⚠️  NARROW"
    row = f"{res['name']:<25} | {res['shoulder_width']:<20.3f} | {status:<10}"
    print(row)

print("=" * 80)

print("\n📁 檢查以下檔案：")
print("\n🔹 VSP 檔案（用 OpenVSP GUI 開啟）：")
for res in results:
    print(f"   - {res['vsp_file']}")

print("\n🔹 視覺化圖片（2D 輪廓）：")
for design in test_designs:
    print(f"   - output/{design['name']}_2D_Profile.png")

print("\n🔹 視覺化圖片（3D 形狀）：")
for design in test_designs:
    print(f"   - output/{design['name']}_3D_Shape.png")

print("\n🔹 比較圖（全部設計）：")
print(f"   - output/Test_Comparison_All.png")

print("\n" + "=" * 80)
print("✅ Verification test completed!")
print("=" * 80)
