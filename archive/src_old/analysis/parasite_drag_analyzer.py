"""
Parasite Drag Analyzer - VSP Built-in Analysis Integration
整合 OpenVSP 內建的 ParasiteDrag 分析功能
"""
import openvsp as vsp
import os


class ParasiteDragAnalyzer:
    """
    VSP 寄生阻力分析器

    使用 OpenVSP 內建的 ParasiteDrag 分析，提供：
    1. 自動化分析流程
    2. 結果提取與驗證
    3. 單位轉換與計算
    """

    def __init__(self):
        self.analysis_name = "ParasiteDrag"

    @staticmethod
    def calculate_projected_area(design_params):
        """
        計算機身最大截面的投影面積（超橢圓）

        Parameters:
        -----------
        design_params : dict
            設計參數（包含 CST 權重、超橢圓指數等）

        Returns:
        --------
        float : 投影面積 (m²)
        """
        import math
        import sys
        import os

        # 導入 CST 導數計算器
        current_dir = os.path.dirname(__file__)
        math_dir = os.path.join(current_dir, '..', 'math')
        sys.path.insert(0, math_dir)
        from cst_derivatives import CSTDerivatives

        # 提取參數
        L = design_params['length']
        N1 = design_params['n_nose']
        N2 = design_params['n_tail']
        W_w = design_params['width_weights']
        H_w = design_params['height_weights']
        super_m = design_params.get('super_m', 2.5)
        super_n = design_params.get('super_n', 2.5)

        # 在 0 到 1 之間搜索最大半徑
        max_r_width = 0
        max_r_height = 0

        for psi in [i / 100.0 for i in range(101)]:
            r_w = CSTDerivatives.cst_radius(psi, N1, N2, W_w, L)
            r_h = CSTDerivatives.cst_radius(psi, N1, N2, H_w, L)
            max_r_width = max(max_r_width, r_w)
            max_r_height = max(max_r_height, r_h)

        # 計算超橢圓面積
        # A = 4 * a * b * Γ(1 + 1/m) * Γ(1 + 1/n) / Γ(1 + 1/m + 1/n)
        # 對於 m = n = 2.5:
        #   Γ(1 + 1/2.5) = Γ(1.4) ≈ 0.8873
        #   Γ(1 + 1/2.5 + 1/2.5) = Γ(1.8) ≈ 0.9314
        # A ≈ 4 * a * b * 0.8873 * 0.8873 / 0.9314

        gamma_1_4 = math.gamma(1 + 1/super_m)
        gamma_1_4_n = math.gamma(1 + 1/super_n)
        gamma_sum = math.gamma(1 + 1/super_m + 1/super_n)

        area = 4 * max_r_width * max_r_height * gamma_1_4 * gamma_1_4_n / gamma_sum

        return area

    def analyze(self, vsp_file_path, flow_conditions, design_params=None, projected_area=None, verbose=True):
        """
        執行寄生阻力分析

        Parameters:
        -----------
        vsp_file_path : str
            VSP 文件路徑
        flow_conditions : dict
            流體條件：{
                'velocity': float,      # m/s
                'density': float,       # kg/m³
                'temperature': float,   # K
                'pressure': float,      # Pa (optional)
                'kinematic_viscosity': float  # m²/s (optional)
            }
        design_params : dict (optional)
            設計參數（用於計算投影面積）：{
                'length': float,
                'n_nose': float,
                'n_tail': float,
                'width_weights': list,
                'height_weights': list,
                'super_m': float,
                'super_n': float
            }
        projected_area : float (optional)
            直接指定投影面積 (m²)，優先於 design_params
        verbose : bool
            是否打印詳細信息

        Returns:
        --------
        dict : {
            'drag_force_N': float,           # 阻力 (N)
            'drag_coefficient': float,       # CD
            'CdA_equivalent': float,         # Cd·A 等效平板面積
            'wetted_area_m2': float,         # 濕面積 (m²)
            'projected_area_m2': float,      # 投影面積 (m²)
            'reynolds_number': float,        # 雷諾數
            'dynamic_pressure_Pa': float,    # 動壓 (Pa)
            'flow_conditions': dict,         # 流體條件
            'analysis_time_s': float         # 分析時間
        }
        """
        import time
        start_time = time.time()

        if verbose:
            print(f"\n{'='*80}")
            print(f"🔬 ParasiteDrag 分析")
            print(f"{'='*80}")
            print(f"📁 模型: {os.path.basename(vsp_file_path)}")
            print(f"💨 流速: {flow_conditions['velocity']} m/s")
            print(f"🌡️  密度: {flow_conditions['density']} kg/m³")

        # 清除並載入模型
        vsp.ClearVSPModel()
        vsp.ReadVSPFile(vsp_file_path)
        vsp.Update()

        # 獲取幾何信息
        geom_ids = vsp.FindGeoms()
        if len(geom_ids) == 0:
            return {"error": "No geometries found in model"}

        # ========== CRITICAL: 執行 CompGeom 獲取濕面積 ==========
        # ParasiteDrag 依賴 CompGeom 計算的濕面積，必須先執行！
        if verbose:
            print(f"\n📐 執行 CompGeom 分析（ParasiteDrag 前置要求）...")

        # 設置 CompGeom 分析參數
        vsp.SetAnalysisInputDefaults("CompGeom")
        vsp.SetIntAnalysisInput("CompGeom", "GeomSet", [vsp.SET_ALL])  # 明確指定 SET_ALL
        vsp.SetIntAnalysisInput("CompGeom", "HalfMesh", [0])  # 不使用半網格
        vsp.SetIntAnalysisInput("CompGeom", "Subsurfs", [1])  # 包含子表面

        # 執行 CompGeom - 這會更新記憶體中的濕面積數據
        if verbose:
            print(f"   執行 CompGeom.ExecAnalysis...")

        comp_geom_res_id = vsp.ExecAnalysis("CompGeom")

        # 從 CompGeom 結果中獲取濕面積
        wetted_area = 0.0
        try:
            wetted_area_results = vsp.GetDoubleResults(comp_geom_res_id, "Wet_Area", 0)
            if len(wetted_area_results) > 0:
                wetted_area = wetted_area_results[0]
        except Exception as e:
            if verbose:
                print(f"   ⚠️ 無法從 CompGeom 獲取濕面積: {e}")

        if verbose:
            print(f"   ✅ CompGeom 完成")
            print(f"   濕面積: {wetted_area:.4f} m²")

        # 計算投影面積
        # 優先級：projected_area 參數 > design_params 計算 > 默認值 1.0
        if projected_area is not None:
            # 直接使用提供的投影面積
            if verbose:
                print(f"   投影面積（手動指定）: {projected_area:.4f} m²")
        elif design_params is not None:
            # 從設計參數計算
            projected_area = self.calculate_projected_area(design_params)
            if verbose:
                print(f"   投影面積（從設計參數計算）: {projected_area:.4f} m²")
        else:
            # 使用默認值
            projected_area = 1.0
            if verbose:
                print(f"   ⚠️  未提供投影面積或設計參數，使用默認值: {projected_area} m²")

        # 設置 ParasiteDrag 分析
        if verbose:
            print(f"\n⚙️  設置 ParasiteDrag 分析參數...")

        # 重置為默認值
        vsp.SetAnalysisInputDefaults(self.analysis_name)

        # ========== CRITICAL: 明確指定幾何集為 SET_ALL ==========
        # 這解決 "Geom ID not included" 警告
        vsp.SetIntAnalysisInput(self.analysis_name, "GeomSet", [vsp.SET_ALL])

        if verbose:
            print(f"   幾何集: SET_ALL ({vsp.SET_ALL}) - 包含所有幾何")

        # 設置大氣模型類型（US Standard Atmosphere 1976）
        vsp.SetIntAnalysisInput(self.analysis_name, "AtmosType", [vsp.ATMOS_TYPE_US_STANDARD_1976])

        # 設置高度（海平面）
        vsp.SetDoubleAnalysisInput(self.analysis_name, "Altitude", [0.0])

        # 設置速度
        vsp.SetDoubleAnalysisInput(self.analysis_name, "Vinf", [flow_conditions['velocity']])

        # 設置溫度偏移（delta temperature，默認為 0）
        vsp.SetDoubleAnalysisInput(self.analysis_name, "DeltaTemp", [0.0])

        # 設置參考面積（使用投影面積）
        vsp.SetDoubleAnalysisInput(self.analysis_name, "Sref", [projected_area])

        # 設置長度單位為米
        vsp.SetIntAnalysisInput(self.analysis_name, "LengthUnit", [vsp.LEN_M])

        # ========== 設置摩擦係數方程式 ==========
        # 層流摩擦係數：Blasius
        vsp.SetIntAnalysisInput(self.analysis_name, "LamCfEqnType", [vsp.CF_LAM_BLASIUS])

        # 紊流摩擦係數：Power Law Prandtl Low Re
        vsp.SetIntAnalysisInput(self.analysis_name, "TurbCfEqnType", [vsp.CF_TURB_POWER_LAW_PRANDTL_LOW_RE])

        # ========== 設置形狀因數方程式 ==========
        # 機身形狀因數：Hoerner Streambody (值為 3)
        try:
            vsp.SetIntAnalysisInput(self.analysis_name, "FFBodyEqnType", [3])  # FF_B_HOERNER_STREAMBODY = 3
        except:
            pass  # 如果無法設置，繼續執行

        if verbose:
            print(f"   流體條件模式: US Standard Atmosphere 1976")
            print(f"   高度: 0.0 m (海平面)")
            print(f"   速度: {flow_conditions['velocity']} m/s")
            print(f"   摩擦係數方程式:")
            print(f"      層流: Blasius")
            print(f"      紊流: Power Law Prandtl Low Re")
            print(f"   形狀因數方程式:")
            print(f"      機身: Hoerner Streamlined")
            print(f"   參考面積 (Sref): {projected_area:.4f} m²")

        # 更新 ParasiteDrag 工具
        vsp.UpdateParasiteDrag()

        # 執行分析
        if verbose:
            print(f"\n🚀 執行分析...")

        result_id = vsp.ExecAnalysis(self.analysis_name)

        # 提取結果
        if verbose:
            print(f"\n📊 提取結果...")

        try:
            # 從結果中提取數據
            cd_total = vsp.GetDoubleResults(result_id, "Total_CD_Total", 0)[0]

            # 嘗試獲取更多詳細結果
            try:
                swet_total = vsp.GetDoubleResults(result_id, "Comp_Swet", 0)[0]
            except:
                swet_total = wetted_area

            try:
                fc_vinf = vsp.GetDoubleResults(result_id, "FC_Vinf", 0)[0]
                fc_rho = vsp.GetDoubleResults(result_id, "FC_Rho", 0)[0]
                fc_sref = vsp.GetDoubleResults(result_id, "FC_Sref", 0)[0]
            except:
                fc_vinf = flow_conditions['velocity']
                fc_rho = flow_conditions['density']
                fc_sref = wetted_area

            # 計算動壓和雷諾數
            q = 0.5 * flow_conditions['density'] * (flow_conditions['velocity'] ** 2)

            # 計算雷諾數（如果有運動粘度）
            if 'kinematic_viscosity' in flow_conditions:
                Re = flow_conditions['velocity'] * (wetted_area ** 0.5) / flow_conditions['kinematic_viscosity']
            else:
                # 使用標準空氣運動粘度估算
                nu_air = 1.5e-5  # m²/s at 15°C
                Re = flow_conditions['velocity'] * (wetted_area ** 0.5) / nu_air

            # Cd·A (等效平板面積) = CD * Sref
            CdA = cd_total * fc_sref

            # 阻力力 = CD * q * Sref
            drag_force = cd_total * q * fc_sref

            analysis_time = time.time() - start_time

            results = {
                'drag_force_N': drag_force,
                'drag_coefficient': cd_total,
                'CdA_equivalent': CdA,
                'wetted_area_m2': swet_total,
                'projected_area_m2': projected_area,
                'reference_area_m2': fc_sref,
                'reynolds_number': Re,
                'dynamic_pressure_Pa': q,
                'flow_conditions': {
                    'velocity_ms': fc_vinf,
                    'density_kgm3': fc_rho,
                    'temperature_K': flow_conditions['temperature']
                },
                'analysis_time_s': analysis_time
            }

            if verbose:
                print(f"\n✅ 分析完成！")
                print(f"\n   阻力結果：")
                print(f"      阻力力: {results['drag_force_N']:.4f} N")
                print(f"      阻力係數 (CD): {results['drag_coefficient']:.6f}")
                print(f"      Cd·A: {results['CdA_equivalent']:.6f} m²")
                print(f"\n   幾何：")
                print(f"      濕面積: {results['wetted_area_m2']:.4f} m²")
                print(f"      投影面積 (Sref): {results['projected_area_m2']:.4f} m²")
                print(f"      雷諾數: {results['reynolds_number']:.0f}")
                print(f"\n   流場：")
                print(f"      動壓: {results['dynamic_pressure_Pa']:.4f} Pa")
                print(f"\n   時間: {results['analysis_time_s']:.3f}s")
                print(f"{'='*80}\n")

            return results

        except Exception as e:
            return {"error": f"Failed to extract results: {str(e)}"}


# 測試
if __name__ == "__main__":
    import sys

    print("="*80)
    print("ParasiteDrag Analyzer - Test")
    print("="*80)

    # 檢查是否有測試文件
    test_file = "output/MathDriven_Test_Cosine40.vsp3"

    if not os.path.exists(test_file):
        print(f"\n❌ 測試文件不存在: {test_file}")
        print("請先運行 cst_geometry_math_driven.py 生成測試文件")
        sys.exit(1)

    # 創建分析器
    analyzer = ParasiteDragAnalyzer()

    # 標準大氣條件（海平面，15°C）
    flow_conditions = {
        'velocity': 6.5,                    # m/s
        'density': 1.225,                   # kg/m³ (標準大氣)
        'temperature': 288.15,              # K (15°C)
        'pressure': 101325.0,               # Pa (1 atm)
        'kinematic_viscosity': 1.4607e-5    # m²/s (空氣 at 15°C)
    }

    # 執行分析
    results = analyzer.analyze(test_file, flow_conditions, verbose=True)

    # 檢查結果
    if "error" in results:
        print(f"\n❌ 分析失敗: {results['error']}")
    else:
        print("\n✅ 測試完成！")
        print(f"\n💡 合理性檢查：")
        print(f"   期望阻力範圍: 0.5-2.0 N (流線型機身 @ 6.5 m/s)")
        print(f"   期望 CD 範圍: 0.0002-0.0005")

        if 0.5 <= results['drag_force_N'] <= 2.0:
            print(f"   ✅ 阻力 {results['drag_force_N']:.4f} N 在合理範圍內")
        else:
            print(f"   ⚠️  阻力 {results['drag_force_N']:.4f} N 可能異常")

        if 0.0002 <= results['drag_coefficient'] <= 0.0005:
            print(f"   ✅ CD {results['drag_coefficient']:.6f} 在合理範圍內")
        else:
            print(f"   ⚠️  CD {results['drag_coefficient']:.6f} 可能異常")

    print("\n" + "="*80)
