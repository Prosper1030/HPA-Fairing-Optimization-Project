"""
Quick test to verify 40 sections are created
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.geometry import CSTGeometryGenerator
import openvsp as vsp

print("Quick Section Count Test")
print("="*50)

# Create geometry generator
geometry = CSTGeometryGenerator(output_dir="output")

# Simple test design with 40 sections
test_design = {
    "name": "Quick_Test_40_Sections",
    "length": 2.5,
    "n_nose": 0.5,
    "n_tail": 1.0,
    "width_weights": [0.25, 0.35, 0.30, 0.10],
    "height_weights": [0.30, 0.45, 0.35, 0.10],
    "super_m": 2.5,
    "super_n": 2.5,
    "num_sections": 40
}

print(f"Generating: {test_design['name']}")
print(f"Requested sections: {test_design['num_sections']}")

vsp_file = geometry.generate_fuselage(test_design)

# Load and check
vsp.ClearVSPModel()
vsp.ReadVSPFile(vsp_file)
geoms = vsp.FindGeoms()
fuse_id = geoms[0]
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
actual_count = vsp.GetNumXSec(xsec_surf)

print(f"Actual sections: {actual_count}")

if actual_count == test_design['num_sections']:
    print("✅ SUCCESS! Correct number of sections created")
else:
    print(f"❌ FAIL! Expected {test_design['num_sections']}, got {actual_count}")

# Check section types
super_ellipse_count = 0
for i in range(actual_count):
    xsec = vsp.GetXSec(xsec_surf, i)
    if vsp.GetXSecShape(xsec) == 3:  # SUPER_ELLIPSE
        super_ellipse_count += 1

print(f"Super ellipse sections: {super_ellipse_count}")
print(f"Point sections: {actual_count - super_ellipse_count}")

print("="*50)
