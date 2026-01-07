"""
CST Geometry Generator - OPTIMIZED VERSION
Improvements:
1. Batch parameter setting with single Update() call
2. Added skinning parameters for smooth surfaces
3. Reduced API calls for better performance
"""
import openvsp as vsp
import math
import os


class CSTGeometryGeneratorOptimized:
    """Generate fuselage geometry using CST parameterization - Optimized"""

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
        """
        CST class function - controls nose and tail shape
        psi: normalized position (0 to 1)
        N1: nose shape parameter (0.5 = elliptical, 1.0 = conical)
        N2: tail shape parameter
        """
        return (psi ** N1) * ((1 - psi) ** N2)

    @staticmethod
    def cst_shape_function(psi, weights):
        """
        CST shape function using Bernstein polynomials
        weights: control point weights
        """
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

    def generate_fuselage(self, design_params):
        """
        Generate fuselage geometry with Super Ellipse cross-sections - OPTIMIZED

        Parameters:
        -----------
        design_params : dict
            name: design name
            length: fuselage length (m)
            n_nose: nose shape parameter
            n_tail: tail shape parameter
            width_weights: CST weights for width distribution
            height_weights: CST weights for height distribution
            super_m: super ellipse exponent for width direction (default: 2.5)
            super_n: super ellipse exponent for height direction (default: 2.5)
            num_sections: number of cross-sections (default: 40)
            skinning_continuity: C0/C1/C2 continuity (default: 1)
            skinning_strength: tangent strength (default: 0.75)

        Returns:
        --------
        filepath: path to saved .vsp3 file
        """
        name = design_params["name"]
        L = design_params["length"]
        N1 = design_params["n_nose"]
        N2 = design_params["n_tail"]
        W_w = design_params["width_weights"]
        H_w = design_params["height_weights"]
        super_m = design_params.get("super_m", 2.5)
        super_n = design_params.get("super_n", 2.5)
        num_sections = design_params.get("num_sections", 40)

        # Skinning parameters for smoothness
        continuity = design_params.get("skinning_continuity", 1)  # C1 continuity
        tan_strength = design_params.get("skinning_strength", 0.75)

        print(f"   🔨 [Modeling] Generating: {name} (L={L}m, {num_sections} sections, C{continuity} continuity)...")

        # Clear existing model
        vsp.ClearVSPModel()

        # Create fuselage
        fuse_id = vsp.AddGeom("FUSELAGE")
        vsp.SetGeomName(fuse_id, name)
        vsp.SetParmVal(fuse_id, "Length", "Design", L)

        # Get cross-section surface
        xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

        # === STEP 1: INSERT ALL XSECS (batch operation) ===
        current_sections = vsp.GetNumXSec(xsec_surf)
        needed_inserts = num_sections - current_sections

        for i in range(needed_inserts):
            insert_index = 1 + i
            vsp.InsertXSec(fuse_id, insert_index, vsp.XS_SUPER_ELLIPSE)

        # Single update after all insertions
        vsp.Update()

        # === STEP 2: CONFIGURE ALL XSECS (batch parameter setting) ===
        final_count = vsp.GetNumXSec(xsec_surf)

        for i in range(final_count):
            psi = i / (final_count - 1)
            is_tip = (i == 0) or (i == final_count - 1)

            # Change shape
            if is_tip:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
            else:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)

            # Get xsec handle
            xsec = vsp.GetXSec(xsec_surf, i)

            # Set position - use SetParmVal (no auto-update)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

            if not is_tip:
                # Calculate CST dimensions
                r_width = self.calculate_cst_radius(psi, N1, N2, W_w, L)
                r_height = self.calculate_cst_radius(psi, N1, N2, H_w, L)

                w = max(r_width * 2, 0.001)
                h = max(r_height * 2, 0.001)

                # Set dimensions - batch without update
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), w)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), h)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), super_m)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), super_n)

                # === NEW: Set skinning parameters for smoothness ===
                vsp.SetXSecContinuity(xsec, continuity)
                vsp.SetXSecTanAngles(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)
                vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES,
                                       tan_strength, tan_strength, tan_strength, tan_strength)

        # === STEP 3: SINGLE UPDATE AT THE END ===
        vsp.Update()

        # Save to output folder
        filepath = os.path.join(self.output_dir, f"{name}.vsp3")
        vsp.WriteVSPFile(filepath)

        return filepath
