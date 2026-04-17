"""
Generate a Gmsh-backed 3D SU2 mesh for low-speed fairing validation.

This module supports two mesh topologies:

1. A tetra-only cut-box mesh for fast smoke tests.
2. A Gmsh boundary-layer extrusion workflow inspired by the official
   `naca_boundary_layer_3d.py` example, which adds prism-dominant layers
   around the fairing before filling the outer domain.
"""

from __future__ import annotations

from pathlib import Path
import json

import numpy as np


DEFAULT_GMSH_3D_MESH_OPTIONS = {
    "section_points": 20,
    "body_section_count": 18,
    "loft_max_degree": 2,
    "make_ruled": True,
    "upstream_factor": 1.5,
    "downstream_factor": 3.5,
    "lateral_factor": 2.8,
    "vertical_factor": 2.8,
    "min_lateral_factor": 0.65,
    "min_vertical_factor": 0.65,
    "near_body_size_factor": 0.040,
    "farfield_size_factor": 0.22,
    "wake_size_factor": 0.070,
    "wake_length_factor": 1.6,
    "wake_half_width_factor": 0.70,
    "tip_trim_scale_factor": 0.004,
    "surface_mesh_size_factor": 0.020,
    "use_boundary_layer_extrusion": False,
    "boundary_layer_recombine": True,
    "boundary_layer_num_layers": 7,
    "boundary_layer_first_height_factor": 2.0e-4,
    "boundary_layer_growth_rate": 1.35,
    "boundary_layer_total_thickness_factor": 0.010,
    "boundary_layer_algorithm_3d": 10,
}

GMSH_TRIANGLE = 2
GMSH_QUAD = 3
GMSH_TETRA = 4
GMSH_HEXAHEDRON = 5
GMSH_PRISM = 6
GMSH_PYRAMID = 7

SU2_LINE = 3
SU2_TRIANGLE = 5
SU2_QUAD = 9
SU2_TETRA = 10
SU2_HEXAHEDRON = 12
SU2_PRISM = 13
SU2_PYRAMID = 14


class Gmsh3DMeshError(RuntimeError):
    """Raised when the Gmsh-backed 3D mesh cannot be created."""


def _gmsh():
    try:
        import gmsh
    except ImportError as exc:
        raise Gmsh3DMeshError(
            "gmsh_3d mesh mode 需要 `gmsh` 套件。請先執行 `source activate_env.sh`。"
        ) from exc
    return gmsh


def _json_default(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _resample_array(x_coords: np.ndarray, values: np.ndarray, sample_x: np.ndarray) -> np.ndarray:
    return np.interp(sample_x, x_coords, values)


def _section_exponents(curves: dict) -> tuple[float, float, float, float]:
    return (
        max(float(curves.get("M_top", 2.5)), 1.2),
        max(float(curves.get("N_top", 2.5)), 1.2),
        max(float(curves.get("M_bot", 2.5)), 1.2),
        max(float(curves.get("N_bot", 2.5)), 1.2),
    )


def _section_profile(
    x_value: float,
    width_half: float,
    z_upper: float,
    z_lower: float,
    top_y_exp: float,
    top_z_exp: float,
    bot_y_exp: float,
    bot_z_exp: float,
    section_points: int,
    length: float,
    min_section_scale: float,
) -> list[tuple[float, float, float]]:
    y_half = max(float(width_half), min_section_scale)
    z_center = 0.5 * (float(z_upper) + float(z_lower))
    total_height = max(float(z_upper) - float(z_lower), min_section_scale)
    half_height = 0.5 * total_height

    points: list[tuple[float, float, float]] = []
    for index in range(section_points):
        theta = (2.0 * np.pi * index) / section_points
        cos_val = np.cos(theta)
        sin_val = np.sin(theta)

        if 0.0 <= theta <= np.pi:
            y_value = y_half * np.sign(cos_val) * (abs(cos_val) ** (2.0 / top_y_exp))
            z_local = half_height * (abs(sin_val) ** (2.0 / top_z_exp))
        else:
            y_value = y_half * np.sign(cos_val) * (abs(cos_val) ** (2.0 / bot_y_exp))
            z_local = -half_height * (abs(sin_val) ** (2.0 / bot_z_exp))

        points.append((float(x_value), float(y_value), float(z_center + z_local)))
    return points


def _section_profiles(curves: dict, options: dict) -> list[list[tuple[float, float, float]]]:
    x_coords = np.asarray(curves["x"], dtype=float)
    width_half = np.asarray(curves["width_half"], dtype=float)
    z_upper = np.asarray(curves["z_upper"], dtype=float)
    z_lower = np.asarray(curves["z_lower"], dtype=float)
    length = float(curves["L"])
    min_section_scale = float(options["tip_trim_scale_factor"]) * length

    section_scale = np.maximum(width_half, z_upper - z_lower)
    valid_indices = np.flatnonzero(section_scale >= min_section_scale)
    if len(valid_indices) >= 2:
        start_index = int(valid_indices[0])
        end_index = int(valid_indices[-1])
    else:
        start_index = 1 if len(x_coords) > 2 else 0
        end_index = len(x_coords) - 2 if len(x_coords) > 2 else len(x_coords) - 1

    section_count = max(int(options["body_section_count"]), len(x_coords))
    sample_x = np.linspace(float(x_coords[start_index]), float(x_coords[end_index]), section_count)
    sampled_width = _resample_array(x_coords, width_half, sample_x)
    sampled_upper = _resample_array(x_coords, z_upper, sample_x)
    sampled_lower = _resample_array(x_coords, z_lower, sample_x)
    top_y_exp, top_z_exp, bot_y_exp, bot_z_exp = _section_exponents(curves)

    profiles: list[list[tuple[float, float, float]]] = []
    for x_value, width_value, upper_value, lower_value in zip(sample_x, sampled_width, sampled_upper, sampled_lower):
        profiles.append(
            _section_profile(
                float(x_value),
                float(width_value),
                float(upper_value),
                float(lower_value),
                top_y_exp,
                top_z_exp,
                bot_y_exp,
                bot_z_exp,
                int(options["section_points"]),
                length,
                min_section_scale,
            )
        )
    return profiles


def _add_section_wire(gmsh, section_points: list[tuple[float, float, float]]) -> int:
    point_tags = [gmsh.model.occ.addPoint(x_value, y_value, z_value) for x_value, y_value, z_value in section_points]
    curve_tags = []
    for index, start_tag in enumerate(point_tags):
        end_tag = point_tags[(index + 1) % len(point_tags)]
        curve_tags.append(gmsh.model.occ.addLine(start_tag, end_tag))
    return gmsh.model.occ.addWire(curve_tags, checkClosed=True)


def _box_bounds(curves: dict, options: dict) -> dict:
    length = float(curves["L"])
    width_half = np.asarray(curves["width_half"], dtype=float)
    z_upper = np.asarray(curves["z_upper"], dtype=float)
    z_lower = np.asarray(curves["z_lower"], dtype=float)

    y_extent = max(np.max(np.abs(width_half)), float(options["min_lateral_factor"]) * length)
    z_upper_extent = max(np.max(z_upper), float(options["min_vertical_factor"]) * length)
    z_lower_extent = min(np.min(z_lower), -float(options["min_vertical_factor"]) * length)

    return {
        "x_min": -float(options["upstream_factor"]) * length,
        "x_max": length + float(options["downstream_factor"]) * length,
        "y_min": -float(options["lateral_factor"]) * y_extent,
        "y_max": float(options["lateral_factor"]) * y_extent,
        "z_min": z_lower_extent - float(options["vertical_factor"]) * abs(z_lower_extent),
        "z_max": z_upper_extent + float(options["vertical_factor"]) * abs(z_upper_extent),
    }


def _boundary_surface_tags(gmsh, volume_tag: int) -> list[int]:
    return [tag for dim, tag in gmsh.model.getBoundary([(3, volume_tag)], oriented=False) if dim == 2]


def _surface_point_entities(gmsh, surface_tags: list[int]) -> list[tuple[int, int]]:
    point_entities: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for surface_tag in surface_tags:
        for entity in gmsh.model.getBoundary([(2, surface_tag)], oriented=False, recursive=True):
            if entity[0] != 0 or entity in seen:
                continue
            seen.add(entity)
            point_entities.append(entity)
    return point_entities


def _configure_gmsh_options(gmsh, *, use_boundary_layer_extrusion: bool, options: dict) -> None:
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 20)
    gmsh.option.setNumber("Mesh.Optimize", 1)
    gmsh.option.setNumber("Mesh.OptimizeNetgen", 1)
    gmsh.option.setNumber(
        "Mesh.Algorithm3D",
        int(options["boundary_layer_algorithm_3d"] if use_boundary_layer_extrusion else 1),
    )


def _classify_boundary_surfaces(gmsh, fluid_volume_tag: int, bounds: dict, tolerance: float) -> tuple[list[int], list[int]]:
    farfield_surfaces: list[int] = []
    fairing_surfaces: list[int] = []
    boundary_entities = gmsh.model.getBoundary([(3, fluid_volume_tag)], oriented=False)

    for dim, tag in boundary_entities:
        if dim != 2:
            continue
        x_min, y_min, z_min, x_max, y_max, z_max = gmsh.model.getBoundingBox(dim, tag)
        touches_box = (
            abs(x_min - bounds["x_min"]) <= tolerance
            or abs(x_max - bounds["x_max"]) <= tolerance
            or abs(y_min - bounds["y_min"]) <= tolerance
            or abs(y_max - bounds["y_max"]) <= tolerance
            or abs(z_min - bounds["z_min"]) <= tolerance
            or abs(z_max - bounds["z_max"]) <= tolerance
        )
        if touches_box:
            farfield_surfaces.append(tag)
        else:
            fairing_surfaces.append(tag)
    return fairing_surfaces, farfield_surfaces


def _configure_mesh_fields(gmsh, curves: dict, fairing_surfaces: list[int], bounds: dict, options: dict) -> dict:
    length = float(curves["L"])
    width_half = np.asarray(curves["width_half"], dtype=float)
    body_half_width = max(float(np.max(width_half)), 0.08 * length)
    near_body_size = float(options["near_body_size_factor"]) * length
    farfield_size = float(options["farfield_size_factor"]) * length
    wake_size = float(options["wake_size_factor"]) * length

    distance_field = gmsh.model.mesh.field.add("Distance")
    gmsh.model.mesh.field.setNumbers(distance_field, "FacesList", fairing_surfaces)

    threshold_field = gmsh.model.mesh.field.add("Threshold")
    gmsh.model.mesh.field.setNumber(threshold_field, "InField", distance_field)
    gmsh.model.mesh.field.setNumber(threshold_field, "SizeMin", near_body_size)
    gmsh.model.mesh.field.setNumber(threshold_field, "SizeMax", farfield_size)
    gmsh.model.mesh.field.setNumber(threshold_field, "DistMin", 0.02 * length)
    gmsh.model.mesh.field.setNumber(threshold_field, "DistMax", 0.35 * length)

    wake_field = gmsh.model.mesh.field.add("Box")
    gmsh.model.mesh.field.setNumber(wake_field, "VIn", wake_size)
    gmsh.model.mesh.field.setNumber(wake_field, "VOut", farfield_size)
    gmsh.model.mesh.field.setNumber(wake_field, "XMin", 0.82 * length)
    gmsh.model.mesh.field.setNumber(
        wake_field,
        "XMax",
        min(length + float(options["wake_length_factor"]) * length, bounds["x_max"]),
    )
    gmsh.model.mesh.field.setNumber(
        wake_field,
        "YMin",
        -float(options["wake_half_width_factor"]) * body_half_width,
    )
    gmsh.model.mesh.field.setNumber(
        wake_field,
        "YMax",
        float(options["wake_half_width_factor"]) * body_half_width,
    )
    gmsh.model.mesh.field.setNumber(wake_field, "ZMin", bounds["z_min"] * 0.15)
    gmsh.model.mesh.field.setNumber(wake_field, "ZMax", bounds["z_max"] * 0.55)

    min_field = gmsh.model.mesh.field.add("Min")
    gmsh.model.mesh.field.setNumbers(min_field, "FieldsList", [threshold_field, wake_field])
    gmsh.model.mesh.field.setAsBackgroundMesh(min_field)

    gmsh.option.setNumber("Mesh.MeshSizeMin", near_body_size * 0.55)
    gmsh.option.setNumber("Mesh.MeshSizeMax", farfield_size)
    _configure_gmsh_options(
        gmsh,
        use_boundary_layer_extrusion=bool(options.get("use_boundary_layer_extrusion", False)),
        options=options,
    )

    return {
        "NearBodySize": near_body_size,
        "FarfieldSize": farfield_size,
        "WakeSize": wake_size,
    }


def _boundary_layer_distribution(length: float, options: dict) -> tuple[list[int], list[float]]:
    num_layers = max(int(options["boundary_layer_num_layers"]), 1)
    growth = max(float(options["boundary_layer_growth_rate"]), 1.0)
    first_height = max(float(options["boundary_layer_first_height_factor"]) * length, 1e-6)
    total_height = max(float(options["boundary_layer_total_thickness_factor"]) * length, first_height)

    if num_layers == 1:
        layer_thicknesses = [total_height]
    elif abs(growth - 1.0) < 1e-9:
        layer_thicknesses = [total_height / num_layers] * num_layers
    else:
        geom_sum = (growth**num_layers - 1.0) / (growth - 1.0)
        base_height = min(first_height, total_height / geom_sum)
        layer_thicknesses = [base_height * (growth**index) for index in range(num_layers)]
        current_total = sum(layer_thicknesses)
        if current_total > 0.0:
            scale_factor = total_height / current_total
            layer_thicknesses = [value * scale_factor for value in layer_thicknesses]

    cumulative = np.cumsum(layer_thicknesses).tolist()
    return [1] * num_layers, cumulative


def _extract_boundary_layer_entities(extbl: list[tuple[int, int]]) -> tuple[list[int], list[int]]:
    top_surfaces: list[int] = []
    layer_volumes: list[int] = []
    seen_surfaces: set[int] = set()
    seen_volumes: set[int] = set()

    for index, dim_tag in enumerate(extbl):
        dim, tag = dim_tag
        if dim != 3:
            continue
        if tag not in seen_volumes:
            seen_volumes.add(tag)
            layer_volumes.append(tag)
        if index > 0 and extbl[index - 1][0] == 2:
            top_tag = int(extbl[index - 1][1])
            if top_tag not in seen_surfaces:
                seen_surfaces.add(top_tag)
                top_surfaces.append(top_tag)

    if not top_surfaces or not layer_volumes:
        raise Gmsh3DMeshError("Gmsh boundary layer extrusion 沒有產生有效的 top surfaces / volumes")
    return top_surfaces, layer_volumes


def _create_geo_farfield_box(gmsh, bounds: dict, mesh_size: float) -> list[int]:
    x_min = float(bounds["x_min"])
    x_max = float(bounds["x_max"])
    y_min = float(bounds["y_min"])
    y_max = float(bounds["y_max"])
    z_min = float(bounds["z_min"])
    z_max = float(bounds["z_max"])

    p000 = gmsh.model.geo.addPoint(x_min, y_min, z_min, mesh_size)
    p100 = gmsh.model.geo.addPoint(x_max, y_min, z_min, mesh_size)
    p110 = gmsh.model.geo.addPoint(x_max, y_max, z_min, mesh_size)
    p010 = gmsh.model.geo.addPoint(x_min, y_max, z_min, mesh_size)
    p001 = gmsh.model.geo.addPoint(x_min, y_min, z_max, mesh_size)
    p101 = gmsh.model.geo.addPoint(x_max, y_min, z_max, mesh_size)
    p111 = gmsh.model.geo.addPoint(x_max, y_max, z_max, mesh_size)
    p011 = gmsh.model.geo.addPoint(x_min, y_max, z_max, mesh_size)

    l000_100 = gmsh.model.geo.addLine(p000, p100)
    l100_110 = gmsh.model.geo.addLine(p100, p110)
    l110_010 = gmsh.model.geo.addLine(p110, p010)
    l010_000 = gmsh.model.geo.addLine(p010, p000)

    l001_101 = gmsh.model.geo.addLine(p001, p101)
    l101_111 = gmsh.model.geo.addLine(p101, p111)
    l111_011 = gmsh.model.geo.addLine(p111, p011)
    l011_001 = gmsh.model.geo.addLine(p011, p001)

    l000_001 = gmsh.model.geo.addLine(p000, p001)
    l100_101 = gmsh.model.geo.addLine(p100, p101)
    l110_111 = gmsh.model.geo.addLine(p110, p111)
    l010_011 = gmsh.model.geo.addLine(p010, p011)

    bottom_loop = gmsh.model.geo.addCurveLoop([l000_100, l100_110, l110_010, l010_000])
    top_loop = gmsh.model.geo.addCurveLoop([l001_101, l101_111, l111_011, l011_001])
    xmin_loop = gmsh.model.geo.addCurveLoop([l010_000, l000_001, -l011_001, -l010_011])
    xmax_loop = gmsh.model.geo.addCurveLoop([l100_110, l110_111, -l101_111, -l100_101])
    ymin_loop = gmsh.model.geo.addCurveLoop([l000_100, l100_101, -l001_101, -l000_001])
    ymax_loop = gmsh.model.geo.addCurveLoop([l110_010, l010_011, -l111_011, -l110_111])

    return [
        gmsh.model.geo.addPlaneSurface([bottom_loop]),
        gmsh.model.geo.addPlaneSurface([top_loop]),
        gmsh.model.geo.addPlaneSurface([xmin_loop]),
        gmsh.model.geo.addPlaneSurface([xmax_loop]),
        gmsh.model.geo.addPlaneSurface([ymin_loop]),
        gmsh.model.geo.addPlaneSurface([ymax_loop]),
    ]


def _create_boundary_layer_volume(
    gmsh,
    fairing_surfaces: list[int],
    bounds: dict,
    curves: dict,
    options: dict,
) -> tuple[list[int], list[int], dict]:
    point_size = max(float(options["surface_mesh_size_factor"]) * float(curves["L"]), 1e-4)
    occ_points = _surface_point_entities(gmsh, fairing_surfaces)
    if occ_points:
        gmsh.model.mesh.setSize(occ_points, point_size)

    num_elements, heights = _boundary_layer_distribution(float(curves["L"]), options)
    extbl = gmsh.model.geo.extrudeBoundaryLayer(
        [(2, tag) for tag in fairing_surfaces],
        num_elements,
        heights,
        bool(options["boundary_layer_recombine"]),
    )
    top_surfaces, boundary_layer_volumes = _extract_boundary_layer_entities(extbl)

    farfield_point_size = max(float(options["farfield_size_factor"]) * float(curves["L"]), point_size)
    farfield_surfaces = _create_geo_farfield_box(gmsh, bounds, farfield_point_size)
    outer_shell = gmsh.model.geo.addSurfaceLoop(farfield_surfaces)
    inner_shell = gmsh.model.geo.addSurfaceLoop(top_surfaces)
    outer_volume = gmsh.model.geo.addVolume([outer_shell, inner_shell])
    gmsh.model.geo.synchronize()

    return (
        boundary_layer_volumes + [outer_volume],
        farfield_surfaces,
        {
            "Enabled": True,
            "NumLayers": int(len(num_elements)),
            "LayerElementCounts": list(num_elements),
            "CumulativeHeights": heights,
            "TopSurfaceCount": int(len(top_surfaces)),
            "BoundaryLayerVolumeCount": int(len(boundary_layer_volumes)),
            "OuterVolumeTag": int(outer_volume),
        },
    )


def _collect_physical_group_elements_raw(gmsh, dim: int, physical_tag: int) -> list[tuple[int, list[int]]]:
    supported_types = {
        GMSH_TRIANGLE: (SU2_TRIANGLE, 3),
        GMSH_QUAD: (SU2_QUAD, 4),
        GMSH_TETRA: (SU2_TETRA, 4),
        GMSH_HEXAHEDRON: (SU2_HEXAHEDRON, 8),
        GMSH_PRISM: (SU2_PRISM, 6),
        GMSH_PYRAMID: (SU2_PYRAMID, 5),
    }

    collected: list[tuple[int, list[int]]] = []
    seen_tags: set[int] = set()
    for entity_tag in gmsh.model.getEntitiesForPhysicalGroup(dim, physical_tag):
        element_types, element_tags_blocks, node_tags_blocks = gmsh.model.mesh.getElements(dim, entity_tag)
        for element_type, element_tags, node_tags in zip(element_types, element_tags_blocks, node_tags_blocks):
            if element_type not in supported_types:
                continue
            su2_type, node_count = supported_types[element_type]
            connectivity = np.asarray(node_tags, dtype=int).reshape(-1, node_count)
            for element_tag, nodes in zip(element_tags, connectivity):
                element_tag = int(element_tag)
                if element_tag in seen_tags:
                    continue
                seen_tags.add(element_tag)
                collected.append((su2_type, [int(node_tag) for node_tag in nodes]))
    return collected


def _write_su2_mesh(gmsh, output_path: Path, marker_names: dict[int, str], fluid_group_tag: int) -> dict:
    node_tags, coords, _ = gmsh.model.mesh.getNodes()
    if len(node_tags) == 0:
        raise Gmsh3DMeshError("Gmsh 沒有產生任何節點")
    coordinates = np.asarray(coords, dtype=float).reshape(-1, 3)
    coordinate_map = {
        int(tag): (float(x_value), float(y_value), float(z_value))
        for tag, (x_value, y_value, z_value) in zip(node_tags, coordinates)
    }

    raw_volume_elements = _collect_physical_group_elements_raw(gmsh, 3, fluid_group_tag)
    if not raw_volume_elements:
        raise Gmsh3DMeshError("找不到 3D 體網格元素，無法寫出 SU2 mesh")
    volume_type_counts: dict[str, int] = {}
    for su2_type, _ in raw_volume_elements:
        key = str(su2_type)
        volume_type_counts[key] = volume_type_counts.get(key, 0) + 1

    raw_marker_elements: dict[str, list[tuple[int, list[int]]]] = {}
    for dim, physical_tag in gmsh.model.getPhysicalGroups():
        if dim != 2:
            continue
        physical_name = gmsh.model.getPhysicalName(dim, physical_tag)
        raw_marker_elements[physical_name] = _collect_physical_group_elements_raw(gmsh, 2, physical_tag)

    used_node_tags: set[int] = set()
    for _, nodes in raw_volume_elements:
        used_node_tags.update(nodes)
    for elements in raw_marker_elements.values():
        for _, nodes in elements:
            used_node_tags.update(nodes)

    ordered_node_tags = [int(tag) for tag in node_tags if int(tag) in used_node_tags]
    if not ordered_node_tags:
        raise Gmsh3DMeshError("找不到任何被元素引用的有效節點")
    node_map = {tag: index for index, tag in enumerate(ordered_node_tags)}

    volume_elements = [
        (su2_type, [node_map[node_tag] for node_tag in nodes])
        for su2_type, nodes in raw_volume_elements
    ]
    marker_elements = {
        name: [(su2_type, [node_map[node_tag] for node_tag in nodes]) for su2_type, nodes in elements]
        for name, elements in raw_marker_elements.items()
    }

    lines = [
        "NDIME= 3",
        f"NPOIN= {len(ordered_node_tags)}",
    ]
    for node_tag in ordered_node_tags:
        x_value, y_value, z_value = coordinate_map[node_tag]
        lines.append(f"{float(x_value):.12f} {float(y_value):.12f} {float(z_value):.12f}")

    lines.append(f"NELEM= {len(volume_elements)}")
    for su2_type, nodes in volume_elements:
        lines.append(f"{su2_type} {' '.join(str(node) for node in nodes)}")

    lines.append(f"NMARK= {len(marker_elements)}")
    for marker_name in marker_names.values():
        elements = marker_elements.get(marker_name, [])
        lines.append(f"MARKER_TAG= {marker_name}")
        lines.append(f"MARKER_ELEMS= {len(elements)}")
        for su2_type, nodes in elements:
            lines.append(f"{su2_type} {' '.join(str(node) for node in nodes)}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "Nodes": int(len(ordered_node_tags)),
        "VolumeElements": int(len(volume_elements)),
        "VolumeElementTypeCounts": volume_type_counts,
        "MarkerElements": {name: int(len(elements)) for name, elements in marker_elements.items()},
    }


def generate_gmsh_3d_mesh(
    curves: dict,
    output_path: str | Path,
    *,
    options: dict | None = None,
) -> dict:
    gmsh = _gmsh()
    resolved_options = dict(DEFAULT_GMSH_3D_MESH_OPTIONS)
    if options:
        resolved_options.update(options)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    msh_path = output_path.with_suffix(".msh")

    marker_names = {
        1: "fluid",
        2: "fairing",
        3: "farfield",
    }

    gmsh.initialize()
    try:
        gmsh.model.add("fairing_3d")
        gmsh.option.setNumber("General.Terminal", 1)

        profiles = _section_profiles(curves, resolved_options)
        wire_tags = [_add_section_wire(gmsh, profile) for profile in profiles]
        loft_entities = gmsh.model.occ.addThruSections(
            wire_tags,
            makeSolid=True,
            makeRuled=bool(resolved_options["make_ruled"]),
            maxDegree=int(resolved_options["loft_max_degree"]),
        )
        fairing_volume_tag = next(tag for dim, tag in loft_entities if dim == 3)
        bounds = _box_bounds(curves, resolved_options)

        gmsh.model.occ.synchronize()
        fairing_surfaces = _boundary_surface_tags(gmsh, fairing_volume_tag)
        if not fairing_surfaces:
            raise Gmsh3DMeshError("無法取得 fairing 外表面")
        mesh_field_info = _configure_mesh_fields(gmsh, curves, fairing_surfaces, bounds, resolved_options)

        if resolved_options.get("use_boundary_layer_extrusion", False):
            # Keep the fairing shell but remove the solid volume: the fluid
            # domain will be represented by the boundary-layer prism volumes
            # plus an outer tetrahedral box, following Gmsh's official example.
            gmsh.model.occ.remove([(3, fairing_volume_tag)], recursive=False)
            gmsh.model.occ.synchronize()
            fluid_volume_tags, farfield_surfaces, boundary_layer_info = _create_boundary_layer_volume(
                gmsh,
                fairing_surfaces,
                bounds,
                curves,
                resolved_options,
            )
        else:
            box_tag = gmsh.model.occ.addBox(
                bounds["x_min"],
                bounds["y_min"],
                bounds["z_min"],
                bounds["x_max"] - bounds["x_min"],
                bounds["y_max"] - bounds["y_min"],
                bounds["z_max"] - bounds["z_min"],
            )
            fluid_volumes, _ = gmsh.model.occ.cut(
                [(3, box_tag)],
                [(3, fairing_volume_tag)],
                removeObject=True,
                removeTool=True,
            )
            gmsh.model.occ.synchronize()
            fluid_volume_tags = [tag for dim, tag in fluid_volumes if dim == 3]
            if len(fluid_volume_tags) != 1:
                raise Gmsh3DMeshError(f"預期只產生一個流體體積，實際得到 {len(fluid_volume_tags)} 個")

            tolerance = max(float(curves["L"]) * 1e-5, 1e-6)
            fairing_surfaces, farfield_surfaces = _classify_boundary_surfaces(
                gmsh,
                fluid_volume_tags[0],
                bounds,
                tolerance,
            )
            if not fairing_surfaces or not farfield_surfaces:
                raise Gmsh3DMeshError("無法正確辨識 fairing / farfield surfaces")
            boundary_layer_info = {"Enabled": False}

        fluid_group_tag = gmsh.model.addPhysicalGroup(3, fluid_volume_tags, 1)
        gmsh.model.setPhysicalName(3, fluid_group_tag, marker_names[1])
        fairing_group_tag = gmsh.model.addPhysicalGroup(2, fairing_surfaces, 2)
        gmsh.model.setPhysicalName(2, fairing_group_tag, marker_names[2])
        farfield_group_tag = gmsh.model.addPhysicalGroup(2, farfield_surfaces, 3)
        gmsh.model.setPhysicalName(2, farfield_group_tag, marker_names[3])

        gmsh.model.mesh.generate(3)
        gmsh.write(str(msh_path))
        su2_stats = _write_su2_mesh(gmsh, output_path, {2: marker_names[2], 3: marker_names[3]}, fluid_group_tag)
    finally:
        gmsh.finalize()

    metadata = {
        "MeshMode": "gmsh_3d",
        "MeshFile": str(output_path),
        "NativeMshFile": str(msh_path),
        "BodySections": int(len(profiles)),
        "SectionPoints": int(resolved_options["section_points"]),
        "FluidVolumeTags": [int(tag) for tag in fluid_volume_tags],
        "FluidPhysicalGroupTag": int(fluid_group_tag),
        "FairingSurfaceCount": int(len(fairing_surfaces)),
        "FarfieldSurfaceCount": int(len(farfield_surfaces)),
        "FarfieldBounds": bounds,
        "MeshFieldInfo": mesh_field_info,
        "BoundaryLayerInfo": boundary_layer_info,
        "Options": resolved_options,
        **su2_stats,
    }
    metadata_path = output_path.with_name("mesh_metadata.json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False, default=_json_default) + "\n",
        encoding="utf-8",
    )
    metadata["MetadataFile"] = str(metadata_path)
    return metadata
