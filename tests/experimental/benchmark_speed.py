"""
Benchmark the speed of VSP file generation
"""
import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.geometry import CSTGeometryGenerator

print("="*80)
print("⏱️  Speed Benchmark Test")
print("="*80)

geometry = CSTGeometryGenerator(output_dir="output")

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

print(f"\n{'Sections':<12} | {'Time (s)':<12} | {'Time per Section (ms)':<25}")
print("-"*80)

for config in test_configs:
    design = {**base_design, **config}

    start_time = time.time()
    vsp_file = geometry.generate_fuselage(design)
    elapsed = time.time() - start_time

    time_per_section = (elapsed / config["num_sections"]) * 1000  # ms

    print(f"{config['num_sections']:<12} | {elapsed:<12.3f} | {time_per_section:<25.1f}")

print("="*80)
print("\n💡 结论：")
print("   - 如果每个section < 100ms，速度正常")
print("   - 如果每个section > 500ms，可能有性能问题")
print("="*80)
