"""
Parasite drag analysis helpers for OpenVSP.

The validated path on this project is:
1. write a `.vsp3` model,
2. reload it into OpenVSP,
3. execute `ParasiteDrag`,
4. read the result fields directly from the OpenVSP results API.

This keeps the same aerodynamic outputs as the old file-based workflow while
removing the extra CSV parsing cost from the GA hot path.
"""
import os

from utils.openvsp_loader import load_openvsp


class DragAnalyzer:
    """Execute parasite drag analysis through the OpenVSP results API."""

    def __init__(self, output_dir="output"):
        self.output_dir = output_dir

    @staticmethod
    def _set_double_input_if_available(vsp, analysis_name, input_names, primary_name, fallback_name, value):
        if primary_name in input_names:
            vsp.SetDoubleAnalysisInput(analysis_name, primary_name, [float(value)])
            return
        if fallback_name and fallback_name in input_names:
            vsp.SetDoubleAnalysisInput(analysis_name, fallback_name, [float(value)])

    @staticmethod
    def _set_int_input_if_available(vsp, analysis_name, input_names, primary_name, fallback_name, value):
        if primary_name in input_names:
            vsp.SetIntAnalysisInput(analysis_name, primary_name, [int(value)])
            return
        if fallback_name and fallback_name in input_names:
            vsp.SetIntAnalysisInput(analysis_name, fallback_name, [int(value)])

    def run_analysis(self, vsp_filepath, velocity, rho, mu):
        """
        Execute Parasite Drag analysis and parse results

        Parameters:
        -----------
        vsp_filepath : str
            Path to .vsp3 file
        velocity : float
            Freestream velocity (m/s)
        rho : float
            Air density (kg/m^3)
        mu : float
            Dynamic viscosity (kg/m·s)

        Returns:
        --------
        result : dict
            Analysis results including Drag, CdA, Cd, Swet
        """
        name = os.path.basename(vsp_filepath).replace(".vsp3", "")
        print(f"   🌪️  [Analysis] Computing aerodynamics for {name}...")
        vsp = load_openvsp()

        # Load model
        vsp.ClearVSPModel()
        vsp.ReadVSPFile(vsp_filepath)
        vsp.Update()

        analysis_name = "ParasiteDrag"
        input_names = set(vsp.GetAnalysisInputNames(analysis_name))
        vsp.SetAnalysisInputDefaults(analysis_name)

        DragAnalyzer._set_int_input_if_available(vsp, analysis_name, input_names, "GeomSet", "Set", vsp.SET_ALL)
        DragAnalyzer._set_double_input_if_available(vsp, analysis_name, input_names, "Vinf", None, velocity)
        DragAnalyzer._set_double_input_if_available(vsp, analysis_name, input_names, "Density", "Rho", rho)
        DragAnalyzer._set_double_input_if_available(vsp, analysis_name, input_names, "DynaVisc", "Mu", mu)

        if "FileName" in input_names:
            try:
                vsp.SetStringAnalysisInput(analysis_name, "FileName", ["/dev/null"])
            except Exception:
                pass

        result_id = vsp.ExecAnalysis(analysis_name)

        try:
            cd_val = float(vsp.GetDoubleResults(result_id, "Total_CD_Total", 0)[0])
            swet_vals = vsp.GetDoubleResults(result_id, "Comp_Swet", 0)
            swet_val = float(sum(swet_vals)) if swet_vals else None
            cda_vals = vsp.GetDoubleResults(result_id, "Total_f_Total", 0)
            cda_val = float(cda_vals[0]) if cda_vals else cd_val
            q = 0.5 * rho * (velocity ** 2)
            return {
                "name": name,
                "file": vsp_filepath,
                "CdA": cda_val,
                "Swet": swet_val,
                "Drag": q * cd_val,
                "Cd": cd_val,
            }
        except Exception as exc:
            print(f"   ❌ Failed to read ParasiteDrag results directly: {exc}")
            return None
