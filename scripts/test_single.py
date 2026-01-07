"""
Quick test script - generates and analyzes a single design
Usage: run.bat scripts/test_single.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.geometry import CSTGeometryGenerator
from src.analysis import DragAnalyzer

print("🧪 Quick Test - Single Design")
print("-" * 50)

# Initialize
geometry = CSTGeometryGenerator(output_dir="output")
analyzer = DragAnalyzer(output_dir="output")

# Test design
test_design = {
    "name": "QuickTest",
    "length": 2.5,
    "n_nose": 0.5,
    "n_tail": 1.0,
    "width_weights": [0.15, 0.20, 0.20, 0.05],
    "height_weights": [0.20, 0.35, 0.25, 0.05],
    "super_m": 2.5,
    "super_n": 2.5,
}

# Generate
print("Generating geometry...")
vsp_file = geometry.generate_fuselage(test_design)

# Analyze
print("Running drag analysis...")
result = analyzer.run_analysis(vsp_file, velocity=6.5, rho=1.1839, mu=1.8371e-05)

if result:
    print("\n✅ Test Passed!")
    print(f"   Drag = {result['Drag']:.4f} N")
    print(f"   Cd   = {result['Cd']:.6f}")
else:
    print("\n❌ Test Failed!")
