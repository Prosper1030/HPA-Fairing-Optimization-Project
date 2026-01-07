"""
測試修正後的角度符號
驗證後段曲線是否平滑
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

current_dir = os.path.dirname(__file__)
geometry_dir = os.path.join(current_dir, '..', 'src', 'geometry')
sys.path.insert(0, geometry_dir)

from cst_geometry_math_driven import CSTGeometryMathDriven

print("="*80)
print("🧪 測試修正後的角度符號（後段曲線修正）")
print("="*80)

generator = CSTGeometryMathDriven(output_dir="output")

# 測試設計
test_design = {
    "name": "Fixed_Angles_Test",
    "length": 2.5,
    "n_nose": 0.5,
    "n_tail": 1.0,
    "width_weights": [0.25, 0.35, 0.30, 0.10],
    "height_weights": [0.30, 0.45, 0.35, 0.10],
    "super_m": 2.5,
    "super_n": 2.5,
    "num_sections": 40,
    "section_distribution": "cosine_full",
    "continuity": 1,
    "tangent_strength": 0.75,
    "run_drag_analysis": False  # 只關注幾何
}

print("\n生成模型...")
result = generator.generate_fuselage(test_design, verbose=True)

print("\n" + "="*80)
print("✅ 模型已生成！")
print(f"📁 文件: {result['filepath']}")
print("\n💡 請在 OpenVSP GUI 中打開此文件，檢查：")
print("   1. 機頭前段是否平滑（應該已經OK）")
print("   2. ⭐ 機身後段（過最高點後）是否平滑（應該已修正）")
print("   3. 機尾收斂是否自然")
print("="*80)
