"""
CST Geometry Generator - Math-Driven Version
純數學驅動的 CST 幾何生成器
整合：數值微分、餘弦分佈、強制切線鎖定
"""
import openvsp as vsp
import os
import sys
import time

# 導入數學模組（使用絕對路徑避免衝突）
current_dir = os.path.dirname(__file__)
math_dir = os.path.join(current_dir, '..', 'math')
sys.path.insert(0, math_dir)

from cst_derivatives import CSTDerivatives
from section_distribution import SectionDistribution


class CSTGeometryMathDriven:
    """
    數學驅動的 CST 幾何生成器

    核心特性：
    1. 使用數值微分引擎計算精確的切線角度
    2. 採用全餘弦分佈提升機頭/機尾解析度
    3. 強制切線鎖定 (Tangent Locking) 消除表面波浪
    4. 自動化 ParasiteDrag 分析流程
    """

    def __init__(self, output_dir="output"):
        self.output_dir = output_dir
        self._ensure_output_folder()

    def _ensure_output_folder(self):
        """創建輸出目錄"""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"📁 Created output folder: {self.output_dir}")

    def generate_fuselage(self, design_params, verbose=True):
        """
        生成機身幾何 - 數學驅動版本

        Parameters:
        -----------
        design_params : dict
            name: 設計名稱
            length: 機身長度 (m)
            n_nose: 機頭形狀參數 (N1)
            n_tail: 機尾形狀參數 (N2)
            width_weights: 寬度 CST 權重
            height_weights: 高度 CST 權重
            super_m: 超橢圓指數 m (默認 2.5)
            super_n: 超橢圓指數 n (默認 2.5)
            num_sections: 截面數量 (默認 40)
            section_distribution: 分佈方式 (默認 "cosine_full")
            continuity: C0/C1/C2 連續性 (默認 1 = C1)
            tangent_strength: 切線強度 (默認 0.75)
            min_spacing: 最小截面間距 (默認 0.001)
            run_drag_analysis: 是否執行阻力分析 (默認 True)

        Returns:
        --------
        dict : {
            'filepath': str,
            'drag_results': dict,
            'timing': dict,
            'section_info': dict
        }
        """
        start_time = time.time()

        # 提取參數
        name = design_params["name"]
        L = design_params["length"]
        N1 = design_params["n_nose"]
        N2 = design_params["n_tail"]
        W_w = design_params["width_weights"]
        H_w = design_params["height_weights"]
        super_m = design_params.get("super_m", 2.5)
        super_n = design_params.get("super_n", 2.5)
        num_sections = design_params.get("num_sections", 40)
        distribution = design_params.get("section_distribution", "cosine_full")
        continuity = design_params.get("continuity", 1)
        tan_strength = design_params.get("tangent_strength", 0.75)
        min_spacing = design_params.get("min_spacing", 0.001)
        run_drag = design_params.get("run_drag_analysis", True)

        if verbose:
            print(f"\n{'='*80}")
            print(f"🔨 數學驅動幾何生成器")
            print(f"{'='*80}")
            print(f"📋 設計: {name}")
            print(f"📏 長度: {L} m")
            print(f"🔢 截面: {num_sections} ({distribution} 分佈)")
            print(f"📐 CST: N1={N1}, N2={N2}")
            print(f"🔄 超橢圓: m={super_m}, n={super_n}")
            print(f"🔒 切線鎖定: C{continuity} 連續, 強度={tan_strength}")

        # ========== STEP 1: 生成截面分佈 ==========
        t_dist_start = time.time()

        if distribution == "cosine_full":
            psi_values = SectionDistribution.cosine_full(num_sections, min_spacing)
        elif distribution == "cosine_nose":
            psi_values = SectionDistribution.cosine_nose_only(num_sections, min_spacing)
        elif distribution == "cosine_tail":
            psi_values = SectionDistribution.cosine_tail_only(num_sections, min_spacing)
        elif distribution == "uniform":
            psi_values = SectionDistribution.uniform(num_sections)
        else:
            raise ValueError(f"未知的分佈方式: {distribution}")

        dist_stats = SectionDistribution.analyze_distribution(psi_values)
        t_dist = time.time() - t_dist_start

        if verbose:
            print(f"\n📍 截面分佈統計:")
            print(f"   最小間距: {dist_stats['min_spacing']:.6f}")
            print(f"   最大間距: {dist_stats['max_spacing']:.6f}")
            print(f"   間距比率: {dist_stats['spacing_ratio']:.2f}x")

        # ========== STEP 2: 創建 VSP 機身 ==========
        t_vsp_start = time.time()

        vsp.ClearVSPModel()
        fuse_id = vsp.AddGeom("FUSELAGE")
        vsp.SetGeomName(fuse_id, name)
        vsp.SetParmVal(fuse_id, "Length", "Design", L)

        # 獲取截面表面
        xsec_surf = vsp.GetXSecSurf(fuse_id, 0)

        # 插入截面
        current_sections = vsp.GetNumXSec(xsec_surf)
        needed_inserts = num_sections - current_sections

        for i in range(needed_inserts):
            insert_index = 1 + i
            vsp.InsertXSec(fuse_id, insert_index, vsp.XS_SUPER_ELLIPSE)

        vsp.Update()
        t_vsp_create = time.time() - t_vsp_start

        # ========== STEP 3: 配置截面幾何與切線 ==========
        t_config_start = time.time()

        final_count = vsp.GetNumXSec(xsec_surf)
        if final_count != num_sections:
            raise RuntimeError(f"截面數量不符: 期望 {num_sections}, 實際 {final_count}")

        for i in range(final_count):
            psi = psi_values[i]
            is_tip = (i == 0) or (i == final_count - 1)

            # 改變形狀（必須先改變形狀再設置參數）
            if is_tip:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
            else:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)

            # 獲取截面物件
            xsec = vsp.GetXSec(xsec_surf, i)

            # 設置位置
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

            if not is_tip:
                # ========== 數學計算：CST 半徑 ==========
                r_width = CSTDerivatives.cst_radius(psi, N1, N2, W_w, L)
                r_height = CSTDerivatives.cst_radius(psi, N1, N2, H_w, L)

                w = max(r_width * 2, 0.001)
                h = max(r_height * 2, 0.001)

                # 設置幾何尺寸
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), w)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), h)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), super_m)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), super_n)

                # ========== 數學計算：切線角度 ==========
                tangent_angles = CSTDerivatives.compute_tangent_angles_for_section(
                    psi, N1, N2, W_w, H_w, L
                )

                # ========== 強制切線鎖定 ==========
                # 設置 C1 連續性
                vsp.SetXSecContinuity(xsec, continuity)

                # 設置切線角度（上、右、下、左）
                # 注意：對於圓形/超橢圓截面，左右使用寬度角度，上下使用高度角度
                vsp.SetXSecTanAngles(
                    xsec, vsp.XSEC_BOTH_SIDES,
                    tangent_angles['top'],      # 上
                    tangent_angles['right'],    # 右
                    tangent_angles['bottom'],   # 下
                    tangent_angles['left']      # 左
                )

                # 設置切線強度
                vsp.SetXSecTanStrengths(
                    xsec, vsp.XSEC_BOTH_SIDES,
                    tan_strength, tan_strength, tan_strength, tan_strength
                )

                # Slew 設置為 0（不扭轉）
                vsp.SetXSecTanSlews(
                    xsec, vsp.XSEC_BOTH_SIDES,
                    0.0, 0.0, 0.0, 0.0
                )

            else:
                # 機頭/機尾：特殊處理
                if i == 0:
                    # 機頭：強制垂直切線
                    nose_angle = CSTDerivatives.tangent_angle_at_nose(N1, N2, W_w)

                    xsec = vsp.GetXSec(xsec_surf, i)
                    vsp.SetXSecContinuity(xsec, continuity)
                    vsp.SetXSecTanAngles(
                        xsec, vsp.XSEC_BOTH_SIDES,
                        nose_angle, nose_angle, nose_angle, nose_angle
                    )
                    vsp.SetXSecTanStrengths(
                        xsec, vsp.XSEC_BOTH_SIDES,
                        tan_strength, tan_strength, tan_strength, tan_strength
                    )

        vsp.Update()
        t_config = time.time() - t_config_start

        # ========== STEP 3.5: 設置 ParasiteDrag 參數（保存前）==========
        # 確保文件中保存正確的 ParasiteDrag 設置，這樣 API 分析時能正確執行
        if verbose:
            print(f"\n⚙️  設置 ParasiteDrag 參數（直接修改 Parm）...")

        # 關鍵：直接找到並設置 ParasiteDragSettings 容器中的參數
        # 這樣設置才會被保存到 VSP 文件中

        # 找到 ParasiteDragSettings 容器ID
        pd_container = vsp.FindContainer("ParasiteDragSettings", 0)

        if pd_container:
            # 設置單位為公制（LengthUnit = 2 = meters）
            length_unit_parm = vsp.FindParm(pd_container, "LengthUnit", "ParasiteDrag")
            if length_unit_parm:
                vsp.SetParmVal(length_unit_parm, 2.0)  # LEN_M = 2

            # 設置參考面積為 1.0 m²
            sref_parm = vsp.FindParm(pd_container, "Sref", "ParasiteDrag")
            if sref_parm:
                vsp.SetParmVal(sref_parm, 1.0)

            # 設置高度為 0（海平面）
            alt_parm = vsp.FindParm(pd_container, "Alt", "ParasiteDrag")
            if alt_parm:
                vsp.SetParmVal(alt_parm, 0.0)

            # 設置高度單位為 meters
            alt_unit_parm = vsp.FindParm(pd_container, "AltLengthUnit", "ParasiteDrag")
            if alt_unit_parm:
                vsp.SetParmVal(alt_unit_parm, 1.0)  # meters

            # 設置速度為 6.5 m/s
            vinf_parm = vsp.FindParm(pd_container, "Vinf", "ParasiteDrag")
            if vinf_parm:
                vsp.SetParmVal(vinf_parm, 6.5)

            # 設置速度單位為 m/s
            vinf_unit_parm = vsp.FindParm(pd_container, "VinfUnitType", "ParasiteDrag")
            if vinf_unit_parm:
                vsp.SetParmVal(vinf_unit_parm, 1.0)  # m/s

            # 設置溫度為 15°C（海平面標準）
            temp_parm = vsp.FindParm(pd_container, "Temp", "ParasiteDrag")
            if temp_parm:
                vsp.SetParmVal(temp_parm, 15.0)

            # 設置溫度單位為 Celsius
            temp_unit_parm = vsp.FindParm(pd_container, "TempUnit", "ParasiteDrag")
            if temp_unit_parm:
                vsp.SetParmVal(temp_unit_parm, 1.0)  # Celsius

            # 設置 Delta 溫度為 0
            delta_temp_parm = vsp.FindParm(pd_container, "DeltaTemp", "ParasiteDrag")
            if delta_temp_parm:
                vsp.SetParmVal(delta_temp_parm, 0.0)

            # 設置層流摩擦係數方程式為 Blasius (0)
            lam_cf_parm = vsp.FindParm(pd_container, "LamCfEqnType", "ParasiteDrag")
            if lam_cf_parm:
                vsp.SetParmVal(lam_cf_parm, 0.0)  # CF_LAM_BLASIUS

            # 設置紊流摩擦係數方程式為 Power Law Prandtl Low Re (7)
            turb_cf_parm = vsp.FindParm(pd_container, "TurbCfEqnType", "ParasiteDrag")
            if turb_cf_parm:
                vsp.SetParmVal(turb_cf_parm, 7.0)  # CF_TURB_POWER_LAW_PRANDTL_LOW_RE

            # 設置 RefFlag = 0 (使用手動 Sref)
            ref_flag_parm = vsp.FindParm(pd_container, "RefFlag", "ParasiteDrag")
            if ref_flag_parm:
                vsp.SetParmVal(ref_flag_parm, 0.0)

            # 設置 GeomSet = 0 (SET_ALL)
            set_parm = vsp.FindParm(pd_container, "Set", "ParasiteDrag")
            if set_parm:
                vsp.SetParmVal(set_parm, 0.0)  # SET_ALL

            vsp.Update()

            if verbose:
                print(f"   ✅ ParasiteDrag 參數已直接設置到文件中")
                print(f"      單位: 公制 (m, m/s, °C)")
                print(f"      Sref: 1.0 m²")
                print(f"      高度: 0 m (海平面)")
                print(f"      速度: 6.5 m/s")
                print(f"      摩擦係數: Blasius + Power Law Prandtl Low Re")
        else:
            if verbose:
                print(f"   ⚠️  找不到 ParasiteDragSettings 容器")

        # ========== STEP 4: 保存文件 ==========
        filepath = os.path.join(self.output_dir, f"{name}.vsp3")
        vsp.WriteVSPFile(filepath)

        t_geometry = time.time() - start_time

        if verbose:
            print(f"\n⏱️  時間統計:")
            print(f"   分佈生成: {t_dist:.3f}s")
            print(f"   VSP 創建: {t_vsp_create:.3f}s")
            print(f"   截面配置: {t_config:.3f}s")
            print(f"   總幾何時間: {t_geometry:.3f}s")

        # ========== STEP 5: 阻力分析（可選） ==========
        drag_results = {}
        t_analysis = 0

        if run_drag:
            if verbose:
                print(f"\n🔬 執行阻力分析...")

            t_analysis_start = time.time()
            drag_results = self._run_drag_analysis(filepath, design_params, verbose)
            t_analysis = time.time() - t_analysis_start

            if verbose and "error" not in drag_results:
                print(f"   分析時間: {t_analysis:.3f}s")

        total_time = time.time() - start_time

        if verbose:
            print(f"\n✅ 總時間: {total_time:.3f}s")
            print(f"💾 已保存: {filepath}")
            print(f"{'='*80}\n")

        return {
            "filepath": filepath,
            "drag_results": drag_results,
            "timing": {
                "distribution": t_dist,
                "vsp_create": t_vsp_create,
                "config": t_config,
                "geometry": t_geometry,
                "analysis": t_analysis,
                "total": total_time
            },
            "section_info": {
                "psi_values": psi_values,
                "distribution_stats": dist_stats
            }
        }

    def _run_drag_analysis(self, vsp_file_path, design_params, verbose=True):
        """
        執行 ParasiteDrag 分析

        Parameters:
        -----------
        vsp_file_path : str
            VSP 文件路徑
        design_params : dict
            設計參數（用於計算投影面積）
        verbose : bool
            是否打印詳細信息

        Returns:
        --------
        dict : 阻力分析結果
        """
        # 導入分析器
        analysis_dir = os.path.join(os.path.dirname(__file__), '..', 'analysis')
        sys.path.insert(0, analysis_dir)

        from parasite_drag_analyzer import ParasiteDragAnalyzer

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

        # 執行分析（傳遞設計參數以計算投影面積）
        results = analyzer.analyze(vsp_file_path, flow_conditions, design_params=design_params, verbose=verbose)

        return results


# 測試
if __name__ == "__main__":
    print("="*80)
    print("Math-Driven CST Geometry Generator - Test")
    print("="*80)

    generator = CSTGeometryMathDriven(output_dir="output")

    # 測試設計
    test_design = {
        "name": "MathDriven_Full_Test",
        "length": 2.5,
        "n_nose": 0.5,
        "n_tail": 1.0,
        "width_weights": [0.25, 0.35, 0.30, 0.10],
        "height_weights": [0.30, 0.45, 0.35, 0.10],
        "super_m": 2.5,
        "super_n": 2.5,
        "num_sections": 40,
        "section_distribution": "cosine_full",
        "continuity": 1,
        "tangent_strength": 0.75,
        "run_drag_analysis": True  # 啟用阻力分析
    }

    result = generator.generate_fuselage(test_design, verbose=True)

    print("\n✅ 測試完成！")
    print(f"📁 文件位置: {result['filepath']}")
    print(f"⏱️  總時間: {result['timing']['total']:.3f}s")
    print("="*80)
