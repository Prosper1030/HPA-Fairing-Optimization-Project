"""
Test VSP ParasiteDrag with correct SI units
測試正確的公制單位設置
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import openvsp as vsp

print("="*80)
print("Testing VSP ParasiteDrag with SI Units")
print("="*80)

# Clear and create test geometry
vsp.ClearVSPModel()
fuse_id = vsp.AddGeom("FUSELAGE")
vsp.SetGeomName(fuse_id, "TestFuselage")
vsp.SetParmVal(fuse_id, "Length", "Design", 2.5)
vsp.Update()

print("\n1. Setting up ParasiteDrag with SI units...")

# Explore FreestreamPropChoice
print("\n   Checking FreestreamPropChoice options...")
freestream_choice = vsp.GetIntAnalysisInput("ParasiteDrag", "FreestreamPropChoice")
print(f"   Current FreestreamPropChoice: {freestream_choice}")
# 0 = Manual input, 1 = Standard atmosphere at altitude

# Set to use velocity directly (not atmosphere model)
vsp.SetIntAnalysisInput("ParasiteDrag", "FreestreamPropChoice", [0])  # Manual properties

# Set velocity: 6.5 m/s
velocity = [6.5]
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", velocity)
vsp.SetIntAnalysisInput("ParasiteDrag", "VelocityUnit", [0])  # Guess: 0 = m/s

# Set atmospheric properties manually (SI units)
# Standard sea level: T = 288.15 K, P = 101325 Pa, rho = 1.225 kg/m³
temperature = [288.15]  # Kelvin
pressure = [101325.0]   # Pa
density = [1.225]       # kg/m³

vsp.SetDoubleAnalysisInput("ParasiteDrag", "Temperature", temperature)
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Pressure", pressure)
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Density", density)

# Set units
vsp.SetIntAnalysisInput("ParasiteDrag", "LengthUnit", [vsp.LEN_M])
vsp.SetIntAnalysisInput("ParasiteDrag", "TempUnit", [0])  # Guess: 0 = K
vsp.SetIntAnalysisInput("ParasiteDrag", "PresUnit", [0])  # Guess: 0 = Pa

# Set reference area (use wetted area from CompGeom)
print("\n2. Computing geometry to get wetted area...")
comp_geom_results = vsp.ComputeCompGeom(vsp.SET_ALL, False, 0)
comp_res_id = vsp.FindLatestResultsID("Comp_Geom")
wetted_area_results = vsp.GetDoubleResults(comp_res_id, "Wet_Area", 0)
wetted_area = wetted_area_results[0] if len(wetted_area_results) > 0 else 1.0

print(f"   Wetted Area: {wetted_area:.4f} m²")

# Set reference area
sref = [wetted_area]
vsp.SetDoubleAnalysisInput("ParasiteDrag", "Sref", sref)

# Set GeomSet to include all geometry
vsp.SetIntAnalysisInput("ParasiteDrag", "GeomSet", [vsp.SET_ALL])

print("\n3. Running ParasiteDrag analysis...")
res_id = vsp.ExecAnalysis("ParasiteDrag")

print("\n4. Extracting results...")

# List all available results
all_res_names = vsp.GetAllDataNames(res_id)
print(f"   Available results: {len(all_res_names)} items")

# Try to extract key results safely
def safe_get_double(res_id, name):
    try:
        result = vsp.GetDoubleResults(res_id, name, 0)
        return result[0] if len(result) > 0 else None
    except:
        return None

cd_total = safe_get_double(res_id, "Total_CD_Total")
comp_swet = safe_get_double(res_id, "Comp_Swet")
fc_vinf = safe_get_double(res_id, "FC_Vinf")
fc_rho = safe_get_double(res_id, "FC_Rho")
fc_sref = safe_get_double(res_id, "FC_Sref")
fc_temp = safe_get_double(res_id, "FC_Temp")
fc_pres = safe_get_double(res_id, "FC_Pres")

print(f"\n   Flow Conditions:")
print(f"      Velocity: {fc_vinf if fc_vinf else 'N/A'}")
print(f"      Density: {fc_rho if fc_rho else 'N/A'}")
print(f"      Temperature: {fc_temp if fc_temp else 'N/A'}")
print(f"      Pressure: {fc_pres if fc_pres else 'N/A'}")
print(f"      Sref: {fc_sref if fc_sref else 'N/A'}")

print(f"\n   Drag Results:")
print(f"      CD_Total: {cd_total if cd_total else 'N/A'}")
print(f"      Swet: {comp_swet if comp_swet else 'N/A'}")

# Calculate drag force manually
# D = CD * q * Sref, where q = 0.5 * rho * V^2
print("\n5. Calculating drag force...")

# Check if all required values are available
if cd_total is None or fc_rho is None or fc_vinf is None or fc_sref is None:
    print("   ⚠️  Missing required data for drag calculation")
    print("="*80)
    print("Test completed with errors!")
    print("="*80)
    exit(1)

# Need to figure out units from the output
# If rho is in slug/ft³, need to convert
# Check if we're getting SI or Imperial units

if fc_rho < 0.01:
    # Likely slug/ft³ (0.00237 for sea level)
    print(f"   ⚠️  Density appears to be in slug/ft³: {fc_rho:.6f}")
    print(f"   Converting to SI...")
    rho_si = fc_rho * 515.378818  # slug/ft³ to kg/m³
    v_si = fc_vinf * 0.3048 if fc_vinf > 10 else fc_vinf  # ft/s to m/s
    sref_si = fc_sref * 0.09290304 if fc_sref > 10 else fc_sref  # ft² to m²
else:
    # Already in SI
    print(f"   ✅ Density appears to be in kg/m³: {fc_rho:.6f}")
    rho_si = fc_rho
    v_si = fc_vinf
    sref_si = fc_sref

q = 0.5 * rho_si * v_si**2
drag_force = cd_total * q * sref_si

print(f"\n   Calculations:")
print(f"      ρ (SI): {rho_si:.6f} kg/m³")
print(f"      V (SI): {v_si:.4f} m/s")
print(f"      Sref (SI): {sref_si:.4f} m²")
print(f"      q: {q:.4f} Pa")
print(f"      Drag Force: {drag_force:.4f} N")

print("\n" + "="*80)
print("Test completed!")
print("="*80)
