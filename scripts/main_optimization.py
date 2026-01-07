"""
Birdman Fairing Optimization - Main Program
Automated CST geometry generation and parasite drag optimization
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.geometry import CSTGeometryGenerator
from src.analysis import DragAnalyzer


def main():
    """Main optimization workflow"""

    # Environment parameters (Birdman competition conditions)
    V = 6.5           # Flight velocity (m/s)
    rho = 1.1839      # Air density (kg/m^3) @ 25°C
    mu = 1.8371e-05   # Dynamic viscosity (kg/m·s)

    print("=" * 80)
    print("🚀 Birdman Fairing Optimization System")
    print(f"   Flight Conditions: V={V} m/s, ρ={rho} kg/m³")
    print("=" * 80)

    # Initialize modules
    geometry = CSTGeometryGenerator(output_dir="output")
    analyzer = DragAnalyzer(output_dir="output")

    # Design parameter library
    # You can add unlimited design cases here
    design_queue = [
        {
            "name": "Type_A_Standard",
            "length": 2.5,
            "n_nose": 0.5,      # Elliptical nose
            "n_tail": 1.0,      # Conical tail
            "width_weights": [0.15, 0.20, 0.20, 0.05],
            "height_weights": [0.20, 0.35, 0.25, 0.05],
            "super_m": 2.5,     # Slightly rectangular (accommodates shoulders)
            "super_n": 2.5,
            "num_sections": 40
        },
        {
            "name": "Type_B_HighSpeed",
            "length": 3.0,
            "n_nose": 0.4,      # More pointed nose
            "n_tail": 1.2,      # Sharper tail
            "width_weights": [0.10, 0.15, 0.15, 0.02],
            "height_weights": [0.15, 0.25, 0.20, 0.02],
            "super_m": 2.3,     # Closer to ellipse
            "super_n": 2.3,
            "num_sections": 45
        },
        {
            "name": "Type_C_Comfort",
            "length": 2.2,
            "n_nose": 0.6,      # Blunter nose
            "n_tail": 0.8,      # Gentler tail
            "width_weights": [0.20, 0.30, 0.25, 0.10],
            "height_weights": [0.25, 0.40, 0.30, 0.10],
            "super_m": 2.8,     # More rectangular (more space)
            "super_n": 2.8,
            "num_sections": 40
        },
        # Add more designs here:
        # {
        #     "name": "Type_D_Custom",
        #     "length": 2.7,
        #     ...
        # }
    ]

    results = []

    # Automated workflow
    print("\n📋 Processing Design Queue:")
    print("-" * 80)

    for i, design in enumerate(design_queue, 1):
        print(f"\n[{i}/{len(design_queue)}] Processing: {design['name']}")

        # Step 1: Generate geometry
        try:
            vsp_file = geometry.generate_fuselage(design)
        except Exception as e:
            print(f"   ❌ Geometry generation failed: {e}")
            continue

        # Step 2: Run drag analysis
        try:
            result = analyzer.run_analysis(vsp_file, V, rho, mu)
        except Exception as e:
            print(f"   ❌ Analysis failed: {e}")
            continue

        if result:
            results.append(result)
            print(f"   ✅ Drag = {result['Drag']:.4f} N, CdA = {result['CdA']:.5f} m², Cd = {result['Cd']:.6f}")
        else:
            print("   ⚠️  No valid results")

        print("-" * 80)

    # Results summary
    if not results:
        print("\n⚠️  No valid results obtained. Check error messages above.")
        return

    print("\n" + "=" * 80)
    print("🏆 OPTIMIZATION RESULTS (Sorted by Drag)")
    print("=" * 80)

    # Sort by drag (ascending)
    results.sort(key=lambda x: x["Drag"])

    # Print table header
    header = f"{'Rank':<6} | {'Design':<25} | {'Drag (N)':<12} | {'CdA (m²)':<12} | {'Cd':<10} | {'S_wet (m²)':<12}"
    print(header)
    print("-" * len(header))

    # Print results
    for rank, res in enumerate(results, 1):
        row = f"{rank:<6} | {res['name']:<25} | {res['Drag']:<12.5f} | {res['CdA']:<12.6f} | {res['Cd']:<10.6f} | {res['Swet']:<12.4f}"
        print(row)

    # Highlight best design
    best = results[0]
    worst = results[-1]
    improvement = worst['Drag'] - best['Drag']
    improvement_pct = (improvement / worst['Drag']) * 100

    print("\n" + "=" * 80)
    print("📊 Performance Summary:")
    print(f"   🥇 Best Design:  {best['name']}")
    print(f"      → Drag = {best['Drag']:.4f} N")
    print(f"      → Cd   = {best['Cd']:.6f}")
    print(f"   ")
    print(f"   📉 Improvement over worst: {improvement:.4f} N ({improvement_pct:.1f}%)")
    print("=" * 80)

    print(f"\n✅ All files saved in 'output/' folder")
    print(f"   Open .vsp3 files in OpenVSP to visualize geometry")


if __name__ == "__main__":
    main()
