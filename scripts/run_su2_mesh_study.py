"""
Run a 3D Gmsh -> SU2 mesh sensitivity study for one shortlisted fairing design.

This command prepares three benchmark meshes (coarse / baseline / fine), runs
SU2 for each profile, and writes a study summary that compares convergence and
mesh sensitivity in one place.
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


def _collect_candidate(args) -> dict:
    if bool(args.gene) == bool(args.best_gene):
        raise AnalysisInputError("請提供且只提供其中一個來源：--gene 或 --best-gene")
    if args.gene:
        return _load_gene_candidate(args.gene)
    return _load_best_gene_candidate(args.best_gene)


def _resolve_profiles(selected_profiles: list[str]) -> list[tuple[str, dict]]:
    profile_names = selected_profiles or ["coarse", "baseline", "fine"]
    return [(name, DEFAULT_STUDY_PROFILES[name]) for name in profile_names]


def _delta_percent(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or abs(previous) < 1e-12:
        return None
    return (current / previous - 1.0) * 100.0


def _build_study_summary(
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

    return {
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


def _build_study_markdown(summary: dict) -> str:
    lines = [
        "# SU2 3D Mesh Sensitivity Study",
        "",
        f"- GeneratedAt: {summary['GeneratedAt']}",
        f"- SourceGene: {summary.get('SourceGene') or 'inline'}",
        f"- SourceCaseName: {summary.get('SourceCaseName') or 'candidate'}",
        f"- Preset: {summary['Preset']}",
        f"- SolverCommand: {summary['SolverCommand']}",
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

    lines.extend(
        [
            "",
            "| Profile | Converged | Nodes | Tetra | Cd | Drag (N) | ΔCd vs proxy | ΔCd vs prev | Last Cauchy CD | Cd Swing(Last10) |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for entry in summary["Profiles"]:
        converged = "yes" if entry.get("Converged") else "no"
        delta_cd = entry.get("DeltaCdVsPreviousPercent")
        delta_proxy = entry.get("DeltaCdVsProxyPercent")
        delta_text = "n/a" if delta_cd is None else f"{delta_cd:+.3f}%"
        delta_proxy_text = "n/a" if delta_proxy is None else f"{delta_proxy:+.3f}%"
        cauchy_text = "n/a" if entry.get("LastCauchyCd") is None else f"{entry['LastCauchyCd']:.3e}"
        swing_text = "n/a" if entry.get("CdSwingPercentLast10") is None else f"{entry['CdSwingPercentLast10']:.3f}%"
        cd_text = "n/a" if entry.get("Cd") is None else f"{entry['Cd']:.6f}"
        drag_text = "n/a" if entry.get("Drag") is None else f"{entry['Drag']:.6f}"
        lines.append(
            f"| {entry['Profile']} | {converged} | {entry.get('Nodes', 'n/a')} | {entry.get('VolumeElements', 'n/a')} | "
            f"{cd_text} | {drag_text} | {delta_proxy_text} | {delta_text} | {cauchy_text} | {swing_text} |"
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="執行 Gmsh 3D -> SU2 mesh sensitivity study")
    parser.add_argument("--gene", help="單一 gene JSON 檔案")
    parser.add_argument("--best-gene", help="GA 產出的 best_gene.json")
    parser.add_argument("--flow", help="流體條件 JSON 檔案路徑")
    parser.add_argument("--out", required=True, help="study 輸出目錄")
    parser.add_argument("--preset", choices=["none", "hpa"], help="限制 preset（預設讀 analysis_config）")
    parser.add_argument("--profile", action="append", choices=["coarse", "baseline", "fine"], default=[], help="只跑指定 mesh profile，可重複提供")
    parser.add_argument("--solver-cmd", default="SU2_CFD", help="SU2 solver 指令，預設 SU2_CFD")
    parser.add_argument("--ranks", type=int, help="MPI ranks；未指定時用 serial SU2_CFD")
    parser.add_argument("--timeout", type=int, help="每個 profile 的 timeout 秒數")
    parser.add_argument("--fill-missing-from-example", action="store_true", help="若 gene 缺欄位，使用範例 gene 預設值補齊")
    parser.add_argument("--dry-run", action="store_true", help="只準備 case，不實際執行 solver")
    args = parser.parse_args()

    defaults = load_analysis_config(os.path.join(project_root, "config", "analysis_config.json"))
    preset = args.preset or defaults["preset"]
    flow_path = args.flow or os.path.join(project_root, "config", "fluid_conditions.json")

    try:
        candidate = _collect_candidate(args)
        profiles = _resolve_profiles(args.profile)
        root = Path(args.out)
        root.mkdir(parents=True, exist_ok=True)

        profile_results: list[dict] = []
        previous_cd = None

        for profile_name, profile_config in profiles:
            profile_dir = root / profile_name
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
                dry_run=args.dry_run,
            )
            case_result = summary["Cases"][0]
            mesh_stats = manifest["Cases"][0].get("MeshStats", {})
            entry = {
                "Profile": profile_name,
                "CaseDir": manifest["Cases"][0]["CaseDir"],
                "Nodes": mesh_stats.get("Nodes"),
                "VolumeElements": mesh_stats.get("VolumeElements"),
                "Cd": case_result.get("Cd"),
                "Drag": case_result.get("Drag"),
                "Converged": case_result.get("Converged"),
                "TerminationReason": case_result.get("TerminationReason"),
                "LastCauchyCd": case_result.get("LastCauchyCd"),
                "CdSwingPercentLast10": case_result.get("CdSwingPercentLast10"),
                "ProxyBaseline": case_result.get("ProxyBaseline"),
                "MeshOptions": profile_config["mesh_options"],
                "SU2Overrides": profile_config["su2_settings"],
                "SummaryFiles": summary["SummaryFiles"],
            }
            entry["DeltaCdVsPreviousPercent"] = _delta_percent(entry["Cd"], previous_cd)
            entry["DeltaCdVsProxyPercent"] = _delta_percent(
                entry["Cd"],
                entry["ProxyBaseline"].get("Cd") if entry.get("ProxyBaseline") else None,
            )
            previous_cd = entry["Cd"]
            profile_results.append(entry)

        study_summary = _build_study_summary(
            candidate=candidate,
            preset=preset,
            flow_path=flow_path if os.path.exists(flow_path) else None,
            solver_command=args.solver_cmd,
            profile_results=profile_results,
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
    print(f"Profiles: {len(profile_results)}")
    print(f"mesh_study_summary.json: {summary_json_path}")
    print(f"mesh_study_summary.md: {summary_md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
