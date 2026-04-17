"""
Prepare and execute shortlist-level SU2 validation bundles.

This module packages the proxy baseline, geometry tables, starter configs, and
shell helpers needed for the final validation stage. Once a `.su2` mesh is
available for a case, the same module can also launch SU2 and summarize the
result into repo-friendly JSON / Markdown artifacts.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
import json
import re
import shlex
import shutil
import subprocess
import time

import numpy as np

from analysis.fairing_analysis import (
    AnalysisInputError,
    analyze_gene,
    get_example_gene,
    load_flow_conditions,
    normalize_gene,
    write_analysis_report_bundle,
)
from analysis.su2_axisymmetric_mesh import generate_axisymmetric_mesh
from analysis.su2_gmsh_3d_mesh import generate_gmsh_3d_mesh


DEFAULT_SU2_SETTINGS = {
    "solver": "INC_NAVIER_STOKES",
    "iterations": 1500,
    "inner_iterations": 50,
    "cfl": 10.0,
    "cfl_adapt": False,
    "cfl_adapt_param": (0.1, 2.0, 1.0, 25.0, 1e-3, 0),
    "conv_startiter": 20,
    "conv_cauchy_elems": 25,
    "conv_cauchy_eps": 1e-6,
    "conv_num_method_flow": "FDS",
    "time_discre_flow": "EULER_IMPLICIT",
    "linear_solver": "FGMRES",
    "linear_solver_prec": "ILU",
    "linear_solver_error": 1e-6,
    "linear_solver_iter": 5,
    "linear_solver_ilu_fill_in": 0,
    "screen_wrt_freq_inner": 1,
    "history_wrt_freq_inner": 1,
    "marker_wall": "fairing",
    "marker_far": "farfield",
    "mesh_filename": "fairing_mesh.su2",
    "mesh_format": "SU2",
    "objective_function": "DRAG",
    "mesh_mode": "manual_3d",
}

DEFAULT_SU2_RUNTIME_SETTINGS = {
    "conv_filename": "history",
    "tabular_format": "CSV",
    "screen_output": "(INNER_ITER, RMS_RES, CAUCHY, AERO_COEFF)",
    "history_output": "(ITER, RMS_RES, CAUCHY, AERO_COEFF)",
}

AXISYMMETRIC_BENCHMARK_SU2_SETTINGS = {
    "iterations": 400,
    "inner_iterations": 400,
    "cfl": 5.0,
    "conv_startiter": 30,
    "conv_cauchy_elems": 25,
    "conv_cauchy_eps": 5e-6,
}

GMSH_3D_BENCHMARK_SU2_SETTINGS = {
    "iterations": 600,
    "inner_iterations": 600,
    "cfl": 1.5,
    "cfl_adapt": True,
    "cfl_adapt_param": (0.5, 1.25, 1.0, 12.0, 1e-2, 30),
    "conv_startiter": 40,
    "conv_cauchy_elems": 30,
    "conv_cauchy_eps": 3e-6,
    "linear_solver": "FGMRES",
    "linear_solver_prec": "ILU",
    "linear_solver_error": 1e-3,
    "linear_solver_iter": 12,
    "linear_solver_ilu_fill_in": 0,
    "screen_wrt_freq_inner": 10,
    "history_wrt_freq_inner": 1,
}

SU2_DOC_LINKS = {
    "configuration": "https://su2code.github.io/docs_v7/Configuration-File/",
    "physical_definition": "https://su2code.github.io/docs_v7/Physical-Definition/",
    "incompressible_tutorial": "https://su2code.github.io/tutorials/Inc_Von_Karman/",
    "download": "https://su2code.github.io/download.html",
}


class HighFidelityValidationNotReady(NotImplementedError):
    """Raised when a planned high-fidelity backend is not implemented yet."""


class SU2ExecutionError(RuntimeError):
    """Raised when a prepared SU2 case cannot be executed or parsed."""


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


def _sanitize_case_name(name: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    candidate = candidate.strip("._-")
    return candidate or "candidate"


def _make_unique_case_name(name: str, used_names: set[str]) -> str:
    base = _sanitize_case_name(name)
    candidate = base
    suffix = 2
    while candidate in used_names:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used_names.add(candidate)
    return candidate


def _candidate_name(candidate: Mapping, index: int) -> str:
    for key in ("name", "CaseName", "case_name", "id", "label"):
        value = candidate.get(key)
        if value:
            return str(value)
    return f"candidate_{index:02d}"


def _extract_gene(candidate: Mapping, *, fill_missing_from_example: bool) -> tuple[dict, dict]:
    if "gene" in candidate and isinstance(candidate["gene"], Mapping):
        raw_gene = dict(candidate["gene"])
    else:
        raw_gene = dict(candidate)

    fallback = get_example_gene() if fill_missing_from_example else None
    normalized_gene, metadata = normalize_gene(
        raw_gene,
        fallback_gene=fallback,
        return_metadata=True,
    )
    return normalized_gene, metadata


def _temperature_to_kelvin(value: float) -> float:
    # The project flow config historically stores temperature in Celsius, while
    # SU2 expects Kelvin in the config. Values above 170 are treated as already
    # expressed in Kelvin.
    if value > 170.0:
        return value
    return value + 273.15


def _compute_reynolds_number(gene: dict, flow_conditions: dict) -> float:
    velocity = float(flow_conditions["velocity"])
    rho = float(flow_conditions["rho"])
    mu = float(flow_conditions["mu"])
    length = float(gene["L"])
    return rho * velocity * length / max(mu, 1e-12)


def _write_geometry_table(curves: dict, output_path: Path) -> None:
    headers = [
        "index",
        "psi",
        "x",
        "width_half",
        "width",
        "top",
        "bottom",
        "z_upper",
        "z_lower",
    ]
    lines = [",".join(headers)]
    count = len(curves["x"])
    for i in range(count):
        lines.append(
            ",".join(
                [
                    str(i),
                    f"{float(curves['psi'][i]):.10f}",
                    f"{float(curves['x'][i]):.10f}",
                    f"{float(curves['width_half'][i]):.10f}",
                    f"{float(curves['width'][i]):.10f}",
                    f"{float(curves['top'][i]):.10f}",
                    f"{float(curves['bottom'][i]):.10f}",
                    f"{float(curves['z_upper'][i]):.10f}",
                    f"{float(curves['z_lower'][i]):.10f}",
                ]
            )
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_config_entries(config_path: Path) -> list[tuple[str | None, str]]:
    entries: list[tuple[str | None, str]] = []
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if "=" in stripped and not stripped.startswith("%"):
            key = stripped.split("=", 1)[0].strip().upper()
            entries.append((key, raw_line))
        else:
            entries.append((None, raw_line))
    return entries


def _write_runtime_config(config_path: Path) -> Path:
    entries = _read_config_entries(config_path)
    overrides = {
        "CONV_FILENAME": DEFAULT_SU2_RUNTIME_SETTINGS["conv_filename"],
        "TABULAR_FORMAT": DEFAULT_SU2_RUNTIME_SETTINGS["tabular_format"],
        "SCREEN_OUTPUT": DEFAULT_SU2_RUNTIME_SETTINGS["screen_output"],
        "HISTORY_OUTPUT": DEFAULT_SU2_RUNTIME_SETTINGS["history_output"],
    }

    seen_keys: set[str] = set()
    output_lines: list[str] = []
    for key, raw_line in entries:
        if key in overrides:
            output_lines.append(f"{key}= {overrides[key]}")
            seen_keys.add(key)
        else:
            output_lines.append(raw_line)

    for key, value in overrides.items():
        if key not in seen_keys:
            output_lines.append(f"{key}= {value}")

    runtime_config_path = config_path.with_name("su2_runtime.cfg")
    runtime_config_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
    return runtime_config_path


def _resolve_su2_settings(mesh_mode: str, su2_settings: Mapping | None = None) -> dict:
    resolved_settings = dict(DEFAULT_SU2_SETTINGS)
    if mesh_mode == "axisymmetric_2d":
        resolved_settings.update(AXISYMMETRIC_BENCHMARK_SU2_SETTINGS)
    elif mesh_mode == "gmsh_3d":
        resolved_settings.update(GMSH_3D_BENCHMARK_SU2_SETTINGS)
    if su2_settings:
        resolved_settings.update(dict(su2_settings))
    resolved_settings["mesh_mode"] = mesh_mode
    return resolved_settings


def _history_candidates(case_dir: Path) -> list[Path]:
    stem = DEFAULT_SU2_RUNTIME_SETTINGS["conv_filename"]
    return [
        case_dir / f"{stem}.csv",
        case_dir / f"{stem}.dat",
        case_dir / stem,
        case_dir / "history.csv",
        case_dir / "history.dat",
    ]


def _parse_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().strip('"')
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _read_history_csv(history_path: Path) -> list[dict]:
    with open(history_path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _read_history_dat(history_path: Path) -> list[dict]:
    lines = history_path.read_text(encoding="utf-8").splitlines()
    data_lines = [line.strip() for line in lines if line.strip()]
    if len(data_lines) < 2:
        raise SU2ExecutionError(f"history 檔案內容不足: {history_path}")

    header = [column.strip().strip('"') for column in data_lines[0].split(",")]
    if len(header) == 1:
        header = data_lines[0].replace("\t", " ").split()

    rows: list[dict] = []
    for line in data_lines[1:]:
        values = [column.strip().strip('"') for column in line.split(",")]
        if len(values) == 1:
            values = line.replace("\t", " ").split()
        if len(values) != len(header):
            continue
        rows.append(dict(zip(header, values)))
    return rows


def _load_history_rows(history_path: Path) -> list[dict]:
    if history_path.suffix.lower() == ".csv":
        return _read_history_csv(history_path)
    return _read_history_dat(history_path)


def _find_history_file(case_dir: Path) -> Path:
    for candidate in _history_candidates(case_dir):
        if candidate.exists():
            return candidate
    raise SU2ExecutionError(f"找不到 SU2 history 檔案: {case_dir}")


def _normalize_history_key(key) -> str:
    normalized = str(key).strip().strip('"').strip("'").strip()
    normalized = normalized.replace("-", "_").replace(" ", "")
    return normalized.upper()


def _lookup_metric(row: dict, *keys: str) -> float | None:
    normalized = {_normalize_history_key(key): value for key, value in row.items()}
    for key in keys:
        normalized_key = _normalize_history_key(key)
        if normalized_key in normalized:
            parsed = _parse_float(normalized[normalized_key])
            if parsed is not None:
                return parsed
    return None


def _build_su2_result_markdown(result: dict) -> str:
    lines = [
        "# SU2 Case Result",
        "",
        f"- Status: {result['Status']}",
        f"- CaseDir: {result['CaseDir']}",
        f"- SolverCommand: {result['SolverCommand']}",
        f"- RuntimeSeconds: {result['RuntimeSeconds']:.3f}",
        f"- HistoryFile: {result['HistoryFile']}",
    ]

    if result.get("Cd") is not None:
        lines.append(f"- Cd: {result['Cd']:.6f}")
    if result.get("Drag") is not None:
        lines.append(f"- Drag: {result['Drag']:.6f} N")
    if result.get("Iterations") is not None:
        lines.append(f"- Iterations: {result['Iterations']}")
    if result.get("ForceX") is not None:
        lines.append(f"- ForceX: {result['ForceX']:.6f}")
    if result.get("Converged") is not None:
        lines.append(f"- Converged: {'yes' if result['Converged'] else 'no'}")
    if result.get("TerminationReason"):
        lines.append(f"- TerminationReason: {result['TerminationReason']}")
    if result.get("LastCauchyCd") is not None:
        lines.append(f"- LastCauchyCd: {result['LastCauchyCd']:.6e}")
    if result.get("CdSwingPercentLast10") is not None:
        lines.append(f"- CdSwingPercentLast10: {result['CdSwingPercentLast10']:.3f}%")

    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- result_json: {result['ResultFiles']['json']}",
            f"- result_markdown: {result['ResultFiles']['markdown']}",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_run_summary(
    case_results: list[dict],
    *,
    solver_command: str,
    mpi_ranks: int | None,
    dry_run: bool,
) -> dict:
    return {
        "GeneratedAt": datetime.now().isoformat(),
        "TotalCases": len(case_results),
        "SuccessfulCases": sum(1 for item in case_results if item["Status"] in {"completed", "dry_run"}),
        "FailedCases": sum(1 for item in case_results if item["Status"] == "error"),
        "Cases": case_results,
        "SolverCommand": solver_command,
        "MpiRanks": mpi_ranks,
        "DryRun": dry_run,
    }


def _build_su2_run_summary_markdown(summary: dict) -> str:
    lines = [
        "# SU2 Run Summary",
        "",
        f"- GeneratedAt: {summary['GeneratedAt']}",
        f"- TotalCases: {summary['TotalCases']}",
        f"- SuccessfulCases: {summary['SuccessfulCases']}",
        f"- FailedCases: {summary['FailedCases']}",
        "",
        "| Case | Status | Converged | Cd | Drag (N) | Cd Swing(Last10) | History |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]

    for entry in summary["Cases"]:
        cd = "n/a" if entry.get("Cd") is None else f"{entry['Cd']:.6f}"
        drag = "n/a" if entry.get("Drag") is None else f"{entry['Drag']:.6f}"
        converged = "n/a" if entry.get("Converged") is None else ("yes" if entry["Converged"] else "no")
        cd_swing = "n/a" if entry.get("CdSwingPercentLast10") is None else f"{entry['CdSwingPercentLast10']:.3f}%"
        lines.append(
            f"| {entry['CaseName']} | {entry['Status']} | {converged} | {cd} | {drag} | {cd_swing} | {entry.get('HistoryFile', 'n/a')} |"
        )

    return "\n".join(lines) + "\n"


def _format_su2_sequence(values: Iterable[float | int]) -> str:
    formatted = []
    for value in values:
        if isinstance(value, int):
            formatted.append(str(value))
        else:
            formatted.append(f"{float(value):g}")
    return f"( {', '.join(formatted)} )"


def _build_su2_config(case_name: str, gene: dict, flow_conditions: dict, su2_settings: dict) -> str:
    velocity = float(flow_conditions["velocity"])
    rho = float(flow_conditions["rho"])
    mu = float(flow_conditions["mu"])
    temp_k = _temperature_to_kelvin(float(flow_conditions["temperature"]))
    reynolds = _compute_reynolds_number(gene, flow_conditions)
    mesh_mode = su2_settings.get("mesh_mode", "manual_3d")
    is_axisymmetric = mesh_mode == "axisymmetric_2d"
    symmetry_line = "MARKER_SYM= ( axis )\n" if is_axisymmetric else ""

    return (
        "% SU2 shortlist validation template generated by HPA Fairing Optimization Project\n"
        f"% Case: {case_name}\n"
        "% Mesh markers must include the wall / far-field markers listed below.\n"
        "% Axisymmetric benchmark meshes also require the symmetry marker defined in this config.\n"
        "\n"
        f"SOLVER= {su2_settings['solver']}\n"
        "MATH_PROBLEM= DIRECT\n"
        "SYSTEM_MEASUREMENTS= SI\n"
        "RESTART_SOL= NO\n"
        f"AXISYMMETRIC= {'YES' if is_axisymmetric else 'NO'}\n"
        "\n"
        f"ITER= {int(su2_settings['iterations'])}\n"
        f"INNER_ITER= {int(su2_settings['inner_iterations'])}\n"
        "CONV_FIELD= DRAG\n"
        "CONV_RESIDUAL_MINVAL= -10\n"
        f"CONV_STARTITER= {int(su2_settings['conv_startiter'])}\n"
        f"CONV_CAUCHY_ELEMS= {int(su2_settings['conv_cauchy_elems'])}\n"
        f"CONV_CAUCHY_EPS= {float(su2_settings['conv_cauchy_eps']):.1e}\n"
        f"CONV_NUM_METHOD_FLOW= {su2_settings['conv_num_method_flow']}\n"
        f"TIME_DISCRE_FLOW= {su2_settings['time_discre_flow']}\n"
        f"CFL_NUMBER= {float(su2_settings['cfl']):.2f}\n"
        f"CFL_ADAPT= {'YES' if su2_settings['cfl_adapt'] else 'NO'}\n"
        f"CFL_ADAPT_PARAM= {_format_su2_sequence(su2_settings['cfl_adapt_param'])}\n"
        "TIME_DOMAIN= NO\n"
        "TIME_MARCHING= NO\n"
        "\n"
        "INC_DENSITY_MODEL= CONSTANT\n"
        "INC_ENERGY_EQUATION= NO\n"
        f"INC_DENSITY_INIT= {rho:.8f}\n"
        f"INC_VELOCITY_INIT= ( {velocity:.8f}, 0.0, 0.0 )\n"
        f"INC_TEMPERATURE_INIT= {temp_k:.8f}\n"
        "INC_NONDIM= DIMENSIONAL\n"
        "\n"
        "FLUID_MODEL= CONSTANT_DENSITY\n"
        "VISCOSITY_MODEL= CONSTANT_VISCOSITY\n"
        f"MU_CONSTANT= {mu:.10e}\n"
        "\n"
        f"REF_LENGTH= {float(gene['L']):.8f}\n"
        f"REF_VELOCITY= {velocity:.8f}\n"
        f"REF_VISCOSITY= {mu:.10e}\n"
        "REF_AREA= 1.0\n"
        f"OBJECTIVE_FUNCTION= {su2_settings['objective_function']}\n"
        f"MARKER_MONITORING = ( {su2_settings['marker_wall']} )\n"
        f"MARKER_PLOTTING = ( {su2_settings['marker_wall']} )\n"
        f"SCREEN_WRT_FREQ_INNER= {int(su2_settings['screen_wrt_freq_inner'])}\n"
        f"HISTORY_WRT_FREQ_INNER= {int(su2_settings['history_wrt_freq_inner'])}\n"
        f"CONV_FILENAME= {DEFAULT_SU2_RUNTIME_SETTINGS['conv_filename']}\n"
        f"TABULAR_FORMAT= {DEFAULT_SU2_RUNTIME_SETTINGS['tabular_format']}\n"
        f"SCREEN_OUTPUT= {DEFAULT_SU2_RUNTIME_SETTINGS['screen_output']}\n"
        f"HISTORY_OUTPUT= {DEFAULT_SU2_RUNTIME_SETTINGS['history_output']}\n"
        "\n"
        f"LINEAR_SOLVER= {su2_settings['linear_solver']}\n"
        f"LINEAR_SOLVER_PREC= {su2_settings['linear_solver_prec']}\n"
        f"LINEAR_SOLVER_ERROR= {float(su2_settings['linear_solver_error']):.1e}\n"
        f"LINEAR_SOLVER_ITER= {int(su2_settings['linear_solver_iter'])}\n"
        f"LINEAR_SOLVER_ILU_FILL_IN= {int(su2_settings['linear_solver_ilu_fill_in'])}\n"
        "\n"
        f"MESH_FILENAME= {su2_settings['mesh_filename']}\n"
        f"MESH_FORMAT= {su2_settings['mesh_format']}\n"
        f"MARKER_HEATFLUX= ( {su2_settings['marker_wall']}, 0.0 )\n"
        f"MARKER_FAR= ( {su2_settings['marker_far']} )\n"
        f"{symmetry_line}"
        "\n"
        f"% Proxy reference Reynolds number based on L = {reynolds:.8e}\n"
        "% If you switch to INC_RANS / transition models later, revisit turbulence settings\n"
        "% and near-wall mesh requirements before trusting the result.\n"
    )


def _build_case_readme(case_name: str, case_entry: dict, su2_settings: dict) -> str:
    included_files = [
        f"# {case_name}",
        "",
        "這個資料夾是 SU2 shortlist 驗證工作包。",
        "",
        "## Included Files",
        "",
        "- `gene.json`: 正規化後的基因參數",
        "- `summary.json` / `summary.md`: 目前 fast proxy 的基準結果",
        "- `fairing_geometry.csv`: 外形曲線與包絡表格，方便檢查或重建幾何",
        "- `su2_case.cfg`: SU2 starter config",
        "- `su2_runtime.cfg`: 已鎖定 history / output 設定的實跑 config",
        "- `PUT_MESH_HERE.txt`: mesh 與 marker 命名提醒",
        "",
    ]
    if case_entry.get("MeshMode") in {"axisymmetric_2d", "gmsh_3d"}:
        included_files.insert(-2, "- `mesh_metadata.json`: 自動生 mesh 時的邊界與解析度摘要")
    if case_entry.get("MeshMode") == "gmsh_3d":
        included_files.insert(-2, "- `fairing_mesh.msh`: Gmsh 原生 mesh，方便除錯與再轉檔")

    lines = [
        *included_files,
        "## Mesh Contract",
        "",
        f"- Mesh filename: `{su2_settings['mesh_filename']}`",
        f"- Wall marker: `{su2_settings['marker_wall']}`",
        f"- Far-field marker: `{su2_settings['marker_far']}`",
        "",
        "## Proxy Baseline",
        "",
        f"- Drag: {case_entry['Drag']:.4f} N",
        f"- Cd: {case_entry['Cd']:.6f}",
        f"- Swet: {case_entry['Swet']:.3f} m^2",
        f"- LaminarFraction: {case_entry['LaminarFraction']:.3f}",
        f"- ReynoldsNumber(L): {case_entry['ReynoldsNumber']:.6e}",
        f"- MeshMode: {case_entry.get('MeshMode', 'manual_3d')}",
        "",
    ]

    if case_entry.get("ProxyScore") is not None:
        lines.extend(
            [
                "## Selection Context",
                "",
                f"- ProxyScore: {case_entry['ProxyScore']:.4f}",
                f"- SourceGeneration: {case_entry.get('SourceGeneration', 'n/a')}",
                f"- SourceIndividual: {case_entry.get('SourceIndividual', 'n/a')}",
                "",
            ]
        )

    if case_entry.get("Recommendations"):
        lines.extend(
            [
                "## Proxy Recommendations",
                "",
            ]
        )
        for recommendation in case_entry["Recommendations"]:
            lines.append(f"- {recommendation}")
        lines.append("")

    lines.extend(
        [
        "## Next Steps",
        "",
        (
            "1. 這個 case 已經附帶 auto-generated axisymmetric benchmark mesh `fairing_mesh.su2`。"
            if case_entry.get("MeshMode") == "axisymmetric_2d"
            else "1. 以這個 case 的外形重建或匯出最終 mesh，存成 `fairing_mesh.su2`。"
        ),
        "2. 確認 mesh markers 名稱與 config 一致。",
        "3. 優先執行 `SU2_CFD su2_runtime.cfg`，或改用 `mpirun -n 4 SU2_CFD su2_runtime.cfg`。",
        "4. 如果你還在 repo 內，也可以用 `python scripts/run_su2_shortlist.py --shortlist-dir <shortlist_dir>` 自動彙整結果。",
        "5. 把 SU2 的 drag / force 結果回填到你的 shortlist 比較表。",
        "",
        "## SU2 References",
        "",
        f"- Configuration syntax: {SU2_DOC_LINKS['configuration']}",
        f"- Incompressible setup: {SU2_DOC_LINKS['physical_definition']}",
        f"- Example incompressible tutorial: {SU2_DOC_LINKS['incompressible_tutorial']}",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_manifest_markdown(manifest: dict) -> str:
    lines = [
        "# SU2 Shortlist Validation Package",
        "",
        f"- GeneratedAt: {manifest['GeneratedAt']}",
        f"- Backend: {manifest['Backend']}",
        f"- Preset: {manifest['Preset']}",
        f"- MeshMode: {manifest.get('MeshMode', 'manual_3d')}",
        f"- Cases: {manifest['CaseCount']}",
        "",
        "## Cases",
        "",
    ]

    for entry in manifest["Cases"]:
        lines.extend(
            [
                f"### {entry['CaseName']}",
                "",
                f"- CaseDir: {entry['CaseDir']}",
                f"- Drag: {entry['Drag']:.4f} N",
                f"- Cd: {entry['Cd']:.6f}",
                f"- ProxyScore: {entry['ProxyScore']:.4f}" if entry.get("ProxyScore") is not None else "- ProxyScore: n/a",
                f"- ReynoldsNumber(L): {entry['ReynoldsNumber']:.6e}",
                f"- MeshMode: {entry.get('MeshMode', 'manual_3d')}",
                f"- FilledFields: {', '.join(entry['FilledFields']) if entry['FilledFields'] else 'none'}",
                "",
            ]
        )

    lines.extend(
        [
            "## Next Steps",
            "",
            (
                "1. `axisymmetric_2d` cases 已附帶可直接執行的 benchmark mesh；`manual_3d` case 仍需自行建 mesh。"
                if manifest.get("MeshMode") == "axisymmetric_2d"
                else (
                    "1. `gmsh_3d` cases 已自動產生可直接執行的 3D benchmark mesh，可先拿來建立 SU2 基準。"
                    if manifest.get("MeshMode") == "gmsh_3d"
                    else "1. Mesh each shortlisted case into SU2 `.su2` format."
                )
            ),
            "2. Keep the wall marker name and far-field marker name consistent with each case config.",
            "3. Run `./run_all_su2_cases.sh` after SU2 is installed and meshes are ready.",
            "",
            "## References",
            "",
            f"- SU2 download / macOS binaries: {SU2_DOC_LINKS['download']}",
            f"- Config reference: {SU2_DOC_LINKS['configuration']}",
            f"- Incompressible physical definition: {SU2_DOC_LINKS['physical_definition']}",
            f"- Incompressible example tutorial: {SU2_DOC_LINKS['incompressible_tutorial']}",
        ]
    )
    return "\n".join(lines) + "\n"


def _build_shortlist_report(case_entries: list[dict], report_files: dict) -> dict:
    summary_cases = []
    for entry in case_entries:
        summary_cases.append(
            {
                "Rank": entry["Rank"],
                "CaseName": entry["CaseName"],
                "ProxyScore": entry.get("ProxyScore"),
                "Drag": entry["Drag"],
                "Cd": entry["Cd"],
                "Swet": entry["Swet"],
                "LaminarFraction": entry["LaminarFraction"],
                "SourceGeneration": entry.get("SourceGeneration"),
                "SourceIndividual": entry.get("SourceIndividual"),
                "FilledFields": entry["FilledFields"],
                "TopRecommendations": entry.get("Recommendations", [])[:2],
                "CaseDir": entry["CaseDir"],
                "SU2Config": entry["PreparedFiles"]["su2_config"],
                "MeshMode": entry.get("MeshMode", "manual_3d"),
            }
        )

    return {
        "GeneratedAt": datetime.now().isoformat(),
        "CaseCount": len(summary_cases),
        "Cases": summary_cases,
        "ReportFiles": report_files,
    }


def _build_shortlist_report_markdown(summary: dict) -> str:
    lines = [
        "# SU2 Shortlist Comparison Report",
        "",
        f"- GeneratedAt: {summary['GeneratedAt']}",
        f"- CaseCount: {summary['CaseCount']}",
        "",
        "| Rank | Case | ProxyScore | Drag (N) | Cd | Source |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]

    for entry in summary["Cases"]:
        source_generation = entry.get("SourceGeneration")
        source_individual = entry.get("SourceIndividual")
        if source_generation is None or source_individual is None:
            source = "n/a"
        else:
            source = f"gen {source_generation} / ind {source_individual}"
        proxy_score = "n/a" if entry.get("ProxyScore") is None else f"{entry['ProxyScore']:.4f}"
        lines.append(
            f"| {entry['Rank']} | {entry['CaseName']} | {proxy_score} | {entry['Drag']:.4f} | {entry['Cd']:.6f} | {source} |"
        )

    lines.extend(
        [
            "",
            "## Case Notes",
            "",
        ]
    )

    for entry in summary["Cases"]:
        lines.extend(
            [
                f"### {entry['Rank']}. {entry['CaseName']}",
                "",
                f"- CaseDir: {entry['CaseDir']}",
                f"- SU2Config: {entry['SU2Config']}",
                f"- MeshMode: {entry.get('MeshMode', 'manual_3d')}",
                f"- FilledFields: {', '.join(entry['FilledFields']) if entry['FilledFields'] else 'none'}",
            ]
        )
        recommendations = entry.get("TopRecommendations", [])
        if recommendations:
            lines.append("- TopRecommendations:")
            for recommendation in recommendations:
                lines.append(f"  - {recommendation}")
        lines.append("")

    return "\n".join(lines) + "\n"


def _write_root_run_script(output_dir: Path, case_entries: list[dict]) -> Path:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        'if ! command -v SU2_CFD >/dev/null 2>&1; then',
        '  echo "SU2_CFD not found in PATH. Install SU2 first." >&2',
        "  exit 1",
        "fi",
        "",
        'ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"',
        "",
        "for case_dir in \\",
    ]

    for index, entry in enumerate(case_entries):
        terminator = " \\" if index < len(case_entries) - 1 else ""
        lines.append(f'  "$ROOT_DIR/{entry["CaseName"]}"{terminator}')

    lines.extend(
        [
            "do",
            '  mesh_path="$case_dir/fairing_mesh.su2"',
            '  runtime_cfg="$case_dir/su2_runtime.cfg"',
            '  if [ ! -f "$mesh_path" ]; then',
            '    echo "Skipping $case_dir (missing fairing_mesh.su2)"',
            "    continue",
            "  fi",
            '  if [ ! -f "$runtime_cfg" ]; then',
            '    echo "Skipping $case_dir (missing su2_runtime.cfg)"',
            "    continue",
            "  fi",
            '  echo "Running $case_dir"',
            '  (cd "$case_dir" && SU2_CFD su2_runtime.cfg)',
            "done",
            "",
        ]
    )

    script_path = output_dir / "run_all_su2_cases.sh"
    script_path.write_text("\n".join(lines), encoding="utf-8")
    script_path.chmod(0o755)
    return script_path


def _resolve_solver_command(solver_command: str) -> list[str]:
    direct_path = Path(solver_command).expanduser()
    if direct_path.exists():
        return [str(direct_path.resolve())]

    command = shlex.split(solver_command)
    if not command:
        raise SU2ExecutionError("solver_command 不可為空")

    executable = command[0]
    if Path(executable).exists():
        command[0] = str(Path(executable).resolve())
        return command
    resolved = shutil.which(executable)
    if resolved is None:
        raise SU2ExecutionError(f"找不到 SU2 solver 指令: {executable}")
    command[0] = resolved
    return command


def _preview_solver_command(solver_command: str) -> list[str]:
    direct_path = Path(solver_command).expanduser()
    if direct_path.exists():
        return [str(direct_path.resolve())]

    command = shlex.split(solver_command)
    if not command:
        raise SU2ExecutionError("solver_command 不可為空")
    return command


def _case_mesh_path(case_dir: Path, config_path: Path) -> Path:
    mesh_path = case_dir / DEFAULT_SU2_SETTINGS["mesh_filename"]
    if mesh_path.exists():
        return mesh_path

    for key, raw_line in _read_config_entries(config_path):
        if key == "MESH_FILENAME":
            mesh_name = raw_line.split("=", 1)[1].split("%", 1)[0].strip()
            candidate = case_dir / mesh_name
            if candidate.exists():
                return candidate
    raise SU2ExecutionError(f"找不到 mesh 檔案: {mesh_path}")


def _result_files_for_case(case_dir: Path) -> dict:
    return {
        "json": str(case_dir / "su2_result.json"),
        "markdown": str(case_dir / "su2_result.md"),
    }


def _parse_stdout_convergence(stdout: str) -> dict:
    lowered = stdout.lower()
    termination_reason = None
    converged = None

    if "before convergence" in lowered:
        termination_reason = "max_iterations_before_convergence"
        converged = False
    elif "exit success" in lowered and "before convergence" not in lowered:
        termination_reason = "completed"

    match = re.search(
        r"\|\s*(?P<field>[^|]+?)\|\s*(?P<value>[-+0-9.eE]+)\|\s*(?P<criterion><\s*[-+0-9.eE]+)\|\s*(?P<flag>Yes|No)\|",
        stdout,
    )
    if match:
        converged = match.group("flag") == "Yes"
        criterion_text = match.group("criterion").replace("<", "").strip()
        return {
            "ConvergenceField": match.group("field").strip(),
            "LastCauchyCd": _parse_float(match.group("value")),
            "ConvergenceCriterion": _parse_float(criterion_text),
            "Converged": converged,
            "TerminationReason": termination_reason,
        }

    return {
        "ConvergenceField": None,
        "LastCauchyCd": None,
        "ConvergenceCriterion": None,
        "Converged": converged,
        "TerminationReason": termination_reason,
    }


def _history_convergence_metrics(rows: list[dict]) -> dict:
    cd_values = []
    for row in rows:
        cd = _lookup_metric(row, "DRAG", "CD", "CFX")
        if cd is not None:
            cd_values.append(float(cd))

    trailing_cd = cd_values[-10:]
    cd_swing_percent = None
    cd_mean_last10 = None
    if trailing_cd:
        cd_mean_last10 = float(np.mean(trailing_cd))
        cd_last = trailing_cd[-1]
        if abs(cd_last) > 1e-12:
            cd_swing_percent = ((max(trailing_cd) - min(trailing_cd)) / abs(cd_last)) * 100.0

    last_row = rows[-1]
    return {
        "LastCauchyCd": _lookup_metric(last_row, "Cauchy[CD]", "CAUCHY[CD]"),
        "CdSwingPercentLast10": cd_swing_percent,
        "CdMeanLast10": cd_mean_last10,
        "ResidualPressure": _lookup_metric(last_row, 'rms[P]', 'RMS_PRESSURE'),
        "ResidualU": _lookup_metric(last_row, 'rms[U]', 'RMS_VELOCITY-X'),
        "ResidualV": _lookup_metric(last_row, 'rms[V]', 'RMS_VELOCITY-Y'),
        "ResidualW": _lookup_metric(last_row, 'rms[W]', 'RMS_VELOCITY-Z'),
    }


def _write_shortlist_run_summary(root: Path, summary: dict) -> dict:
    summary_json_path = root / "su2_run_summary.json"
    summary_md_path = root / "su2_run_summary.md"
    summary["SummaryFiles"] = {
        "json": str(summary_json_path),
        "markdown": str(summary_md_path),
    }
    summary_json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )
    summary_md_path.write_text(_build_su2_run_summary_markdown(summary), encoding="utf-8")
    return summary


def run_prepared_su2_case(
    case_dir: str | Path,
    *,
    solver_command: str = "SU2_CFD",
    mpi_ranks: int | None = None,
    timeout_seconds: int | None = None,
    dry_run: bool = False,
) -> dict:
    case_path = Path(case_dir)
    if not case_path.exists() or not case_path.is_dir():
        raise SU2ExecutionError(f"找不到 case 資料夾: {case_path}")

    config_path = case_path / "su2_case.cfg"
    if not config_path.exists():
        raise SU2ExecutionError(f"找不到 su2_case.cfg: {config_path}")

    mesh_path = _case_mesh_path(case_path, config_path)
    runtime_config_path = _write_runtime_config(config_path)
    result_files = _result_files_for_case(case_path)
    base_command = _preview_solver_command(solver_command) if dry_run else _resolve_solver_command(solver_command)

    if mpi_ranks is not None and mpi_ranks > 1:
        mpi_exec = shutil.which("mpirun") or shutil.which("mpiexec")
        if mpi_exec is None:
            raise SU2ExecutionError("指定了 mpi_ranks，但找不到 mpirun/mpiexec")
        command = [mpi_exec, "-n", str(int(mpi_ranks)), *base_command, runtime_config_path.name]
    else:
        command = [*base_command, runtime_config_path.name]

    started_at = time.time()
    if dry_run:
        runtime_seconds = time.time() - started_at
        return {
            "CaseName": case_path.name,
            "CaseDir": str(case_path),
            "Status": "dry_run",
            "SolverCommand": " ".join(command),
            "RuntimeConfig": str(runtime_config_path),
            "MeshFile": str(mesh_path),
            "RuntimeSeconds": runtime_seconds,
            "ResultFiles": result_files,
        }

    completed = subprocess.run(
        command,
        cwd=case_path,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    runtime_seconds = time.time() - started_at
    if completed.returncode != 0:
        raise SU2ExecutionError(
            f"SU2 執行失敗 ({case_path.name}): exit={completed.returncode}\n{completed.stderr.strip()}"
        )

    history_path = _find_history_file(case_path)
    rows = _load_history_rows(history_path)
    if not rows:
        raise SU2ExecutionError(f"history 檔案沒有資料列: {history_path}")
    last_row = rows[-1]
    cd = _lookup_metric(last_row, "DRAG", "CD", "CFX")
    force_x = _lookup_metric(last_row, "FORCE_X", "CFX")
    iter_value = _lookup_metric(last_row, "ITER", "INNER_ITER", "OUTER_ITER")

    summary_json_path = case_path / "summary.json"
    if not summary_json_path.exists():
        raise SU2ExecutionError(f"找不到 proxy summary.json: {summary_json_path}")
    with open(summary_json_path, "r", encoding="utf-8") as handle:
        proxy_summary = json.load(handle)
    flow_conditions = proxy_summary["Analysis"]["FlowConditions"]
    ref_area = 1.0
    dynamic_pressure = 0.5 * float(flow_conditions["rho"]) * float(flow_conditions["velocity"]) ** 2
    drag_force = None if cd is None else float(cd) * dynamic_pressure * ref_area
    history_metrics = _history_convergence_metrics(rows)
    stdout_convergence = _parse_stdout_convergence(completed.stdout)

    converged = stdout_convergence["Converged"]
    if converged is None and history_metrics["CdSwingPercentLast10"] is not None:
        converged = history_metrics["CdSwingPercentLast10"] <= 0.5

    result = {
        "CaseName": case_path.name,
        "CaseDir": str(case_path),
        "Status": "completed",
        "SolverCommand": " ".join(command),
        "RuntimeConfig": str(runtime_config_path),
        "MeshFile": str(mesh_path),
        "HistoryFile": str(history_path),
        "RuntimeSeconds": runtime_seconds,
        "Iterations": None if iter_value is None else int(iter_value),
        "Cd": cd,
        "Drag": drag_force,
        "ForceX": force_x,
        "Converged": converged,
        "TerminationReason": stdout_convergence["TerminationReason"],
        "ConvergenceField": stdout_convergence["ConvergenceField"],
        "ConvergenceCriterion": stdout_convergence["ConvergenceCriterion"],
        "LastCauchyCd": (
            stdout_convergence["LastCauchyCd"]
            if stdout_convergence["LastCauchyCd"] is not None
            else history_metrics["LastCauchyCd"]
        ),
        "CdSwingPercentLast10": history_metrics["CdSwingPercentLast10"],
        "CdMeanLast10": history_metrics["CdMeanLast10"],
        "ResidualPressure": history_metrics["ResidualPressure"],
        "ResidualU": history_metrics["ResidualU"],
        "ResidualV": history_metrics["ResidualV"],
        "ResidualW": history_metrics["ResidualW"],
        "ProxyBaseline": {
            "Cd": proxy_summary["Analysis"].get("Cd"),
            "Drag": proxy_summary["Analysis"].get("Drag"),
        },
        "ResultFiles": result_files,
        "Stdout": completed.stdout,
        "Stderr": completed.stderr,
    }

    Path(result_files["json"]).write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )
    Path(result_files["markdown"]).write_text(_build_su2_result_markdown(result), encoding="utf-8")
    return result


def _collect_case_dirs(shortlist_dir: Path, selected_cases: Iterable[str] | None = None) -> list[Path]:
    wanted = {name for name in (selected_cases or [])}
    case_dirs = []
    for entry in sorted(shortlist_dir.iterdir()):
        if not entry.is_dir():
            continue
        if not (entry / "su2_case.cfg").exists():
            continue
        if wanted and entry.name not in wanted:
            continue
        case_dirs.append(entry)
    if not case_dirs:
        raise SU2ExecutionError(f"shortlist 內沒有可執行 case: {shortlist_dir}")
    return case_dirs


def run_shortlist_su2_cases(
    shortlist_dir: str | Path,
    *,
    solver_command: str = "SU2_CFD",
    mpi_ranks: int | None = None,
    timeout_seconds: int | None = None,
    selected_cases: Iterable[str] | None = None,
    continue_on_error: bool = False,
    dry_run: bool = False,
) -> dict:
    root = Path(shortlist_dir)
    if not root.exists() or not root.is_dir():
        raise SU2ExecutionError(f"找不到 shortlist 目錄: {root}")

    case_dirs = _collect_case_dirs(root, selected_cases)
    case_results: list[dict] = []
    failed_cases = 0

    for case_dir in case_dirs:
        try:
            result = run_prepared_su2_case(
                case_dir,
                solver_command=solver_command,
                mpi_ranks=mpi_ranks,
                timeout_seconds=timeout_seconds,
                dry_run=dry_run,
            )
        except Exception as exc:
            failed_cases += 1
            result = {
                "CaseName": case_dir.name,
                "CaseDir": str(case_dir),
                "Status": "error",
                "Error": str(exc),
            }
            if not continue_on_error:
                case_results.append(result)
                summary = _build_run_summary(
                    case_results,
                    solver_command=solver_command,
                    mpi_ranks=mpi_ranks,
                    dry_run=dry_run,
                )
                _write_shortlist_run_summary(root, summary)
                raise SU2ExecutionError(str(exc)) from exc
        case_results.append(result)

    summary = _build_run_summary(
        case_results,
        solver_command=solver_command,
        mpi_ranks=mpi_ranks,
        dry_run=dry_run,
    )
    return _write_shortlist_run_summary(root, summary)


def _candidate_to_mapping(candidate) -> Mapping:
    if not isinstance(candidate, Mapping):
        raise AnalysisInputError("shortlist candidate 必須是 dict / mapping")
    return candidate


def prepare_shortlist_validation_package(
    candidates: Iterable[Mapping],
    *,
    output_dir: str | Path,
    backend: str = "su2",
    flow_conditions: str | Path | dict | None = None,
    preset: str = "none",
    fill_missing_from_example: bool = False,
    su2_settings: Mapping | None = None,
    mesh_mode: str = "manual_3d",
    mesh_options: Mapping | None = None,
    report_config: Mapping | None = None,
) -> dict:
    if backend != "su2":
        raise ValueError(f"Unsupported high-fidelity backend: {backend}")
    if mesh_mode not in {"manual_3d", "axisymmetric_2d", "gmsh_3d"}:
        raise ValueError(f"Unsupported mesh_mode: {mesh_mode}")

    candidate_list = [_candidate_to_mapping(candidate) for candidate in candidates]
    if not candidate_list:
        raise AnalysisInputError("shortlist 不可為空")

    normalized_flow = load_flow_conditions(flow_conditions)
    resolved_settings = _resolve_su2_settings(mesh_mode, su2_settings)

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    used_names: set[str] = set()
    case_entries: list[dict] = []

    for index, candidate in enumerate(candidate_list, start=1):
        case_name = _make_unique_case_name(_candidate_name(candidate, index), used_names)
        gene, gene_metadata = _extract_gene(candidate, fill_missing_from_example=fill_missing_from_example)
        analysis = analyze_gene(
            gene,
            flow_conditions=normalized_flow,
            preset=preset,
            backend="fast_proxy",
            include_geometry=True,
        )

        case_dir = root / case_name
        case_dir.mkdir(parents=True, exist_ok=True)

        (case_dir / "gene.json").write_text(
            json.dumps(gene, indent=2, ensure_ascii=False, default=_json_default) + "\n",
            encoding="utf-8",
        )
        report_files = write_analysis_report_bundle(
            case_dir,
            gene,
            analysis,
            report_config=report_config,
            gene_metadata=gene_metadata,
        )
        _write_geometry_table(analysis["Curves"], case_dir / "fairing_geometry.csv")
        su2_config_path = case_dir / "su2_case.cfg"
        su2_config_path.write_text(
            _build_su2_config(case_name, gene, normalized_flow, resolved_settings),
            encoding="utf-8",
        )
        runtime_config_path = _write_runtime_config(su2_config_path)
        mesh_metadata = None
        mesh_metadata_path = case_dir / "mesh_metadata.json"
        if mesh_mode == "axisymmetric_2d":
            mesh_metadata = generate_axisymmetric_mesh(
                analysis["Curves"],
                case_dir / resolved_settings["mesh_filename"],
                options=dict(mesh_options or {}),
            )
        elif mesh_mode == "gmsh_3d":
            mesh_metadata = generate_gmsh_3d_mesh(
                analysis["Curves"],
                case_dir / resolved_settings["mesh_filename"],
                options=dict(mesh_options or {}),
            )
        (case_dir / "PUT_MESH_HERE.txt").write_text(
            "\n".join(
                [
                    (
                        "An axisymmetric benchmark mesh was auto-generated as `fairing_mesh.su2`."
                        if mesh_mode == "axisymmetric_2d"
                        else (
                            "A Gmsh-generated 3D benchmark mesh was auto-generated as `fairing_mesh.su2`."
                            if mesh_mode == "gmsh_3d"
                            else "Place your final SU2 mesh here as `fairing_mesh.su2`."
                        )
                    ),
                    f"Required wall marker: {resolved_settings['marker_wall']}",
                    f"Required far-field marker: {resolved_settings['marker_far']}",
                    "Required symmetry marker: axis" if mesh_mode == "axisymmetric_2d" else "",
                    "Then run `SU2_CFD su2_runtime.cfg` inside this folder.",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        case_entry = {
            "CaseName": case_name,
            "CaseDir": str(case_dir),
            "Drag": float(analysis["Drag"]),
            "Cd": float(analysis["Cd"]),
            "Swet": float(analysis["Swet"]),
            "LaminarFraction": float(analysis["LaminarFraction"]),
            "ReynoldsNumber": float(_compute_reynolds_number(gene, normalized_flow)),
            "ReferenceLength": float(gene["L"]),
            "FilledFields": gene_metadata.get("filled_fields", []),
            "Recommendations": list(analysis.get("Recommendations", [])),
            "MeshMode": mesh_mode,
            "PreparedFiles": {
                "gene_json": str(case_dir / "gene.json"),
                "summary_json": report_files["summary_json"],
                "summary_md": report_files["summary_md"],
                "geometry_csv": str(case_dir / "fairing_geometry.csv"),
                "su2_config": str(su2_config_path),
                "su2_runtime_config": str(runtime_config_path),
                "mesh_su2": str(case_dir / resolved_settings["mesh_filename"]) if mesh_mode in {"axisymmetric_2d", "gmsh_3d"} else None,
                "mesh_metadata_json": str(mesh_metadata_path) if mesh_mode in {"axisymmetric_2d", "gmsh_3d"} else None,
                "mesh_msh": str(case_dir / "fairing_mesh.msh") if mesh_mode == "gmsh_3d" else None,
                "mesh_placeholder": str(case_dir / "PUT_MESH_HERE.txt"),
            },
        }
        if mesh_metadata is not None:
            case_entry["MeshStats"] = mesh_metadata
        if "GeneFile" in candidate:
            case_entry["GeneFile"] = str(candidate["GeneFile"])
        case_entry["Notes"] = dict(candidate.get("Notes", {})) if isinstance(candidate.get("Notes"), Mapping) else candidate.get("Notes")
        if isinstance(case_entry["Notes"], Mapping):
            score = case_entry["Notes"].get("score")
            case_entry["ProxyScore"] = float(score) if isinstance(score, (int, float)) else None
            case_entry["SourceGeneration"] = case_entry["Notes"].get("generation")
            case_entry["SourceIndividual"] = case_entry["Notes"].get("individual")
        else:
            case_entry["ProxyScore"] = None
            case_entry["SourceGeneration"] = None
            case_entry["SourceIndividual"] = None
        (case_dir / "README.md").write_text(
            _build_case_readme(case_name, case_entry, resolved_settings),
            encoding="utf-8",
        )
        case_entries.append(case_entry)

    case_entries.sort(key=lambda entry: (entry["Drag"], entry["Cd"], entry["CaseName"]))
    for rank, entry in enumerate(case_entries, start=1):
        entry["Rank"] = rank

    run_script = _write_root_run_script(root, case_entries)
    shortlist_report_json = root / "shortlist_report.json"
    shortlist_report_md = root / "shortlist_report.md"
    shortlist_report_files = {
        "json": str(shortlist_report_json),
        "markdown": str(shortlist_report_md),
    }
    shortlist_report = _build_shortlist_report(case_entries, shortlist_report_files)
    shortlist_report_json.write_text(
        json.dumps(shortlist_report, indent=2, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )
    shortlist_report_md.write_text(_build_shortlist_report_markdown(shortlist_report), encoding="utf-8")
    manifest = {
        "GeneratedAt": datetime.now().isoformat(),
        "Backend": backend,
        "Preset": preset,
        "MeshMode": mesh_mode,
        "CaseCount": len(case_entries),
        "FlowConditions": normalized_flow,
        "SU2Settings": resolved_settings,
        "Cases": case_entries,
        "RunScript": str(run_script),
        "Sources": SU2_DOC_LINKS,
        "Status": "prepared",
        "ManifestFiles": {
            "json": str(root / "validation_manifest.json"),
            "markdown": str(root / "validation_manifest.md"),
        },
        "ShortlistReportFiles": shortlist_report_files,
    }

    manifest_json = root / "validation_manifest.json"
    manifest_md = root / "validation_manifest.md"
    manifest_json.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )
    manifest_md.write_text(_build_manifest_markdown(manifest), encoding="utf-8")
    return manifest


def validate_shortlist(
    candidates: Iterable[Mapping],
    *,
    backend: str = "su2",
    output_dir: str | Path,
    flow_conditions: str | Path | dict | None = None,
    preset: str = "none",
    fill_missing_from_example: bool = False,
    su2_settings: Mapping | None = None,
    mesh_mode: str = "manual_3d",
    mesh_options: Mapping | None = None,
    report_config: Mapping | None = None,
) -> dict:
    return prepare_shortlist_validation_package(
        candidates,
        output_dir=output_dir,
        backend=backend,
        flow_conditions=flow_conditions,
        preset=preset,
        fill_missing_from_example=fill_missing_from_example,
        su2_settings=su2_settings,
        mesh_mode=mesh_mode,
        mesh_options=mesh_options,
        report_config=report_config,
    )
