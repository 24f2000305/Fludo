from __future__ import annotations

import math
import re
from typing import List

import numpy as np
import trimesh

DETAIL_LEVELS = {
    "low": {
        "cylinder_sections": 24,
        "sphere_subdivisions": 3,
        "torus_sections": 32,
        "torus_segments": 48,
    },
    "medium": {
        "cylinder_sections": 48,
        "sphere_subdivisions": 4,
        "torus_sections": 64,
        "torus_segments": 96,
    },
    "high": {
        "cylinder_sections": 96,
        "sphere_subdivisions": 5,
        "torus_sections": 128,
        "torus_segments": 192,
    },
}

_ACTIVE_CFG = DETAIL_LEVELS["medium"]

_ColorMap = {
    "red": "#ff5a5f",
    "blue": "#3d7eff",
    "green": "#34c759",
    "yellow": "#ffd60a",
    "orange": "#ff8c42",
    "purple": "#a855f7",
    "pink": "#ff5fa2",
    "teal": "#3cc1b3",
    "white": "#f5f5f5",
    "black": "#111111",
    "gray": "#8e8e93",
    "grey": "#8e8e93",
}


def _color_from_prompt(prompt: str, fallback: str) -> str:
    low = prompt.lower()
    for name, hex_value in _ColorMap.items():
        if name in low:
            return hex_value
    return fallback


def _hex_to_rgba(hex_color: str) -> List[int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(ch * 2 for ch in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return [r, g, b, 255]


def _apply_color(mesh: trimesh.Trimesh, color_hex: str | None) -> None:
    if not color_hex:
        return
    rgba = _hex_to_rgba(color_hex)
    mesh.visual.face_colors = np.tile(rgba, (len(mesh.faces), 1))


def _box(extents: List[float], translation: List[float], color: str | None = None) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(translation)
    _apply_color(mesh, color)
    return mesh


def _cylinder(radius: float, height: float, translation: List[float], axis: str = "z", color: str | None = None) -> trimesh.Trimesh:
    mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=_ACTIVE_CFG["cylinder_sections"])
    axis = axis.lower()
    if axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0, 1, 0]))
    elif axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1, 0, 0]))
    mesh.apply_translation(translation)
    _apply_color(mesh, color)
    return mesh


def _sphere(radius: float, translation: List[float], color: str | None = None) -> trimesh.Trimesh:
    mesh = trimesh.creation.icosphere(subdivisions=_ACTIVE_CFG["sphere_subdivisions"], radius=radius)
    mesh.apply_translation(translation)
    _apply_color(mesh, color)
    return mesh


def _torus(radius: float, tube_radius: float, translation: List[float], axis: str = "z", color: str | None = None) -> trimesh.Trimesh:
    mesh = trimesh.creation.torus(
        radius=radius,
        tube_radius=tube_radius,
        sections=_ACTIVE_CFG["torus_sections"],
        segments=_ACTIVE_CFG["torus_segments"],
    )
    axis = axis.lower()
    if axis == "x":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [0, 1, 0]))
    elif axis == "y":
        mesh.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, [1, 0, 0]))
    mesh.apply_translation(translation)
    _apply_color(mesh, color)
    return mesh


def _detect(prompt: str, keywords: tuple[str, ...]) -> bool:
    low = prompt.lower()
    return any(k in low for k in keywords)


def _humanoid(prompt: str) -> List[trimesh.Trimesh]:
    primary = _color_from_prompt(prompt, "#9aa7ff")
    accent = _color_from_prompt(prompt, "#d6e4ff")
    meshes: List[trimesh.Trimesh] = []
    torso_h = 3.6
    meshes.append(_box([1.8, 1.2, torso_h], [0, 0, torso_h / 2.0], primary))
    meshes.append(_sphere(0.8, [0, 0, torso_h + 0.9], accent))
    shoulder_z = torso_h * 0.75
    arm_len = 2.4
    for side in (-1.2, 1.2):
        meshes.append(_cylinder(0.25, arm_len, [side, 0, shoulder_z], axis="y", color=primary))
        meshes.append(_cylinder(0.22, arm_len * 0.8, [side * 1.6, 0, shoulder_z - arm_len * 0.4], axis="y", color=primary))
        meshes.append(_box([0.4, 0.6, 0.3], [side * 2.1, 0, shoulder_z - arm_len * 0.8], "#ffcd8a"))
    hip_z = torso_h * 0.2
    leg_len = 2.6
    for side in (-0.7, 0.7):
        meshes.append(_cylinder(0.35, leg_len, [side, 0, hip_z], axis="y", color=primary))
        meshes.append(_cylinder(0.3, leg_len * 0.8, [side * 1.1, 0, hip_z - leg_len * 0.4], axis="y", color=primary))
        meshes.append(_box([0.45, 1.0, 0.25], [side * 1.2, 0.5, hip_z - leg_len * 0.9], "#46506b"))
    return meshes


def _delivery_bot(prompt: str) -> List[trimesh.Trimesh]:
    primary = _color_from_prompt(prompt, "#9aa7ff")
    meshes: List[trimesh.Trimesh] = []
    meshes.append(_box([2.2, 2.6, 0.8], [0, 0, 0.4], primary))
    meshes.append(_cylinder(0.55, 3.2, [0, 0, 2.0], color=primary))
    meshes.append(_box([1.6, 1.6, 0.18], [0, 0, 3.0], "#d6e4ff"))
    for side in (-1.1, 1.1):
        meshes.append(_torus(0.75, 0.22, [side, 1.2, 0.5], axis="x", color="#2b3145"))
        meshes.append(_torus(0.75, 0.22, [side, -1.2, 0.5], axis="x", color="#2b3145"))
    return meshes


def _tracked_bot(prompt: str) -> List[trimesh.Trimesh]:
    primary = _color_from_prompt(prompt, "#7582a6")
    accent = _color_from_prompt(prompt, "#9aa7ff")
    meshes: List[trimesh.Trimesh] = []
    meshes.append(_box([3.4, 4.6, 1.0], [0, 0, 0.5], primary))
    meshes.append(_box([1.8, 2.4, 0.9], [0, 0, 1.7], accent))
    meshes.append(_cylinder(0.45, 1.2, [0, 0, 2.4], color="#d6e4ff"))
    meshes.append(_box([0.6, 1.0, 0.4], [0, 0, 3.0], "#ffd670"))
    for side in (-2.0, 2.0):
        meshes.append(_box([0.6, 4.8, 0.9], [side, 0, 0.45], "#222833"))
    return meshes


def _drone(prompt: str) -> List[trimesh.Trimesh]:
    primary = _color_from_prompt(prompt, "#9aa7ff")
    meshes: List[trimesh.Trimesh] = []
    arm = 3.0
    meshes.append(_box([arm, 0.2, 0.12], [0, 0, 0.06], primary))
    meshes.append(_box([0.2, arm, 0.12], [0, 0, 0.06], primary))
    for ox, oy in ((arm / 2, arm / 2), (arm / 2, -arm / 2), (-arm / 2, arm / 2), (-arm / 2, -arm / 2)):
        meshes.append(_cylinder(0.6, 0.2, [ox, oy, 0.35], color="#20262f"))
        meshes.append(_cylinder(0.55, 0.05, [ox, oy, 0.5], axis="y", color="#d6e4ff"))
    return meshes


def _arm(prompt: str) -> List[trimesh.Trimesh]:
    primary = _color_from_prompt(prompt, "#9aa7ff")
    meshes: List[trimesh.Trimesh] = []
    base = _cylinder(1.0, 0.5, [0, 0, 0.25], color=primary)
    meshes.append(base)
    z = 0.5
    for i in range(5):
        radius = 0.45 - i * 0.05
        segment = _cylinder(radius, 1.4, [0, 0.6 * (i + 1), z + 0.7], axis="y", color=primary)
        meshes.append(segment)
        z += 0.7
    meshes.append(_box([0.6, 0.2, 0.4], [0, 3.6, z + 0.5], "#ffcd8a"))
    return meshes


def _spider(prompt: str) -> List[trimesh.Trimesh]:
    primary = _color_from_prompt(prompt, "#9aa7ff")
    accent = _color_from_prompt(prompt, "#d6e4ff")
    meshes: List[trimesh.Trimesh] = []
    body_len = 3.2
    meshes.append(_box([1.6, body_len, 0.8], [0, 0, 0.4], primary))
    meshes.append(_sphere(0.8, [0, 0.6, 1.2], accent))
    leg_len = 2.0
    for side in (-1, 1):
        for i, offset in enumerate((-1.5, -0.5, 0.5, 1.5)):
            base = [side * 0.9, offset, 0.6]
            meshes.append(_cylinder(0.18, leg_len, base, axis="x", color=primary))
            tip = [side * (0.9 + leg_len), offset + 0.4 * side, 0.2]
            meshes.append(_box([0.25, 0.4, 0.2], tip, "#46506b"))
    return meshes


def _quadruped(prompt: str) -> List[trimesh.Trimesh]:
    primary = _color_from_prompt(prompt, "#9aa7ff")
    accent = _color_from_prompt(prompt, "#d6e4ff")
    meshes: List[trimesh.Trimesh] = []
    body = _box([3.0, 1.2, 1.0], [0, 0, 1.0], primary)
    meshes.append(body)
    head = _box([1.0, 1.0, 0.8], [1.8, 0, 1.4], accent)
    meshes.append(head)
    for side in (-1, 1):
        for offset in (-1.1, 1.1):
            hip = _cylinder(0.28, 1.2, [side * 0.7, offset, 0.8], axis="x", color=primary)
            meshes.append(hip)
            shin = _cylinder(0.24, 1.0, [side * 1.6, offset, 0.4], axis="x", color=primary)
            meshes.append(shin)
            foot = _box([0.4, 0.6, 0.2], [side * 2.0, offset, 0.15], "#46506b")
            meshes.append(foot)
    return meshes


def _sphere_scout(prompt: str) -> List[trimesh.Trimesh]:
    primary = _color_from_prompt(prompt, "#8da2ff")
    meshes: List[trimesh.Trimesh] = []
    meshes.append(_sphere(1.5, [0, 0, 1.5], primary))
    meshes.append(_box([0.6, 1.4, 0.3], [0, 1.7, 1.4], "#ffd670"))
    for side in (-1.2, 1.2):
        meshes.append(_cylinder(0.35, 1.2, [side, 0, 0.7], color="#2b3145"))
        meshes.append(_torus(0.55, 0.18, [side, 0.8, 0.7], axis="x", color="#2b3145"))
        meshes.append(_torus(0.55, 0.18, [side, -0.8, 0.7], axis="x", color="#2b3145"))
    return meshes


def _default_core(prompt: str) -> List[trimesh.Trimesh]:
    primary = _color_from_prompt(prompt, "#9aa7ff")
    meshes: List[trimesh.Trimesh] = []
    meshes.append(_box([2.4, 2.0, 1.2], [0, 0, 0.6], primary))
    meshes.append(_box([1.6, 1.2, 2.0], [0, 0, 2.0], primary))
    meshes.append(_cylinder(0.8, 1.6, [0, 0, 3.2], color="#d6e4ff"))
    return meshes


def generate_glb(prompt: str) -> bytes:
    prompt_clean = prompt.strip()
    if not prompt_clean:
        raise ValueError("prompt is required")
    meshes: List[trimesh.Trimesh]
    if _detect(prompt_clean, ("spider", "arachnid")):
        meshes = _spider(prompt_clean)
    elif _detect(prompt_clean, ("quadruped", "dog", "cat robot")):
        meshes = _quadruped(prompt_clean)
    elif _detect(prompt_clean, ("scout", "sphere robot", "ball robot")):
        meshes = _sphere_scout(prompt_clean)
    elif _detect(prompt_clean, ("humanoid", "android", "biped")):
        meshes = _humanoid(prompt_clean)
    elif _detect(prompt_clean, ("delivery robot", "service robot", "wheeled")):
        meshes = _delivery_bot(prompt_clean)
    elif _detect(prompt_clean, ("tracked", "tank", "exploration")):
        meshes = _tracked_bot(prompt_clean)
    elif _detect(prompt_clean, ("drone", "quadcopter")):
        meshes = _drone(prompt_clean)
    elif _detect(prompt_clean, ("robot arm", "manipulator", "6dof")):
        meshes = _arm(prompt_clean)
    else:
        meshes = _default_core(prompt_clean)
    if not meshes:
        raise ValueError("no geometry generated")
    scene = trimesh.Scene()
    for mesh in meshes:
        scene.add_geometry(mesh)
    data = scene.export(file_type="glb")
    if isinstance(data, str):
        data = data.encode("utf-8")
    return data
