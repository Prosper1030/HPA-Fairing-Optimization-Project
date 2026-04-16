"""
Shared design evaluation flow for proxy and OpenVSP-backed fairing scoring.

This module keeps the end-to-end "evaluate one candidate" logic in one place
so CLI workers and the optimizer do not each maintain their own copy.
"""

from __future__ import annotations

import traceback
from typing import Callable

from analysis.drag_analysis import DragAnalyzer
from analysis.fairing_analysis import analyze_gene, load_flow_conditions, score_analysis_result


INVALID_SCORE = 1e6


def _optimizer_dependencies():
    # Import lazily to avoid introducing a circular import back into the
    # legacy optimizer module.
    from optimization.hpa_asymmetric_optimizer import CST_Modeler, ConstraintChecker, VSPModelGenerator

    return CST_Modeler, ConstraintChecker, VSPModelGenerator


def _finalize_result(
    *,
    score: float,
    analysis_mode: str,
    return_details: bool,
    drag: float | None = None,
    swet: float | None = None,
    cd: float | None = None,
    cda: float | None = None,
    valid: bool = True,
    extra: dict | None = None,
) -> float | dict:
    if not return_details:
        return float(score)

    payload = {
        "Score": float(score),
        "Drag": None if drag is None else float(drag),
        "Swet": None if swet is None else float(swet),
        "Cd": None if cd is None else float(cd),
        "CdA": None if cda is None else float(cda),
        "Valid": bool(valid),
        "AnalysisMode": analysis_mode,
    }
    if extra:
        payload.update(extra)
    return payload


def evaluate_design_gene(
    gene: dict,
    name: str,
    *,
    area_penalty: float = 0.1,
    analysis_mode: str = "openvsp",
    flow_conditions: dict | None = None,
    return_details: bool = False,
    logger: Callable[[str], None] | None = None,
    drag_analyzer: DragAnalyzer | None = None,
    emit_traceback: bool = False,
) -> float | dict:
    normalized_flow = load_flow_conditions(flow_conditions)
    velocity = float(normalized_flow["velocity"])
    rho = float(normalized_flow["rho"])
    mu = float(normalized_flow["mu"])

    def emit(message: str) -> None:
        if logger is not None:
            logger(message)

    def emit_exception(prefix: str, exc: Exception) -> None:
        emit(f"{prefix}: {exc}")
        if emit_traceback:
            emit(traceback.format_exc())

    try:
        cst_modeler, constraint_checker, vsp_model_generator = _optimizer_dependencies()
        curves = cst_modeler.generate_asymmetric_fairing(gene)
        passed, results = constraint_checker.check_all_constraints(gene, curves)
        if not passed:
            return _finalize_result(
                score=INVALID_SCORE,
                analysis_mode=analysis_mode,
                return_details=return_details,
                valid=False,
                extra={"ConstraintResults": results},
            )

        if analysis_mode == "proxy":
            result = analyze_gene(
                gene,
                flow_conditions=normalized_flow,
                preset="hpa",
                backend="fast_proxy",
            )
            scored = score_analysis_result(result, area_penalty)
            drag = scored["Drag"]
            swet = scored["Swet"]
            cd = scored["Cd"]
            score = scored["Score"]
            emit(
                f"{name}: [proxy] Cd={cd:.6f}, Swet={swet:.3f}m², "
                f"Drag={drag:.4f}N, Lam={scored['LaminarFraction']:.2f}, "
                f"Score={score:.4f}N"
            )
            return _finalize_result(
                score=score,
                analysis_mode=analysis_mode,
                return_details=return_details,
                drag=drag,
                swet=swet,
                cd=cd,
                cda=scored.get("CdA", cd),
                extra=scored,
            )

        if analysis_mode != "openvsp":
            raise ValueError(f"不支援的 analysis_mode: {analysis_mode}")

        try:
            vsp_model_generator.create_fuselage(curves, name, filepath=None)
        except Exception as exc:
            emit_exception(f"VSP 生成失敗 ({name})", exc)
            return _finalize_result(
                score=INVALID_SCORE,
                analysis_mode=analysis_mode,
                return_details=return_details,
                valid=False,
                extra={"Error": str(exc)},
            )

        analyzer = drag_analyzer or DragAnalyzer()
        try:
            result = analyzer.run_analysis_current_model(
                name,
                velocity=velocity,
                rho=rho,
                mu=mu,
            )
            if not result:
                emit(f"阻力計算失敗 ({name}): 無法取得 ParasiteDrag 結果")
                return _finalize_result(
                    score=INVALID_SCORE,
                    analysis_mode=analysis_mode,
                    return_details=return_details,
                    valid=False,
                    extra={"Error": "analysis_failed"},
                )

            drag = result["Drag"]
            swet = result.get("Swet")
            cd = result["Cd"]
            cda = result.get("CdA", cd)

            if swet is not None:
                penalty_value = area_penalty * swet
                score = drag + penalty_value
                emit(
                    f"{name}: Cd={cd:.6f}, Swet={swet:.3f}m², "
                    f"Drag={drag:.4f}N, Penalty={penalty_value:.4f}N, "
                    f"Score={score:.4f}N"
                )
                enriched = dict(result)
                enriched["AreaPenalty"] = penalty_value
                enriched["Score"] = score
                return _finalize_result(
                    score=score,
                    analysis_mode=analysis_mode,
                    return_details=return_details,
                    drag=drag,
                    swet=swet,
                    cd=cd,
                    cda=cda,
                    extra=enriched,
                )

            emit(f"{name}: Cd={cd:.6f}, Drag={drag:.4f}N (無Swet)")
            return _finalize_result(
                score=drag,
                analysis_mode=analysis_mode,
                return_details=return_details,
                drag=drag,
                cd=cd,
                cda=cda,
                extra=result,
            )
        except Exception as exc:
            emit_exception(f"阻力計算失敗 ({name})", exc)
            return _finalize_result(
                score=INVALID_SCORE,
                analysis_mode=analysis_mode,
                return_details=return_details,
                valid=False,
                extra={"Error": str(exc)},
            )
    except Exception as exc:
        emit_exception("Worker錯誤", exc)
        return _finalize_result(
            score=INVALID_SCORE,
            analysis_mode=analysis_mode,
            return_details=return_details,
            valid=False,
            extra={"Error": str(exc)},
        )
