"""
CST (Class Shape Transformation) Geometry Generator for OpenVSP
Supports Super Ellipse cross-sections for better space utilization
"""
import openvsp as vsp
import math
import os


class CSTGeometryGenerator:
    """Generate fuselage geometry using CST parameterization"""

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
        Generate fuselage geometry with Super Ellipse cross-sections

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
        super_m = design_params.get("super_m", 2.5)  # >2.0 makes it more rectangular
        super_n = design_params.get("super_n", 2.5)
        num_sections = design_params.get("num_sections", 40)

        print(f"   🔨 [Modeling] Generating: {name} (L={L}m, Super Ellipse m={super_m}, n={super_n})...")

        # Clear existing model
        vsp.ClearVSPModel()

        # Create fuselage
        fuse_id = vsp.AddGeom("FUSELAGE")
        vsp.SetGeomName(fuse_id, name)
        vsp.SetParmVal(fuse_id, "Length", "Design", L)

        # Get cross-section surface
        xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

        # Create required number of cross-sections
        # Use InsertXSec to ADD sections (not CutXSec which REMOVES them!)
        current_sections = vsp.GetNumXSec(xsec_surf)
        needed_inserts = num_sections - current_sections

        # Insert new XSecs at incrementing indices starting from 1
        # Each insert pushes subsequent sections (including tail) back by 1
        # Example: Start with [0-nose, 1, 2, 3, 4-tail]
        #   Insert at 1: [0-nose, 1-NEW, 2-old1, 3-old2, 4-old3, 5-tail]
        #   Insert at 2: [0-nose, 1-first, 2-NEW, 3-old1, 4-old2, 5-old3, 6-tail]
        for i in range(needed_inserts):
            insert_index = 1 + i  # Insert at 1, then 2, then 3, etc.
            vsp.InsertXSec(fuse_id, insert_index, vsp.XS_SUPER_ELLIPSE)

        vsp.Update()

        # Configure each cross-section
        final_count = vsp.GetNumXSec(xsec_surf)

        # Configure each section: change shape first, then set XLocPercent, then other params
        for i in range(final_count):
            psi = i / (final_count - 1)

            # Check if this is a tip section
            is_tip = (i == 0) or (i == final_count - 1)

            # Change shape first
            if is_tip:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
            else:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)

            # Get the xsec handle
            xsec = vsp.GetXSec(xsec_surf, i)

            # Set XLocPercent immediately after shape change (before Update!)
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

            if not is_tip:
                # Calculate CST dimensions
                r_width = self.calculate_cst_radius(psi, N1, N2, W_w, L)
                r_height = self.calculate_cst_radius(psi, N1, N2, H_w, L)

                w = max(r_width * 2, 0.001)
                h = max(r_height * 2, 0.001)

                # Set dimensions
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), w)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), h)

                # Set super ellipse exponents (m and n)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), super_m)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), super_n)

        vsp.Update()

        # Save to output folder
        filepath = os.path.join(self.output_dir, f"{name}.vsp3")
        vsp.WriteVSPFile(filepath)

        return filepath
