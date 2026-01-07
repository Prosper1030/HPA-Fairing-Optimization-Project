"""
Test if CutXSec actually SPLITS sections instead of removing them
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import openvsp as vsp

print("="*80)
print("🔍 Debug: CutXSec Behavior")
print("="*80)

# Clear and create fresh fuselage
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetGeomName(fuse_id, "Debug_Cut_Test")

# Get XSec surface
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

# Check initial state
initial_count = vsp.GetNumXSec(xsec_surf)
print(f"\n📊 Initial XSec count: {initial_count}")

# Try CutXSec at different positions
print(f"\n🔨 Testing CutXSec (might split, not remove)...\n")

for i in range(5):
    before_count = vsp.GetNumXSec(xsec_surf)

    # Cut at index 1 (between nose and first section)
    print(f"Cut #{i+1}: Before={before_count} sections, cutting at index 1")

    vsp.CutXSec(xsec_surf, 1)

    after_count = vsp.GetNumXSec(xsec_surf)

    if after_count > before_count:
        print(f"  ✅ CutXSec SPLITS! Now have {after_count} sections (+{after_count - before_count})")
    elif after_count < before_count:
        print(f"  ❌ CutXSec REMOVES! Now have {after_count} sections ({before_count - after_count} removed)")
        break
    else:
        print(f"  ⚠️  No change, still {after_count} sections")
        break

print(f"\n📊 Final XSec count: {vsp.GetNumXSec(xsec_surf)}")

# List all XSecs
print(f"\n📋 XSec Details:")
for i in range(vsp.GetNumXSec(xsec_surf)):
    xsec = vsp.GetXSec(xsec_surf, i)
    xsec_type = vsp.GetXSecShape(xsec)
    type_names = {0: "POINT", 1: "CIRCLE", 2: "ELLIPSE", 3: "SUPER_ELLIPSE"}
    xloc = vsp.GetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"))
    print(f"  Index {i}: Type = {type_names.get(xsec_type, xsec_type)}, XLoc = {xloc:.3f}")

print("\n" + "="*80)

# Now test the opposite: can we split by inserting at intermediate positions?
print("\n🔨 Testing InsertXSec with intermediate XLocPercent values...")
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

print(f"Initial count: {vsp.GetNumXSec(xsec_surf)}")

# Try inserting and immediately setting XLocPercent
for idx in [1, 2, 3]:
    before = vsp.GetNumXSec(xsec_surf)
    vsp.InsertXSec(fuse_id, idx, vsp.XS_SUPER_ELLIPSE)
    vsp.Update()
    after = vsp.GetNumXSec(xsec_surf)
    print(f"  Insert at {idx}: {before} -> {after}")

print(f"Final count: {vsp.GetNumXSec(xsec_surf)}")
print("="*80)
