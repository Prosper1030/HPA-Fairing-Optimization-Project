"""
Test VSP ParasiteDrag Analysis API
探索 ParasiteDrag 分析的輸入/輸出
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import openvsp as vsp

print("="*80)
print("Testing VSP ParasiteDrag Analysis API")
print("="*80)

# Clear and create a simple test geometry
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetGeomName(fuse_id, "TestFuselage")
vsp.SetParmVal(fuse_id, "Length", "Design", 2.5)
vsp.Update()

# Save file
vsp.WriteVSPFile("output/test_drag_api.vsp3")

print("\n1. Analysis Inputs for ParasiteDrag:")
inputs = vsp.GetAnalysisInputNames("ParasiteDrag")
for inp in inputs:
    print(f"   - {inp}")

# Setup ParasiteDrag analysis
print("\n2. Setting up ParasiteDrag analysis...")

# Set flow conditions
velocity = [6.5]  # m/s
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", velocity)

# Set length unit
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])

# Set altitude
altitude = [0.0]  # sea level
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Altitude", altitude)

# Run analysis
print("\n3. Running ParasiteDrag analysis...")
res_id = vsp.ExecAnalysis("ParasiteDrag")

print(f"   Result ID: {res_id}")

# Get results - use the returned result ID directly
print("\n4. Extracting results...")
print(f"   Using result ID from ExecAnalysis: {res_id}")

# List all available result data names
all_res_names = vsp.GetAllDataNames(res_id)
print(f"\n   Available result data ({len(all_res_names)} items):")
for name in all_res_names:
    res_type = vsp.GetResultsType(res_id, name)
    print(f"      - {name} (type: {res_type})")

# Try to extract drag coefficient and other values
print("\n5. Key drag results:")
try:
    cd = vsp.GetDoubleResults(res_id, "CD_Total", 0)
    print(f"   CD_Total: {cd}")
except:
    print("   CD_Total: Not found")

try:
    drag_counts = vsp.GetDoubleResults(res_id, "Total_Drag_Counts", 0)
    print(f"   Total_Drag_Counts: {drag_counts}")
except:
    print("   Total_Drag_Counts: Not found")

try:
    wetted_area = vsp.GetDoubleResults(res_id, "Swet_Total", 0)
    print(f"   Swet_Total: {wetted_area}")
except:
    print("   Swet_Total: Not found")

print("\n6. Trying to extract all double results:")
for name in all_res_names:
    try:
        data = vsp.GetDoubleResults(res_id, name, 0)
        if len(data) > 0:
            print(f"   {name}: {data[0]}")
    except:
        pass

print("\n" + "="*80)
print("Test completed!")
print("="*80)
