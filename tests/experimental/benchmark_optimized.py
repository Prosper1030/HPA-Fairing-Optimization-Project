"""
Benchmark optimized vs original implementation
"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.geometry import CSTGeometryGenerator
from src.geometry.cst_geometry_optimized import CSTGeometryGeneratorOptimized

print("="*80)
print("⏱️  Performance Comparison: Original vs Optimized")
print("="*80)

# Test configurations
test_configs = [
    {"name": "10_sections", "num_sections": 10},
    {"name": "20_sections", "num_sections": 20},
    {"name": "40_sections", "num_sections": 40},
]

base_design = {
    "length": 2.5,
    "n_nose": 0.5,
    "n_tail": 1.0,
    "width_weights": [0.25, 0.35, 0.30, 0.10],
    "height_weights": [0.30, 0.45, 0.35, 0.10],
    "super_m": 2.5,
    "super_n": 2.5,
}

print(f"\n{'Sections':<12} | {'Original (s)':<15} | {'Optimized (s)':<15} | {'Speedup':<10}")
print("-"*80)

for config in test_configs:
    design = {**base_design, **config}

    # Test original
    geometry_orig = CSTGeometryGenerator(output_dir="output")
    start_time = time.time()
    geometry_orig.generate_fuselage(design)
    time_orig = time.time() - start_time

    # Test optimized
    design_opt = {**design, "name": config["name"] + "_opt"}
    geometry_opt = CSTGeometryGeneratorOptimized(output_dir="output")
    start_time = time.time()
    geometry_opt.generate_fuselage(design_opt)
    time_opt = time.time() - start_time

    speedup = time_orig / time_opt if time_opt > 0 else 0

    print(f"{config['num_sections']:<12} | {time_orig:<15.3f} | {time_opt:<15.3f} | {speedup:<10.2f}x")

print("="*80)
print("\n💡 结论：")
print("   - Speedup > 1.5x: 优化有效")
print("   - Speedup < 1.2x: 优化效果有限")
print("="*80)
