"""
Diagnostic tool to inspect VSP file cross-sections
Prints detailed information about each XSec in a fuselage
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import openvsp as vsp

def diagnose_vsp_file(vsp_filepath):
    """Load VSP file and print detailed XSec information"""
    print(f"\n{'='*80}")
    print(f"🔍 Diagnosing: {os.path.basename(vsp_filepath)}")
    print(f"{'='*80}\n")

    # Load the file
    vsp.ClearVSPModel()
    vsp.ReadVSPFile(vsp_filepath)

    # Get all geometries
    geoms = vsp.FindGeoms()
    if not geoms:
        print("❌ No geometries found in file!")
        return

    # Use first geometry (should be fuselage)
    fuse_id = geoms[0]
    fuse_name = vsp.GetGeomName(fuse_id)
    fuse_length = vsp.GetParmVal(fuse_id, "Length", "Design")

    print(f"📦 Geometry: {fuse_name}")
    print(f"📏 Length: {fuse_length:.3f} m\n")

    # Get cross-section surface
    xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
    num_xsecs = vsp.GetNumXSec(xsec_surf)

    print(f"🔢 Total XSecs: {num_xsecs}\n")
    print(f"{'Index':<6} | {'Type':<15} | {'XLoc%':<8} | {'Width':<8} | {'Height':<8} | {'M':<6} | {'N':<6}")
    print("-" * 80)

    for i in range(num_xsecs):
        xsec = vsp.GetXSec(xsec_surf, i)

        # Get XSec type
        xsec_type = vsp.GetXSecShape(xsec)
        type_names = {
            0: "POINT",
            1: "CIRCLE",
            2: "ELLIPSE",
            3: "SUPER_ELLIPSE",
            4: "ROUNDED_RECT",
            5: "GENERAL_FUSE",
            6: "FILE_FUSE"
        }
        type_name = type_names.get(xsec_type, f"UNKNOWN({xsec_type})")

        # Get position
        xloc_parm = vsp.GetXSecParm(xsec, "XLocPercent")
        xloc = vsp.GetParmVal(xloc_parm)

        # Try to get dimensions (will be 0 for POINT type)
        width = 0.0
        height = 0.0
        super_m = 0.0
        super_n = 0.0

        if xsec_type == 3:  # SUPER_ELLIPSE
            width_parm = vsp.GetXSecParm(xsec, "Super_Width")
            height_parm = vsp.GetXSecParm(xsec, "Super_Height")
            m_parm = vsp.GetXSecParm(xsec, "Super_M")
            n_parm = vsp.GetXSecParm(xsec, "Super_N")

            width = vsp.GetParmVal(width_parm)
            height = vsp.GetParmVal(height_parm)
            super_m = vsp.GetParmVal(m_parm)
            super_n = vsp.GetParmVal(n_parm)
        elif xsec_type == 2:  # ELLIPSE
            width_parm = vsp.GetXSecParm(xsec, "Ellipse_Width")
            height_parm = vsp.GetXSecParm(xsec, "Ellipse_Height")
            width = vsp.GetParmVal(width_parm)
            height = vsp.GetParmVal(height_parm)

        print(f"{i:<6} | {type_name:<15} | {xloc:<8.3f} | {width:<8.4f} | {height:<8.4f} | {super_m:<6.2f} | {super_n:<6.2f}")

    print("-" * 80)

    # Check for issues
    print("\n🔍 DIAGNOSTIC CHECKS:\n")

    # Check 1: Section distribution
    xlocs = []
    for i in range(num_xsecs):
        xsec = vsp.GetXSec(xsec_surf, i)
        xloc = vsp.GetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"))
        xlocs.append(xloc)

    # Check if evenly distributed
    if num_xsecs > 2:
        expected_spacing = 1.0 / (num_xsecs - 1)
        actual_spacings = [xlocs[i+1] - xlocs[i] for i in range(num_xsecs - 1)]
        avg_spacing = sum(actual_spacings) / len(actual_spacings)

        if abs(avg_spacing - expected_spacing) < 0.001:
            print(f"✅ Sections are evenly distributed (spacing ≈ {expected_spacing:.4f})")
        else:
            print(f"⚠️  Sections have irregular spacing:")
            print(f"   Expected: {expected_spacing:.4f}, Average: {avg_spacing:.4f}")
            print(f"   Min: {min(actual_spacings):.4f}, Max: {max(actual_spacings):.4f}")

    # Check 2: Super ellipse parameters
    super_ellipse_count = 0
    different_widths = set()
    different_ms = set()

    for i in range(num_xsecs):
        xsec = vsp.GetXSec(xsec_surf, i)
        xsec_type = vsp.GetXSecShape(xsec)

        if xsec_type == 3:  # SUPER_ELLIPSE
            super_ellipse_count += 1
            width = vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_Width"))
            m_val = vsp.GetParmVal(vsp.GetXSecParm(xsec, "Super_M"))
            different_widths.add(round(width, 4))
            different_ms.add(round(m_val, 2))

    if super_ellipse_count > 0:
        print(f"\n✅ Found {super_ellipse_count} super ellipse sections")
        print(f"   Number of different widths: {len(different_widths)}")
        print(f"   Number of different M values: {len(different_ms)}")

        if len(different_widths) > 1:
            print(f"   ✅ Sections have varying widths (CST is working)")
        else:
            print(f"   ⚠️  All sections have same width!")

        if len(different_ms) == 1:
            m_val = list(different_ms)[0]
            print(f"   ✅ Super ellipse M parameter is set to: {m_val}")
        else:
            print(f"   ⚠️  Different M values found: {different_ms}")
    else:
        print(f"⚠️  No super ellipse sections found!")

    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    # Diagnose all test files
    test_files = [
        "output/Test_1_Baseline.vsp3",
        "output/Test_2_SuperEllipse.vsp3",
        "output/Test_5_HighWeights.vsp3"
    ]

    for filepath in test_files:
        if os.path.exists(filepath):
            diagnose_vsp_file(filepath)
        else:
            print(f"⚠️  File not found: {filepath}")
