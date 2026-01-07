"""
Diagnose the quick test file
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import openvsp as vsp

vsp_filepath = "output/Quick_Test_40_Sections.vsp3"

print(f"\n{'='*80}")
print(f"🔍 Diagnosing: {os.path.basename(vsp_filepath)}")
print(f"{'='*80}\n")

# Load the file
vsp.ClearVSPModel()
vsp.ReadVSPFile(vsp_filepath)

# Get geometry
geoms = vsp.FindGeoms()
fuse_id = geoms[0]
fuse_name = vsp.GetGeomName(fuse_id)

xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
num_xsecs = vsp.GetNumXSec(xsec_surf)

print(f"📦 Geometry: {fuse_name}")
print(f"🔢 Total XSecs: {num_xsecs}\n")

# Show first 5, middle 3, and last 5 sections
indices_to_show = list(range(5)) + list(range(18, 22)) + list(range(35, 40))

print(f"{'Index':<6} | {'Type':<15} | {'XLoc%':<8} | {'Width':<8} | {'Height':<8} | {'M':<6} | {'N':<6}")
print("-" * 80)

for i in indices_to_show:
    if i >= num_xsecs:
        continue

    xsec = vsp.GetXSec(xsec_surf, i)
    xsec_type = vsp.GetXSecShape(xsec)

    type_names = {0: "POINT", 1: "CIRCLE", 2: "ELLIPSE", 3: "SUPER_ELLIPSE"}
    type_name = type_names.get(xsec_type, f"UNKNOWN({xsec_type})")

    xloc_parm = vsp.GetXSecParm(xsec, "XLocPercent")
    xloc = vsp.GetParmVal(xloc_parm)

    width = 0.0
    height = 0.0
    super_m = 0.0
    super_n = 0.0

    if xsec_type == 3:  # SUPER_ELLIPSE
        width = vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_Width"))
        height = vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_Height"))
        super_m = vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_M"))
        super_n = vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_N"))

    print(f"{i:<6} | {type_name:<15} | {xloc:<8.3f} | {width:<8.4f} | {height:<8.4f} | {super_m:<6.2f} | {super_n:<6.2f}")

    if i == 4:
        print("  ... (sections 5-17) ...")
    elif i == 21:
        print("  ... (sections 22-34) ...")

print("-" * 80)

# Statistics
print(f"\n🔍 VERIFICATION CHECKS:\n")

# Check section distribution
xlocs = []
for i in range(num_xsecs):
    xsec = vsp.GetXSec(xsec_surf, i)
    xloc = vsp.GetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"))
    xlocs.append(xloc)

expected_spacing = 1.0 / (num_xsecs - 1)
actual_spacings = [xlocs[i+1] - xlocs[i] for i in range(num_xsecs - 1)]
avg_spacing = sum(actual_spacings) / len(actual_spacings)

print(f"✅ Expected spacing: {expected_spacing:.5f}")
print(f"✅ Average spacing: {avg_spacing:.5f}")
print(f"   Min spacing: {min(actual_spacings):.5f}")
print(f"   Max spacing: {max(actual_spacings):.5f}")

# Check super ellipse parameters
widths = []
heights = []
m_values = set()
n_values = set()

for i in range(num_xsecs):
    xsec = vsp.GetXSec(xsec_surf, i)
    if vsp.GetXSecShape(xsec) == 3:
        widths.append(vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_Width")))
        heights.append(vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_Height")))
        m_values.add(round(vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_M")), 2))
        n_values.add(round(vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_N")), 2))

print(f"\n✅ Super Ellipse Parameters:")
print(f"   Unique M values: {m_values}")
print(f"   Unique N values: {n_values}")
print(f"   Width range: {min(widths):.4f} - {max(widths):.4f} m")
print(f"   Height range: {min(heights):.4f} - {max(heights):.4f} m")
print(f"   Number of unique widths: {len(set([round(w, 4) for w in widths]))}")

# Find shoulder (40% position)
shoulder_idx = int(0.4 * (num_xsecs - 1))
xsec_shoulder = vsp.GetXSec(xsec_surf, shoulder_idx)
shoulder_width = vsp.GetParmVal(vsp.GetXSecParm(xsec_shoulder, "Super_Width"))

print(f"\n✅ Shoulder Position (index {shoulder_idx}):")
print(f"   Width: {shoulder_width:.4f} m")
print(f"   XLoc: {xlocs[shoulder_idx]:.3f}")

print(f"\n{'='*80}\n")
