"""
Run a 3D Gmsh -> SU2 mesh sensitivity study for one or more shortlisted designs.

This command prepares multiple benchmark meshes per case, runs SU2 for each
profile, and writes a study summary that compares convergence and mesh
sensitivity across a representative case set in one place.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys

from _bootstrap import ensure_src_path


project_root = os.fspath(ensure_src_path())

from analysis import (
    AnalysisInputError,
    load_analysis_config,
    prepare_shortlist_validation_package,
    run_shortlist_su2_cases,
)


DEFAULT_STUDY_PROFILES = {
    "coarse": {
        "mesh_options": {
            "section_points": 16,
            "body_section_count": 14,
            "near_body_size_factor": 0.052,
            "farfield_size_factor": 0.25,
            "wake_size_factor": 0.082,
            "wake_half_width_factor": 0.65,
            "surface_mesh_size_factor": 0.024,
            "use_boundary_layer_extrusion": True,
            "boundary_layer_num_layers": 5,
            "boundary_layer_total_thickness_factor": 0.008,
        },
        "su2_settings": {
            "iterations": 500,
            "inner_iterations": 500,
        },
    },
    "baseline": {
        "mesh_options": {
            "use_boundary_layer_extrusion": True,
        },
        "su2_settings": {},
    },
    "fine": {
        "mesh_options": {
            "section_points": 24,
            "body_section_count": 22,
            "near_body_size_factor": 0.030,
            "farfield_size_factor": 0.18,
            "wake_size_factor": 0.052,
            "wake_half_width_factor": 0.85,
            "surface_mesh_size_factor": 0.016,
            "use_boundary_layer_extrusion": True,
            "boundary_layer_num_layers": 7,
            "boundary_layer_first_height_factor": 1.5e-4,
            "boundary_layer_total_thickness_factor": 0.012,
        },
        "su2_settings": {
            "iterations": 750,
            "inner_iterations": 750,
            "conv_cauchy_elems": 35,
            "conv_cauchy_eps": 2e-6,
        },
    },
    "finer": {
        "mesh_options": {
            "section_points": 28,
            "body_section_count": 28,
            "near_body_size_factor": 0.024,
            "farfield_size_factor": 0.16,
            "wake_size_factor": 0.042,
            "wake_half_width_factor": 0.95,
            "surface_mesh_size_factor": 0.013,
            "use_boundary_layer_extrusion": True,
            "boundary_layer_num_layers": 9,
            "boundary_layer_first_height_factor": 1.0e-4,
            "boundary_layer_total_thickness_factor": 0.014,
        },
        "su2_settings": {
            "iterations": 900,
            "inner_iterations": 900,
            "conv_cauchy_elems": 40,
            "conv_cauchy_eps": 1e-6,
        },
    },
}

REFERENCE_READY_POLICY = {
    "required_profiles": ("fine", "finer"),
    "cd_swing_percent_last10_max": 0.2,
    "mesh_delta_percent_max": 5.0,
}


def _load_json(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_gene_candidate(gene_path: str | Path) -> dict:
    path = Path(gene_path)
    if not path.exists():
        raise AnalysisInputError(f"找不到 gene 檔案: {path}")
    try:
        payload = _load_json(path)
    except json.JSONDecodeError as exc:
        raise AnalysisInputError(f"gene JSON 格式錯誤: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise AnalysisInputError(f"gene 檔案必須是 JSON 物件: {path}")
    return {
        "name": path.stem,
        "GeneFile": str(path),
        "gene": payload,
    }


def _load_best_gene_candidate(best_gene_path: str | Path) -> dict:
    path = Path(best_gene_path)
    if not path.exists():
        raise AnalysisInputError(f"找不到 best_gene 檔案: {path}")
    try:
        payload = _load_json(path)
    except json.JSONDecodeError as exc:
        raise AnalysisInputError(f"best_gene JSON 格式錯誤: {exc.msg}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("gene"), dict):
        raise AnalysisInputError(f"best_gene 檔案格式錯誤，缺少 gene 區塊: {path}")
    return {
        "name": path.stem,
        "GeneFile": str(path),
        "gene": payload["gene"],
        "Notes": {
            "fitness": payload.get("fitness"),
            "generation": payload.get("generation"),
            "timestamp": payload.get("timestamp"),
        },
    }


def _load_gene_dir_candidates(gene_dir: str | Path) -> list[dict]:
    path = Path(gene_dir)
    if not path.exists() or not path.is_dir():
        raise AnalysisInputError(f"找不到 gene 資料夾: {path}")

    gene_files = sorted(entry for entry in path.iterdir() if entry.is_file() and entry.suffix.lower() == ".json")
    if not gene_files:
        raise AnalysisInputError(f"gene 資料夾內沒有 JSON 檔案: {path}")

    return [_load_gene_candidate(gene_file) for gene_file in gene_files]


def _load_batch_summary_candidates(batch_summary_path: str | Path, top: int | None) -> list[dict]:
    path = Path(batch_summary_path)
    if not path.exists():
        raise AnalysisInputError(f"找不到 batch_summary 檔案: {path}")

    try:
        payload = _load_json(path)
    except json.JSONDecodeError as exc:
        raise AnalysisInputError(f"batch_summary JSON 格式錯誤: {exc.msg}") from exc

    ranked_cases = payload.get("RankedCases")
    if not isinstance(ranked_cases, list):
        raise AnalysisInputError(f"batch_summary 缺少 RankedCases 陣列: {path}")

    if top is not None:
        ranked_cases = ranked_cases[:top]
    if not ranked_cases:
        raise AnalysisInputError("batch_summary 沒有可用的成功案例")

    candidates: list[dict] = []
    for entry in ranked_cases:
        if not isinstance(entry, dict):
            raise AnalysisInputError("RankedCases 內每筆資料都必須是 JSON 物件")
        gene_file = entry.get("GeneFile")
        if not gene_file:
            raise AnalysisInputError("RankedCases 缺少 GeneFile 欄位")
        candidate = _load_gene_candidate(gene_file)
        candidate["name"] = entry.get("CaseName") or candidate["name"]
        candidate["Notes"] = {
            "rank": entry.get("Rank"),
            "drag": entry.get("Drag"),
            "cd": entry.get("Cd"),
            "source_batch_summary": str(path),
        }
        candidates.append(candidate)
    return candidates


def _collect_candidates(args) -> list[dict]:
    candidates: list[dict] = []

    for gene_path in args.gene:
        candidates.append(_load_gene_candidate(gene_path))
    for gene_dir in args.gene_dir:
        candidates.extend(_load_gene_dir_candidates(gene_dir))
    for best_gene_path in args.best_gene:
        candidates.append(_load_best_gene_candidate(best_gene_path))
    for batch_summary_path in args.batch_summary:
        candidates.extend(_load_batch_summary_candidates(batch_summary_path, args.top))

    if not candidates:
        raise AnalysisInputError(
            "至少要提供一個來源：--gene、--gene-dir、--best-gene 或 --batch-summary"
        )
    return candidates


def _resolve_profiles(selected_profiles: list[str]) -> list[tuple[str, dict]]:
    profile_names = selected_profiles or ["coarse", "baseline", "fine", "finer"]
    return [(name, DEFAULT_STUDY_PROFILES[name]) for name in profile_names]


def _delta_percent(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or abs(previous) < 1e-12:
        return None
    return (current / previous - 1.0) * 100.0


def _summarize_reference_readiness(profile_results: list[dict]) -> dict:
    profile_map = {entry["Profile"]: entry for entry in profile_results}
    fine_name, finer_name = REFERENCE_READY_POLICY["required_profiles"]
    fine = profile_map.get(fine_name)
    finer = profile_map.get(finer_name)

    checks = []

    def add_check(name: str, passed: bool, *, detail=None) -> None:
        checks.append({"name": name, "pass": bool(passed), "detail": detail})

    has_required_profiles = fine is not None and finer is not None
    add_check(
        "required_profiles_present",
        has_required_profiles,
        detail=list(REFERENCE_READY_POLICY["required_profiles"]),
    )

    no_profile_errors = all(entry.get("Status") == "completed" for entry in profile_results)
    add_check("all_profiles_completed", no_profile_errors)

    for profile_name, entry in ((fine_name, fine), (finer_name, finer)):
        prefix = f"{profile_name}_"
        if entry is None:
            add_check(prefix + "converged", False, detail="missing_profile")
            add_check(prefix + "cauchy_within_target", False, detail="missing_profile")
            add_check(prefix + "cd_swing_within_target", False, detail="missing_profile")
            continue

        converged = entry.get("Converged") is True
        add_check(prefix + "converged", converged, detail=entry.get("ConvergenceSource"))

        cauchy = entry.get("LastCauchyCd")
        criterion = entry.get("ConvergenceCriterion")
        cauchy_ok = cauchy is not None and criterion is not None and float(cauchy) <= float(criterion)
        add_check(
            prefix + "cauchy_within_target",
            cauchy_ok,
            detail={"LastCauchyCd": cauchy, "ConvergenceCriterion": criterion},
        )

        swing = entry.get("CdSwingPercentLast10")
        swing_limit = float(REFERENCE_READY_POLICY["cd_swing_percent_last10_max"])
        swing_ok = swing is not None and float(swing) <= swing_limit
        add_check(
            prefix + "cd_swing_within_target",
            swing_ok,
            detail={"CdSwingPercentLast10": swing, "Threshold": swing_limit},
        )

    fine_to_finer_delta = None
    mesh_delta_limit = float(REFERENCE_READY_POLICY["mesh_delta_percent_max"])
    if fine is not None and finer is not None:
        fine_to_finer_delta = _delta_percent(finer.get("Cd"), fine.get("Cd"))
    add_check(
        "fine_to_finer_cd_delta_within_target",
        fine_to_finer_delta is not None and abs(float(fine_to_finer_delta)) < mesh_delta_limit,
        detail={"DeltaPercent": fine_to_finer_delta, "Threshold": mesh_delta_limit},
    )

    reference_ready = all(check["pass"] for check in checks)
    return {
        "ReferenceReady": reference_ready,
        "ReferenceStatus": "ReferenceReady" if reference_ready else "NotReferenceReady",
        "RequiredProfiles": list(REFERENCE_READY_POLICY["required_profiles"]),
        "MeshDeltaPercentMax": mesh_delta_limit,
        "CdSwingPercentLast10Max": float(REFERENCE_READY_POLICY["cd_swing_percent_last10_max"]),
        "FineToFinerDeltaCdPercent": fine_to_finer_delta,
        "Checks": checks,
    }


def _build_case_summary(
    *,
    candidate: dict,
    preset: str,
    flow_path: str | None,
    solver_command: str,
    profile_results: list[dict],
) -> dict:
    proxy_baseline = None
    for entry in profile_results:
        proxy_baseline = entry.get("ProxyBaseline")
        if proxy_baseline:
            break

    recommended_profile = None
    if len(profile_results) >= 2:
        fine = profile_results[-1]
        previous = profile_results[-2]
        delta_cd = fine.get("DeltaCdVsPreviousPercent")
        if (
            fine.get("Converged")
            and previous.get("Converged")
            and delta_cd is not None
            and abs(delta_cd) <= 2.0
        ):
            recommended_profile = fine["Profile"]

    summary = {
        "GeneratedAt": datetime.now().isoformat(),
        "Preset": preset,
        "FlowConfig": flow_path,
        "SolverCommand": solver_command,
        "SourceGene": candidate.get("GeneFile"),
        "SourceCaseName": candidate.get("name"),
        "Profiles": profile_results,
        "ProxyBaseline": proxy_baseline,
        "RecommendedReferenceProfile": recommended_profile,
    }
    summary["ReferenceAssessment"] = _summarize_reference_readiness(profile_results)
    return summary


def _build_study_summary(
    *,
    cases: list[dict],
    preset: str,
    flow_path: str | None,
    solver_command: str,
    selected_profiles: list[str],
) -> dict:
    ready_cases = [case["SourceCaseName"] for case in cases if case["ReferenceAssessment"]["ReferenceReady"]]
    not_ready_cases = [case["SourceCaseName"] for case in cases if not case["ReferenceAssessment"]["ReferenceReady"]]
    summary = {
        "GeneratedAt": datetime.now().isoformat(),
        "Preset": preset,
        "FlowConfig": flow_path,
        "SolverCommand": solver_command,
        "CaseCount": len(cases),
        "RequestedProfiles": selected_profiles,
        "RequiredProfilesForReferenceReady": list(REFERENCE_READY_POLICY["required_profiles"]),
        "Cases": cases,
        "ReferenceReadyCaseCount": len(ready_cases),
        "NotReferenceReadyCaseCount": len(not_ready_cases),
        "ReferenceReadyCases": ready_cases,
        "NotReferenceReadyCases": not_ready_cases,
    }
    if len(cases) == 1:
        summary.update(cases[0])
    return summary


def _build_case_markdown(summary: dict) -> list[str]:
    lines = [
        f"## Case: {summary.get('SourceCaseName') or 'candidate'}",
        "",
        f"- SourceGene: {summary.get('SourceGene') or 'inline'}",
        f"- ReferenceStatus: {summary['ReferenceAssessment']['ReferenceStatus']}",
    ]

    proxy = summary.get("ProxyBaseline")
    if proxy:
        lines.extend(
            [
                f"- Proxy Cd: {proxy.get('Cd', 'n/a'):.6f}" if proxy.get("Cd") is not None else "- Proxy Cd: n/a",
                f"- Proxy Drag: {proxy.get('Drag', 'n/a'):.6f} N" if proxy.get("Drag") is not None else "- Proxy Drag: n/a",
            ]
        )
    if summary.get("RecommendedReferenceProfile"):
        lines.append(f"- RecommendedReferenceProfile: {summary['RecommendedReferenceProfile']}")
    fine_to_finer_delta = summary["ReferenceAssessment"].get("FineToFinerDeltaCdPercent")
    if fine_to_finer_delta is not None:
        lines.append(f"- FineToFinerDeltaCdPercent: {fine_to_finer_delta:+.3f}%")

    lines.extend(
        [
            "",
            "| Check | Pass | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in summary["ReferenceAssessment"]["Checks"]:
        detail = check.get("detail")
        if isinstance(detail, dict):
            detail_text = json.dumps(detail, ensure_ascii=False, sort_keys=True)
        elif isinstance(detail, list):
            detail_text = ", ".join(str(item) for item in detail)
        else:
            detail_text = str(detail) if detail is not None else ""
        lines.append(f"| {check['name']} | {'yes' if check['pass'] else 'no'} | {detail_text} |")

    lines.extend(
        [
            "",
            "| Profile | Converged | Source | Nodes | Tetra | Cd | Drag (N) | ΔCd vs proxy | ΔCd vs prev | Last Cauchy CD | Cd Swing(Last10) |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for entry in summary["Profiles"]:
        converged = "n/a" if entry.get("Converged") is None else ("yes" if entry["Converged"] else "no")
        source_text = entry.get("ConvergenceSource") or "n/a"
        delta_cd = entry.get("DeltaCdVsPreviousPercent")
        delta_proxy = entry.get("DeltaCdVsProxyPercent")
        delta_text = "n/a" if delta_cd is None else f"{delta_cd:+.3f}%"
        delta_proxy_text = "n/a" if delta_proxy is None else f"{delta_proxy:+.3f}%"
        cauchy_text = "n/a" if entry.get("LastCauchyCd") is None else f"{entry['LastCauchyCd']:.3e}"
        swing_text = "n/a" if entry.get("CdSwingPercentLast10") is None else f"{entry['CdSwingPercentLast10']:.3f}%"
        cd_text = "n/a" if entry.get("Cd") is None else f"{entry['Cd']:.6f}"
        drag_text = "n/a" if entry.get("Drag") is None else f"{entry['Drag']:.6f}"
        lines.append(
            f"| {entry['Profile']} | {converged} | {source_text} | {entry.get('Nodes', 'n/a')} | {entry.get('VolumeElements', 'n/a')} | "
            f"{cd_text} | {drag_text} | {delta_proxy_text} | {delta_text} | {cauchy_text} | {swing_text} |"
        )

    return lines


def _build_study_markdown(summary: dict) -> str:
    lines = [
        "# SU2 3D Multi-Case Mesh Sensitivity Study",
        "",
        f"- GeneratedAt: {summary['GeneratedAt']}",
        f"- Preset: {summary['Preset']}",
        f"- SolverCommand: {summary['SolverCommand']}",
        f"- CaseCount: {summary['CaseCount']}",
        f"- ReferenceReadyCaseCount: {summary['ReferenceReadyCaseCount']}",
        f"- NotReferenceReadyCaseCount: {summary['NotReferenceReadyCaseCount']}",
        f"- RequestedProfiles: {', '.join(summary['RequestedProfiles'])}",
        f"- RequiredProfilesForReferenceReady: {', '.join(summary['RequiredProfilesForReferenceReady'])}",
        "",
        "| Case | ReferenceStatus | RecommendedProfile | Fine->Finer ΔCd |",
        "| --- | --- | --- | ---: |",
    ]
    for case in summary["Cases"]:
        delta = case["ReferenceAssessment"].get("FineToFinerDeltaCdPercent")
        delta_text = "n/a" if delta is None else f"{delta:+.3f}%"
        lines.append(
            f"| {case.get('SourceCaseName') or 'candidate'} | {case['ReferenceAssessment']['ReferenceStatus']} | "
            f"{case.get('RecommendedReferenceProfile') or 'n/a'} | {delta_text} |"
        )

    for case in summary["Cases"]:
        lines.extend(["", * _build_case_markdown(case)])

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="執行 Gmsh 3D -> SU2 mesh sensitivity study")
    parser.add_argument("--gene", action="append", default=[], help="單一 gene JSON 檔案，可重複提供")
    parser.add_argument("--gene-dir", action="append", default=[], help="包含多個 gene JSON 的資料夾，可重複提供")
    parser.add_argument("--best-gene", action="append", default=[], help="GA 產出的 best_gene.json，可重複提供")
    parser.add_argument("--batch-summary", action="append", default=[], help="analyze_fairing.py 產出的 batch_summary.json，可重複提供")
    parser.add_argument("--top", type=int, help="搭配 --batch-summary 使用，只取前 N 名")
    parser.add_argument("--flow", help="流體條件 JSON 檔案路徑")
    parser.add_argument("--out", required=True, help="study 輸出目錄")
    parser.add_argument("--preset", choices=["none", "hpa"], help="限制 preset（預設讀 analysis_config）")
    parser.add_argument("--profile", action="append", choices=["coarse", "baseline", "fine", "finer"], default=[], help="只跑指定 mesh profile，可重複提供")
    parser.add_argument("--solver-cmd", default="SU2_CFD", help="SU2 solver 指令，預設 SU2_CFD")
    parser.add_argument("--ranks", type=int, help="MPI ranks；未指定時用 serial SU2_CFD")
    parser.add_argument("--timeout", type=int, help="每個 profile 的 timeout 秒數")
    parser.add_argument("--fill-missing-from-example", action="store_true", help="若 gene 缺欄位，使用範例 gene 預設值補齊")
    parser.add_argument("--dry-run", action="store_true", help="只準備 case，不實際執行 solver")
    args = parser.parse_args()

    defaults = load_analysis_config(os.path.join(project_root, "config", "analysis_config.json"))
    preset = args.preset or defaults["preset"]
    flow_path = args.flow or os.path.join(project_root, "config", "fluid_conditions.json")
    if args.top is not None and args.top <= 0:
        parser.error("--top 必須是正整數")

    try:
        candidates = _collect_candidates(args)
        profiles = _resolve_profiles(args.profile)
        root = Path(args.out)
        root.mkdir(parents=True, exist_ok=True)

        case_summaries: list[dict] = []
        for candidate in candidates:
            case_root = root / str(candidate.get("name") or Path(candidate["GeneFile"]).stem)
            case_root.mkdir(parents=True, exist_ok=True)
            profile_results: list[dict] = []
            previous_cd = None

            for profile_name, profile_config in profiles:
                profile_dir = case_root / profile_name
                manifest = prepare_shortlist_validation_package(
                    [candidate],
                    output_dir=profile_dir,
                    flow_conditions=flow_path if os.path.exists(flow_path) else None,
                    preset=preset,
                    fill_missing_from_example=args.fill_missing_from_example,
                    mesh_mode="gmsh_3d",
                    mesh_options=profile_config["mesh_options"],
                    su2_settings=profile_config["su2_settings"],
                )
                summary = run_shortlist_su2_cases(
                    profile_dir,
                    solver_command=args.solver_cmd,
                    mpi_ranks=args.ranks,
                    timeout_seconds=args.timeout,
                    continue_on_error=True,
                    dry_run=args.dry_run,
                )
                case_result = summary["Cases"][0]
                mesh_stats = manifest["Cases"][0].get("MeshStats", {})
                entry = {
                    "Profile": profile_name,
                    "Status": case_result.get("Status"),
                    "CaseDir": manifest["Cases"][0]["CaseDir"],
                    "Nodes": mesh_stats.get("Nodes"),
                    "VolumeElements": mesh_stats.get("VolumeElements"),
                    "Cd": case_result.get("Cd"),
                    "Drag": case_result.get("Drag"),
                    "Converged": case_result.get("Converged"),
                    "BuiltInConverged": case_result.get("BuiltInConverged"),
                    "EngineeringStable": case_result.get("EngineeringStable"),
                    "ConvergenceSource": case_result.get("ConvergenceSource"),
                    "ConvergenceCriterion": case_result.get("ConvergenceCriterion"),
                    "TerminationReason": case_result.get("TerminationReason"),
                    "LastCauchyCd": case_result.get("LastCauchyCd"),
                    "CdSwingPercentLast10": case_result.get("CdSwingPercentLast10"),
                    "ProxyBaseline": case_result.get("ProxyBaseline"),
                    "MeshOptions": profile_config["mesh_options"],
                    "SU2Overrides": profile_config["su2_settings"],
                    "SummaryFiles": summary["SummaryFiles"],
                    "Error": case_result.get("Error"),
                }
                entry["DeltaCdVsPreviousPercent"] = _delta_percent(entry["Cd"], previous_cd)
                entry["DeltaCdVsProxyPercent"] = _delta_percent(
                    entry["Cd"],
                    entry["ProxyBaseline"].get("Cd") if entry.get("ProxyBaseline") else None,
                )
                previous_cd = entry["Cd"]
                profile_results.append(entry)

            case_summaries.append(
                _build_case_summary(
                    candidate=candidate,
                    preset=preset,
                    flow_path=flow_path if os.path.exists(flow_path) else None,
                    solver_command=args.solver_cmd,
                    profile_results=profile_results,
                )
            )

        study_summary = _build_study_summary(
            cases=case_summaries,
            preset=preset,
            flow_path=flow_path if os.path.exists(flow_path) else None,
            solver_command=args.solver_cmd,
            selected_profiles=[name for name, _config in profiles],
        )
        summary_json_path = root / "mesh_study_summary.json"
        summary_md_path = root / "mesh_study_summary.md"
        summary_json_path.write_text(
            json.dumps(study_summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        summary_md_path.write_text(_build_study_markdown(study_summary), encoding="utf-8")
    except AnalysisInputError as exc:
        print(f"錯誤: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"執行 SU2 mesh study 失敗: {exc}", file=sys.stderr)
        return 1

    print("SU2 mesh study 執行完成")
    print(f"Cases: {study_summary['CaseCount']}")
    print(f"ReferenceReadyCases: {study_summary['ReferenceReadyCaseCount']}")
    print(f"ProfilesPerCase: {len(profiles)}")
    print(f"mesh_study_summary.json: {summary_json_path}")
    print(f"mesh_study_summary.md: {summary_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
