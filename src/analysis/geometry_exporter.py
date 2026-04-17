"""
Generate lightweight geometry artifacts for shortlist cases.

Outputs include:
- Single-file HTML preview (interactive rotate / zoom / preset views)
- STL + OBJ surface geometry for quick interoperability
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np


def _require_float_array(curves: dict, key: str) -> np.ndarray:
    if key not in curves:
        raise ValueError(f"Curves 缺少欄位: {key}")
    return np.asarray(curves[key], dtype=float)


def _section_exponents(curves: dict) -> tuple[float, float]:
    top_exp = 0.5 * (float(curves.get("M_top", 2.5)) + float(curves.get("N_top", 2.5)))
    bot_exp = 0.5 * (float(curves.get("M_bot", 2.5)) + float(curves.get("N_bot", 2.5)))
    return max(top_exp, 1.2), max(bot_exp, 1.2)


def _section_profile(
    x_value: float,
    width_half: float,
    z_upper: float,
    z_lower: float,
    top_exp: float,
    bot_exp: float,
    section_points: int,
    min_section_scale: float,
) -> list[tuple[float, float, float]]:
    y_half = max(float(width_half), min_section_scale)
    z_center = 0.5 * (float(z_upper) + float(z_lower))
    total_height = max(float(z_upper) - float(z_lower), min_section_scale)
    half_height = 0.5 * total_height

    profile: list[tuple[float, float, float]] = []
    for index in range(section_points):
        theta = (2.0 * math.pi * index) / section_points
        cos_val = math.cos(theta)
        sin_val = math.sin(theta)
        exponent = top_exp if 0.0 <= theta <= math.pi else bot_exp
        y_value = y_half * math.copysign(abs(cos_val) ** (2.0 / exponent), cos_val)

        if 0.0 <= theta <= math.pi:
            z_local = half_height * (abs(sin_val) ** (2.0 / top_exp))
        else:
            z_local = -half_height * (abs(sin_val) ** (2.0 / bot_exp))

        profile.append((float(x_value), float(y_value), float(z_center + z_local)))
    return profile


def _build_surface_mesh(
    curves: dict,
    section_count: int,
    section_points: int,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, int, int]]]:
    x_coords = _require_float_array(curves, "x")
    width_half = _require_float_array(curves, "width_half")
    z_upper = _require_float_array(curves, "z_upper")
    z_lower = _require_float_array(curves, "z_lower")

    if not (len(x_coords) == len(width_half) == len(z_upper) == len(z_lower)):
        raise ValueError("Curves 陣列長度不一致（x/width_half/z_upper/z_lower）")

    if len(x_coords) < 2:
        raise ValueError("Curves 至少需要兩個截面點")

    length = float(x_coords[-1] - x_coords[0]) if len(x_coords) >= 2 else 1.0
    min_section_scale = max(abs(length) * 0.004, 1e-6)
    section_count = max(int(section_count), 2)
    section_points = max(int(section_points), 8)

    top_exp, bot_exp = _section_exponents(curves)
    sample_x = np.linspace(float(x_coords[0]), float(x_coords[-1]), section_count)
    sampled_width = np.interp(sample_x, x_coords, width_half)
    sampled_upper = np.interp(sample_x, x_coords, z_upper)
    sampled_lower = np.interp(sample_x, x_coords, z_lower)

    vertices: list[tuple[float, float, float]] = []
    rings: list[list[int]] = []
    for value_x, value_w, value_u, value_l in zip(
        sample_x,
        sampled_width,
        sampled_upper,
        sampled_lower,
    ):
        ring_indices: list[int] = []
        for point in _section_profile(
            float(value_x),
            float(value_w),
            float(value_u),
            float(value_l),
            top_exp,
            bot_exp,
            section_points,
            min_section_scale,
        ):
            ring_indices.append(len(vertices))
            vertices.append(point)
        rings.append(ring_indices)

    faces: list[tuple[int, int, int]] = []
    for section_index in range(section_count - 1):
        current_ring = rings[section_index]
        next_ring = rings[section_index + 1]
        for point_index in range(section_points):
            current = current_ring[point_index]
            current_next = current_ring[(point_index + 1) % section_points]
            next = next_ring[point_index]
            next_next = next_ring[(point_index + 1) % section_points]
            faces.append((current, current_next, next_next))
            faces.append((current, next_next, next))

    return vertices, faces


def _normalize_mesh(
    vertices: list[tuple[float, float, float]],
) -> tuple[list[tuple[float, float, float]], tuple[float, float, float], float]:
    arr = np.asarray(vertices, dtype=float)
    min_values = np.min(arr, axis=0)
    max_values = np.max(arr, axis=0)
    center = 0.5 * (min_values + max_values)
    extent = np.max(max_values - min_values)
    return [tuple(point - center) for point in arr.tolist()], tuple(center.tolist()), float(extent if extent > 0 else 1.0)


def _write_obj(vertices: list[tuple[float, float, float]], faces: list[tuple[int, int, int]], path: Path) -> None:
    lines = ["# Fairing surface OBJ"]
    for x_value, y_value, z_value in vertices:
        lines.append(f"v {x_value:.10g} {y_value:.10g} {z_value:.10g}")
    for a, b, c in faces:
        lines.append(f"f {a + 1} {b + 1} {c + 1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stl(vertices: list[tuple[float, float, float]], faces: list[tuple[int, int, int]], path: Path) -> None:
    v = np.asarray(vertices, dtype=float)
    lines = ["solid fairing"]
    for a, b, c in faces:
        p0 = v[a]
        p1 = v[b]
        p2 = v[c]
        edge1 = p1 - p0
        edge2 = p2 - p0
        normal = np.cross(edge1, edge2)
        norm = float(np.linalg.norm(normal))
        if norm > 0.0:
            normal = normal / norm
        else:
            normal = np.zeros(3, dtype=float)
        lines.extend(
            [
                "  facet normal "
                f"{normal[0]:.8e} {normal[1]:.8e} {normal[2]:.8e}",
                "    outer loop",
                f"      vertex {p0[0]:.10g} {p0[1]:.10g} {p0[2]:.10g}",
                f"      vertex {p1[0]:.10g} {p1[1]:.10g} {p1[2]:.10g}",
                f"      vertex {p2[0]:.10g} {p2[1]:.10g} {p2[2]:.10g}",
                "    endloop",
                "  endfacet",
            ]
        )
    lines.append("endsolid fairing")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_preview_html(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    metrics: dict,
    path: Path,
) -> None:
    bbox_center = [
        sum(v[0] for v in vertices) / len(vertices),
        sum(v[1] for v in vertices) / len(vertices),
        sum(v[2] for v in vertices) / len(vertices),
    ]
    x_extent = max(v[0] for v in vertices) - min(v[0] for v in vertices)
    y_extent = max(v[1] for v in vertices) - min(v[1] for v in vertices)
    z_extent = max(v[2] for v in vertices) - min(v[2] for v in vertices)
    extent = max(x_extent, y_extent, z_extent)
    payload = {
        "vertices": [{"x": point[0] - bbox_center[0], "y": point[1] - bbox_center[1], "z": point[2] - bbox_center[2]} for point in vertices],
        "faces": [{"a": a, "b": b, "c": c} for a, b, c in faces],
        "metrics": {k: float(v) if isinstance(v, (int, float)) else str(v) for k, v in metrics.items()},
    }
    html = f"""<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Fairing Geometry Preview</title>
    <style>
      :root {{ font-family: "Trebuchet MS", Arial, sans-serif; }}
      body {{ margin: 16px; background: #f3f5f9; color: #111; }}
      #canvasWrap {{ width: min(96vw, 920px); margin: 0 auto; border: 1px solid #c8ceda; background: #fff; }}
      canvas {{ width: 100%; display: block; }}
      .panel {{ margin: 8px auto 0; width: min(96vw, 920px); display: flex; gap: 10px; align-items: center; }}
      .metric {{ margin-top: 8px; font-size: 13px; width: min(96vw, 920px); }}
      label {{ font-size: 13px; }}
      select, button {{ padding: 6px 10px; }}
    </style>
  </head>
  <body>
    <h2 style="margin:0 0 8px;">Fairing Geometry Preview</h2>
    <p style="margin:0 0 10px;color:#4d5566;font-size:14px;">旋轉與滾輪縮放，拖拽可改視角，按 side/top/front 切換視角。</p>
    <div class="panel">
      <label for="viewPreset">預設視角:</label>
      <select id="viewPreset">
        <option value="isometric">等角</option>
        <option value="side">側視</option>
        <option value="top">頂視</option>
        <option value="front">前視</option>
      </select>
      <button type="button" id="resetView">重置視角</button>
    </div>
    <div id="canvasWrap"><canvas id="preview" width="920" height="560"></canvas></div>
    <div class="metric">
      <pre id="metricJson"></pre>
    </div>
    <script>
      const geometry = {json.dumps(payload, ensure_ascii=False)};
      const canvas = document.getElementById("preview");
      const ctx = canvas.getContext("2d");
      const preset = document.getElementById("viewPreset");
      const metricText = document.getElementById("metricJson");
      const resetView = document.getElementById("resetView");

      const verts = geometry.vertices;
      const faces = geometry.faces;
      metricText.textContent = JSON.stringify(geometry.metrics, null, 2);

      let yaw = -0.4;
      let pitch = 0.55;
      let roll = 0.0;
      let zoom = 0.82;
      let panX = 0.0;
      let panY = 0.0;
      let dragging = false;
      let lastX = 0.0;
      let lastY = 0.0;
      const extent = {extent:.8f};
      const scaleBase = Math.min(canvas.width, canvas.height) / Math.max(extent, 1e-8) * 0.38;

      function applyRotation(point) {{
        const cx = Math.cos(yaw), sx = Math.sin(yaw);
        const cy = Math.cos(pitch), sy = Math.sin(pitch);
        const cz = Math.cos(roll), sz = Math.sin(roll);
        let x = point.x;
        let y = point.y;
        let z = point.z;

        let x1 = x * cz - y * sz;
        let y1 = x * sz + y * cz;
        let z1 = z;

        let x2 = x1;
        let y2 = y1 * cx - z1 * sx;
        let z2 = y1 * sx + z1 * cx;

        let x3 = x2 * cy + z2 * sy;
        let y3 = y2;
        let z3 = -x2 * sy + z2 * cy;
        return [x3, y3, z3];
      }}

      function project(point) {{
        const rotated = applyRotation(point);
        const perspective = 1.25 / (1.25 - rotated[2] / Math.max(extent, 1e-8));
        return [
          canvas.width / 2 + (rotated[0] * scaleBase * zoom * perspective) + panX,
          canvas.height / 2 + (-rotated[1] * scaleBase * zoom * perspective) + panY,
          rotated[2],
          perspective,
        ];
      }}

      function draw() {{
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const projected = verts.map((v) => project(v));
        const triangles = faces.map((f, index) => {{
          const p0 = projected[f.a];
          const p1 = projected[f.b];
          const p2 = projected[f.c];
          const depth = (p0[2] + p1[2] + p2[2]) / 3;
          return {{p0, p1, p2, depth, index}};
        }}).sort((left, right) => left.depth - right.depth);

        for (const tri of triangles) {{
          const shade = Math.max(20, Math.min(180, Math.round(180 - tri.depth * 25)));
          ctx.beginPath();
          ctx.moveTo(tri.p0[0], tri.p0[1]);
          ctx.lineTo(tri.p1[0], tri.p1[1]);
          ctx.lineTo(tri.p2[0], tri.p2[1]);
          ctx.closePath();
          ctx.fillStyle = `rgb({{shade}}, {{Math.min(220, shade + 25)}}, 240)`;
          ctx.strokeStyle = "rgba(28, 35, 45, 0.6)";
          ctx.lineWidth = 0.35;
          ctx.globalAlpha = 0.92;
          ctx.fill();
          ctx.stroke();
        }}

        ctx.fillStyle = "#444";
        ctx.fillText("Drag / Cd / Swet", 8, 18);
      }}

      canvas.addEventListener("mousedown", (event) => {{
        dragging = true;
        lastX = event.clientX;
        lastY = event.clientY;
      }});
      window.addEventListener("mouseup", () => {{
        dragging = false;
      }});
      canvas.addEventListener("mousemove", (event) => {{
        if (!dragging) {{
          return;
        }}
        const dx = event.clientX - lastX;
        const dy = event.clientY - lastY;
        lastX = event.clientX;
        lastY = event.clientY;
        yaw += dx * 0.006;
        pitch += dy * 0.006;
        draw();
      }});
      canvas.addEventListener("wheel", (event) => {{
        event.preventDefault();
        const delta = Math.sign(event.deltaY);
        zoom *= 1 - delta * 0.08;
        zoom = Math.max(0.08, Math.min(4.0, zoom));
        draw();
      }}, {{ passive: false }});

      preset.addEventListener("change", () => {{
        const choice = preset.value;
        if (choice === "side") {{
          yaw = 1.3; pitch = 0.0; roll = 0.0;
        }} else if (choice === "top") {{
          yaw = 0.0; pitch = -1.25; roll = 0.0;
        }} else if (choice === "front") {{
          yaw = 0.0; pitch = 0.0; roll = 0.0;
        }} else {{
          yaw = -0.4; pitch = 0.55; roll = 0.0;
        }}
        draw();
      }});

      resetView.addEventListener("click", () => {{
        zoom = 0.82;
        panX = 0.0;
        panY = 0.0;
        yaw = -0.4;
        pitch = 0.55;
        roll = 0.0;
        preset.value = "isometric";
        draw();
      }});

      const updateSize = () => {{
        const bounds = canvas.parentNode.getBoundingClientRect();
        canvas.width = Math.floor(bounds.width * 1.0);
        canvas.height = 560;
        draw();
      }};
      window.addEventListener("resize", updateSize);
      updateSize();
      draw();
    </script>
  </body>
</html>"""
    path.write_text(html, encoding="utf-8")


def _normalize_formats(formats: Iterable[str] | None) -> list[str]:
    if formats is None:
        return ["stl", "obj", "preview"]
    normalized = []
    for item in formats:
        token = str(item).strip().lower()
        if not token:
            continue
        if token == "html":
            normalized.append("preview")
            continue
        normalized.append(token)
    unique: list[str] = []
    for token in normalized:
        if token not in unique:
            unique.append(token)
    return unique


def _write_exports(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
    output_dir: Path,
    exports: list[str],
    metrics: dict,
) -> dict:
    produced: dict[str, str | None] = {
        "preview_html": None,
        "obj": None,
        "stl": None,
        "step": None,
        "brep": None,
    }
    warnings: list[str] = []
    if not exports:
        return {"Produced": produced, "Warnings": warnings}

    centered_vertices, _, _ = _normalize_mesh(vertices)

    if "stl" in exports:
        path = output_dir / "fairing_surface.stl"
        _write_stl(centered_vertices, faces, path)
        produced["stl"] = str(path)

    if "obj" in exports:
        path = output_dir / "fairing_surface.obj"
        _write_obj(centered_vertices, faces, path)
        produced["obj"] = str(path)

    if "preview" in exports:
        path = output_dir / "geometry_preview.html"
        _write_preview_html(centered_vertices, faces, metrics, path)
        produced["preview_html"] = str(path)

    if "step" in exports or "brep" in exports:
        warnings.append("STEP/BREP 匯出目前需要額外 CAD 匯出鏈接，尚未啟用。")

    return {"Produced": produced, "Warnings": warnings}


def generate_geometry_assets(
    case_dir: str | Path,
    case_name: str,
    curves: dict,
    metrics: dict,
    *,
    exports: Iterable[str] | None = None,
    section_count: int = 64,
    section_points: int = 40,
) -> dict:
    output_dir = Path(case_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    requested = _normalize_formats(exports)
    payload = {
        "CaseName": case_name,
        "RequestedFormats": requested,
    }

    try:
        vertices, faces = _build_surface_mesh(curves, section_count=section_count, section_points=section_points)
    except Exception as exc:
        payload["Status"] = "failed"
        payload["Error"] = str(exc)
        payload["Produced"] = {
            "preview_html": None,
            "obj": None,
            "stl": None,
            "step": None,
            "brep": None,
        }
        payload["Warnings"] = ["geometry export 失敗：" + str(exc)]
        return payload

    if not faces or not vertices:
        payload["Status"] = "skipped"
        payload["Warnings"] = ["geometry mesh 資料不足，已略過匯出"]
        payload["Produced"] = {
            "preview_html": None,
            "obj": None,
            "stl": None,
            "step": None,
            "brep": None,
        }
        return payload

    export_summary = _write_exports(vertices, faces, output_dir, requested, metrics)
    payload.update(export_summary)
    payload["Status"] = "ok"
    payload["MeshVertices"] = len(vertices)
    payload["MeshTriangles"] = len(faces)
    payload["Warnings"] = payload["Warnings"] if payload.get("Warnings") else export_summary.get("Warnings", [])
    return payload
