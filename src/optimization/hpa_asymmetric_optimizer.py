"""
HPA 整流罩非對稱優化器
使用已驗證的 VSP API 方法 + GA 優化

作者：Claude
日期：2026-01-04
"""

import numpy as np
from scipy.special import comb
from scipy.interpolate import PchipInterpolator
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
from analysis.design_evaluator import evaluate_design_gene
from utils.openvsp_loader import load_openvsp

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
def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


_CANONICAL_GENE_BOUNDS = {
    # === 幾何主尺度（6個）===
    'L': (1.8, 3.0),                     # 整流罩總長 (m)
    'W_max': (0.48, 0.65),               # 最大全寬 (m)
    'H_max': (1.05, 1.70),               # 最大總厚度 (m)
    'camber_peak': (0.0, 0.50),          # 峰值站位的中心線高度 (m)
    'X_peak': (0.2, 0.5),                # 最大寬度/厚度位置
    'X_offset': (0.5, 1.0),              # 踏板位置 (m)

    # === 半寬曲線控制（4個，皆為相對峰值比例）===
    'width_le_ctrl_1': (0.08, 0.36),
    'width_le_ctrl_2': (0.50, 0.92),
    'width_te_ctrl_1': (0.48, 0.95),
    'width_te_ctrl_2': (0.03, 0.38),

    # === 總厚度曲線控制（4個，皆為相對峰值比例）===
    'height_le_ctrl_1': (0.12, 0.42),
    'height_le_ctrl_2': (0.56, 0.94),
    'height_te_ctrl_1': (0.46, 0.95),
    'height_te_ctrl_2': (0.02, 0.32),

    # === 中心線尾段控制（3個）===
    'centerline_te_ctrl_1': (0.05, 0.60),   # 從 peak_center → tail_z 的相對進度
    'centerline_te_ctrl_2': (0.35, 0.95),
    'tail_z': (0.05, 0.20),                 # 尾端中心線高度 (m)

    # === 超橢圓參數（4個，上下分開）===
    'M_top': (2.0, 4.0),
    'N_top': (2.0, 4.0),
    'M_bot': (2.0, 4.0),
    'N_bot': (2.0, 4.0),
}

_LEGACY_GENE_BOUNDS = {
    'L': (1.8, 3.0),
    'W_max': (0.48, 0.65),
    'H_top_max': (0.85, 1.15),
    'H_bot_max': (0.25, 0.50),
    'N1': (0.4, 0.9),
    'N2_top': (0.5, 1.0),
    'N2_bot': (0.5, 1.0),
    'X_max_pos': (0.2, 0.5),
    'X_offset': (0.5, 1.0),
    'M_top': (2.0, 4.0),
    'N_top': (2.0, 4.0),
    'M_bot': (2.0, 4.0),
    'N_bot': (2.0, 4.0),
    'tail_rise': (0.05, 0.20),
    'blend_start': (0.65, 0.85),
    'blend_power': (1.5, 3.0),
    'w0': (0.15, 0.35),
    'w1': (0.25, 0.45),
    'w2': (0.20, 0.40),
    'w3': (0.05, 0.20),
}

_CANONICAL_ONLY_FIELDS = set(_CANONICAL_GENE_BOUNDS) - {'L', 'W_max', 'X_offset', 'M_top', 'N_top', 'M_bot', 'N_bot'}
_LEGACY_ONLY_FIELDS = set(_LEGACY_GENE_BOUNDS) - {'L', 'W_max', 'X_offset', 'M_top', 'N_top', 'M_bot', 'N_bot'}


def _coerce_float(value, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"gene 欄位 {field_name} 必須是數值") from exc


def _normalized_parameter(value: float, lower: float, upper: float) -> float:
    if upper <= lower:
        return 0.5
    return float(np.clip((float(value) - lower) / (upper - lower), 0.0, 1.0))


def _legacy_width_control_overrides(gene: Dict) -> dict[str, float]:
    w0_n = _normalized_parameter(_coerce_float(gene['w0'], 'w0'), 0.15, 0.35)
    w1_n = _normalized_parameter(_coerce_float(gene['w1'], 'w1'), 0.25, 0.45)
    w2_n = _normalized_parameter(_coerce_float(gene['w2'], 'w2'), 0.20, 0.40)
    w3_n = _normalized_parameter(_coerce_float(gene['w3'], 'w3'), 0.05, 0.20)

    left_1 = 0.08 + 0.28 * w0_n
    left_2 = min(0.92, max(left_1 + 0.10, 0.50 + 0.28 * w1_n))
    right_2 = 0.03 + 0.35 * w3_n
    right_1 = min(0.95, max(right_2 + 0.18, 0.48 + 0.34 * w2_n))

    return {
        'width_le_ctrl_1': float(left_1),
        'width_le_ctrl_2': float(left_2),
        'width_te_ctrl_1': float(right_1),
        'width_te_ctrl_2': float(right_2),
    }


def _legacy_height_control_overrides(gene: Dict) -> dict[str, float]:
    n1_n = _normalized_parameter(_coerce_float(gene['N1'], 'N1'), 0.4, 0.9)
    n2_avg = 0.5 * (
        _coerce_float(gene['N2_top'], 'N2_top') + _coerce_float(gene['N2_bot'], 'N2_bot')
    )
    n2_avg_n = _normalized_parameter(n2_avg, 0.5, 1.0)

    nose_bluntness = 1.0 - n1_n
    tail_fullness = 1.0 - n2_avg_n

    left_1 = 0.12 + 0.30 * nose_bluntness
    left_2 = min(0.94, max(left_1 + 0.12, 0.56 + 0.24 * nose_bluntness))
    right_2 = 0.02 + 0.30 * tail_fullness
    right_1 = min(0.95, max(right_2 + 0.18, 0.46 + 0.32 * tail_fullness))

    return {
        'height_le_ctrl_1': float(left_1),
        'height_le_ctrl_2': float(left_2),
        'height_te_ctrl_1': float(right_1),
        'height_te_ctrl_2': float(right_2),
    }


def _legacy_centerline_overrides(gene: Dict) -> dict[str, float]:
    top_peak = _coerce_float(gene['H_top_max'], 'H_top_max')
    bot_peak = _coerce_float(gene['H_bot_max'], 'H_bot_max')
    peak_center = 0.5 * (top_peak - bot_peak)
    tail_rise = _coerce_float(gene['tail_rise'], 'tail_rise')
    peak_position = float(np.clip(_coerce_float(gene.get('X_max_pos', 0.25), 'X_max_pos'), 0.15, 0.85))

    tail_start = float(np.clip(
        _coerce_float(gene.get('blend_start', 0.75), 'blend_start'),
        peak_position + 0.05,
        0.97,
    ))
    tail_hold = (tail_start - peak_position) / max(1.0 - peak_position, 1e-9)
    power_n = _normalized_parameter(_coerce_float(gene.get('blend_power', 2.0), 'blend_power'), 1.5, 3.0)
    tail_balance = float(np.clip(
        (
            _coerce_float(gene['N2_bot'], 'N2_bot')
            - _coerce_float(gene['N2_top'], 'N2_top')
        ) / 0.5,
        -1.0,
        1.0,
    ))

    h_max = top_peak + bot_peak
    thickness_max = max(h_max, 1e-6)
    progress_1 = float(np.clip(0.14 + 0.26 * (1.0 - tail_hold) + 0.10 * (1.0 - power_n), 0.05, 0.60))
    progress_2 = float(np.clip(0.62 + 0.18 * (1.0 - tail_hold) + 0.08 * (1.0 - power_n), 0.40, 0.95))
    bias = 0.08 * tail_balance * thickness_max
    zc_min = min(peak_center, tail_rise) - 0.20 * thickness_max
    zc_max = max(peak_center, tail_rise) + 0.20 * thickness_max

    right_1 = float(np.clip(peak_center + progress_1 * (tail_rise - peak_center) + 0.5 * bias, zc_min, zc_max))
    right_2 = float(np.clip(peak_center + progress_2 * (tail_rise - peak_center) + 0.2 * bias, zc_min, zc_max))

    delta = tail_rise - peak_center
    if abs(delta) <= 1e-9:
        ctrl_1 = 0.30
        ctrl_2 = 0.70
    else:
        ctrl_1 = float(np.clip((right_1 - peak_center) / delta, 0.0, 1.0))
        ctrl_2 = float(np.clip((right_2 - peak_center) / delta, 0.0, 1.0))

    return {
        'centerline_te_ctrl_1': ctrl_1,
        'centerline_te_ctrl_2': ctrl_2,
        'tail_z': tail_rise,
    }


def _extract_canonical_overrides(gene: Dict) -> tuple[dict[str, float], dict[str, object]]:
    overrides: dict[str, float] = {}
    used_canonical_fields: list[str] = []
    used_legacy_fields: list[str] = []

    for key in _CANONICAL_GENE_BOUNDS:
        if key in gene:
            overrides[key] = _coerce_float(gene[key], key)
            used_canonical_fields.append(key)

    if 'X_max_pos' in gene:
        overrides['X_peak'] = _coerce_float(gene['X_max_pos'], 'X_max_pos')
        used_legacy_fields.append('X_max_pos')

    if 'H_top_max' in gene and 'H_bot_max' in gene:
        top_peak = _coerce_float(gene['H_top_max'], 'H_top_max')
        bot_peak = _coerce_float(gene['H_bot_max'], 'H_bot_max')
        overrides['H_max'] = top_peak + bot_peak
        overrides['camber_peak'] = 0.5 * (top_peak - bot_peak)
        used_legacy_fields.extend(['H_top_max', 'H_bot_max'])

    if all(key in gene for key in ('w0', 'w1', 'w2', 'w3')):
        overrides.update(_legacy_width_control_overrides(gene))
        used_legacy_fields.extend(['w0', 'w1', 'w2', 'w3'])

    if all(key in gene for key in ('N1', 'N2_top', 'N2_bot')):
        overrides.update(_legacy_height_control_overrides(gene))
        used_legacy_fields.extend(['N1', 'N2_top', 'N2_bot'])

    centerline_fields = ('H_top_max', 'H_bot_max', 'N2_top', 'N2_bot', 'tail_rise', 'blend_start', 'blend_power')
    if all(key in gene for key in centerline_fields):
        overrides.update(_legacy_centerline_overrides(gene))
        used_legacy_fields.extend(list(centerline_fields))
    elif 'tail_rise' in gene:
        overrides['tail_z'] = _coerce_float(gene['tail_rise'], 'tail_rise')
        used_legacy_fields.append('tail_rise')

    return overrides, {
        'used_canonical_fields': sorted(set(used_canonical_fields)),
        'used_legacy_fields': sorted(set(used_legacy_fields)),
    }


def _canonicalize_gene_dict(gene: Dict, fallback_gene: Dict | None = None) -> tuple[dict[str, float], dict[str, object]]:
    if not isinstance(gene, dict):
        raise ValueError("gene 必須是 JSON 物件")

    fallback_canonical: dict[str, float] = {}
    if fallback_gene is not None:
        if not isinstance(fallback_gene, dict):
            raise ValueError("fallback_gene 必須是 JSON 物件")
        fallback_canonical, _ = _extract_canonical_overrides(fallback_gene)

    overrides, override_metadata = _extract_canonical_overrides(gene)

    canonical = dict(fallback_canonical)
    filled_fields = [key for key in _CANONICAL_GENE_BOUNDS if key not in overrides and key in fallback_canonical]
    canonical.update(overrides)

    missing = [key for key in _CANONICAL_GENE_BOUNDS if key not in canonical]
    if missing:
        raise ValueError(f"gene 缺少必要欄位: {', '.join(missing)}")

    normalized = {key: _coerce_float(canonical[key], key) for key in _CANONICAL_GENE_BOUNDS}
    used_legacy_fields = override_metadata['used_legacy_fields']
    used_canonical_fields = override_metadata['used_canonical_fields']
    used_legacy_specific = [field for field in used_legacy_fields if field in _LEGACY_ONLY_FIELDS]
    used_canonical_specific = [field for field in used_canonical_fields if field in _CANONICAL_ONLY_FIELDS]

    if used_legacy_specific and used_canonical_specific:
        input_schema = "mixed"
    elif used_legacy_specific:
        input_schema = "legacy"
    else:
        input_schema = "canonical"

    return normalized, {
        'filled_fields': filled_fields,
        'input_schema': input_schema,
        'used_legacy_fields': used_legacy_fields,
        'used_canonical_fields': used_canonical_fields,
        'used_legacy_specific_fields': used_legacy_specific,
        'used_canonical_specific_fields': used_canonical_specific,
    }


class ProjectManager:
    """管理專案輸出目錄和檔案"""

    def __init__(self, base_output_dir: str = "output", existing_run_dir: str | None = None):
        self.base_dir = Path(base_output_dir)
        if existing_run_dir:
            self.run_dir = Path(existing_run_dir)
        else:
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
        self.candidate_scores_file = self.log_dir / "candidate_scores.jsonl"

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

    def save_best_gene(self, gene: Dict, fitness: float, generation: int, analysis: Dict | None = None):
        """保存最佳基因"""
        data = {
            'gene': gene,
            'fitness': fitness,
            'generation': generation,
            'timestamp': datetime.now().isoformat()
        }
        if analysis is not None:
            data['analysis'] = analysis
        with open(self.best_gene_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=_json_default)
        self.log(f"保存最佳基因: fitness={fitness:.6f}, gen={generation}")

    def save_results(self, payload: Dict):
        """保存最終結果摘要"""
        with open(self.results_file, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False, default=_json_default)

    def record_candidate(self, gene: Dict, score: float, generation: int, individual: int, analysis_mode: str):
        """追加記錄每個已評估候選，供後續 shortlist 與追蹤使用。"""
        payload = {
            'name': f'gen{generation:03d}_ind{individual:03d}',
            'generation': generation,
            'individual': individual,
            'score': float(score),
            'analysis_mode': analysis_mode,
            'timestamp': datetime.now().isoformat(),
            'gene': {key: float(value) for key, value in gene.items()},
        }
        with open(self.candidate_scores_file, 'a', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False)
            f.write('\n')

    def get_vsp_path(self, name: str) -> str:
        """獲取 VSP 檔案路徑"""
        return str(self.vsp_dir / f"{name}.vsp3")


# ==========================================
# CST 幾何建模器（手寫公式，上下非對稱）
# ==========================================
class CST_Modeler:
    """CST 幾何建模器，支援上下非對稱"""

    @staticmethod
    def _normalized_parameter(value: float, lower: float, upper: float) -> float:
        return _normalized_parameter(value, lower, upper)

    @staticmethod
    def _clip_peak_position(value: float) -> float:
        return float(np.clip(float(value), 0.15, 0.85))

    @staticmethod
    def _bezier_cubic(u: np.ndarray, p0: float, p1: float, p2: float, p3: float) -> np.ndarray:
        one_minus_u = 1.0 - u
        return (
            (one_minus_u ** 3) * p0
            + 3.0 * (one_minus_u ** 2) * u * p1
            + 3.0 * one_minus_u * (u ** 2) * p2
            + (u ** 3) * p3
        )

    @staticmethod
    def _shape_preserving_curve(
        psi: np.ndarray,
        split_position: float,
        start_value: float,
        split_value: float,
        end_value: float,
        left_ctrl: tuple[float, float],
        right_ctrl: tuple[float, float],
        *,
        left_positions: tuple[float, float] = (0.32, 0.74),
        right_positions: tuple[float, float] = (0.28, 0.72),
    ) -> np.ndarray:
        """
        用 support points + PCHIP 生成 shape-preserving 的縱向曲線。

        與直接拼兩段 cubic Bezier 相比，這裡的 peak station 會以 C1 方式
        平滑接續，不容易在最大截面位置形成視覺稜線。
        """
        split = float(np.clip(split_position, 1e-3, 1.0 - 1e-3))
        left_pos = np.clip(np.asarray(left_positions, dtype=float), 1e-3, 0.98)
        right_pos = np.clip(np.asarray(right_positions, dtype=float), 1e-3, 0.98)
        left_pos = np.sort(left_pos)
        right_pos = np.sort(right_pos)

        support_x = np.array(
            [
                0.0,
                split * left_pos[0],
                split * left_pos[1],
                split,
                split + (1.0 - split) * right_pos[0],
                split + (1.0 - split) * right_pos[1],
                1.0,
            ],
            dtype=float,
        )
        support_y = np.array(
            [
                float(start_value),
                float(left_ctrl[0]),
                float(left_ctrl[1]),
                float(split_value),
                float(right_ctrl[0]),
                float(right_ctrl[1]),
                float(end_value),
            ],
            dtype=float,
        )
        interpolator = PchipInterpolator(support_x, support_y, extrapolate=False)
        curve = interpolator(np.clip(psi, 0.0, 1.0))
        return np.asarray(curve, dtype=float)

    @staticmethod
    def _build_width_curve(psi: np.ndarray, gene: Dict, peak_position: float) -> np.ndarray:
        width_peak = max(float(gene['W_max']) * 0.5, 1e-6)
        left_values = sorted(
            [
                width_peak * float(np.clip(gene['width_le_ctrl_1'], 0.0, 0.98)),
                width_peak * float(np.clip(gene['width_le_ctrl_2'], 0.0, 0.98)),
            ]
        )
        right_values = sorted(
            [
                width_peak * float(np.clip(gene['width_te_ctrl_1'], 0.0, 0.98)),
                width_peak * float(np.clip(gene['width_te_ctrl_2'], 0.0, 0.98)),
            ],
            reverse=True,
        )

        return CST_Modeler._shape_preserving_curve(
            psi,
            peak_position,
            0.0,
            width_peak,
            0.0,
            (left_values[0], left_values[1]),
            (right_values[0], right_values[1]),
        )

    @staticmethod
    def _build_thickness_curve(psi: np.ndarray, gene: Dict, peak_position: float) -> np.ndarray:
        thickness_peak = max(float(gene['H_max']), 1e-6)
        left_values = sorted(
            [
                thickness_peak * float(np.clip(gene['height_le_ctrl_1'], 0.0, 0.98)),
                thickness_peak * float(np.clip(gene['height_le_ctrl_2'], 0.0, 0.98)),
            ]
        )
        right_values = sorted(
            [
                thickness_peak * float(np.clip(gene['height_te_ctrl_1'], 0.0, 0.98)),
                thickness_peak * float(np.clip(gene['height_te_ctrl_2'], 0.0, 0.98)),
            ],
            reverse=True,
        )

        return CST_Modeler._shape_preserving_curve(
            psi,
            peak_position,
            0.0,
            thickness_peak,
            0.0,
            (left_values[0], left_values[1]),
            (right_values[0], right_values[1]),
        )

    @staticmethod
    def _build_centerline_curve(
        psi: np.ndarray,
        gene: Dict,
        peak_position: float,
        thickness_curve: np.ndarray,
    ) -> np.ndarray:
        peak_center = float(gene['camber_peak'])
        tail_z = float(gene['tail_z'])
        peak_half_thickness = max(0.5 * float(np.max(thickness_curve)), 1e-6)
        asymmetry = abs(peak_center) / peak_half_thickness

        left_1 = peak_center * (0.18 + 0.18 * asymmetry)
        left_2 = peak_center * (0.72 + 0.10 * asymmetry)

        right_1_ratio = float(np.clip(gene['centerline_te_ctrl_1'], 0.0, 1.0))
        right_2_ratio = float(np.clip(gene['centerline_te_ctrl_2'], 0.0, 1.0))
        right_1 = peak_center + right_1_ratio * (tail_z - peak_center)
        right_2 = peak_center + right_2_ratio * (tail_z - peak_center)

        return CST_Modeler._shape_preserving_curve(
            psi,
            peak_position,
            0.0,
            peak_center,
            tail_z,
            (left_1, left_2),
            (right_1, right_2),
        )

    @staticmethod
    def _warp_psi_to_peak_position(
        psi: np.ndarray,
        target_peak_position: float | None,
        nominal_peak_position: float,
    ) -> np.ndarray:
        """
        Smoothly remap the longitudinal coordinate so the sampled CST curve peaks
        closer to the requested physical location.

        We use a monotonic cubic interpolation instead of a piecewise-linear map
        to avoid introducing an obvious kink around the requested peak station.
        """
        if target_peak_position is None:
            return psi

        target_peak = float(np.clip(target_peak_position, 1e-3, 1.0 - 1e-3))
        nominal_peak = float(np.clip(nominal_peak_position, 1e-3, 1.0 - 1e-3))

        if abs(target_peak - nominal_peak) < 1e-6:
            return psi

        mapper = PchipInterpolator(
            [0.0, target_peak, 1.0],
            [0.0, nominal_peak, 1.0],
            extrapolate=False,
        )
        warped = mapper(np.clip(psi, 0.0, 1.0))
        return np.clip(np.asarray(warped, dtype=float), 0.0, 1.0)

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
                  weights: np.ndarray, peak_position: float | None = None) -> np.ndarray:
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
        psi_peak_nominal = N1 / (N1 + N2) if (N1 + N2) > 1e-6 else 0.5
        psi_eval = CST_Modeler._warp_psi_to_peak_position(psi, peak_position, psi_peak_nominal)

        # 1. 計算原始 Class Function
        C = CST_Modeler.class_function(psi_eval, N1, N2)

        # 2. 計算 Shape Function
        S = CST_Modeler.shape_function(psi_eval, weights)

        # 3. 組合原始曲線
        raw_curve = C * S

        # 4. 使用離散曲線本身的峰值做正規化，這樣在加入 peak_position
        #    重新映射後仍能精確保持目標尺寸。
        peak_val = float(np.max(raw_curve)) if raw_curve.size else 0.0

        # 5. 歸一化並縮放（保證峰值 = target_height）
        if peak_val > 1e-6:
            normalized_curve = (raw_curve / peak_val) * target_height
        else:
            normalized_curve = raw_curve * 0.0  # 防止除以零

        return normalized_curve

    @staticmethod
    def generate_asymmetric_fairing(gene: Dict, num_sections: int = 40) -> Dict:
        """
        生成非對稱整流罩曲線

        正式基因參數：
        - L, W_max, H_max, camber_peak, X_peak, X_offset
        - width_le_ctrl_1/2, width_te_ctrl_1/2
        - height_le_ctrl_1/2, height_te_ctrl_1/2
        - centerline_te_ctrl_1/2, tail_z
        - M_top/N_top/M_bot/N_bot

        同時保留 legacy gene 相容：若呼叫端仍提供 H_top_max / N1 / w0..w3 /
        blend_* 等欄位，會先轉成 canonical schema 再生成幾何。
        """
        gene, _ = _canonicalize_gene_dict(gene)

        # 生成截面位置 - 使用餘弦分布（機頭機尾密集）
        psi_list = SectionDistribution.cosine_full(num_sections, min_spacing=0.001)
        psi = np.array(psi_list, dtype=float)
        x_peak = CST_Modeler._clip_peak_position(gene.get('X_peak', 0.25))
        if not np.any(np.isclose(psi, x_peak, atol=1e-9)):
            psi = np.sort(np.append(psi, x_peak))
        x = psi * gene['L']

        width_half = CST_Modeler._build_width_curve(psi, gene, x_peak)
        super_height = CST_Modeler._build_thickness_curve(psi, gene, x_peak)
        z_loc = CST_Modeler._build_centerline_curve(psi, gene, x_peak, super_height)

        z_upper = z_loc + 0.5 * super_height
        z_lower = z_loc - 0.5 * super_height

        # 用解析端點條件硬鎖 nose / tail，避免浮點誤差污染閉合。
        z_upper[0] = 0.0
        z_lower[0] = 0.0
        z_loc[0] = 0.0
        super_height[0] = 0.0

        tail_z = float(gene.get('tail_z', 0.10))
        z_upper[-1] = tail_z
        z_lower[-1] = tail_z
        z_loc[-1] = tail_z
        super_height[-1] = 0.0

        peak_top = float(gene['camber_peak'] + 0.5 * gene['H_max'])
        peak_bot = float(0.5 * gene['H_max'] - gene['camber_peak'])

        return {
            'L': gene['L'],
            'X_peak': x_peak,
            'psi': psi,
            'x': x,
            'width_half': width_half,      # 半寬（用於生成截面）
            'width': width_half * 2.0,     # 全寬（用於限制檢查）
            'z_upper': z_upper,            # 上邊界曲線
            'z_lower': z_lower,            # 下邊界曲線
            'super_height': super_height,  # VSP總厚度
            'z_loc': z_loc,                # VSP幾何中心
            'W_max': gene['W_max'],
            'H_max': gene['H_max'],
            'camber_peak': gene['camber_peak'],
            'tail_z': tail_z,
            'X_offset': gene['X_offset'],
            'H_top_peak': peak_top,
            'H_bot_peak': peak_bot,
            # 超橢圓參數（上下分開，從基因或使用預設值）
            'M_top': gene.get('M_top', 2.5),
            'N_top': gene.get('N_top', 2.5),
            'M_bot': gene.get('M_bot', 2.5),
            'N_bot': gene.get('N_bot', 2.5),
            'parameterization': 'whzc_bezier_v3',
            # 保留舊格式以便兼容（可選）
            'top': z_upper,
            'bottom': z_lower,
        }

    @staticmethod
    def generate_super_ellipse_profile(y_half: float, z_top: float, z_bot: float,
                                       n_points: int = 50, exponent: float = 2.5,
                                       m_top: float | None = None, n_top: float | None = None,
                                       m_bot: float | None = None, n_bot: float | None = None) -> List:
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
        top_y_exp = max(float(m_top if m_top is not None else exponent), 1.2)
        top_z_exp = max(float(n_top if n_top is not None else exponent), 1.2)
        bot_y_exp = max(float(m_bot if m_bot is not None else exponent), 1.2)
        bot_z_exp = max(float(n_bot if n_bot is not None else exponent), 1.2)

        for i in range(n_points + 1):
            # 從右邊開始逆時針（0° → 360°）
            theta = 2 * np.pi * i / n_points

            # 計算 y（左右對稱）
            cos_val = np.cos(theta)

            # 計算 z（上下不同）
            sin_val = np.sin(theta)

            if 0 <= theta <= np.pi:
                # 上半部（θ ∈ [0, π]）：用 z_top
                y = y_half * np.sign(cos_val) * (np.abs(cos_val) ** (2.0 / top_y_exp))
                z = z_top * (np.abs(sin_val) ** (2.0 / top_z_exp))
            else:
                # 下半部（θ ∈ [π, 2π]）：用 z_bot（負值）
                y = y_half * np.sign(cos_val) * (np.abs(cos_val) ** (2.0 / bot_y_exp))
                z = -z_bot * (np.abs(sin_val) ** (2.0 / bot_z_exp))

            # VSP XSec 是局部座標，x=0（垂直於機身軸）
            points.append([0.0, y, z])

        return points

    @staticmethod
    def write_fxs_file(filepath: str, y_half: float, z_top: float, z_bot: float,
                       n_points: int = 60, exponent: float = 2.5,
                       m_top: float | None = None, n_top: float | None = None,
                       m_bot: float | None = None, n_bot: float | None = None) -> bool:
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
                y_half, z_top, z_bot, n_points, exponent, m_top, n_top, m_bot, n_bot
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
    def create_fuselage(curves: Dict, name: str, filepath: str | None = None):
        """
        從 CST 曲線創建 VSP Fuselage
        使用 cst_geometry_math_driven.py 中已驗證的方法
        """
        vsp = load_openvsp()

        # 清空模型
        vsp.ClearVSPModel()

        # 創建 Fuselage
        fuse_id = vsp.AddGeom("FUSELAGE")
        vsp.SetGeomName(fuse_id, name)
        vsp.SetParmVal(fuse_id, "Length", "Design", curves['L'])
        vsp.SetSetFlag(fuse_id, vsp.SET_ALL, True)
        if hasattr(vsp, "SET_SHOWN"):
            vsp.SetSetFlag(fuse_id, vsp.SET_SHOWN, True)
        if hasattr(vsp, "SET_NOT_SHOWN"):
            vsp.SetSetFlag(fuse_id, vsp.SET_NOT_SHOWN, False)

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

                # 直接從實際離散曲線計算四向切線，避免 legacy CST 導數
                # 與新 w/H/z_c 參數化互相打架。
                tangent_angles = CSTDerivatives.compute_tangent_angles_for_curves(
                    curves['x'], curves['width_half'], curves['z_upper'], curves['z_lower'], i
                )

                # 設置切線
                vsp.SetXSecContinuity(xsec, 1)  # C1 連續性
                vsp.SetXSecTanAngles(
                    xsec, vsp.XSEC_BOTH_SIDES,
                    tangent_angles['top'],
                    tangent_angles['right'],
                    tangent_angles['bottom'],
                    tangent_angles['left']
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
                    nose_angles = CSTDerivatives.compute_tangent_angles_for_curves(
                        curves['x'], curves['width_half'], curves['z_upper'], curves['z_lower'], i
                    )

                    vsp.SetXSecContinuity(xsec, 1)
                    vsp.SetXSecTanAngles(
                        xsec, vsp.XSEC_BOTH_SIDES,
                        nose_angles['top'],
                        nose_angles['right'],
                        nose_angles['bottom'],
                        nose_angles['left']
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

        # 保存檔案（GA 熱路徑可略過，避免額外 I/O）
        if filepath:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            vsp.WriteVSPFile(filepath)


# ==========================================
# HPA 優化器主類
# ==========================================
class HPA_Optimizer:
    """HPA 整流罩優化器"""

    # 正式 GA / analysis schema
    GENE_BOUNDS = dict(_CANONICAL_GENE_BOUNDS)
    LEGACY_GENE_BOUNDS = dict(_LEGACY_GENE_BOUNDS)

    @staticmethod
    def canonicalize_gene_dict(gene: Dict, fallback_gene: Dict | None = None) -> tuple[Dict, Dict]:
        return _canonicalize_gene_dict(gene, fallback_gene=fallback_gene)

    def __init__(
        self,
        project_manager: ProjectManager,
        W_area_penalty: float = 0.1,
        analysis_mode: str = "openvsp",
        flow_conditions: Dict | None = None,
    ):
        self.pm = project_manager
        self.analysis_mode = analysis_mode
        flow_conditions = flow_conditions or {}
        self.velocity = float(flow_conditions.get("velocity", 6.5))
        self.rho = float(flow_conditions.get("rho", 1.225))
        self.mu = float(flow_conditions.get("mu", 1.7894e-5))

        # 統一透過 OpenVSP results API 讀取結果，避免 GA 熱路徑再做 CSV 解析。
        self.drag_analyzer = DragAnalyzer(output_dir=str(self.pm.vsp_dir))
        # 面積懲罰因子 (N/m²)：Score = Drag + W_area_penalty × S_wet
        self.W_area_penalty = W_area_penalty
        self.pm.log(f"面積懲罰因子 W_area_penalty = {W_area_penalty} N/m²")
        self.pm.log(f"評估模式 = {self.analysis_mode}")

    def evaluate_individual(self, gene_array: np.ndarray, gen: int, ind: int) -> float:
        """
        評估單個個體

        Returns:
            fitness (越小越好，阻力 N)
        """
        # 轉換為基因字典
        gene = self.array_to_gene(gene_array)

        name = f"gen{gen:03d}_ind{ind:03d}"
        return float(
            evaluate_design_gene(
                gene,
                name,
                area_penalty=self.W_area_penalty,
                analysis_mode=self.analysis_mode,
                flow_conditions={
                    "velocity": self.velocity,
                    "rho": self.rho,
                    "mu": self.mu,
                },
                logger=self.pm.log,
                drag_analyzer=self.drag_analyzer,
                emit_traceback=True,
            )
        )

    def gene_to_array(self, gene: Dict) -> np.ndarray:
        """基因字典轉陣列"""
        keys = list(self.GENE_BOUNDS.keys())
        canonical_gene, _ = self.canonicalize_gene_dict(gene)
        return np.array([canonical_gene[k] for k in keys], dtype=float)

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
