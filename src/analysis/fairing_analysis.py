"""
Shared fast-analysis helpers for low-speed fairing studies.

This module keeps the proxy-based aerodynamic evaluation, report generation,
and HPA-specific constraint reporting in one place so the user-facing CLI and
the optimization worker can rely on the same behavior.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import base64
import json
from typing import Any

import numpy as np

from analysis.fairing_drag_proxy import FairingDragProxy


DEFAULT_FLOW_CONDITIONS = {
    "velocity": 6.5,
    "rho": 1.225,
    "mu": 1.7894e-5,
    "temperature": 15.0,
    "altitude": 0.0,
}

DEFAULT_ANALYSIS_CONFIG = {
    "backend": "fast_proxy",
    "preset": "none",
    "report": {
        "output_root": "output/analysis",
        "write_summary_json": True,
        "write_summary_markdown": True,
        "plot_side_profile": True,
        "plot_drag_breakdown": True,
        "use_placeholder_plots": False,
    },
}

DEFAULT_EXAMPLE_GENE = {
    "L": 2.5,
    "W_max": 0.60,
    "H_max": 1.30,
    "camber_peak": 0.30,
    "X_peak": 0.32,
    "X_offset": 0.70,
    "width_le_ctrl_1": 0.22,
    "width_le_ctrl_2": 0.64,
    "width_te_ctrl_1": 0.86,
    "width_te_ctrl_2": 0.28,
    "height_le_ctrl_1": 0.36,
    "height_le_ctrl_2": 0.752,
    "height_te_ctrl_1": 0.84,
    "height_te_ctrl_2": 0.30,
    "centerline_te_ctrl_1": 0.12,
    "centerline_te_ctrl_2": 0.45,
    "tail_z": 0.02,
    "M_top": 2.5,
    "N_top": 2.5,
    "M_bot": 2.5,
    "N_bot": 2.5,
}

DEFAULT_EXAMPLE_GENE_LEGACY = {
    "L": 2.5,
    "W_max": 0.60,
    "H_top_max": 0.95,
    "H_bot_max": 0.35,
    "N1": 0.5,
    "N2_top": 0.75,
    "N2_bot": 0.80,
    "X_max_pos": 0.32,
    "X_offset": 0.70,
    "M_top": 2.5,
    "N_top": 2.5,
    "M_bot": 2.5,
    "N_bot": 2.5,
    "tail_rise": 0.08,
    "blend_start": 0.80,
    "blend_power": 2.2,
    "w0": 0.25,
    "w1": 0.35,
    "w2": 0.30,
    "w3": 0.10,
}

REPRESENTATIVE_THRESHOLDS = {
    "fineness_slender_min": 2.9,
    "fineness_short_fat_max": 2.27,
    "x_peak_forward_max": 0.25,
    "x_peak_aft_min": 0.40,
    "pressure_risk_aggressive_min": 0.85,
    "pressure_risk_conservative_max": 0.35,
    "tail_top_aggressive_min": 48.0,
    "tail_bottom_aggressive_min": 26.0,
    "tail_side_aggressive_min": 16.0,
    "tail_top_conservative_max": 36.0,
    "tail_bottom_conservative_max": 15.0,
    "tail_side_conservative_max": 11.0,
}

REPRESENTATIVE_GENE_ARCHETYPES = (
    {
        "case_name": "mid_pack_example",
        "description": "Use the project example gene as a balanced mid-pack reference.",
        "target_tags": ["mid_pack"],
        "overrides": {},
    },
    {
        "case_name": "slender_forward_conservative",
        "description": "Long, forward-peak body with a gentle recovery tail.",
        "target_tags": ["slender", "peak_forward", "tail_conservative"],
        "overrides": {
            "L": 3.0,
            "W_max": 0.49,
            "H_top_max": 0.85,
            "H_bot_max": 0.25,
            "X_max_pos": 0.22,
            "tail_rise": 0.05,
            "blend_start": 0.65,
            "blend_power": 1.55,
            "w0": 0.35,
            "w1": 0.45,
            "w2": 0.20,
            "w3": 0.05,
        },
    },
    {
        "case_name": "shortfat_aft_aggressive",
        "description": "Short and bulky body with aft peak and aggressive tail recovery.",
        "target_tags": ["short_fat", "peak_aft", "tail_aggressive"],
        "overrides": {
            "L": 1.80,
            "W_max": 0.65,
            "H_top_max": 1.12,
            "H_bot_max": 0.49,
            "X_max_pos": 0.48,
            "tail_rise": 0.19,
            "blend_start": 0.84,
            "blend_power": 2.9,
            "M_top": 3.9,
            "M_bot": 3.8,
            "N_top": 2.2,
            "N_bot": 2.2,
            "w0": 0.16,
            "w1": 0.26,
            "w2": 0.38,
            "w3": 0.20,
        },
    },
    {
        "case_name": "slender_aft_aggressive",
        "description": "Long body with aft peak and aggressive tail recovery.",
        "target_tags": ["slender", "peak_aft", "tail_aggressive"],
        "overrides": {
            "L": 3.0,
            "W_max": 0.49,
            "H_top_max": 0.85,
            "H_bot_max": 0.25,
            "X_max_pos": 0.49,
            "tail_rise": 0.18,
            "blend_start": 0.84,
            "blend_power": 2.9,
            "M_top": 3.9,
            "M_bot": 3.9,
            "w0": 0.17,
            "w1": 0.25,
            "w2": 0.39,
            "w3": 0.19,
        },
    },
    {
        "case_name": "shortfat_forward_aggressive",
        "description": "Short body with forward peak and intentionally aggressive tail recovery.",
        "target_tags": ["short_fat", "peak_forward", "tail_aggressive"],
        "overrides": {
            "L": 1.80,
            "W_max": 0.65,
            "H_top_max": 1.12,
            "H_bot_max": 0.49,
            "X_max_pos": 0.21,
            "tail_rise": 0.05,
            "blend_start": 0.65,
            "blend_power": 1.55,
            "w0": 0.35,
            "w1": 0.45,
            "w2": 0.20,
            "w3": 0.05,
        },
    },
    {
        "case_name": "tail_aggressive_midbody",
        "description": "Mid-body reference with clearly aggressive tail recovery.",
        "target_tags": ["tail_aggressive"],
        "overrides": {
            "L": 2.3,
            "W_max": 0.57,
            "H_top_max": 0.95,
            "H_bot_max": 0.33,
            "X_max_pos": 0.34,
            "tail_rise": 0.18,
            "blend_start": 0.84,
            "blend_power": 2.8,
            "M_top": 3.7,
            "M_bot": 3.5,
            "N_top": 2.2,
            "N_bot": 2.2,
            "w0": 0.16,
            "w1": 0.25,
            "w2": 0.39,
            "w3": 0.19,
        },
    },
    {
        "case_name": "slender_center_conservative",
        "description": "Long body with centered peak and conservative tail recovery.",
        "target_tags": ["tail_conservative"],
        "overrides": {
            "L": 2.95,
            "W_max": 0.49,
            "H_top_max": 0.85,
            "H_bot_max": 0.25,
            "X_max_pos": 0.33,
            "tail_rise": 0.05,
            "blend_start": 0.65,
            "blend_power": 1.55,
            "w0": 0.35,
            "w1": 0.45,
            "w2": 0.20,
            "w3": 0.05,
        },
    },
)


class AnalysisInputError(ValueError):
    """Raised when analysis input is incomplete or malformed."""


def _optimizer_dependencies():
    # Import lazily to avoid a circular import between the shared analysis
    # helpers and the legacy optimizer module.
    from optimization.hpa_asymmetric_optimizer import CST_Modeler, ConstraintChecker, HPA_Optimizer

    return CST_Modeler, ConstraintChecker, HPA_Optimizer


def _json_default(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _load_json_file(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_analysis_config(config_path: str | Path | None) -> dict:
    config = json.loads(json.dumps(DEFAULT_ANALYSIS_CONFIG))

    if not config_path:
        return config

    path = Path(config_path)
    if not path.exists():
        return config

    loaded = _load_json_file(path)
    if "backend" in loaded:
        config["backend"] = loaded["backend"]
    if "preset" in loaded:
        config["preset"] = loaded["preset"]
    if isinstance(loaded.get("report"), dict):
        config["report"].update(loaded["report"])
    return config


def get_required_gene_fields() -> list[str]:
    _, _, optimizer_cls = _optimizer_dependencies()
    return list(optimizer_cls.GENE_BOUNDS.keys())


def get_gene_field_bounds() -> dict[str, tuple[float, float]]:
    _, _, optimizer_cls = _optimizer_dependencies()
    return dict(optimizer_cls.GENE_BOUNDS)


def get_example_gene() -> dict:
    return dict(DEFAULT_EXAMPLE_GENE)


def get_representative_gene_cases() -> list[dict]:
    example = get_example_gene()
    cases: list[dict] = []

    for spec in REPRESENTATIVE_GENE_ARCHETYPES:
        gene = dict(example)
        gene.update(spec["overrides"])
        cases.append(
            {
                "CaseName": spec["case_name"],
                "Description": spec["description"],
                "TargetTags": list(spec["target_tags"]),
                "Gene": normalize_gene(gene),
            }
        )

    return cases


def format_required_gene_fields() -> str:
    lines = ["必填 gene 欄位與建議範圍:"]
    bounds = get_gene_field_bounds()
    for field in get_required_gene_fields():
        lower, upper = bounds[field]
        lines.append(f"- {field}: {lower:g} ~ {upper:g}")
    lines.extend(
        [
            "",
            "接受 legacy 欄位並自動轉換，例如：",
            "- H_top_max + H_bot_max -> H_max + camber_peak",
            "- X_max_pos -> X_peak",
            "- w0..w3 -> width_* controls",
            "- N1/N2_top/N2_bot -> height_* controls",
            "- tail_rise/blend_* -> centerline_* + tail_z",
        ]
    )
    return "\n".join(lines)


def normalize_gene(
    gene: dict,
    *,
    fallback_gene: dict | None = None,
    return_metadata: bool = False,
) -> dict | tuple[dict, dict]:
    _, _, optimizer_cls = _optimizer_dependencies()
    try:
        normalized, metadata = optimizer_cls.canonicalize_gene_dict(
            gene,
            fallback_gene=fallback_gene,
        )
    except ValueError as exc:
        raise AnalysisInputError(str(exc)) from exc

    if return_metadata:
        return normalized, metadata

    return normalized


def load_gene_file(
    gene_path: str | Path,
    *,
    fill_missing_from_example: bool = False,
    return_metadata: bool = False,
) -> dict | tuple[dict, dict]:
    path = Path(gene_path)
    if not path.exists():
        raise AnalysisInputError(f"找不到 gene 檔案: {path}")
    try:
        data = _load_json_file(path)
    except json.JSONDecodeError as exc:
        raise AnalysisInputError(f"gene JSON 格式錯誤: {exc.msg}") from exc
    fallback_gene = get_example_gene() if fill_missing_from_example else None
    return normalize_gene(data, fallback_gene=fallback_gene, return_metadata=return_metadata)


def load_flow_conditions(flow_source: str | Path | dict | None) -> dict:
    if flow_source is None:
        return dict(DEFAULT_FLOW_CONDITIONS)

    if isinstance(flow_source, (str, Path)):
        path = Path(flow_source)
        if not path.exists():
            raise AnalysisInputError(f"找不到流場設定檔: {path}")
        try:
            data = _load_json_file(path)
        except json.JSONDecodeError as exc:
            raise AnalysisInputError(f"flow JSON 格式錯誤: {exc.msg}") from exc
    elif isinstance(flow_source, dict):
        data = flow_source
    else:
        raise AnalysisInputError("flow_conditions 必須是 dict 或 JSON 檔案路徑")

    flow_block = data.get("flow_conditions", data)

    def read_value(name: str, default: float) -> float:
        raw = flow_block.get(name, default)
        if isinstance(raw, dict):
            raw = raw.get("value", default)
        return float(raw)

    normalized = dict(DEFAULT_FLOW_CONDITIONS)
    normalized["velocity"] = read_value("velocity", normalized["velocity"])
    normalized["rho"] = read_value("density", flow_block.get("rho", normalized["rho"]))
    normalized["mu"] = read_value("viscosity", flow_block.get("mu", normalized["mu"]))
    normalized["temperature"] = read_value("temperature", normalized["temperature"])
    normalized["altitude"] = read_value("altitude", normalized["altitude"])
    return normalized


def generate_recommendations(result: dict) -> list[str]:
    recommendations: list[str] = []
    x_peak = float(result["XPeakAreaFrac"])
    tail = result["TailAngles"]
    lam = float(result["LaminarFraction"])
    swet = float(result["Swet"])
    quality = result["Quality"]

    if x_peak > 0.40:
        recommendations.append("把最大截面往前移一些，峰值位置目前偏後，會讓尾段壓力回收更吃力。")
    elif x_peak < 0.24:
        recommendations.append("最大截面位置偏前，前段膨脹率可能過大，可微幅往後移讓外形更平順。")

    if float(tail["bottom_deg"]) > 18.0:
        recommendations.append("放緩下尾收縮，底部尾角偏大，是目前壓力阻力的主要來源。")
    elif float(tail["top_deg"]) > 40.0 or float(tail["side_deg"]) > 15.0:
        recommendations.append("尾部回收偏陡，建議拉長後段或降低尾部抬升，減少分離風險。")

    if swet > 6.2:
        recommendations.append("目前濕面積偏大，若總阻力差距接近，優先縮減中後段包絡尺寸。")

    if lam < 0.30:
        recommendations.append("層流保持比例偏低，優先改善峰值位置與尾段平滑度，讓外形更容易維持附著流。")

    if float(quality["area_monotonicity"]) < 0.98:
        recommendations.append("尾段截面回收有非單調跡象，建議檢查尾部混合區參數，避免局部再膨脹。")

    if float(quality.get("pressure_risk", 0.0)) > 0.65:
        recommendations.append("目前尾段分離風險偏高，若要拿去做高保真驗證，建議先把上/下尾角再放緩。")

    if not recommendations:
        recommendations.append("目前沒有明顯拖累特徵，可先微調最大截面位置與尾段平滑度做小幅優化。")

    return recommendations


def build_representative_case_metadata(result: dict) -> dict:
    tail = result["TailAngles"]
    quality = result["Quality"]
    fineness = float(result.get("FinenessRatio", 0.0))
    x_peak = float(result["XPeakAreaFrac"])
    pressure_risk = float(quality.get("pressure_risk", 0.0))
    top_tail = float(tail["top_deg"])
    bottom_tail = float(tail["bottom_deg"])
    side_tail = float(tail["side_deg"])

    tags: list[str] = []
    if fineness >= REPRESENTATIVE_THRESHOLDS["fineness_slender_min"]:
        tags.append("slender")
    elif fineness <= REPRESENTATIVE_THRESHOLDS["fineness_short_fat_max"]:
        tags.append("short_fat")

    if x_peak <= REPRESENTATIVE_THRESHOLDS["x_peak_forward_max"]:
        tags.append("peak_forward")
    elif x_peak >= REPRESENTATIVE_THRESHOLDS["x_peak_aft_min"]:
        tags.append("peak_aft")

    aggressive_tail = (
        pressure_risk >= REPRESENTATIVE_THRESHOLDS["pressure_risk_aggressive_min"]
        or bottom_tail >= REPRESENTATIVE_THRESHOLDS["tail_bottom_aggressive_min"]
        or top_tail >= REPRESENTATIVE_THRESHOLDS["tail_top_aggressive_min"]
        or side_tail >= REPRESENTATIVE_THRESHOLDS["tail_side_aggressive_min"]
    )
    conservative_tail = (
        pressure_risk <= REPRESENTATIVE_THRESHOLDS["pressure_risk_conservative_max"]
        and bottom_tail <= REPRESENTATIVE_THRESHOLDS["tail_bottom_conservative_max"]
        and top_tail <= REPRESENTATIVE_THRESHOLDS["tail_top_conservative_max"]
        and side_tail <= REPRESENTATIVE_THRESHOLDS["tail_side_conservative_max"]
    )
    if aggressive_tail:
        tags.append("tail_aggressive")
    elif conservative_tail:
        tags.append("tail_conservative")

    if not tags:
        tags.append("mid_pack")

    return {
        "RepresentativeTags": tags,
        "GeometryTraits": {
            "FinenessRatio": fineness,
            "XPeakAreaFrac": x_peak,
            "PressureRisk": pressure_risk,
            "TailTopDeg": top_tail,
            "TailBottomDeg": bottom_tail,
            "TailSideDeg": side_tail,
            "AreaMonotonicity": float(quality.get("area_monotonicity", 0.0)),
            "RecoveryCurvature": float(quality.get("recovery_curvature", 0.0)),
        },
    }


def build_constraint_report(preset: str, gene: dict, curves: dict) -> dict:
    if preset == "none":
        return {}
    if preset != "hpa":
        raise AnalysisInputError(f"不支援的 preset: {preset}")

    _, constraint_checker, _ = _optimizer_dependencies()
    passed, checks = constraint_checker.check_all_constraints(gene, curves)
    return {
        "enabled": True,
        "all_pass": bool(passed),
        "checks": checks,
    }


def score_analysis_result(result: dict, area_penalty: float) -> dict:
    swet = result.get("Swet")
    area_penalty_value = float(area_penalty) * float(swet) if swet is not None else 0.0
    score = float(result["Drag"]) + area_penalty_value

    scored = dict(result)
    scored["AreaPenalty"] = area_penalty_value
    scored["Score"] = score
    return scored


def analyze_gene(
    gene: dict,
    *,
    flow_conditions: dict | None = None,
    preset: str = "none",
    backend: str = "fast_proxy",
    include_geometry: bool = False,
) -> dict:
    if backend != "fast_proxy":
        raise AnalysisInputError(f"目前只支援 backend=fast_proxy，收到 {backend}")

    normalized_gene = normalize_gene(gene)
    normalized_flow = load_flow_conditions(flow_conditions)

    cst_modeler, _, _ = _optimizer_dependencies()
    curves = cst_modeler.generate_asymmetric_fairing(normalized_gene)
    proxy = FairingDragProxy(
        velocity=normalized_flow["velocity"],
        rho=normalized_flow["rho"],
        mu=normalized_flow["mu"],
        s_ref=1.0,
    )
    proxy_result = proxy.evaluate_curves(curves)

    result = {
        "Drag": float(proxy_result["Drag"]),
        "Cd": float(proxy_result["Cd"]),
        "Cd_viscous": float(proxy_result["Cd_viscous"]),
        "Cd_pressure": float(proxy_result["Cd_pressure"]),
        "Swet": float(proxy_result["Swet"]),
        "LaminarFraction": float(proxy_result["LaminarFraction"]),
        "FinenessRatio": float(proxy_result["FinenessRatio"]),
        "XPeakAreaFrac": float(proxy_result["XPeakAreaFrac"]),
        "TailAngles": proxy_result["TailAngles"],
        "Quality": proxy_result["Quality"],
        "RepresentativeTags": [],
        "GeometryTraits": {},
        "Recommendations": [],
        "ConstraintReport": {},
        "PresetUsed": preset,
        "Backend": backend,
        "FlowConditions": normalized_flow,
        "Model": proxy_result["Model"],
    }

    result["Recommendations"] = generate_recommendations(result)
    result.update(build_representative_case_metadata(result))
    result["ConstraintReport"] = build_constraint_report(preset, normalized_gene, curves)

    if include_geometry:
        result["Curves"] = curves

    return result


def _plot_side_profile(curves: dict, output_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        _write_placeholder_png(output_path)
        return

    x_coords = np.asarray(curves["x"], dtype=float)
    z_upper = np.asarray(curves["z_upper"], dtype=float)
    z_lower = np.asarray(curves["z_lower"], dtype=float)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.fill_between(x_coords, z_lower, z_upper, color="#cfe8ff", alpha=0.8)
    ax.plot(x_coords, z_upper, color="#175676", linewidth=2.0, label="Upper surface")
    ax.plot(x_coords, z_lower, color="#175676", linewidth=2.0, label="Lower surface")
    ax.axhline(0.0, color="#6c757d", linewidth=0.8, alpha=0.5)
    ax.set_title("Fairing Side Profile")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("z (m)")
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _plot_drag_breakdown(result: dict, output_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        _write_placeholder_png(output_path)
        return

    labels = ["Viscous", "Pressure", "Total"]
    values = [
        float(result["Cd_viscous"]),
        float(result["Cd_pressure"]),
        float(result["Cd"]),
    ]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, values, color=["#4c78a8", "#f58518", "#54a24b"])
    ax.set_title("Drag Breakdown")
    ax.set_ylabel("Cd")
    ax.grid(True, axis="y", alpha=0.25)

    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            value,
            f"{value:.4f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _write_placeholder_png(output_path: Path) -> None:
    # 1x1 transparent PNG. This keeps the report bundle complete even when
    # matplotlib is not installed in the current Python environment.
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9VE3D9sAAAAASUVORK5CYII="
    )
    with open(output_path, "wb") as handle:
        handle.write(png_bytes)


def _build_summary_markdown(summary: dict) -> str:
    analysis = summary["Analysis"]
    report_files = summary["ReportFiles"]
    gene_metadata = summary.get("GeneMetadata", {})
    lines = [
        "# Low-Speed Fairing Analysis Summary",
        "",
        f"- GeneratedAt: {summary['GeneratedAt']}",
        f"- Backend: {analysis['Backend']}",
        f"- Preset: {analysis['PresetUsed']}",
    ]

    filled_fields = gene_metadata.get("filled_fields", [])
    if filled_fields:
        lines.extend(["", "## Gene Fill", "", f"- FilledFields: {', '.join(filled_fields)}"])

    lines.extend(
        [
            "",
            "## Aerodynamics",
            "",
            f"- Drag: {analysis['Drag']:.4f} N",
            f"- Cd: {analysis['Cd']:.6f}",
            f"- Cd_viscous: {analysis['Cd_viscous']:.6f}",
            f"- Cd_pressure: {analysis['Cd_pressure']:.6f}",
            f"- Swet: {analysis['Swet']:.3f} m^2",
            f"- LaminarFraction: {analysis['LaminarFraction']:.3f}",
            f"- FinenessRatio: {analysis['FinenessRatio']:.3f}",
            f"- XPeakAreaFrac: {analysis['XPeakAreaFrac']:.3f}",
            f"- PressureRisk: {analysis['Quality'].get('pressure_risk', 0.0):.3f}",
            f"- RepresentativeTags: {', '.join(analysis.get('RepresentativeTags', [])) or 'none'}",
            "",
            "## Tail Angles",
            "",
            f"- Top: {analysis['TailAngles']['top_deg']:.2f} deg",
            f"- Bottom: {analysis['TailAngles']['bottom_deg']:.2f} deg",
            f"- Side: {analysis['TailAngles']['side_deg']:.2f} deg",
            "",
            "## Recommendations",
            "",
        ]
    )

    for recommendation in analysis["Recommendations"]:
        lines.append(f"- {recommendation}")

    constraint_report = analysis["ConstraintReport"]
    if constraint_report:
        lines.extend(["", "## Constraint Report", ""])
        lines.append(f"- all_pass: {constraint_report['all_pass']}")
        for name, info in constraint_report["checks"].items():
            value = float(info["value"]) if isinstance(info.get("value"), (int, float, np.floating, np.integer)) else info.get("value")
            line = f"- {name}: pass={info['pass']}, value={value:.4f}" if isinstance(value, float) else f"- {name}: pass={info['pass']}, value={value}"
            if "required" in info:
                required = float(info["required"])
                line += f", required={required:.4f}"
            lines.append(line)

    lines.extend(
        [
            "",
            "## Report Files",
            "",
            f"- summary.json: {report_files['summary_json']}",
            f"- side_profile.png: {report_files['side_profile']}",
            f"- drag_breakdown.png: {report_files['drag_breakdown']}",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_batch_summary_markdown(summary: dict) -> str:
    lines = [
        "# Low-Speed Fairing Batch Analysis",
        "",
        f"- GeneratedAt: {summary['GeneratedAt']}",
        f"- Backend: {summary['Backend']}",
        f"- Preset: {summary['Preset']}",
        f"- TotalCases: {summary['TotalCases']}",
        f"- SuccessfulCases: {summary['SuccessfulCases']}",
        f"- FailedCases: {summary['FailedCases']}",
        "",
        "## Ranked Cases",
        "",
    ]

    ranked_cases = summary["RankedCases"]
    if not ranked_cases:
        lines.append("- No successful cases.")
    else:
        for entry in ranked_cases:
            constraint_state = entry.get("ConstraintState")
            if constraint_state is None:
                constraint_text = "n/a"
            else:
                constraint_text = "PASS" if constraint_state else "FAIL"
            lines.extend(
                [
                    f"### {entry['Rank']}. {entry['CaseName']}",
                    "",
                    f"- GeneFile: {entry['GeneFile']}",
                    f"- Drag: {entry['Drag']:.4f} N",
                    f"- Cd: {entry['Cd']:.6f}",
                    f"- Swet: {entry['Swet']:.3f} m^2",
                    f"- LaminarFraction: {entry['LaminarFraction']:.3f}",
                    f"- FinenessRatio: {entry['GeometryTraits']['FinenessRatio']:.3f}",
                    f"- XPeakAreaFrac: {entry['GeometryTraits']['XPeakAreaFrac']:.3f}",
                    f"- PressureRisk: {entry['GeometryTraits']['PressureRisk']:.3f}",
                    f"- RepresentativeTags: {', '.join(entry['RepresentativeTags']) if entry.get('RepresentativeTags') else 'none'}",
                    f"- ConstraintState: {constraint_text}",
                    f"- FilledFields: {', '.join(entry['FilledFields']) if entry.get('FilledFields') else 'none'}",
                    f"- ReportDir: {entry['ReportDir']}",
                    "",
                ]
            )

    failed_cases = summary["FailedCasesDetail"]
    lines.extend(["## Failed Cases", ""])
    if not failed_cases:
        lines.append("- None")
    else:
        for entry in failed_cases:
            lines.append(f"- {entry['CaseName']} ({entry['GeneFile']}): {entry['Error']}")

    return "\n".join(lines) + "\n"


def write_analysis_report_bundle(
    output_dir: str | Path,
    gene: dict,
    analysis_result: dict,
    report_config: dict | None = None,
    gene_metadata: dict | None = None,
) -> dict:
    config = dict(DEFAULT_ANALYSIS_CONFIG["report"])
    if report_config:
        config.update(report_config)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    summary_json_path = output_path / "summary.json"
    summary_md_path = output_path / "summary.md"
    side_profile_path = output_path / "side_profile.png"
    drag_breakdown_path = output_path / "drag_breakdown.png"

    report_files = {
        "summary_json": str(summary_json_path),
        "summary_md": str(summary_md_path),
        "side_profile": str(side_profile_path),
        "drag_breakdown": str(drag_breakdown_path),
    }

    serializable_analysis = {k: v for k, v in analysis_result.items() if k != "Curves"}
    summary = {
        "GeneratedAt": datetime.now().isoformat(),
        "Gene": normalize_gene(gene),
        "GeneMetadata": gene_metadata or {"filled_fields": []},
        "Analysis": serializable_analysis,
        "ReportFiles": report_files,
    }

    if config.get("write_summary_json", True):
        with open(summary_json_path, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, ensure_ascii=False, default=_json_default)

    if config.get("write_summary_markdown", True):
        with open(summary_md_path, "w", encoding="utf-8") as handle:
            handle.write(_build_summary_markdown(summary))

    curves = analysis_result.get("Curves")
    if curves is None:
        cst_modeler, _, _ = _optimizer_dependencies()
        curves = cst_modeler.generate_asymmetric_fairing(normalize_gene(gene))

    if config.get("plot_side_profile", True):
        if config.get("use_placeholder_plots", False):
            _write_placeholder_png(side_profile_path)
        else:
            _plot_side_profile(curves, side_profile_path)

    if config.get("plot_drag_breakdown", True):
        if config.get("use_placeholder_plots", False):
            _write_placeholder_png(drag_breakdown_path)
        else:
            _plot_drag_breakdown(analysis_result, drag_breakdown_path)

    return report_files


def write_batch_analysis_summary(
    output_dir: str | Path,
    entries: list[dict],
    *,
    preset: str,
    backend: str,
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    success_entries = [dict(entry) for entry in entries if entry.get("Status") == "ok"]
    success_entries.sort(key=lambda entry: (float(entry["Drag"]), float(entry["Cd"]), entry["CaseName"]))
    for rank, entry in enumerate(success_entries, start=1):
        entry["Rank"] = rank

    failed_entries = [dict(entry) for entry in entries if entry.get("Status") != "ok"]

    summary_json_path = output_path / "batch_summary.json"
    summary_md_path = output_path / "batch_summary.md"
    report_files = {
        "summary_json": str(summary_json_path),
        "summary_md": str(summary_md_path),
    }

    summary = {
        "GeneratedAt": datetime.now().isoformat(),
        "Backend": backend,
        "Preset": preset,
        "TotalCases": len(entries),
        "SuccessfulCases": len(success_entries),
        "FailedCases": len(failed_entries),
        "RankedCases": success_entries,
        "FailedCasesDetail": failed_entries,
        "ReportFiles": report_files,
    }

    with open(summary_json_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False, default=_json_default)

    with open(summary_md_path, "w", encoding="utf-8") as handle:
        handle.write(_build_batch_summary_markdown(summary))

    return report_files


def prepare_analysis_output_dir(output_arg: str | Path | None, output_root: str | Path) -> Path:
    if output_arg:
        return Path(output_arg)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(output_root) / f"fairing_analysis_{timestamp}"
