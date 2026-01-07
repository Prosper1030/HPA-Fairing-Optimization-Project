"""
HPA 整流罩非對稱優化器
使用已驗證的 VSP API 方法 + GA 優化

作者：Claude
日期：2026-01-04
"""

import numpy as np
import openvsp as vsp
from scipy.special import comb
import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, Tuple, List
from pathlib import Path

# 添加專案路徑
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from analysis.drag_analysis import DragAnalyzer

# 導入數學工具（來自 src/math/）
import importlib.util
math_dir = os.path.join(src_path, 'math')

spec_dist = importlib.util.spec_from_file_location("section_distribution",
                                                     os.path.join(math_dir, "section_distribution.py"))
section_distribution = importlib.util.module_from_spec(spec_dist)
spec_dist.loader.exec_module(section_distribution)
SectionDistribution = section_distribution.SectionDistribution

spec_deriv = importlib.util.spec_from_file_location("cst_derivatives",
                                                      os.path.join(math_dir, "cst_derivatives.py"))
cst_derivatives = importlib.util.module_from_spec(spec_deriv)
spec_deriv.loader.exec_module(cst_derivatives)
CSTDerivatives = cst_derivatives.CSTDerivatives


# ==========================================
# 專案檔案管理器
# ==========================================
class ProjectManager:
    """管理專案輸出目錄和檔案"""

    def __init__(self, base_output_dir: str = "output"):
        self.base_dir = Path(base_output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = self.base_dir / f"hpa_run_{timestamp}"

        # 創建子目錄
        self.vsp_dir = self.run_dir / "vsp_models"
        self.csv_dir = self.run_dir / "drag_csv"
        self.log_dir = self.run_dir / "logs"

        for d in [self.vsp_dir, self.csv_dir, self.log_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # 初始化日誌檔案
        self.log_file = self.log_dir / "optimization_log.txt"
        self.results_file = self.log_dir / "results.json"
        self.best_gene_file = self.log_dir / "best_gene.json"

        self.log(f"創建運行目錄: {self.run_dir}")

    def log(self, message: str):
        """寫入日誌"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {message}"
        print(log_msg)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')

    def save_gene(self, gene: Dict, generation: int, individual: int):
        """保存基因到 JSON"""
        gene_file = self.log_dir / f"gen{generation:03d}_ind{individual:03d}.json"
        with open(gene_file, 'w', encoding='utf-8') as f:
            json.dump(gene, f, indent=2)

    def save_best_gene(self, gene: Dict, fitness: float, generation: int):
        """保存最佳基因"""
        data = {
            'gene': gene,
            'fitness': fitness,
            'generation': generation,
            'timestamp': datetime.now().isoformat()
        }
        with open(self.best_gene_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        self.log(f"保存最佳基因: fitness={fitness:.6f}, gen={generation}")

    def get_vsp_path(self, name: str) -> str:
        """獲取 VSP 檔案路徑"""
        return str(self.vsp_dir / f"{name}.vsp3")


# ==========================================
# CST 幾何建模器（手寫公式，上下非對稱）
# ==========================================
class CST_Modeler:
    """CST 幾何建模器，支援上下非對稱"""

    @staticmethod
    def class_function(psi: np.ndarray, N1: float, N2: float) -> np.ndarray:
        """CST 類別函數 C(ψ) = ψ^N1 * (1-ψ)^N2"""
        return (psi ** N1) * ((1 - psi) ** N2)

    @staticmethod
    def shape_function(psi: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """CST 形狀函數 S(ψ) = Σ(w_i * B_i(ψ))，使用 Bernstein 多項式"""
        n = len(weights) - 1
        S = np.zeros_like(psi)
        for i, w in enumerate(weights):
            B_i = comb(n, i) * (psi ** i) * ((1 - psi) ** (n - i))
            S += w * B_i
        return S

    @staticmethod
    def cst_curve(psi: np.ndarray, target_height: float, N1: float, N2: float,
                  weights: np.ndarray) -> np.ndarray:
        """
        完整 CST 曲線（峰值歸一化版本）

        採用「峰值歸一化」策略，確保：
        1. 曲線形狀不被扭曲
        2. 最大值精確等於 target_height
        3. 峰值位置由 N1/(N1+N2) 自然決定

        Parameters:
            psi: 截面位置陣列 (0-1)
            target_height: 目標最大高度 (m)
            N1, N2: CST 形狀參數
            weights: Bernstein 權重陣列

        Returns:
            歸一化並縮放後的 CST 曲線
        """
        # 1. 計算原始 Class Function
        C = CST_Modeler.class_function(psi, N1, N2)

        # 2. 計算 Shape Function
        S = CST_Modeler.shape_function(psi, weights)

        # 3. 組合原始曲線
        raw_curve = C * S

        # 4. 找出理論峰值位置（避免分母為 0）
        psi_peak = N1 / (N1 + N2) if (N1 + N2) > 1e-6 else 0.5

        # 5. 計算峰值處的數值
        C_peak = CST_Modeler.class_function(np.array([psi_peak]), N1, N2)[0]
        S_peak = CST_Modeler.shape_function(np.array([psi_peak]), weights)[0]
        peak_val = C_peak * S_peak

        # 6. 歸一化並縮放（保證峰值 = target_height）
        if peak_val > 1e-6:
            normalized_curve = (raw_curve / peak_val) * target_height
        else:
            normalized_curve = raw_curve * 0.0  # 防止除以零

        return normalized_curve

    @staticmethod
    def generate_asymmetric_fairing(gene: Dict, num_sections: int = 40) -> Dict:
        """
        生成非對稱整流罩曲線

        基因參數：
        - L: 總長度 (m)
        - W_max: 最大全寬 (Full Width) - 注意：代入 CST 時需除以 2
        - H_top_max: 上部最大高度 (Upper Radius) - 已經是半徑
        - H_bot_max: 下部最大高度 (Lower Radius) - 已經是半徑
        - N1: 機頭形狀係數
        - N2_top: 上機尾形狀係數
        - N2_bot: 下機尾形狀係數
        - X_max_pos: 最大截面位置 (0-1)
        - X_offset: 踏板位置 (m)
        - Super_M, Super_N: 超橢圓指數（可選）
        - tail_rise: 機尾上升高度（可選）
        - blend_start: 混合開始位置（可選）
        - blend_power: 混合曲線冪次（可選）
        - w0, w1, w2, w3: CST權重（可選）
        """
        # CST權重（從基因或使用預設值）
        w0 = gene.get('w0', 0.25)
        w1 = gene.get('w1', 0.35)
        w2 = gene.get('w2', 0.30)
        w3 = gene.get('w3', 0.10)
        weights = np.array([w0, w1, w2, w3])

        # 生成截面位置 - 使用餘弦分布（機頭機尾密集）
        psi_list = SectionDistribution.cosine_full(num_sections, min_spacing=0.001)
        psi = np.array(psi_list)
        x = psi * gene['L']

        # 生成半寬度曲線（W_max 是全寬，需除以 2）
        # 使用平均 N2 來控制寬度曲線
        N2_avg = (gene['N2_top'] + gene['N2_bot']) / 2.0
        width_half = CST_Modeler.cst_curve(
            psi, gene['W_max'] / 2.0, gene['N1'], N2_avg, weights
        )

        # ==========================================
        # 上下邊界獨立反推法（混合法）
        # ==========================================

        # 尾部參數（從基因或使用預設值）
        tail_rise = gene.get('tail_rise', 0.10)    # 機尾上升高度 (m)
        blend_start = gene.get('blend_start', 0.75)  # 混合開始位置
        blend_power = gene.get('blend_power', 2.0)   # 混合曲線冪次

        # 1. 生成基礎CST曲線
        z_upper_cst = CST_Modeler.cst_curve(
            psi, gene['H_top_max'], gene['N1'], gene['N2_top'], weights
        )
        z_lower_cst = -CST_Modeler.cst_curve(
            psi, gene['H_bot_max'], gene['N1'], gene['N2_bot'], weights
        )

        # 2. 計算混合因子
        blend_factor = np.zeros_like(psi)
        mask = psi >= blend_start
        if np.any(mask):
            psi_blend = (psi[mask] - blend_start) / (1.0 - blend_start)
            blend_factor[mask] = psi_blend**blend_power

        # 3. 混合到機尾高度（確保單調收斂，避免拐點）
        # 策略：在曲線接近 tail_rise 之前就開始線性插值
        z_upper_target = z_upper_cst * (1 - blend_factor) + tail_rise * blend_factor
        z_lower_target = z_lower_cst * (1 - blend_factor) + tail_rise * blend_factor

        z_upper = np.copy(z_upper_target)
        z_lower = np.copy(z_lower_target)

        if np.any(mask):
            blend_indices = np.where(mask)[0]

            # ⚠️ 關鍵修復：找到曲線接近 tail_rise 的點，從那裡開始線性插值
            # 避免曲線降到 tail_rise 以下再上升（造成拐點）

            # 上曲線：找第一個降到接近 tail_rise 的點（給 10% 容差）
            linear_start_idx_upper = None
            tolerance = tail_rise * 1.10  # tail_rise + 10%

            for i, idx in enumerate(blend_indices):
                if z_upper[idx] <= tolerance:
                    linear_start_idx_upper = i
                    break

            # 如果找到了，從該點開始強制線性插值到 tail_rise
            if linear_start_idx_upper is not None:
                start_idx = blend_indices[linear_start_idx_upper]
                start_z = z_upper[start_idx]
                start_psi = psi[start_idx]

                # 確保起點不低於 tail_rise（避免上升）
                if start_z < tail_rise:
                    start_z = tail_rise

                for i in range(linear_start_idx_upper, len(blend_indices)):
                    idx = blend_indices[i]
                    # 線性插值（如果起點 = tail_rise，則全程保持 tail_rise）
                    t = (psi[idx] - start_psi) / (1.0 - start_psi) if start_psi < 1.0 else 1.0
                    z_upper[idx] = start_z + (tail_rise - start_z) * t

            # 下曲線：找第一個上升到接近 tail_rise 的點
            linear_start_idx_lower = None
            tolerance_lower = tail_rise * 0.90  # tail_rise - 10%

            for i, idx in enumerate(blend_indices):
                if z_lower[idx] >= tolerance_lower:
                    linear_start_idx_lower = i
                    break

            # 從該點開始強制線性插值到 tail_rise
            if linear_start_idx_lower is not None:
                start_idx = blend_indices[linear_start_idx_lower]
                start_z = z_lower[start_idx]
                start_psi = psi[start_idx]

                # 確保起點不高於 tail_rise（避免下降）
                if start_z > tail_rise:
                    start_z = tail_rise

                for i in range(linear_start_idx_lower, len(blend_indices)):
                    idx = blend_indices[i]
                    t = (psi[idx] - start_psi) / (1.0 - start_psi) if start_psi < 1.0 else 1.0
                    z_lower[idx] = start_z + (tail_rise - start_z) * t

        # 4. 反推VSP參數
        super_height = z_upper - z_lower  # 總厚度
        z_loc = (z_upper + z_lower) / 2   # 幾何中心

        return {
            'L': gene['L'],
            'psi': psi,
            'x': x,
            'width_half': width_half,      # 半寬（用於生成截面）
            'width': width_half * 2.0,     # 全寬（用於限制檢查）
            'z_upper': z_upper,            # 上邊界曲線
            'z_lower': z_lower,            # 下邊界曲線
            'super_height': super_height,  # VSP總厚度
            'z_loc': z_loc,                # VSP幾何中心
            'N1': gene['N1'],
            'N2_top': gene['N2_top'],      # 上曲線N2（用於切線計算）
            'N2_bot': gene['N2_bot'],      # 下曲線N2（用於切線計算）
            'N2_avg': N2_avg,              # 平均N2（用於左右切線）
            # 超橢圓參數（上下分開，從基因或使用預設值）
            'M_top': gene.get('M_top', 2.5),
            'N_top': gene.get('N_top', 2.5),
            'M_bot': gene.get('M_bot', 2.5),
            'N_bot': gene.get('N_bot', 2.5),
            # CST權重（用於切線計算）
            'weights': weights.tolist(),
            # 保留舊格式以便兼容（可選）
            'top': z_upper,
            'bottom': z_lower,
        }

    @staticmethod
    def generate_super_ellipse_profile(y_half: float, z_top: float, z_bot: float,
                                       n_points: int = 50, exponent: float = 2.5) -> List:
        """
        生成上下非對稱的超橢圓截面輪廓（用於 VSP File XSec）

        超橢圓公式：(y/a)^n + (z/b)^n = 1
        參數化：y = a*cos(θ)^(2/n), z = b*sin(θ)^(2/n)

        上半部使用 z_top，下半部使用 z_bot

        Parameters:
            y_half: 半寬（m）
            z_top: 上半部高度（m，正值）
            z_bot: 下半部高度（m，正值）
            n_points: 總點數（建議 50-100）
            exponent: 超橢圓指數（2=橢圓，2.5=VSP默認，>2=方形化）

        Returns:
            點列表 [[x, y, z], ...] **閉合**輪廓（逆時針）
        """
        points = []

        # 生成 n_points + 1 個點，確保最後一點 = 第一點（閉合曲線）
        for i in range(n_points + 1):
            # 從右邊開始逆時針（0° → 360°）
            theta = 2 * np.pi * i / n_points

            # 計算 y（左右對稱）
            cos_val = np.cos(theta)
            y = y_half * np.sign(cos_val) * (np.abs(cos_val) ** (2.0 / exponent))

            # 計算 z（上下不同）
            sin_val = np.sin(theta)

            if 0 <= theta <= np.pi:
                # 上半部（θ ∈ [0, π]）：用 z_top
                z = z_top * (np.abs(sin_val) ** (2.0 / exponent))
            else:
                # 下半部（θ ∈ [π, 2π]）：用 z_bot（負值）
                z = -z_bot * (np.abs(sin_val) ** (2.0 / exponent))

            # VSP XSec 是局部座標，x=0（垂直於機身軸）
            points.append([0.0, y, z])

        return points

    @staticmethod
    def write_fxs_file(filepath: str, y_half: float, z_top: float, z_bot: float,
                       n_points: int = 60, exponent: float = 2.5) -> bool:
        """
        生成並寫入 VSP .fxs 檔案（上下非對稱超橢圓截面）

        .fxs 格式：純文字檔，每行兩個數字 "Y Z"（空格分隔）

        Parameters:
            filepath: 輸出檔案路徑
            y_half: 半寬（m）
            z_top: 上半部高度（m，正值）
            z_bot: 下半部高度（m，正值）
            n_points: 總點數
            exponent: 超橢圓指數

        Returns:
            True 如果成功寫入
        """
        try:
            # 生成超橢圓截面點
            profile_points = CST_Modeler.generate_super_ellipse_profile(
                y_half, z_top, z_bot, n_points, exponent
            )

            # 寫入 .fxs 檔案
            with open(filepath, 'w') as f:
                for pt in profile_points:
                    # .fxs 格式：Y Z（忽略 X，因為它永遠是 0）
                    f.write(f"{pt[1]:.6f} {pt[2]:.6f}\n")

            return True
        except Exception as e:
            print(f"寫入 .fxs 檔案失敗: {e}")
            return False


# ==========================================
# 限制檢查器
# ==========================================
class ConstraintChecker:
    """硬限制檢查器"""

    # 限制常數
    FRAME_CLEARANCE = 0.3  # 車架包覆距離 (m)
    PEDAL_WIDTH = 0.45     # 踏板寬度 (m)
    SHOULDER_OFFSET = 0.5  # 肩膀相對踏板位置 (m)
    SHOULDER_WIDTH = 0.52  # 肩膀寬度 (m)
    SHOULDER_HEIGHT_TOP = 0.75  # 肩膀上高 (m)
    SHOULDER_HEIGHT_BOT = 0.25  # 肩膀下高 (m)
    TAIL_LENGTH = 1.5      # 機尾長度 (m)

    @staticmethod
    def interpolate_curve(x_target: float, x_array: np.ndarray, y_array: np.ndarray) -> float:
        """線性插值"""
        return np.interp(x_target, x_array, y_array)

    @staticmethod
    def check_all_constraints(gene: Dict, curves: Dict) -> Tuple[bool, Dict]:
        """
        檢查所有硬限制

        Returns:
            (通過, 結果字典)
        """
        results = {}

        # 1. 車架包覆
        x_frame = gene['X_offset'] - ConstraintChecker.FRAME_CLEARANCE
        results['frame'] = {'pass': x_frame >= 0, 'value': x_frame}

        # 2. 踏板寬度
        w_pedal = ConstraintChecker.interpolate_curve(
            gene['X_offset'], curves['x'], curves['width']
        )
        results['pedal_width'] = {
            'pass': w_pedal >= ConstraintChecker.PEDAL_WIDTH,
            'value': w_pedal,
            'required': ConstraintChecker.PEDAL_WIDTH
        }

        # 3-5. 肩膀位置檢查
        x_shoulder = gene['X_offset'] + ConstraintChecker.SHOULDER_OFFSET
        w_shoulder = ConstraintChecker.interpolate_curve(x_shoulder, curves['x'], curves['width'])
        h_top_shoulder = ConstraintChecker.interpolate_curve(x_shoulder, curves['x'], curves['top'])
        h_bot_shoulder = abs(ConstraintChecker.interpolate_curve(x_shoulder, curves['x'], curves['bottom']))

        results['shoulder_width'] = {
            'pass': w_shoulder >= ConstraintChecker.SHOULDER_WIDTH,
            'value': w_shoulder,
            'required': ConstraintChecker.SHOULDER_WIDTH
        }
        results['shoulder_top'] = {
            'pass': h_top_shoulder >= ConstraintChecker.SHOULDER_HEIGHT_TOP,
            'value': h_top_shoulder,
            'required': ConstraintChecker.SHOULDER_HEIGHT_TOP
        }
        results['shoulder_bot'] = {
            'pass': h_bot_shoulder >= ConstraintChecker.SHOULDER_HEIGHT_BOT,
            'value': h_bot_shoulder,
            'required': ConstraintChecker.SHOULDER_HEIGHT_BOT
        }

        # 6. 機尾長度
        tail_length = gene['L'] - gene['X_offset']
        results['tail_length'] = {
            'pass': tail_length >= ConstraintChecker.TAIL_LENGTH,
            'value': tail_length,
            'required': ConstraintChecker.TAIL_LENGTH
        }

        # 判斷是否全部通過
        all_pass = all(r['pass'] for r in results.values())

        return all_pass, results


# ==========================================
# VSP 模型生成器（使用已驗證方法）
# ==========================================
class VSPModelGenerator:
    """使用已驗證的 VSP API 方法生成模型"""

    @staticmethod
    def create_fuselage(curves: Dict, name: str, filepath: str):
        """
        從 CST 曲線創建 VSP Fuselage
        使用 cst_geometry_math_driven.py 中已驗證的方法
        """
        # 清空模型
        vsp.ClearVSPModel()

        # 創建 Fuselage
        fuse_id = vsp.AddGeom("FUSELAGE")
        vsp.SetGeomName(fuse_id, name)
        vsp.SetParmVal(fuse_id, "Length", "Design", curves['L'])

        # 獲取截面表面
        xsec_surf = vsp.GetXSecSurf(fuse_id, 0)
        num_sections = len(curves['psi'])

        # 插入截面（使用已驗證方法）
        current_sections = vsp.GetNumXSec(xsec_surf)
        needed_inserts = num_sections - current_sections
        for i in range(needed_inserts):
            vsp.InsertXSec(fuse_id, 1 + i, vsp.XS_SUPER_ELLIPSE)

        vsp.Update()

        # 設置每個截面
        for i in range(num_sections):
            psi = curves['psi'][i]
            is_nose = (i == 0)
            is_tail = (i == num_sections - 1)

            # 獲取新的VSP參數（來自上下邊界獨立反推法）
            total_width = curves['width_half'][i] * 2.0
            total_height = curves['super_height'][i]   # 總厚度（z_upper - z_lower）
            z_loc_value = curves['z_loc'][i]           # 幾何中心（(z_upper + z_lower) / 2）

            # 改變形狀
            if is_nose or is_tail:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_POINT)
            else:
                vsp.ChangeXSecShape(xsec_surf, i, vsp.XS_SUPER_ELLIPSE)

            xsec = vsp.GetXSec(xsec_surf, i)

            # 設置 X 位置
            vsp.SetParmVal(vsp.GetXSecParm(xsec, "XLocPercent"), psi)

            # 設置 Z 位置（幾何中心）
            # ⚠️ 關鍵：ZLocPercent是百分比（0-1），需要除以長度！
            z_loc_parm = vsp.GetXSecParm(xsec, "ZLocPercent")
            if z_loc_parm:
                z_loc_normalized = z_loc_value / curves['L']  # 歸一化到0-1範圍
                vsp.SetParmVal(z_loc_parm, z_loc_normalized)

            if not (is_nose or is_tail):
                # 中間截面：設置幾何參數
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Width"), total_width)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_Height"), total_height)

                # 超橢圓指數（上下分開）
                m_top = curves.get('M_top', 2.5)
                n_top = curves.get('N_top', 2.5)
                m_bot = curves.get('M_bot', 2.5)
                n_bot = curves.get('N_bot', 2.5)

                # 設置上半部 M/N
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_M"), m_top)
                vsp.SetParmVal(vsp.GetXSecParm(xsec, "Super_N"), n_top)

                # 關閉上下對稱，設置下半部 M/N
                tb_sym_parm = vsp.GetXSecParm(xsec, "Super_TopBotSym")
                if tb_sym_parm:
                    vsp.SetParmVal(tb_sym_parm, 0)  # 0 = 關閉對稱
                m_bot_parm = vsp.GetXSecParm(xsec, "Super_M_bot")
                n_bot_parm = vsp.GetXSecParm(xsec, "Super_N_bot")
                if m_bot_parm:
                    vsp.SetParmVal(m_bot_parm, m_bot)
                if n_bot_parm:
                    vsp.SetParmVal(n_bot_parm, n_bot)

                # 計算並設置切線角度（上下分開計算）
                # 使用curves中的權重（如果有），否則使用預設值
                weights_fixed = curves.get('weights', [0.25, 0.35, 0.30, 0.10])

                # 獲取實際的 N2 值（從 curves 中）
                N1 = curves.get('N1', 0.5)
                N2_top = curves.get('N2_top', 0.7)  # 上曲線N2
                N2_bot = curves.get('N2_bot', 0.8)  # 下曲線N2
                N2_avg = curves.get('N2_avg', 0.75) # 平均N2（用於左右）

                # ⚠️ 新方法：直接從z_upper和z_lower曲線計算角度
                # 這樣能正確反映非對稱幾何的真實斜率
                asymmetric_angles = CSTDerivatives.compute_asymmetric_tangent_angles(
                    curves['x'], curves['z_upper'], curves['z_lower'], i
                )
                angle_top_use = asymmetric_angles['top']
                angle_bot_use = asymmetric_angles['bottom']

                # 左右對稱，使用平均值（寬度方向）
                tangent_lr = CSTDerivatives.compute_tangent_angles_for_section(
                    psi, N1, N2_avg, weights_fixed, weights_fixed, curves['L']
                )

                # 設置切線
                vsp.SetXSecContinuity(xsec, 1)  # C1 連續性
                vsp.SetXSecTanAngles(
                    xsec, vsp.XSEC_BOTH_SIDES,
                    angle_top_use,           # 上（對稱時使用平均）
                    tangent_lr['right'],     # 右（左右對稱）
                    angle_bot_use,           # 下（對稱時使用平均）
                    tangent_lr['left']       # 左（左右對稱）
                )

                # 根據位置調整Strength以改善平滑度
                # 前段較低（保持形狀），後段較高（增加平滑）
                if psi < 0.3:
                    strength = 0.6
                elif psi < 0.7:
                    strength = 0.85
                else:
                    strength = 1.1

                vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES, strength, strength, strength, strength)
                vsp.SetXSecTanSlews(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)
            else:
                # 機頭/機尾特殊處理
                if i == 0:
                    # 機頭切線 - 使用新的非對稱角度計算法
                    # 即使機頭是對稱的，仍使用新方法以保持一致性
                    nose_angles = CSTDerivatives.compute_asymmetric_tangent_angles(
                        curves['x'], curves['z_upper'], curves['z_lower'], i
                    )
                    # 機頭左右對稱，使用相同的角度
                    angle_lr = nose_angles['top']  # 左右使用上角度作為參考

                    vsp.SetXSecContinuity(xsec, 1)
                    vsp.SetXSecTanAngles(
                        xsec, vsp.XSEC_BOTH_SIDES,
                        nose_angles['top'],      # 上
                        angle_lr,                # 右
                        nose_angles['bottom'],   # 下（已包含正負號修正）
                        angle_lr                 # 左
                    )
                    vsp.SetXSecTanStrengths(xsec, vsp.XSEC_BOTH_SIDES, 0.75, 0.75, 0.75, 0.75)
                    vsp.SetXSecTanSlews(xsec, vsp.XSEC_BOTH_SIDES, 0.0, 0.0, 0.0, 0.0)

        vsp.Update()

        # 設置 ParasiteDrag 參數（使用已驗證方法）
        pd_container = vsp.FindContainer("ParasiteDragSettings", 0)
        if pd_container:
            # 公制單位
            parm = vsp.FindParm(pd_container, "LengthUnit", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 2.0)  # meters

            # Sref = 1.0 m²
            parm = vsp.FindParm(pd_container, "Sref", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 1.0)

            # 海平面
            parm = vsp.FindParm(pd_container, "Alt", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 0.0)

            parm = vsp.FindParm(pd_container, "AltLengthUnit", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 1.0)

            # 速度 6.5 m/s
            parm = vsp.FindParm(pd_container, "Vinf", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 6.5)

            parm = vsp.FindParm(pd_container, "VinfUnitType", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 1.0)

            # 溫度 15°C
            parm = vsp.FindParm(pd_container, "Temp", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 15.0)

            parm = vsp.FindParm(pd_container, "TempUnit", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 1.0)

            # 摩擦係數方程式
            parm = vsp.FindParm(pd_container, "LamCfEqnType", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 0.0)  # Blasius

            parm = vsp.FindParm(pd_container, "TurbCfEqnType", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 7.0)  # Power Law Prandtl Low Re

            # RefFlag = 0 (手動 Sref)
            parm = vsp.FindParm(pd_container, "RefFlag", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 0.0)

            # Set = 0 (SET_ALL)
            parm = vsp.FindParm(pd_container, "Set", "ParasiteDrag")
            if parm: vsp.SetParmVal(parm, 0.0)

            vsp.Update()

        # 保存檔案
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        vsp.WriteVSPFile(filepath)


# ==========================================
# HPA 優化器主類
# ==========================================
class HPA_Optimizer:
    """HPA 整流罩優化器"""

    # 基因範圍（擴展版：9 → 18 個參數）
    GENE_BOUNDS = {
        # === 幾何參數（4個）===
        'L': (1.8, 3.0),              # 整流罩總長 (m)
        'W_max': (0.48, 0.65),        # 最大全寬 (m)
        'H_top_max': (0.85, 1.15),    # 上半部高度 (m)
        'H_bot_max': (0.25, 0.50),    # 下半部高度 (m)

        # === CST形狀參數（3個）===
        'N1': (0.4, 0.9),             # Class function N1
        'N2_top': (0.5, 1.0),         # Shape function N2（上）
        'N2_bot': (0.5, 1.0),         # Shape function N2（下）

        # === 位置參數（2個）===
        'X_max_pos': (0.2, 0.5),      # 最大寬度/高度位置
        'X_offset': (0.5, 1.0),       # 收縮開始位置 (m)

        # === 超橢圓參數（4個，上下分開）===
        'M_top': (2.0, 4.0),          # 上半部超橢圓指數M
        'N_top': (2.0, 4.0),          # 上半部超橢圓指數N
        'M_bot': (2.0, 4.0),          # 下半部超橢圓指數M
        'N_bot': (2.0, 4.0),          # 下半部超橢圓指數N

        # === 尾部參數（3個）===
        'tail_rise': (0.05, 0.20),    # 機尾上升高度 (m)
        'blend_start': (0.65, 0.85),  # 混合開始位置
        'blend_power': (1.5, 3.0),    # 混合曲線冪次

        # === CST權重（4個）===
        'w0': (0.15, 0.35),           # 前段斜率
        'w1': (0.25, 0.45),           # 最大值附近
        'w2': (0.20, 0.40),           # 後段平滑
        'w3': (0.05, 0.20),           # 尾部收斂
    }

    def __init__(self, project_manager: ProjectManager):
        self.pm = project_manager
        # DragAnalyzer 不需要指定輸出目錄，CSV 會在 VSP 檔案所在目錄生成
        self.drag_analyzer = None

    def evaluate_individual(self, gene_array: np.ndarray, gen: int, ind: int) -> float:
        """
        評估單個個體

        Returns:
            fitness (越小越好，阻力 N)
        """
        # 轉換為基因字典
        gene = self.array_to_gene(gene_array)

        # 1. 生成幾何曲線
        curves = CST_Modeler.generate_asymmetric_fairing(gene)

        # 2. 檢查限制
        passed, results = ConstraintChecker.check_all_constraints(gene, curves)

        if not passed:
            # 限制失敗，返回懲罰值
            return 1e6

        # 3. 生成 VSP 模型
        name = f"gen{gen:03d}_ind{ind:03d}"
        vsp_path = self.pm.get_vsp_path(name)

        try:
            VSPModelGenerator.create_fuselage(curves, name, vsp_path)
        except Exception as e:
            self.pm.log(f"VSP 生成失敗 ({name}): {e}")
            return 1e6

        # 4. 計算阻力（使用已驗證方法）
        try:
            # 執行阻力分析
            vsp.ClearVSPModel()
            vsp.ReadVSPFile(vsp_path)

            vsp.SetAnalysisInputDefaults("ParasiteDrag")
            vsp.SetDoubleAnalysisInput("ParasiteDrag", "Rho", [1.225])
            vsp.SetDoubleAnalysisInput("ParasiteDrag", "Vinf", [6.5])
            vsp.SetDoubleAnalysisInput("ParasiteDrag", "Mu", [1.7894e-5])
            vsp.ExecAnalysis("ParasiteDrag")

            # CSV 檔案在 VSP 檔案所在目錄生成
            csv_file = os.path.join(self.pm.vsp_dir, f"{name}_ParasiteBuildUp.csv")

            if os.path.exists(csv_file):
                with open(csv_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # 解析 Totals 行
                for line in lines:
                    if 'Totals:' in line:
                        # 找到 "Totals:" 後的數值
                        # 格式: ... Totals:, f, Cd, %
                        parts = [p.strip() for p in line.split(',')]
                        # 過濾掉空字串
                        values = [p for p in parts if p and p != 'Totals:']

                        if len(values) >= 2:
                            try:
                                # values[0] = f (m²), values[1] = Cd
                                f_value = float(values[0])
                                cd = float(values[1])

                                # 從主數據行獲取 Swet
                                for data_line in lines:
                                    if name in data_line and ',' in data_line:
                                        data_parts = [p.strip() for p in data_line.split(',')]
                                        if len(data_parts) > 1:
                                            swet = float(data_parts[1])
                                            break
                                else:
                                    swet = 0.0

                                q = 0.5 * 1.225 * (6.5 ** 2)
                                drag = q * swet * cd

                                self.pm.log(f"{name}: Cd={cd:.6f}, Swet={swet:.3f}m², Drag={drag:.4f}N")
                                return drag
                            except Exception as parse_err:
                                self.pm.log(f"CSV 解析錯誤: {parse_err}, line={line}")
                                pass

            self.pm.log(f"阻力計算失敗 ({name}): CSV 檔案 {csv_file} 不存在或解析失敗")
            return 1e6

        except Exception as e:
            self.pm.log(f"阻力計算失敗 ({name}): {e}")
            import traceback
            self.pm.log(traceback.format_exc())
            return 1e6

    def gene_to_array(self, gene: Dict) -> np.ndarray:
        """基因字典轉陣列"""
        keys = list(self.GENE_BOUNDS.keys())
        return np.array([gene[k] for k in keys])

    def array_to_gene(self, arr: np.ndarray) -> Dict:
        """陣列轉基因字典"""
        keys = list(self.GENE_BOUNDS.keys())
        return {k: arr[i] for i, k in enumerate(keys)}

    def get_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """獲取邊界"""
        keys = list(self.GENE_BOUNDS.keys())
        lower = np.array([self.GENE_BOUNDS[k][0] for k in keys])
        upper = np.array([self.GENE_BOUNDS[k][1] for k in keys])
        return lower, upper


# ==========================================
# GA 優化（使用 pymoo）
# ==========================================
def run_ga_optimization(n_gen: int = 5, pop_size: int = 10):
    """
    執行 GA 優化

    Parameters:
        n_gen: 代數（測試用少量）
        pop_size: 族群大小（測試用少量）
    """
    try:
        from pymoo.core.problem import Problem
        from pymoo.algorithms.soo.nonconvex.ga import GA
        from pymoo.optimize import minimize
        from pymoo.operators.sampling.rnd import FloatRandomSampling
        from pymoo.operators.crossover.sbx import SBX
        from pymoo.operators.mutation.pm import PM
    except ImportError:
        print("錯誤: 需要安裝 pymoo")
        print("請執行: pip install pymoo")
        return

    # 創建專案管理器
    pm = ProjectManager(base_output_dir="output")
    pm.log(f"開始 GA 優化: {n_gen} 代, 族群大小 {pop_size}")

    # 創建優化器
    optimizer = HPA_Optimizer(pm)

    # 定義問題
    class HPAProblem(Problem):
        def __init__(self):
            lower, upper = optimizer.get_bounds()
            super().__init__(
                n_var=len(lower),
                n_obj=1,
                n_constr=0,
                xl=lower,
                xu=upper
            )
            self.generation = 0
            self.individual_counter = 0

        def _evaluate(self, X, out, *args, **kwargs):
            # X 是 (n_pop, n_var) 陣列
            fitness = []
            for i, x in enumerate(X):
                f = optimizer.evaluate_individual(x, self.generation, self.individual_counter)
                fitness.append(f)
                self.individual_counter += 1

            out["F"] = np.array(fitness).reshape(-1, 1)

            # 每代結束後更新
            if self.individual_counter >= pop_size:
                self.generation += 1
                self.individual_counter = 0

    # 創建問題實例
    problem = HPAProblem()

    # 設置 GA 演算法
    algorithm = GA(
        pop_size=pop_size,
        sampling=FloatRandomSampling(),
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        eliminate_duplicates=True
    )

    # 執行優化
    pm.log("開始 GA 演算法...")

    res = minimize(
        problem,
        algorithm,
        ('n_gen', n_gen),
        verbose=True,
        seed=42
    )

    # 保存結果
    best_gene = optimizer.array_to_gene(res.X)
    best_fitness = float(res.F[0])

    pm.save_best_gene(best_gene, best_fitness, n_gen)
    pm.log(f"\n{'='*60}")
    pm.log(f"優化完成！")
    pm.log(f"最佳適應度: {best_fitness:.6f} N")
    pm.log(f"最佳基因: {best_gene}")
    pm.log(f"結果保存於: {pm.run_dir}")
    pm.log(f"{'='*60}")

    return res, pm


# ==========================================
# 測試模式
# ==========================================
def run_test_mode():
    """測試單個設計"""
    pm = ProjectManager(base_output_dir="output")
    pm.log("測試模式: 評估單個設計")

    # 測試基因（擴展版：18個參數）
    test_gene = {
        # 幾何參數
        'L': 2.5,
        'W_max': 0.60,
        'H_top_max': 0.95,
        'H_bot_max': 0.35,
        # CST形狀參數
        'N1': 0.5,
        'N2_top': 0.7,
        'N2_bot': 0.8,
        # 位置參數
        'X_max_pos': 0.25,
        'X_offset': 0.7,
        # 超橢圓參數（上下分開）
        'M_top': 2.5,
        'N_top': 2.5,
        'M_bot': 2.5,
        'N_bot': 2.5,
        # 尾部參數
        'tail_rise': 0.10,
        'blend_start': 0.75,
        'blend_power': 2.0,
        # CST權重
        'w0': 0.25,
        'w1': 0.35,
        'w2': 0.30,
        'w3': 0.10,
    }

    pm.log(f"測試基因: {test_gene}")

    optimizer = HPA_Optimizer(pm)
    gene_array = optimizer.gene_to_array(test_gene)

    fitness = optimizer.evaluate_individual(gene_array, gen=0, ind=0)

    pm.log(f"\n結果: fitness = {fitness:.6f} N")
    pm.log(f"輸出目錄: {pm.run_dir}")


# ==========================================
# 主程式
# ==========================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='HPA 整流罩優化器')
    parser.add_argument('--mode', type=str, default='test',
                       choices=['test', 'ga'],
                       help='運行模式: test=測試單個設計, ga=GA優化')
    parser.add_argument('--gen', type=int, default=5,
                       help='GA 代數（預設 5）')
    parser.add_argument('--pop', type=int, default=10,
                       help='GA 族群大小（預設 10）')

    args = parser.parse_args()

    if args.mode == 'test':
        run_test_mode()
    elif args.mode == 'ga':
        run_ga_optimization(n_gen=args.gen, pop_size=args.pop)
