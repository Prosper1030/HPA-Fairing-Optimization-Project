"""
Generate lightweight axisymmetric SU2 benchmark meshes.

The meshes created here are not intended to replace a full 3D external-flow
mesh. They provide a repeatable 2D axisymmetric benchmark so shortlisted
fairings can be compared in SU2 without a separate meshing package.
"""

from __future__ import annotations

from pathlib import Path
import json

import numpy as np


AXIS_MARKER_ID = 1
FAIRING_MARKER_ID = 2
FARFIELD_MARKER_ID = 3

MARKER_NAMES = {
    AXIS_MARKER_ID: "axis",
    FAIRING_MARKER_ID: "fairing",
    FARFIELD_MARKER_ID: "farfield",
}

DEFAULT_AXISYMMETRIC_MESH_OPTIONS = {
    "upstream_factor": 0.75,
    "downstream_factor": 2.0,
    "radial_factor": 4.0,
    "min_farfield_radius_factor": 1.5,
    "target_triangles": 2800,
    "quality_min_angle_deg": 28.0,
}


class AxisymmetricMeshError(RuntimeError):
    """Raised when an axisymmetric benchmark mesh cannot be generated."""


def _triangle():
    try:
        import triangle as triangle_module
    except ImportError as exc:
        raise AxisymmetricMeshError(
            "axisymmetric_2d mesh mode 需要 `triangle` 套件。請先執行 `source activate_env.sh`。"
        ) from exc
    return triangle_module


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def build_area_equivalent_radius_profile(curves: dict) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(curves["x"], dtype=float)
    width_half = np.asarray(curves["width_half"], dtype=float)
    super_height = np.maximum(np.asarray(curves["z_upper"], dtype=float) - np.asarray(curves["z_lower"], dtype=float), 0.0)

    # Area-equivalent radius based on an ellipse-like sectional area:
    # A ~= 0.5 * pi * a * h  =>  r_eq = sqrt(A / pi) = sqrt(0.5 * a * h)
    radius = np.sqrt(np.maximum(0.5 * width_half * super_height, 0.0))
    if len(radius) >= 1:
        radius[0] = 0.0
        radius[-1] = 0.0
    return x, radius


def _dedupe_profile_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped = [points[0]]
    for point in points[1:]:
        if abs(point[0] - deduped[-1][0]) > 1e-9 or abs(point[1] - deduped[-1][1]) > 1e-9:
            deduped.append(point)
    return deduped


def _polygon_definition(curves: dict, options: dict) -> dict:
    x, radius = build_area_equivalent_radius_profile(curves)
    body_points = _dedupe_profile_points([(float(xi), float(ri)) for xi, ri in zip(x, radius)])
    if len(body_points) < 3:
        raise AxisymmetricMeshError("外形截面點數不足，無法建立 axisymmetric mesh")

    length = float(curves["L"])
    max_radius = max(point[1] for point in body_points)
    upstream = float(options["upstream_factor"]) * length
    downstream = float(options["downstream_factor"]) * length
    min_radius = float(options["min_farfield_radius_factor"]) * length
    farfield_radius = max(float(options["radial_factor"]) * max_radius, min_radius)

    vertices = [
        (-upstream, 0.0),
        (0.0, 0.0),
        *body_points[1:-1],
        (length, 0.0),
        (length + downstream, 0.0),
        (length + downstream, farfield_radius),
        (-upstream, farfield_radius),
    ]

    segments: list[tuple[int, int]] = []
    segment_markers: list[int] = []

    # Upstream axis section.
    segments.append((0, 1))
    segment_markers.append(AXIS_MARKER_ID)

    # Body wall segments.
    for index in range(1, len(body_points)):
        segments.append((index, index + 1))
        segment_markers.append(FAIRING_MARKER_ID)

    tail_vertex = len(body_points)
    downstream_axis_vertex = tail_vertex + 1
    top_right_vertex = tail_vertex + 2
    top_left_vertex = tail_vertex + 3

    segments.append((tail_vertex, downstream_axis_vertex))
    segment_markers.append(AXIS_MARKER_ID)

    segments.append((downstream_axis_vertex, top_right_vertex))
    segment_markers.append(FARFIELD_MARKER_ID)
    segments.append((top_right_vertex, top_left_vertex))
    segment_markers.append(FARFIELD_MARKER_ID)
    segments.append((top_left_vertex, 0))
    segment_markers.append(FARFIELD_MARKER_ID)

    return {
        "body_points": body_points,
        "vertices": np.asarray(vertices, dtype=float),
        "segments": np.asarray(segments, dtype=int),
        "segment_markers": np.asarray(segment_markers, dtype=int).reshape(-1, 1),
        "length": length,
        "max_radius": max_radius,
        "farfield_radius": farfield_radius,
        "bounds": {
            "x_min": -upstream,
            "x_max": length + downstream,
            "r_max": farfield_radius,
        },
    }


def _triangulate_polygon(polygon: dict, options: dict) -> dict:
    triangle_module = _triangle()
    domain_area = (polygon["bounds"]["x_max"] - polygon["bounds"]["x_min"]) * polygon["bounds"]["r_max"]
    target_triangles = max(int(options["target_triangles"]), 200)
    max_area = domain_area / float(target_triangles)
    min_angle = float(options["quality_min_angle_deg"])
    triangulation_flags = f"pq{min_angle:.0f}a{max_area:.8f}"

    result = triangle_module.triangulate(
        {
            "vertices": polygon["vertices"],
            "segments": polygon["segments"],
            "segment_markers": polygon["segment_markers"],
        },
        triangulation_flags,
    )
    if "triangles" not in result or len(result["triangles"]) == 0:
        raise AxisymmetricMeshError("triangle 沒有成功產生內部單元")
    return result


def _write_su2_mesh(mesh: dict, output_path: Path) -> None:
    vertices = np.asarray(mesh["vertices"], dtype=float)
    triangles = np.asarray(mesh["triangles"], dtype=int)
    segments = np.asarray(mesh["segments"], dtype=int)
    segment_markers = np.asarray(mesh["segment_markers"], dtype=int).reshape(-1)

    lines = [
        "NDIME= 2",
        f"NPOIN= {len(vertices)}",
    ]
    for x_value, r_value in vertices:
        lines.append(f"{float(x_value):.12f} {float(r_value):.12f}")

    lines.append(f"NELEM= {len(triangles)}")
    for triangle in triangles:
        lines.append(f"5 {int(triangle[0])} {int(triangle[1])} {int(triangle[2])}")

    marker_ids = [AXIS_MARKER_ID, FAIRING_MARKER_ID, FARFIELD_MARKER_ID]
    lines.append(f"NMARK= {len(marker_ids)}")
    for marker_id in marker_ids:
        marker_segments = segments[segment_markers == marker_id]
        lines.append(f"MARKER_TAG= {MARKER_NAMES[marker_id]}")
        lines.append(f"MARKER_ELEMS= {len(marker_segments)}")
        for segment in marker_segments:
            lines.append(f"3 {int(segment[0])} {int(segment[1])}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_axisymmetric_mesh(
    curves: dict,
    output_path: str | Path,
    *,
    options: dict | None = None,
) -> dict:
    resolved_options = dict(DEFAULT_AXISYMMETRIC_MESH_OPTIONS)
    if options:
        resolved_options.update(options)

    polygon = _polygon_definition(curves, resolved_options)
    triangulation = _triangulate_polygon(polygon, resolved_options)
    output_path = Path(output_path)
    _write_su2_mesh(triangulation, output_path)

    metadata = {
        "MeshMode": "axisymmetric_2d",
        "Nodes": int(len(triangulation["vertices"])),
        "Elements": int(len(triangulation["triangles"])),
        "BoundaryElements": int(len(triangulation["segments"])),
        "BodyStations": int(len(polygon["body_points"])),
        "MaxTriangleArea": float(
            (polygon["bounds"]["x_max"] - polygon["bounds"]["x_min"]) * polygon["bounds"]["r_max"]
            / float(resolved_options["target_triangles"])
        ),
        "ProfileMaxRadius": float(polygon["max_radius"]),
        "FarfieldBounds": polygon["bounds"],
        "Markers": dict(MARKER_NAMES),
        "MeshFile": str(output_path),
        "Options": resolved_options,
    }
    metadata_path = output_path.with_name("mesh_metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )
    metadata["MetadataFile"] = str(metadata_path)
    return metadata
