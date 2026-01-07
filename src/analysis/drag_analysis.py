"""
Parasite Drag Analysis Module for OpenVSP
Handles analysis execution and CSV result parsing
"""
import openvsp as vsp
import csv
import os
import shutil


class DragAnalyzer:
    """Execute parasite drag analysis and parse results"""

    def __init__(self, output_dir="output"):
        self.output_dir = output_dir

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

        # Load model
        vsp.ClearVSPModel()
        vsp.ReadVSPFile(vsp_filepath)

        # Setup analysis
        analysis_name = "ParasiteDrag"
        vsp.SetAnalysisInputDefaults(analysis_name)
        vsp.SetDoubleAnalysisInput(analysis_name, "Rho", [rho])
        vsp.SetDoubleAnalysisInput(analysis_name, "Vinf", [velocity])
        vsp.SetDoubleAnalysisInput(analysis_name, "Mu", [mu])

        # Execute (CSV files generated automatically in working directory)
        vsp.ExecAnalysis(analysis_name)

        # Move generated CSV files to output folder
        generated_csv = f"{name}_ParasiteBuildUp.csv"
        target_csv = os.path.join(self.output_dir, generated_csv)

        # Check if CSV was generated in current directory
        if os.path.exists(generated_csv):
            # Remove existing file if present
            if os.path.exists(target_csv):
                os.remove(target_csv)
            shutil.move(generated_csv, target_csv)
        else:
            # Check if CSV was generated in vsp file's directory
            vsp_dir = os.path.dirname(vsp_filepath)
            vsp_dir_csv = os.path.join(vsp_dir, generated_csv)

            if os.path.exists(vsp_dir_csv):
                # Move from vsp directory to output folder
                if os.path.exists(target_csv):
                    os.remove(target_csv)
                shutil.move(vsp_dir_csv, target_csv)
            # Check if CSV is already in output folder (may happen if working dir = output)
            elif not os.path.exists(target_csv):
                print("   ❌ Analysis CSV not found, analysis may have failed.")
                return None

        # Clean up other generated files
        geom_csv = f"{name}_CompGeom.csv"
        if os.path.exists(geom_csv):
            target_geom = os.path.join(self.output_dir, geom_csv)
            if os.path.exists(target_geom):
                os.remove(target_geom)
            shutil.move(geom_csv, target_geom)

        # Also move .txt files if they exist
        geom_txt = f"{name}_CompGeom.txt"
        if os.path.exists(geom_txt):
            target_txt = os.path.join(self.output_dir, geom_txt)
            if os.path.exists(target_txt):
                os.remove(target_txt)
            shutil.move(geom_txt, target_txt)

        # Parse results
        return self._parse_csv_results(target_csv, name, velocity, rho)

    def _parse_csv_results(self, csv_filepath, name, velocity, rho):
        """
        Parse ParasiteBuildUp CSV to extract drag metrics

        Returns:
        --------
        result : dict with keys: name, file, CdA, Swet, Drag, Cd
        """
        q = 0.5 * rho * (velocity ** 2)  # Dynamic pressure
        result = {"name": name, "file": csv_filepath}

        try:
            with open(csv_filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                rows = list(reader)

                # Find header row to identify column indices
                header_idx = -1
                f_idx = -1
                swet_idx = -1
                cd_idx = -1

                for i, row in enumerate(rows):
                    # Check if this is the header row
                    if len(row) > 0 and "Component Name" in row[0]:
                        header_idx = i
                        # Parse header to find column indices
                        for j, col in enumerate(row):
                            col_lower = col.lower().strip()
                            if "s_wet" in col_lower:
                                swet_idx = j
                            elif "f (" in col_lower:  # "f (ft^2)"
                                f_idx = j
                            elif col_lower == "cd":
                                cd_idx = j
                        break

                # Now search for data rows (Total or component name)
                if header_idx != -1:
                    for i in range(header_idx + 1, len(rows)):
                        row = rows[i]
                        if len(row) > max(f_idx, swet_idx, cd_idx):
                            row_name = row[0].strip().lower()

                            # Look for "Totals:" or the component name
                            if "total" in row_name or name.lower() in row_name:
                                try:
                                    f_val = float(row[f_idx])
                                    s_wet = float(row[swet_idx])
                                    cd_val = float(row[cd_idx])

                                    result["CdA"] = f_val
                                    result["Swet"] = s_wet
                                    result["Drag"] = q * f_val
                                    result["Cd"] = cd_val

                                    return result
                                except (ValueError, IndexError) as e:
                                    continue

        except Exception as e:
            print(f"   ❌ CSV parsing failed: {e}")
            return None

        return None
