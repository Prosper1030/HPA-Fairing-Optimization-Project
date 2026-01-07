"""
Debug script to understand XSec insertion behavior
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import openvsp as vsp

print("="*80)
print("🔍 Debug: XSec Insertion Behavior")
print("="*80)

# Clear and create fresh fuselage
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetGeomName(fuse_id, "Debug_Test")

# Get XSec surface
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

# Check initial state
initial_count = vsp.GetNumXSec(xsec_surf)
print(f"\n📊 Initial XSec count: {initial_count}")

# Try inserting sections
print(f"\n🔨 Attempting to insert 10 sections...\n")

for i in range(10):
    before_count = vsp.GetNumXSec(xsec_surf)
    tail_index = before_count - 1

    print(f"Insert #{i+1}: Before={before_count} sections, inserting at index {tail_index}")

    # Try insertion
    vsp.InsertXSec(fuse_id, tail_index, vsp.XS_SUPER_ELLIPSE)

    after_count = vsp.GetNumXSec(xsec_surf)

    if after_count > before_count:
        print(f"  ✅ Success! Now have {after_count} sections")
    else:
        print(f"  ❌ FAILED! Still have {after_count} sections")
        break

print(f"\n📊 Final XSec count: {vsp.GetNumXSec(xsec_surf)}")

# List all XSecs
print(f"\n📋 XSec Details:")
for i in range(vsp.GetNumXSec(xsec_surf)):
    xsec = vsp.GetXSec(xsec_surf, i)
    xsec_type = vsp.GetXSecShape(xsec)
    type_names = {0: "POINT", 1: "CIRCLE", 2: "ELLIPSE", 3: "SUPER_ELLIPSE"}
    print(f"  Index {i}: Type = {type_names.get(xsec_type, xsec_type)}")

print("\n" + "="*80)
