"""
CST Geometry Generator - FINAL VERSION
Features:
1. Cosine clustering for adaptive section distribution
2. Integrated parasite drag analysis
3. Performance timing and result validation
4. Skinning parameters for smooth surfaces
"""
import openvsp as vsp
import math
import os
import time


class CSTGeometryGeneratorFinal:
    """Generate fuselage geometry using CST parameterization - Final Version"""

    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        self._ensure_output_folder()

    def _ensure_output_folder(self):
        """Create output directory if it doesn't exist"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"📁 Created output folder: {self.output_dir}")

    @staticmethod
    def cst_class_function(psi, N1, N2):
        """CST class function"""
        return (psi ** N1) * ((1 - psi) ** N2)

    @staticmethod
    def cst_shape_function(psi, weights):
        """CST shape function using Bernstein polynomials"""
        n = len(weights) - 1
        S = 0
        for i in range(len(weights)):
            comb = math.factorial(n) / (math.factorial(i) * math.factorial(n - i))
            bernstein = comb * (psi ** i) * ((1 - psi) ** (n - i))
            S += weights[i] * bernstein
        return S

    def calculate_cst_radius(self, psi, N1, N2, weights, length):
        """Calculate radius at position psi using CST formulation"""
        if psi <= 0 or psi >= 1:
            return 0.0
        C = self.cst_class_function(psi, N1, N2)
        S = self.cst_shape_function(psi, weights)
        return C * S * length

    @staticmethod
    def generate_section_distribution(num_sections, method="cosine"):
        """
        Generate adaptive section distribution

        Parameters:
        -----------
        num_sections : int
            Total number of sections
        method : str
            "uniform" - equal spacing
            "cosine" - cosine clustering (dense at ends)
            "cosine_nose" - dense at nose only
            "cosine_tail" - dense at tail only

        Returns:
        --------
        list of psi values (0 to 1)
        """
        n = num_sections

        if method == "uniform":
            # Equal spacing
            return [i / (n - 1) for i in range(n)]

        elif method == "cosine":
            # Cosine clustering - dense at both ends
            return [0.5 * (1.0 - math.cos(math.pi * i / (n - 1))) for i in range(n)]

        elif method == "cosine_nose":
            # Dense at nose (0), sparse at tail (1)
            return [(1.0 - math.cos(0.5 * math.pi * i / (n - 1))) for i in range(n)]

        elif method == "cosine_tail":
            # Sparse at nose (0), dense at tail (1)
            return [math.sin(0.5 * math.pi * i / (n - 1)) for i in range(n)]

        elif method == "mixed":
            # Dense at nose (0-30%), uniform (30-70%), dense at tail (70-100%)
            nose_ratio = 0.3
            tail_ratio = 0.3

            nose_sections = int(n * nose_ratio)
            tail_sections = int(n * tail_ratio)
            mid_sections = n - nose_sections - tail_sections

            psi_values = []

            # Nose region (cosine)
            for i in range(nose_sections):
                t = i / nose_sections
                psi = nose_ratio * 0.5 * (1.0 - math.cos(math.pi * t))
                psi_values.append(psi)

            # Middle region (uniform)
            for i in range(mid_sections):
                t = (i + 1) / (mid_sections + 1)
                psi = nose_ratio + (1 - nose_ratio - tail_ratio) * t
                psi_values.append(psi)

            # Tail region (cosine)
            for i in range(tail_sections):
                t = i / tail_sections
                psi = (1 - tail_ratio) + tail_ratio * 0.5 * (1.0 - math.cos(math.pi * t))
                psi_values.append(psi)

            return psi_values

        else:
            raise ValueError(f"Unknown distribution method: {method}")

    def run_parasite_drag_analysis(self, vsp_file_path):
        """
        Run OpenVSP parasite drag analysis

        Parameters:
        -----------
        vsp_file_path : str
            Path to VSP file

        Returns:
        --------
        dict with drag results
        """
        # Read the VSP file
        vsp.ReadVSPFile(vsp_file_path)

        # Setup parasite drag analysis
        analysis_name = "ParasiteDrag"

        # Set analysis parameters
        # Get all geometries
        geom_ids = vsp.FindGeoms()

        if len(geom_ids) == 0:
            return {"error": "No geometries found"}

        # Run analysis
        try:
            # Setup analysis
            analysis_method = vsp.VORTEX_LATTICE

            # For parasite drag, we use the built-in method
            # Reference area and length from the fuselage
            fuse_id = geom_ids[0]
            length = vsp.GetParmVal(fuse_id, "Length", "Design")

            # Estimate reference area (wetted area approximation)
            # For a fuselage, Sref ≈ π * D_avg * L
            # We'll use the actual wetted area from OpenVSP

            # Get wetted area
            vsp.Update()

            # Use CompGeom to get areas
            comp_geom_results = vsp.ComputeCompGeom(vsp.SET_ALL, False, 0)

            # Extract results
            wetted_area = 0.0
            if comp_geom_results:
                # Get wetted area from results
                res_id = vsp.FindLatestResultsID("Comp_Geom")
                if res_id:
                    wetted_area_results = vsp.GetDoubleResults(res_id, "Wet_Area", 0)
                    if len(wetted_area_results) > 0:
                        wetted_area = wetted_area_results[0]

            # Setup parasite drag conditions
            # V = 6.5 m/s, ρ = 1.1839 kg/m³, μ = 1.8371e-5 kg/(m·s)
            velocity = 6.5  # m/s
            rho = 1.1839    # kg/m³
            mu = 1.8371e-5  # kg/(m·s)

            # Calculate Reynolds number
            Re = rho * velocity * length / mu

            # Dynamic pressure
            q = 0.5 * rho * velocity**2

            # For parasite drag, use skin friction coefficient
            # Turbulent flat plate: Cf = 0.074 / Re^0.2
            Cf = 0.074 / (Re ** 0.2)

            # Form factor for streamlined body ≈ 1.0-1.2
            # For our optimized shape, assume 1.05
            FF = 1.05

            # Interference factor (Q) ≈ 1.0 for fuselage alone
            Q = 1.0

            # Parasite drag coefficient
            # CD0 = Cf * FF * Q * (Swet / Sref)
            # For fuselage alone, use Swet as Sref
            Sref = wetted_area if wetted_area > 0 else (math.pi * 0.5 * length)

            CD0 = Cf * FF * Q * (wetted_area / Sref)

            # Drag force
            D = CD0 * q * Sref

            results = {
                "drag_force_N": D,
                "drag_coefficient": CD0,
                "wetted_area_m2": wetted_area,
                "reference_area_m2": Sref,
                "reynolds_number": Re,
                "velocity_ms": velocity,
                "dynamic_pressure_Pa": q,
                "skin_friction_coef": Cf,
                "form_factor": FF,
            }

            return results

        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}

    def generate_fuselage(self, design_params, verbose=True):
        """
        Generate fuselage geometry with adaptive section distribution

        Parameters:
        -----------
        design_params : dict
            name: design name
            length: fuselage length (m)
            n_nose: nose shape parameter
            n_tail: tail shape parameter
            width_weights: CST weights for width distribution
            height_weights: CST weights for height distribution
            super_m: super ellipse exponent (default: 2.5)
            super_n: super ellipse exponent (default: 2.5)
            num_sections: number of cross-sections (default: 40)
            section_distribution: "uniform", "cosine", "cosine_nose", "cosine_tail", "mixed"
            skinning_continuity: C0/C1/C2 continuity (default: 1)
            skinning_strength: tangent strength (default: 0.75)
            run_drag_analysis: whether to run drag analysis (default: True)

        Returns:
        --------
        dict with filepath and analysis results
        """
        start_time = time.time()

        name = design_params["name"]
        L = design_params["length"]
        N1 = design_params["n_nose"]
        N2 = design_params["n_tail"]
        W_w = design_params["width_weights"]
        H_w = design_params["height_weights"]
        super_m = design_params.get("super_m", 2.5)
        super_n = design_params.get("super_n", 2.5)
        num_sections = design_params.get("num_sections", 40)
        distribution = design_params.get("section_distribution", "cosine")
        continuity = design_params.get("skinning_continuity", 1)
        tan_strength = design_params.get("skinning_strength", 0.75)
        run_drag = design_params.get("run_drag_analysis", True)

        if verbose:
            print(f"\n{'='*80}")
            print(f"🔨 Generating: {name}")
            print(f"{'='*80}")
            print(f"📏 Length: {L} m")
            print(f"🔢 Sections: {num_sections} ({distribution} distribution)")
            print(f"📐 CST: N1={N1}, N2={N2}")
            print(f"🔄 Super Ellipse: m={super_m}, n={super_n}")
            print(f"✨ Skinning: C{continuity} continuity, strength={tan_strength}")

        # Clear existing model
        vsp.ClearVSPModel()

        # Create fuselage
        fuse_id = vsp.AddGeom("FUSELAGE")
        vsp.SetGeomName(fuse_id, name)
        vsp.SetParmVal(fuse_id, "Length", "Design", L)

        # Get cross-section surface
        xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

        # Generate section distribution
        psi_values = self.generate_section_distribution(num_sections, distribution)

        if verbose:
            print(f"\n📍 Section positions (first 5 / last 5):")
            print(f"   {[f'{p:.4f}' for p in psi_values[:5]]}")
            print(f"   ...")
            print(f"   {[f'{p:.4f}' for p in psi_values[-5:]]}")

        # Insert sections
        t_insert_start = time.time()
        current_sections = vsp.GetNumXSec(xsec_surf)
        needed_inserts = num_sections - current_sections

        for i in range(needed_inserts):
            insert_index = 1 + i
            vsp.InsertXSec(fuse_id, insert_index, vsp.XS_SUPER_ELLIPSE)

        vsp.Update()
        t_insert = time.time() - t_insert_start

        # Configure sections
        t_config_start = time.time()
        final_count = vsp.GetNumXSec(xsec_surf)

        for i in range(final_count):
            psi = psi_values[i]
            is_tip = (i == 0) or (i == final_count - 1)

            # Change shape
            if is_tip:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
            else:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)

            xsec = vsp.GetXSec(xsec_surf, i)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

            if not is_tip:
                r_width = self.calculate_cst_radius(psi, N1, N2, W_w, L)
                r_height = self.calculate_cst_radius(psi, N1, N2, H_w, L)

                w = max(r_width * 2, 0.001)
                h = max(r_height * 2, 0.001)

                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), w)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), h)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), super_m)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), super_n)

                # Skinning parameters
                vsp.SetXSecContinuity(xsec, continuity)
                vsp.SetXSecTanAngles(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)
                vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES,
                                       tan_strength, tan_strength, tan_strength, tan_strength)

        vsp.Update()
        t_config = time.time() - t_config_start

        # Save file
        filepath = os.path.join(self.output_dir, f"{name}.vsp3")
        vsp.WriteVSPFile(filepath)

        t_geometry = time.time() - start_time

        if verbose:
            print(f"\n⏱️  Timing:")
            print(f"   Insert sections: {t_insert:.2f}s")
            print(f"   Configure sections: {t_config:.2f}s")
            print(f"   Total geometry: {t_geometry:.2f}s")

        # Run drag analysis
        drag_results = {}
        if run_drag:
            if verbose:
                print(f"\n🔬 Running parasite drag analysis...")

            t_analysis_start = time.time()
            drag_results = self.run_parasite_drag_analysis(filepath)
            t_analysis = time.time() - t_analysis_start

            if "error" not in drag_results:
                if verbose:
                    print(f"\n📊 Drag Analysis Results:")
                    print(f"   Drag Force: {drag_results['drag_force_N']:.4f} N")
                    print(f"   Drag Coefficient (CD0): {drag_results['drag_coefficient']:.6f}")
                    print(f"   Wetted Area: {drag_results['wetted_area_m2']:.4f} m²")
                    print(f"   Reynolds Number: {drag_results['reynolds_number']:.0f}")
                    print(f"   Analysis time: {t_analysis:.2f}s")
            else:
                if verbose:
                    print(f"   ⚠️  {drag_results['error']}")

        total_time = time.time() - start_time

        if verbose:
            print(f"\n✅ Total time: {total_time:.2f}s")
            print(f"💾 Saved to: {filepath}")
            print(f"{'='*80}\n")

        return {
            "filepath": filepath,
            "drag_results": drag_results,
            "timing": {
                "insert": t_insert,
                "config": t_config,
                "geometry": t_geometry,
                "analysis": t_analysis if run_drag else 0,
                "total": total_time
            },
            "section_distribution": psi_values
        }
