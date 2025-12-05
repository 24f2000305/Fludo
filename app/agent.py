from __future__ import annotations

import os
import json
import copy
import math
import re
from typing import Any, Dict, List


SYSTEM_PROMPT = (
    "You are an expert 3D CAD modeling agent. Create realistic 3D object specifications from natural language.\n\n"
    "SCHEMA:\n"
    "{\n"
    "  \"objects\": [\n"
    "    {\n"
    "      \"id\": \"unique_name\",\n"
    "      \"type\": \"box|cylinder|sphere|cone|torus|torusknot|plane\",\n"
    "      \"params\": { width, depth, height (box) | radius, depth (cylinder) | radius (sphere) | radius, height (cone) | radius, tube (torus) | color: \"#RRGGBB\" },\n"
    "      \"transform\": {\n"
    "        \"position\": [x, y, z],\n"
    "        \"rotation\": [rx, ry, rz],  // radians\n"
    "        \"scale\": [sx, sy, sz]\n"
    "      }\n"
    "    }\n"
    "  ]\n"
    "}\n\n"
    "CRITICAL RULES:\n"
    "1. For COMPLEX OBJECTS (bicycle, chair, table, car, etc.), create REALISTIC COMPOSITE models with many parts\n"
    "2. Use appropriate primitive shapes: cylinders for tubes/wheels, torus for wheel rims, boxes for frames\n"
    "3. Position and orient parts ACCURATELY to form recognizable objects\n"
    "4. Use realistic proportions and dimensions (e.g., bicycle wheels are torus/cylinder combos, frame uses thin cylinders)\n"
    "5. For wheels: use torus (rim) + cylinder (tire) + cylinder (hub) + thin cylinders (spokes)\n\n"
    "BICYCLE EXAMPLE (REFERENCE THIS):\n"
    "- Front wheel: torus rim (radius 35, tube 2), cylinder tire (radius 37, depth 4), cylinder hub (radius 2, depth 3), 8-12 spoke cylinders (radius 0.2)\n"
    "- Rear wheel: same structure, positioned at [0,0,-80]\n"
    "- Frame: cylinders for top tube, down tube, seat tube, chainstays, seatstays (radius 1-1.5)\n"
    "- Handlebars: curved cylinders or torus sections\n"
    "- Seat: box or sphere section\n"
    "- Pedals: small boxes\n\n"
    "For editing: preserve existing objects and modify only what's requested.\n"
    "Return ONLY valid JSON. No markdown, no explanations.\n"
)


COLOR_KEYWORDS = {
    "bright red": "#ff4b5c",
    "red": "#ff4b5c",
    "blue": "#3d7eff",
    "navy": "#2b4c9a",
    "light blue": "#7ab8ff",
    "green": "#34c759",
    "lime": "#a8f152",
    "emerald": "#2ecc71",
    "yellow": "#ffd60a",
    "gold": "#f5c542",
    "orange": "#ff8c42",
    "purple": "#a855f7",
    "violet": "#8f5bff",
    "pink": "#ff5fa2",
    "magenta": "#ff2d95",
    "cyan": "#4dd0e1",
    "aqua": "#4dd0e1",
    "turquoise": "#2ad7b6",
    "white": "#f5f5f5",
    "black": "#111111",
    "gray": "#8e8e93",
    "grey": "#8e8e93",
    "silver": "#b0b8c5",
    "bronze": "#b07d3c",
    "copper": "#b87333",
    "teal": "#3cc1b3",
    "brown": "#8b5a2b"
}


TYPE_SYNONYMS: Dict[str, set[str]] = {
    "box": {"box", "cube", "block", "rect", "rectangle", "rectangular"},
    "cylinder": {"cylinder", "tube", "pipe", "column"},
    "sphere": {"sphere", "ball", "orb", "globe"},
    "plane": {"plane", "sheet", "panel", "floor", "ground", "surface"},
    "cone": {"cone", "pyramid"},
    "torus": {"torus", "ring", "donut", "doughnut"},
    "torusknot": {"torus knot", "torusknot", "knot"},
    "external_model": {"model", "import", "mesh", "gltf", "obj", "asset"},
    "assembly": {"assembly", "mechanism", "robot hand", "robotic hand", "gripper", "end effector", "bicycle", "bike"}
}


ORDINAL_KEYWORDS = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
    "fourth": 3,
    "4th": 3,
    "fifth": 4,
    "5th": 4,
    "last": -1,
    "final": -1,
    "previous": -1,
    "current": -1
}


SCALE_UP_WORDS = {"bigger", "larger", "increase", "wider", "taller", "longer", "scale up", "expand", "grow"}
SCALE_DOWN_WORDS = {"smaller", "shorter", "narrower", "reduce", "decrease", "shrink", "scale down", "thin"}
WIDTH_POSITIVE = {"wider", "thicker", "broader"}
WIDTH_NEGATIVE = {"narrower", "thinner", "slimmer"}
HEIGHT_POSITIVE = {"taller", "higher", "raise", "elevate"}
HEIGHT_NEGATIVE = {"shorter", "lower", "shorten", "flatten"}
DEPTH_POSITIVE = {"longer", "deeper", "extend", "stretch"}
DEPTH_NEGATIVE = {"shorter", "shallower", "trim"}


DIMENSION_KEYWORDS = {
    "width",
    "wide",
    "depth",
    "deep",
    "length",
    "long",
    "height",
    "tall",
    "radius",
    "rad",
    "diameter",
    "tube",
    "minor",
    "major",
    "size",
    "thick",
    "thin",
    "thickness",
    "scale",
}


DIRECTION_KEYWORDS = {
    "up": (0.0, 0.0, 1.0),
    "upwards": (0.0, 0.0, 1.0),
    "raise": (0.0, 0.0, 1.0),
    "higher": (0.0, 0.0, 1.0),
    "above": (0.0, 0.0, 1.0),
    "down": (0.0, 0.0, -1.0),
    "lower": (0.0, 0.0, -1.0),
    "drop": (0.0, 0.0, -1.0),
    "below": (0.0, 0.0, -1.0),
    "beneath": (0.0, 0.0, -1.0),
    "under": (0.0, 0.0, -1.0),
    "left": (-1.0, 0.0, 0.0),
    "right": (1.0, 0.0, 0.0),
    "forward": (0.0, 1.0, 0.0),
    "ahead": (0.0, 1.0, 0.0),
    "front": (0.0, 1.0, 0.0),
    "back": (0.0, -1.0, 0.0),
    "backward": (0.0, -1.0, 0.0),
    "toward": (0.0, 1.0, 0.0),
    "towards": (0.0, 1.0, 0.0)
}


ROTATION_AXIS_HINTS = {
    "x": 0,
    "x-axis": 0,
    "roll": 0,
    "y": 1,
    "y-axis": 1,
    "yaw": 1,
    "z": 2,
    "z-axis": 2,
    "pitch": 2
}


ADD_KEYWORDS = {"add", "include", "spawn", "create", "new", "another", "place", "insert", "generate"}
CLONE_KEYWORDS = {"duplicate", "copy", "clone"}
REPLACE_KEYWORDS = {"replace", "swap", "switch"}
ADD_PHRASES = {"make a", "make an", "build a", "build another", "create a", "create an"}


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _extract_numbers(text: str) -> List[float]:
    nums = re.findall(r"[-+]?\d*\.?\d+", text)
    return [float(n) for n in nums]


def _extract_position_triplet(text: str) -> List[float] | None:
    match = re.search(r"(?:at|to)\s*\(?\s*([-+]?\d*\.?\d+)\s*[,\s]+([-+]?\d*\.?\d+)\s*[,\s]+([-+]?\d*\.?\d+)", text)
    if not match:
        return None
    return [float(match.group(1)), float(match.group(2)), float(match.group(3))]


def _color_from_text(text: str) -> str | None:
    lowered = text.lower()
    for key, value in sorted(COLOR_KEYWORDS.items(), key=lambda kv: -len(kv[0])):
        if key in lowered:
            return value
    return None


def _colors_in_text(text: str) -> set[str]:
    return {color for _, color in _color_mentions(text)}


def _color_mentions(text: str) -> List[tuple[int, str]]:
    lowered = text.lower()
    mentions: List[tuple[int, str]] = []
    used = [False] * len(lowered)
    for key, value in sorted(COLOR_KEYWORDS.items(), key=lambda kv: -len(kv[0])):
        pattern = re.compile(r"\b" + re.escape(key) + r"\b")
        for match in pattern.finditer(lowered):
            start, end = match.span()
            if any(used[i] for i in range(start, end)):
                continue
            for idx in range(start, end):
                used[idx] = True
            mentions.append((start, value))
    mentions.sort(key=lambda item: item[0])
    return mentions


def _generate_id(base: str, spec: Dict[str, Any] | None) -> str:
    existing: set[str] = set()
    if spec:
        for obj in spec.get("objects", []):
            obj_id = str(obj.get("id", ""))
            if obj_id:
                existing.add(obj_id)
    index = 1
    candidate = f"{base}{index}"
    while candidate in existing:
        index += 1
        candidate = f"{base}{index}"
    return candidate


def _match_type(type_name: str, text: str) -> bool:
    synonyms = TYPE_SYNONYMS.get(type_name, {type_name})
    return any(word in text for word in synonyms)


def _find_targets(spec: Dict[str, Any] | None, text: str, *, fallback: bool = False) -> List[Dict[str, Any]]:
    if not spec:
        return []
    objects = spec.get("objects", [])
    if not objects:
        return []
    lowered = text.lower()
    text_colors = _colors_in_text(text)
    color_order: Dict[str, int] = {}
    for idx, (_, color) in enumerate(_color_mentions(text)):
        color_order.setdefault(color, idx)
    matches: list[tuple[int, Dict[str, Any]]] = []
    for idx, obj in enumerate(objects):
        score = 0
        obj_id = str(obj.get("id", "")).lower()
        obj_type = str(obj.get("type", "")).lower()
        if obj_id and obj_id in lowered:
            score += 5
        if obj_type and _match_type(obj_type, lowered):
            score += 3
        obj_color = str(obj.get("params", {}).get("color", "")).lower()
        if obj_color:
            if obj_color in color_order:
                order_idx = color_order[obj_color]
                score += max(1, 6 - min(order_idx, 5))
            elif obj_color in text_colors:
                score += 3
        for word, ordinal_index in ORDINAL_KEYWORDS.items():
            if word in lowered:
                target_index = ordinal_index if ordinal_index >= 0 else len(objects) - 1
                if target_index == idx:
                    score += 2
        if score > 0:
            matches.append((score, obj))
    if matches:
        matches.sort(key=lambda item: item[0], reverse=True)
        return [obj for _, obj in matches]
    if fallback:
        return [objects[-1]]
    return []


def _ensure_transform(obj: Dict[str, Any]) -> Dict[str, List[float]]:
    transform = obj.setdefault("transform", {})
    position = transform.setdefault("position", [0.0, 0.0, 0.0])
    rotation = transform.setdefault("rotation", [0.0, 0.0, 0.0])
    scale = transform.setdefault("scale", [1.0, 1.0, 1.0])
    # Ensure lists are exactly length 3
    if len(position) != 3:
        transform["position"] = [float(position[i]) if i < len(position) else 0.0 for i in range(3)]
    if len(rotation) != 3:
        transform["rotation"] = [float(rotation[i]) if i < len(rotation) else 0.0 for i in range(3)]
    if len(scale) != 3:
        transform["scale"] = [float(scale[i]) if i < len(scale) else 1.0 for i in range(3)]
    return transform  # type: ignore[return-value]


def _apply_color_change(targets: List[Dict[str, Any]], text: str) -> bool:
    mentions = _color_mentions(text)
    if not mentions:
        return False
    color = mentions[-1][1]
    changed = False
    for obj in targets:
        params = obj.setdefault("params", {})
        if params.get("color") != color:
            params["color"] = color
            changed = True
    return changed


def _adjust_param(params: Dict[str, Any], key: str, numbers: List[float], up: bool, down: bool) -> bool:
    if key not in params:
        return False
    current = float(params.get(key, 1.0))
    if numbers:
        params[key] = max(0.001, float(numbers[0]))
        return True
    if up:
        params[key] = max(0.001, current * 1.25)
        return True
    if down:
        params[key] = max(0.001, current * 0.8)
        return True
    return False


def _apply_dimension_change(targets: List[Dict[str, Any]], text: str, numbers: List[float]) -> bool:
    lowered = text.lower()
    scale_up = any(word in lowered for word in SCALE_UP_WORDS)
    scale_down = any(word in lowered for word in SCALE_DOWN_WORDS)
    width_up = any(word in lowered for word in WIDTH_POSITIVE)
    width_down = any(word in lowered for word in WIDTH_NEGATIVE)
    height_up = any(word in lowered for word in HEIGHT_POSITIVE)
    height_down = any(word in lowered for word in HEIGHT_NEGATIVE)
    depth_up = any(word in lowered for word in DEPTH_POSITIVE)
    depth_down = any(word in lowered for word in DEPTH_NEGATIVE)

    changed = False
    for obj in targets:
        params = obj.setdefault("params", {})
        otype = obj.get("type", "")
        if otype == "box":
            changed |= _adjust_param(params, "width", numbers if "width" in lowered or width_up or width_down else [], width_up or scale_up, width_down or scale_down)
            changed |= _adjust_param(params, "depth", numbers if "depth" in lowered or depth_up or depth_down else [], depth_up or scale_up, depth_down or scale_down)
            changed |= _adjust_param(params, "height", numbers if "height" in lowered or height_up or height_down else [], height_up or scale_up, height_down or scale_down)
        elif otype == "cylinder":
            changed |= _adjust_param(params, "radius", numbers if "radius" in lowered or width_up or width_down else [], width_up or scale_up, width_down or scale_down)
            changed |= _adjust_param(params, "depth", numbers if "depth" in lowered or height_up or height_down else [], height_up or scale_up, height_down or scale_down)
        elif otype == "sphere":
            changed |= _adjust_param(params, "radius", numbers, scale_up, scale_down)
        elif otype == "cone":
            changed |= _adjust_param(params, "radius", numbers if "radius" in lowered or width_up or width_down else [], width_up or scale_up, width_down or scale_down)
            changed |= _adjust_param(params, "height", numbers if "height" in lowered or height_up or height_down else [], height_up or scale_up, height_down or scale_down)
        elif otype == "torus":
            changed |= _adjust_param(params, "radius", numbers if "radius" in lowered or scale_up or scale_down else [], scale_up, scale_down)
            changed |= _adjust_param(params, "tube", numbers if "tube" in lowered or width_up or width_down else [], width_up or scale_up, width_down or scale_down)
        elif otype == "torusknot":
            changed |= _adjust_param(params, "radius", numbers if "radius" in lowered or scale_up or scale_down else [], scale_up, scale_down)
            changed |= _adjust_param(params, "tube", numbers if "tube" in lowered or width_up or width_down else [], width_up or scale_up, width_down or scale_down)
        elif otype == "plane":
            changed |= _adjust_param(params, "size", numbers, scale_up, scale_down)

        if not changed and (scale_up or scale_down) and "scale" in lowered:
            factor = numbers[0] if numbers else (1.25 if scale_up else 0.8)
            for obj2 in targets:
                transform = _ensure_transform(obj2)
                transform["scale"] = [max(0.01, float(v) * factor) for v in transform["scale"]]
            changed = True

    return changed


def _apply_directional_move(targets: List[Dict[str, Any]], text: str, numbers: List[float]) -> bool:
    lowered = text.lower()
    if not any(keyword in lowered for keyword in ("move", "shift", "slide", "raise", "lower", "position", "place")):
        return False
    absolute = _extract_position_triplet(lowered)
    changed = False
    if absolute:
        for obj in targets:
            transform = _ensure_transform(obj)
            transform["position"] = absolute
            changed = True
        return changed

    delta = numbers[0] if numbers else 1.0
    for obj in targets:
        transform = _ensure_transform(obj)
        for keyword, vector in DIRECTION_KEYWORDS.items():
            if keyword in lowered:
                transform["position"] = [
                    transform["position"][0] + vector[0] * delta,
                    transform["position"][1] + vector[1] * delta,
                    transform["position"][2] + vector[2] * delta,
                ]
                changed = True
    return changed


def _apply_rotation_change(targets: List[Dict[str, Any]], text: str, numbers: List[float]) -> bool:
    lowered = text.lower()
    if not any(keyword in lowered for keyword in ("rotate", "rotation", "twist", "spin", "turn")):
        return False
    axis_index = 1
    for hint, idx in ROTATION_AXIS_HINTS.items():
        if hint in lowered:
            axis_index = idx
            break
    degrees = numbers[0] if numbers else 90.0
    radians = math.radians(degrees)
    additive = "by" in lowered or "+=" in lowered
    changed = False
    for obj in targets:
        transform = _ensure_transform(obj)
        if additive:
            transform["rotation"][axis_index] = float(transform["rotation"][axis_index]) + radians
        else:
            transform["rotation"][axis_index] = radians
        changed = True
    return changed


def _duplicate_object(target: Dict[str, Any], spec: Dict[str, Any]) -> Dict[str, Any]:
    copy_obj = copy.deepcopy(target)
    base = str(copy_obj.get("type") or "obj")
    copy_obj["id"] = _generate_id(base, spec)
    transform = _ensure_transform(copy_obj)
    transform["position"] = [transform["position"][0] + 2.0, transform["position"][1], transform["position"][2]]
    return copy_obj


def _apply_scale_change(targets: List[Dict[str, Any]], text: str, numbers: List[float]) -> bool:
    lowered = text.lower()
    if "scale" not in lowered:
        return False

    explicit_patterns = (
        r"scale(?:\s+\w+){0,3}\s+to\s+([-+0-9.,\s]+)",
        r"set\s+scale\s+to\s+([-+0-9.,\s]+)",
        r"scale\s*=\s*([-+0-9.,\s]+)",
        r"scale(?:\s+\w+){0,3}\s+at\s+([-+0-9.,\s]+)",
    )
    factor_patterns = (
        r"scale(?:\s+\w+){0,3}\s+by\s+([-+0-9.,\s]+)",
    )

    explicit_numbers: List[float] = []
    for pattern in explicit_patterns:
        match = re.search(pattern, lowered)
        if match:
            explicit_numbers = _extract_numbers(match.group(1))
            if explicit_numbers:
                break

    factor_numbers: List[float] = []
    for pattern in factor_patterns:
        match = re.search(pattern, lowered)
        if match:
            factor_numbers = _extract_numbers(match.group(1))
            if factor_numbers:
                break

    explicit_mentioned = bool(explicit_numbers) or any(phrase in lowered for phrase in ("scale to", "set scale", "scale =", "scale at"))
    factor_mentioned = bool(factor_numbers) or "scale by" in lowered

    if not explicit_numbers and explicit_mentioned:
        explicit_numbers = numbers
    if not factor_numbers and factor_mentioned:
        factor_numbers = numbers

    explicit = bool(explicit_numbers)
    by_factor = bool(factor_numbers)

    changed = False
    if explicit and explicit_numbers:
        values: List[float]
        if len(explicit_numbers) >= 3:
            values = [float(explicit_numbers[0]), float(explicit_numbers[1]), float(explicit_numbers[2])]
        else:
            values = [float(explicit_numbers[0])] * 3
        for obj in targets:
            transform = _ensure_transform(obj)
            transform["scale"] = [max(0.01, v) for v in values]
            changed = True

    if by_factor and factor_numbers:
        factor = float(factor_numbers[0])
        for obj in targets:
            transform = _ensure_transform(obj)
            transform["scale"] = [max(0.01, float(v) * factor) for v in transform["scale"]]
            changed = True

    return changed


def _default_transform() -> Dict[str, List[float]]:
    return {
        "position": [0.0, 0.0, 0.0],
        "rotation": [0.0, 0.0, 0.0],
        "scale": [1.0, 1.0, 1.0],
    }


def _extract_named_value(text: str, keywords: List[str]) -> float | None:
    for keyword in keywords:
        escaped = re.escape(keyword)
        following_value: float | None = None
        pattern = rf"\b{escaped}\b\s*(?:is|=|:|of|with|at|to)?\s*(-?\d*\.?\d+)"
        match = re.search(pattern, text)
        if match:
            try:
                following_value = float(match.group(1))
            except ValueError:
                following_value = None

        preceding_value: float | None = None
        preceding = re.search(rf"([-+]?\d*\.?\d+)\s*(?:units?\s*)?{escaped}\b", text)
        if preceding:
            prefix = text[: preceding.start()]
            prev_word_match = re.search(r"([a-z]+)\s*$", prefix)
            if not (prev_word_match and prev_word_match.group(1) in DIMENSION_KEYWORDS):
                try:
                    preceding_value = float(preceding.group(1))
                except ValueError:
                    preceding_value = None

        if preceding_value is not None:
            return preceding_value
        if following_value is not None:
            return following_value
    return None


def _detect_object_type(text: str) -> str:
    lowered = text.lower()
    for candidate in ("cylinder", "sphere", "cone", "torus", "plane", "box"):
        if _match_type(candidate, lowered):
            return "box" if candidate == "box" else candidate
    return "box"


def _default_params_for_type(obj_type: str, text: str, numbers: List[float]) -> Dict[str, Any]:
    available = list(numbers)

    def consume(value: float) -> None:
        try:
            available.remove(value)
        except ValueError:
            pass

    def param_value(keywords: List[str], default: float) -> float:
        named = _extract_named_value(text, keywords)
        if named is not None:
            consume(named)
            return named
        if available:
            return float(available.pop(0))
        return default

    if obj_type == "box":
        width = param_value(["width", "wide"], 10.0)
        depth = param_value(["depth", "deep", "length", "long"], width)
        height = param_value(["height", "tall"], width)
        return {"width": width, "depth": depth, "height": height}
    if obj_type == "cylinder":
        radius = param_value(["radius", "rad", "diameter"], 5.0)
        depth = param_value(["depth", "height"], 10.0)
        return {"radius": radius, "depth": depth}
    if obj_type == "sphere":
        radius = param_value(["radius", "rad", "size"], 5.0)
        return {"radius": radius}
    if obj_type == "cone":
        radius = param_value(["radius", "base"], 5.0)
        height = param_value(["height"], 10.0)
        return {"radius": radius, "height": height}
    if obj_type == "torus":
        radius = param_value(["radius", "major"], 5.0)
        tube = param_value(["tube", "minor"], 1.5)
        return {"radius": radius, "tube": tube}
    if obj_type == "plane":
        size = param_value(["size", "width", "length"], 10.0)
        return {"size": size}
    if obj_type == "assembly":
        low = text.lower()
        if "bicycle" in low or "bike" in low:
            return {
                "template": "bicycle_basic",
                "wheelRadius": _extract_named_value(text, ["wheel radius", "radius"]) or 3.0,
                "tireThickness": _extract_named_value(text, ["tire", "thickness"]) or 0.4,
                "wheelbase": _extract_named_value(text, ["wheelbase", "length"]) or 8.0,
                "frameHeight": _extract_named_value(text, ["height"]) or 4.0,
                "frameColor": _color_from_text(text) or "#b9c6ff",
            }
        # Default to a robot hand template when asking for mechanisms/grippers
        return {
            "template": "robot_hand",
            "fingerCount": int(_extract_named_value(text, ["fingers", "finger"]) or 5),
            "palmWidth": _extract_named_value(text, ["palm width", "width"]) or 8.0,
            "palmDepth": _extract_named_value(text, ["palm depth", "depth"]) or 2.0,
            "palmHeight": _extract_named_value(text, ["palm height", "height"]) or 10.0,
            "fingerLength": _extract_named_value(text, ["finger length"]) or 8.0,
        }
    return {}


def _is_add_intent(text: str) -> bool:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ADD_KEYWORDS):
        return True
    return any(phrase in lowered for phrase in ADD_PHRASES)


def _build_external_model(url: str, text: str, spec: Dict[str, Any]) -> Dict[str, Any] | None:
    import urllib.parse

    parsed = urllib.parse.urlparse(url)
    ext = parsed.path.split(".")[-1].lower() if "." in parsed.path else ""
    if ext not in ("gltf", "glb", "obj", "fbx", "stl"):
        return None
    obj = {
        "id": _generate_id("model", spec),
        "type": "external_model",
        "params": {"url": url, "format": ext},
        "transform": _default_transform(),
    }
    color = _color_from_text(text)
    if color:
        obj["params"]["color"] = color
    return obj


def _build_composite_objects(text: str, spec: Dict[str, Any], numbers: List[float]) -> List[Dict[str, Any]]:
    """Return a list of primitive objects to approximate a complex noun (e.g., car).

    We intentionally use simple primitives so it works offline without any external assets.
    """
    low = text.lower()
    color = _color_from_text(text)

    def add_id(base: str) -> str:
        return _generate_id(base, spec)

    objs: List[Dict[str, Any]] = []

    # Small helper creators
    def add_box(w: float, d: float, h: float, pos: List[float], rot: List[float] | None = None, color: str | None = None) -> Dict[str, Any]:
        return {
            "id": add_id("box"),
            "type": "box",
            "params": {"width": w, "depth": d, "height": h, **({"color": color} if color else {})},
            "transform": {"position": pos, "rotation": rot or [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        }

    def add_cyl(radius: float, depth: float, pos: List[float], rot: List[float] | None = None, color: str | None = None) -> Dict[str, Any]:
        return {
            "id": add_id("cyl"),
            "type": "cylinder",
            "params": {"radius": radius, "depth": depth, **({"color": color} if color else {})},
            "transform": {"position": pos, "rotation": rot or [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        }

    def add_torus(radius: float, tube: float, pos: List[float], rot: List[float] | None = None, color: str | None = None) -> Dict[str, Any]:
        return {
            "id": add_id("torus"),
            "type": "torus",
            "params": {"radius": radius, "tube": tube, **({"color": color} if color else {})},
            "transform": {"position": pos, "rotation": rot or [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        }

    def add_sphere(radius: float, pos: List[float], color: str | None = None) -> Dict[str, Any]:
        return {
            "id": add_id("sphere"),
            "type": "sphere",
            "params": {"radius": radius, **({"color": color} if color else {})},
            "transform": {"position": pos, "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        }

    # Automotive – car
    if any(k in low for k in ("car", "vehicle", "automobile", "sedan", "suv", "coupe")):
        # Dimensions heuristic (length x width x height)
        length = 8.0
        width = 3.2
        height = 2.2
        # try to extract numbers as L W H if provided
        if len(numbers) >= 3:
            length, width, height = float(numbers[0]), float(numbers[1]), float(numbers[2])

        body = {
            "id": add_id("car_body"),
            "type": "box",
            "params": {"width": width, "depth": length, "height": height, **({"color": color} if color else {})},
            "transform": {"position": [0.0, 0.0, height / 2.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        }
        objs.append(body)

        # Wheels as tori
        wheel_radius = max(0.4, min(width, height) * 0.34)
        wheel_tube = max(0.12, wheel_radius * 0.2)
        wheel_y = 0.0
        z = wheel_radius
        x_offset = width / 2.0 - wheel_radius * 0.8
        y_offset = length / 2.0 - wheel_radius * 0.8
        for ox in (-x_offset, x_offset):
            for oy in (-y_offset, y_offset):
                objs.append(add_torus(wheel_radius, wheel_tube, [ox, oy, z], [math.pi / 2.0, 0.0, 0.0], "#20262f"))
        return objs

    # Mechanical – gear (spur)
    if "gear" in low and ("helical" not in low and "worm" not in low and "bevel" not in low):
        r = 2.0
        thickness = 0.6
        objs.append(add_cyl(r, thickness, [0.0, 0.0, thickness / 2.0], None, color or "#b9c6ff"))
        # teeth as small boxes around
        teeth = 16
        for i in range(teeth):
            ang = (2 * math.pi / teeth) * i
            tx = math.cos(ang) * (r + 0.3)
            ty = math.sin(ang) * (r + 0.3)
            tooth = add_box(0.25, 0.6, thickness * 0.7, [tx, ty, thickness / 2.0], [0.0, 0.0, ang], "#dfe6ff")
            objs.append(tooth)
        return objs

    # Mechanical – pulley / sprocket
    if any(k in low for k in ("pulley", "sprocket", "timing pulley")):
        r = 2.0
        tube = 0.35
        objs.append(add_torus(r, tube, [0.0, 0.0, r * 0.25], [math.pi / 2.0, 0.0, 0.0], color or "#9aa7ff"))
        objs.append(add_cyl(r * 0.2, r * 0.5, [0.0, 0.0, r * 0.25], None, "#2b3145"))
        return objs

    # Structural – I-beam
    if any(k in low for k in ("i-beam", "ibeam", "i beam", "structural beam")):
        h = 4.0; w = 1.8; t = 0.3; d = 8.0
        # Top/bottom flanges + web
        objs.append(add_box(w, d, t, [0.0, 0.0, t / 2.0]))
        objs.append(add_box(w, d, t, [0.0, 0.0, h - t / 2.0]))
        objs.append(add_box(t, d, h - t, [0.0, 0.0, (h - t) / 2.0]))
        return objs

    # Brackets
    if any(k in low for k in ("l-bracket", "l bracket", "mounting bracket")):
        objs.append(add_box(3.0, 0.5, 0.4, [1.5, 0.0, 0.2]))
        objs.append(add_box(0.5, 3.0, 0.4, [0.25, 1.5, 0.2]))
        return objs

    # Pipe flange
    if any(k in low for k in ("flange", "pipe flange")):
        objs.append(add_cyl(2.0, 0.4, [0.0, 0.0, 0.2]))
        objs.append(add_cyl(0.7, 1.2, [0.0, 0.0, 0.6]))
        return objs

    # Fan / impeller
    if any(k in low for k in ("fan", "impeller")):
        objs.append(add_cyl(0.6, 0.4, [0.0, 0.0, 0.2]))
        blades = 6
        for i in range(blades):
            ang = (2 * math.pi / blades) * i
            objs.append(add_box(0.2, 2.0, 0.1, [math.cos(ang) * 1.0, math.sin(ang) * 1.0, 0.25], [0.0, 0.0, ang]))
        return objs

    # Robotics – humanoid or service robot
    if any(k in low for k in ("humanoid", "android", "biped robot", "service robot")):
        torso_h = 4.0
        torso = add_box(2.2, 1.2, torso_h, [0.0, 0.0, torso_h / 2.0], color=color or "#9aa7ff")
        objs.append(torso)
        head = add_sphere(0.9, [0.0, 0.0, torso_h + 1.1], color or "#d6e4ff")
        objs.append(head)
        shoulder_z = torso_h * 0.75
        arm_len = 2.8
        for side in (-1.4, 1.4):
            upper = add_cyl(0.35, arm_len, [side, 0.0, shoulder_z], [0.0, math.pi / 2.0, 0.0], color or "#8da2ff")
            objs.append(upper)
            lower = add_cyl(0.3, arm_len * 0.8, [side * 1.6, 0.0, shoulder_z - arm_len * 0.4], [0.0, math.pi / 2.0, 0.0], color or "#8da2ff")
            objs.append(lower)
            hand = add_box(0.6, 0.4, 0.4, [side * 2.2, 0.0, shoulder_z - arm_len * 0.8], None, color or "#ffcd8a")
            objs.append(hand)
        hip_z = torso_h * 0.2
        leg_len = 3.0
        for side in (-0.8, 0.8):
            upper_leg = add_cyl(0.45, leg_len, [side, 0.0, hip_z], [0.0, math.pi / 2.0, 0.0], color or "#9aa7ff")
            objs.append(upper_leg)
            lower_leg = add_cyl(0.38, leg_len * 0.85, [side * 1.1, 0.0, hip_z - leg_len * 0.4], [0.0, math.pi / 2.0, 0.0], color or "#9aa7ff")
            objs.append(lower_leg)
            foot = add_box(0.6, 1.4, 0.3, [side * 1.3, 0.4, hip_z - leg_len * 0.9], None, color or "#46506b")
            objs.append(foot)
        return objs

    # Robotics – wheeled service robot
    if any(k in low for k in ("service robot", "delivery robot", "wheeled robot", "autonomous cart")):
        base = add_box(2.4, 3.0, 0.8, [0.0, 0.0, 0.4], color or "#9aa7ff")
        objs.append(base)
        column = add_cyl(0.6, 3.5, [0.0, 0.0, 2.2], None, color or "#8da2ff")
        objs.append(column)
        tray = add_box(1.6, 1.6, 0.2, [0.0, 0.0, 3.2], None, color or "#d6e4ff")
        objs.append(tray)
        for side in (-1.2, 1.2):
            wheel = add_torus(0.8, 0.25, [side, 1.3, 0.5], [math.pi / 2.0, 0.0, 0.0], "#2b3145")
            objs.append(wheel)
            wheel_back = add_torus(0.8, 0.25, [side, -1.3, 0.5], [math.pi / 2.0, 0.0, 0.0], "#2b3145")
            objs.append(wheel_back)
        return objs

    # Robotics – tracked exploration robot
    if any(k in low for k in ("tracked robot", "tank robot", "exploration robot")):
        hull = add_box(3.6, 5.0, 1.2, [0.0, 0.0, 0.6], color or "#7582a6")
        objs.append(hull)
        turret = add_box(2.0, 2.6, 1.0, [0.0, 0.0, 1.8], color or "#9aa7ff")
        objs.append(turret)
        mast = add_cyl(0.5, 1.4, [0.0, 0.0, 2.6], None, color or "#d6e4ff")
        objs.append(mast)
        sensor = add_box(0.8, 1.2, 0.5, [0.0, 0.0, 3.3], None, color or "#ffd670")
        objs.append(sensor)
        for side in (-2.1, 2.1):
            tread = add_box(0.7, 5.2, 1.0, [side, 0.0, 0.5], None, "#222833")
            objs.append(tread)
        return objs

    # Robotics – 6DOF arm (very simplified chain)
    if any(k in low for k in ("robot arm", "6 dof", "6dof")):
        z = 0.0
        base = add_cyl(1.2, 0.6, [0.0, 0.0, 0.3], None, color or "#9aa7ff"); objs.append(base); z += 0.6
        for i in range(1, 6):
            link = add_cyl(0.4 + 0.06 * (6 - i), 1.8, [0.0, 0.7 * i, z + 0.9], [math.pi / 2.0, 0.0, 0.0], color or "#9aa7ff")
            objs.append(link)
        gripper = add_box(0.8, 0.3, 0.2, [0.0, 4.2, z + 1.2])
        objs.append(gripper)
        return objs

    # Drones – quadcopter frame
    if any(k in low for k in ("quadcopter", "drone frame", "drone")):
        armL = 3.2
        objs.append(add_box(armL, 0.25, 0.15, [0.0, 0.0, 0.075]))
        objs.append(add_box(0.25, armL, 0.15, [0.0, 0.0, 0.075]))
        r = 0.7
        for ox, oy in ((armL/2, armL/2), (armL/2, -armL/2), (-armL/2, armL/2), (-armL/2, -armL/2)):
            objs.append(add_torus(r, 0.15, [ox, oy, 0.4], [math.pi / 2.0, 0.0, 0.0]))
        return objs

    # Hexacopter body
    if any(k in low for k in ("hexacopter",)):
        armL = 3.6
        # 3 arms at 60-degree intervals (each is a plate to both directions)
        for ang in (0.0, math.pi/3.0, 2*math.pi/3.0):
            dx, dy = math.cos(ang), math.sin(ang)
            objs.append(add_box(armL, 0.25, 0.15, [0.0, 0.0, 0.075], [0.0, 0.0, ang]))
        r = 0.7
        for i in range(6):
            ang = i * (2*math.pi/6)
            ox, oy = math.cos(ang)*(armL/2), math.sin(ang)*(armL/2)
            objs.append(add_torus(r, 0.15, [ox, oy, 0.4], [math.pi/2.0, 0.0, 0.0]))
        return objs

    # Drone propeller
    if any(k in low for k in ("drone propeller", "propeller")):
        hub = add_cyl(0.3, 0.2, [0.0, 0.0, 0.1])
        objs.append(hub)
        blades = 2 if "2" in low else 3 if "3" in low else 2
        for i in range(blades):
            ang = i * (2*math.pi/blades)
            objs.append(add_box(0.2, 2.2, 0.06, [math.cos(ang)*1.1, math.sin(ang)*1.1, 0.13], [0.0, 0.0, ang]))
        return objs

    # Aerospace – rocket / spacecraft / spaceship (stylized)
    if any(k in low for k in ("rocket", "spacecraft", "spaceship", "shuttle")):
        # Main body
        body_r = 1.2
        body_h = 8.0
        color_body = color or "#b9c6ff"
        body = add_cyl(body_r, body_h, [0.0, 0.0, body_h/2.0], [math.pi/2.0, 0.0, 0.0], color_body)
        objs.append(body)

        # Nose cone
        nose_h = max(2.0, body_r * 2.0)
        nose = {
            "id": add_id("cone"),
            "type": "cone",
            "params": {"radius": body_r*0.95, "height": nose_h, **({"color": color_body} if color_body else {})},
            "transform": {"position": [0.0, 0.0, body_h + nose_h/2.0], "rotation": [math.pi/2.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        }
        objs.append(nose)

        # Engine skirt (torus ring)
        ring = add_torus(body_r*0.9, 0.18, [0.0, 0.0, 0.2], [0.0, 0.0, 0.0], "#2b3145")
        objs.append(ring)

        # Fins (4 around)
        fin_w, fin_d, fin_h = 0.15, 1.2, 1.0
        fin_z = 0.6
        fin_color = "#9aa7ff"
        for ang in (0.0, math.pi/2.0, math.pi, 3*math.pi/2.0):
            x = math.cos(ang) * (body_r + fin_w*4)
            y = math.sin(ang) * (body_r + fin_w*4)
            rotz = ang
            objs.append(add_box(fin_w, fin_d, fin_h, [x, y, fin_z], [0.0, 0.0, rotz], fin_color))

        return objs

    # SCARA robot
    if any(k in low for k in ("scara robot", "scara")):
        base = add_cyl(1.0, 0.5, [0.0, 0.0, 0.25])
        objs.append(base)
        arm1 = add_box(2.2, 0.4, 0.25, [1.1, 0.0, 0.75])
        arm2 = add_box(1.8, 0.35, 0.25, [2.0, 0.0, 0.75])
        zaxis = add_cyl(0.25, 1.2, [2.0, 0.0, 1.35])
        ee = add_box(0.6, 0.4, 0.2, [2.0, 0.0, 2.0])
        objs.extend([arm1, arm2, zaxis, ee])
        return objs

    # Delta robot
    if any(k in low for k in ("delta robot",)):
        plate_top = add_box(2.4, 2.4, 0.2, [0.0, 0.0, 2.2])
        plate_bot = add_box(1.2, 1.2, 0.15, [0.0, 0.0, 1.0])
        objs.extend([plate_top, plate_bot])
        for ang in (0.0, 2*math.pi/3.0, 4*math.pi/3.0):
            x, y = math.cos(ang)*1.1, math.sin(ang)*1.1
            objs.append(add_cyl(0.12, 1.2, [x, y, 1.6]))
        return objs

    # Differential drive robot chassis
    if any(k in low for k in ("differential drive", "robot chassis")):
        deck = add_box(3.2, 2.4, 0.2, [0.0, 0.0, 0.1])
        objs.append(deck)
        wheel_r = 0.6
        objs.append(add_torus(wheel_r, 0.15, [0.0, 1.2, wheel_r], [math.pi/2.0, 0.0, 0.0]))
        objs.append(add_torus(wheel_r, 0.15, [0.0, -1.2, wheel_r], [math.pi/2.0, 0.0, 0.0]))
        caster = add_cyl(0.2, 0.3, [-1.3, 0.0, 0.15])
        objs.append(caster)
        return objs

    # Mecanum / omni wheel (stylized)
    if any(k in low for k in ("mecanum wheel", "omni wheel")):
        core = add_torus(1.0, 0.25, [0.0, 0.0, 1.0], [math.pi/2.0, 0.0, 0.0])
        objs.append(core)
        rollers = 8
        for i in range(rollers):
            ang = i * (2*math.pi/rollers)
            objs.append(add_cyl(0.15, 0.8, [math.cos(ang)*0.9, math.sin(ang)*0.9, 1.0], [0.0, ang, math.pi/4.0]))
        return objs

    # Grippers (claw, parallel, 3-finger), suction/vacuum
    if any(k in low for k in ("gripper claw", "parallel gripper", "3-finger", "three-finger")):
        base = add_box(1.2, 0.6, 0.25, [0.0, 0.0, 0.125])
        objs.append(base)
        fingers = 3 if ("3" in low or "three" in low) else 2
        for i in range(fingers):
            ang = (-0.3 if i==0 else 0.3) if fingers==2 else (-0.5 if i==0 else (0.0 if i==1 else 0.5))
            objs.append(add_box(0.9, 0.2, 0.2, [0.6*math.cos(ang), 0.6*math.sin(ang), 0.3], [0.0, 0.0, ang]))
        return objs
    if any(k in low for k in ("vacuum gripper", "suction pad", "suction")):
        plate = add_box(1.2, 1.2, 0.1, [0.0, 0.0, 0.05])
        cup = add_torus(0.5, 0.18, [0.0, 0.0, 0.2], [math.pi/2.0, 0.0, 0.0])
        objs.extend([plate, cup])
        return objs

    # Electronics enclosures (arduino, rpi, pcb, imu)
    if any(k in low for k in ("arduino enclosure", "pcb enclosure", "imu case", "controller enclosure", "controller case")):
        case = add_box(2.6, 1.8, 0.6, [0.0, 0.0, 0.3])
        lid = add_box(2.6, 1.8, 0.1, [0.0, 0.0, 0.65])
        vent1 = add_box(2.2, 0.08, 0.02, [0.0, -0.6, 0.62])
        vent2 = add_box(2.2, 0.08, 0.02, [0.0, -0.3, 0.62])
        objs.extend([case, lid, vent1, vent2])
        return objs

    # 201–300 Robotics & Mechatronics continued
    # Caster wheel
    if any(k in low for k in ("caster wheel",)):
        fork = add_box(0.6, 0.4, 0.2, [0.0, 0.0, 0.9])
        stem = add_cyl(0.15, 0.5, [0.0, 0.0, 1.15])
        wheel = add_torus(0.5, 0.14, [0.0, 0.0, 0.5], [math.pi/2.0, 0.0, 0.0])
        objs.extend([fork, stem, wheel])
        return objs

    # Lidar mount
    if any(k in low for k in ("lidar mount", "lidar")):
        plate = add_box(1.8, 1.8, 0.15, [0.0, 0.0, 0.075])
        ring = add_torus(0.7, 0.12, [0.0, 0.0, 0.4], [math.pi/2.0, 0.0, 0.0])
        standoff = add_cyl(0.12, 0.6, [0.8, 0.8, 0.3])
        objs.extend([plate, ring, standoff])
        return objs

    # Camera gimbal housing / gimbal assembly
    if any(k in low for k in ("gimbal", "camera gimbal", "gimbal assembly", "camera gimbal housing")):
        outer = add_torus(1.2, 0.12, [0.0, 0.0, 1.0])
        inner = add_torus(0.9, 0.1, [0.0, 0.0, 1.0], [0.0, math.pi/2.0, 0.0])
        cam = add_box(0.9, 0.6, 0.5, [0.0, 0.0, 0.9])
        lens = add_cyl(0.25, 0.25, [0.45, 0.0, 0.95], [0.0, math.pi/2.0, 0.0])
        objs.extend([outer, inner, cam, lens])
        return objs

    # Wire routing clip / cable management bracket
    if any(k in low for k in ("wire routing clip", "cable management bracket", "cable clip")):
        base = add_box(1.6, 0.5, 0.2, [0.0, 0.0, 0.1])
        arch = add_torus(0.6, 0.18, [0.0, 0.0, 0.3])
        objs.extend([base, arch])
        return objs

    # Sensor mount (ultrasonic, IR)
    if any(k in low for k in ("sensor mount", "ultrasonic", "ir sensor mount")):
        plate = add_box(2.0, 0.8, 0.15, [0.0, 0.0, 0.075])
        s1 = add_cyl(0.35, 0.4, [-0.5, 0.0, 0.35])
        s2 = add_cyl(0.35, 0.4, [0.5, 0.0, 0.35])
        objs.extend([plate, s1, s2])
        return objs

    # Raspberry Pi mount
    if any(k in low for k in ("raspberry pi mount", "rpi mount")):
        base = add_box(2.8, 2.0, 0.2, [0.0, 0.0, 0.1])
        for x, y in ((-1.1, -0.8), (1.1, -0.8), (-1.1, 0.8), (1.1, 0.8)):
            objs.append(add_cyl(0.1, 0.4, [x, y, 0.3]))
        return objs

    # Power distribution board case
    if any(k in low for k in ("power distribution board case", "pdb case")):
        case = add_box(2.2, 2.2, 0.7, [0.0, 0.0, 0.35])
        vent = add_box(1.8, 0.1, 0.05, [0.0, 0.8, 0.7])
        objs.extend([case, vent])
        return objs

    # Cooling fan duct
    if any(k in low for k in ("cooling fan duct", "fan duct")):
        inlet = add_box(1.4, 1.4, 0.6, [-0.7, 0.0, 0.3])
        outlet = add_box(1.0, 1.0, 0.6, [0.6, 0.0, 0.3])
        bridge = add_box(0.8, 1.0, 0.6, [0.0, 0.0, 0.3])
        objs.extend([inlet, outlet, bridge])
        return objs

    # Cable protector
    if any(k in low for k in ("cable protector",)):
        base = add_box(3.0, 1.0, 0.15, [0.0, 0.0, 0.075])
        ribs = 6
        for i in range(ribs):
            objs.append(add_box(0.2, 1.0, 0.1, [-1.25 + i*0.5, 0.0, 0.2]))
        objs.append(base)
        return objs

    # Wheel hub motor
    if any(k in low for k in ("wheel hub motor",)):
        ring = add_torus(1.1, 0.2, [0.0, 0.0, 1.0], [math.pi/2.0, 0.0, 0.0])
        core = add_cyl(0.5, 0.6, [0.0, 0.0, 0.3])
        objs.extend([ring, core])
        return objs

    # Suspension for mobile robot
    if any(k in low for k in ("suspension",)):
        spring = add_torus(0.5, 0.12, [0.0, 0.0, 0.7])
        arm = add_box(1.6, 0.3, 0.2, [0.8, 0.0, 0.4])
        objs.extend([spring, arm])
        return objs

    # Camera housing / robot head
    if any(k in low for k in ("camera housing",)):
        body = add_box(1.2, 0.9, 0.7, [0.0, 0.0, 0.35])
        lens = add_cyl(0.25, 0.35, [0.6, 0.0, 0.5], [0.0, math.pi/2.0, 0.0])
        objs.extend([body, lens])
        return objs
    if any(k in low for k in ("robot head",)):
        head = {"id": add_id("sph"), "type":"sphere", "params":{"radius": 0.8}, "transform":{"position":[0,0,0.8], "rotation":[0,0,0], "scale":[1,1,1]}}
        eye1 = add_cyl(0.12, 0.2, [0.25, 0.2, 0.9], [0.0, math.pi/2.0, 0.0])
        eye2 = add_cyl(0.12, 0.2, [0.25, -0.2, 0.9], [0.0, math.pi/2.0, 0.0])
        objs.extend([head, eye1, eye2])
        return objs

    # Arm link / wrist joint
    if any(k in low for k in ("arm link",)):
        link = add_cyl(0.35, 2.0, [0.0, 1.0, 1.0], [math.pi/2.0, 0.0, 0.0])
        objs.append(link)
        return objs
    if any(k in low for k in ("wrist joint",)):
        joint = add_cyl(0.5, 0.8, [0.0, 0.0, 0.4])
        tor = add_torus(0.6, 0.1, [0.0, 0.0, 0.8])
        objs.extend([joint, tor])
        return objs

    # Tool changer / end effector interface / force-torque sensor mount
    if any(k in low for k in ("tool changer", "end effector interface", "force-torque sensor mount")):
        plate = add_box(1.8, 1.8, 0.2, [0.0, 0.0, 0.1])
        ring = add_torus(0.7, 0.12, [0.0, 0.0, 0.25])
        for i in range(6):
            ang = (2*math.pi/6)*i
            objs.append(add_cyl(0.08, 0.25, [math.cos(ang)*0.6, math.sin(ang)*0.6, 0.125]))
        objs.extend([plate, ring])
        return objs

    # Robot base frame
    if any(k in low for k in ("robot base frame",)):
        w, d, h = 4.0, 3.0, 0.25
        objs.append(add_box(w, 0.25, h, [0.0, d/2, h/2]))
        objs.append(add_box(w, 0.25, h, [0.0, -d/2, h/2]))
        objs.append(add_box(0.25, d, h, [w/2, 0.0, h/2]))
        objs.append(add_box(0.25, d, h, [-w/2, 0.0, h/2]))
        return objs

    # Joint cover / axis housing / cable harness
    if any(k in low for k in ("joint cover",)):
        cover = {"id": add_id("sph"), "type":"sphere", "params": {"radius": 0.9}, "transform": {"position":[0,0,0.9], "rotation":[0,0,0], "scale":[1,1,0.6]}}
        objs.append(cover)
        return objs
    if any(k in low for k in ("axis housing",)):
        objs.append(add_cyl(0.6, 2.2, [0.0, 0.0, 1.1]))
        return objs
    if any(k in low for k in ("cable harness",)):
        for i in range(5):
            objs.append(add_cyl(0.06, 2.2, [-0.2 + i*0.1, 0.0, 1.1], [0.0, math.pi/2.0, 0.0]))
        return objs

    # Battery holder
    if any(k in low for k in ("battery holder",)):
        base = add_box(2.2, 1.2, 0.2, [0.0, 0.0, 0.1])
        tube1 = add_cyl(0.3, 1.0, [-0.6, 0.0, 0.5], [0.0, math.pi/2.0, 0.0])
        tube2 = add_cyl(0.3, 1.0, [0.6, 0.0, 0.5], [0.0, math.pi/2.0, 0.0])
        objs.extend([base, tube1, tube2])
        return objs

    # Track system (tank robot)
    if any(k in low for k in ("track system", "tank robot", "tracks")):
        base = add_box(4.0, 2.0, 0.3, [0.0, 0.0, 0.15])
        ringL = add_torus(1.0, 0.2, [-1.8, 0.0, 0.6], [math.pi/2.0, 0.0, 0.0])
        ringR = add_torus(1.0, 0.2, [1.8, 0.0, 0.6], [math.pi/2.0, 0.0, 0.0])
        objs.extend([base, ringL, ringR])
        return objs

    # Furniture – table
    if "table" in low:
        top_w, top_d, top_h = 3.0, 1.6, 0.15
        objs.append(add_box(top_w, top_d, top_h, [0.0, 0.0, 0.8]))
        leg_h = 0.8
        for sx in (-1, 1):
            for sy in (-1, 1):
                objs.append(add_cyl(0.07, leg_h, [sx*(top_w/2-0.15), sy*(top_d/2-0.15), leg_h/2]))
        return objs

    # Furniture – chair
    if any(k in low for k in ("chair", "stool")):
        seat_w, seat_d, seat_h = 1.2, 1.2, 0.1
        objs.append(add_box(seat_w, seat_d, seat_h, [0.0, 0.0, 0.55]))
        for sx in (-1, 1):
            for sy in (-1, 1):
                objs.append(add_cyl(0.06, 0.55, [sx*(seat_w/2-0.1), sy*(seat_d/2-0.1), 0.275]))
        objs.append(add_box(1.2, 0.1, 1.0, [0.0, -(seat_d/2-0.05), 1.05]))
        return objs

    # Everyday – cup / mug / bowl / vase
    if any(k in low for k in ("cup", "mug")):
        objs.append(add_cyl(0.6, 1.0, [0.0, 0.0, 0.5]))
        objs.append(add_torus(0.6, 0.1, [0.0, 0.0, 1.02]))
        return objs
    if "bowl" in low:
        objs.append({"id": add_id("sph"), "type":"sphere", "params": {"radius": 0.8}, "transform": {"position":[0,0,0.8], "rotation":[0,0,0], "scale":[1,1,0.6]}})
        return objs
    if any(k in low for k in ("vase", "parametric vase")):
        objs.append(add_cyl(0.5, 1.6, [0.0, 0.0, 0.8]))
        objs.append(add_torus(0.5, 0.12, [0.0, 0.0, 1.65]))
        return objs

    # Batch 1–100 (Mechanical & Industrial Parts) – generic coverage
    FIRST100_KEYWORDS = {
        # 1–20
        "gear (spur)": ["spur gear", "gear (spur)", "gear"],
        "helical gear": ["helical gear"],
        "planetary gear system": ["planetary gear", "planet gear", "sun gear", "ring gear"],
        "shaft coupling": ["shaft coupling", "coupling"],
        "bearing housing": ["bearing housing"],
        "ball bearing assembly": ["ball bearing", "bearing"],
        "pulley": ["pulley"],
        "chain drive": ["chain drive"],
        "belt drive": ["belt drive"],
        "flywheel": ["flywheel"],
        "crankshaft": ["crankshaft"],
        "connecting rod": ["connecting rod", "conrod"],
        "piston": ["piston"],
        "engine block": ["engine block"],
        "camshaft": ["camshaft"],
        "valve assembly": ["valve assembly"],
        "clutch plate": ["clutch plate"],
        "differential gear": ["differential"],
        "axle hub": ["axle hub"],
        "suspension arm": ["suspension arm"],
        # 21–40
        "shock absorber": ["shock absorber"],
        "hydraulic piston": ["hydraulic piston"],
        "compressor rotor": ["compressor rotor"],
        "turbine blade": ["turbine blade"],
        "centrifugal pump impeller": ["impeller", "centrifugal pump"],
        "gearbox casing": ["gearbox casing"],
        "worm gear": ["worm gear"],
        "sprocket": ["sprocket"],
        "universal joint": ["universal joint", "u-joint"],
        "threaded bolt": ["threaded bolt", "bolt"],
        "nut and washer": ["nut and washer", "nut", "washer"],
        "fastener set": ["fastener set"],
        "l-bracket": ["l-bracket", "l bracket"],
        "structural beam": ["structural beam", "i-beam", "ibeam", "i beam"],
        "angle section": ["angle section", "angle profile"],
        "pipe joint": ["pipe joint"],
        "pipe flange": ["pipe flange", "flange"],
        "pressure valve": ["pressure valve"],
        "ball valve": ["ball valve"],
        "gate valve": ["gate valve"],
        # 41–60
        "manifold": ["manifold"],
        "heat exchanger": ["heat exchanger"],
        "radiator fin": ["radiator fin"],
        "cooling fan": ["cooling fan"],
        "air duct": ["air duct"],
        "vent grill": ["vent grill", "vent grille"],
        "bearing block": ["bearing block"],
        "key and keyway": ["keyway", "key and keyway"],
        "splined shaft": ["splined shaft"],
        "tool holder": ["tool holder"],
        "cnc fixture": ["cnc fixture", "fixture"],
        "milling vice": ["milling vice", "milling vise"],
        "drill chuck": ["drill chuck"],
        "end mill": ["end mill"],
        "lathe toolpost": ["lathe toolpost", "toolpost"],
        "machine base": ["machine base"],
        "robot arm joint": ["robot arm joint"],
        "rotary actuator": ["rotary actuator"],
        "pneumatic cylinder": ["pneumatic cylinder"],
        "servo motor housing": ["servo motor housing"],
        # 61–80
        "motor mount plate": ["motor mount plate"],
        "stepper motor bracket": ["stepper motor bracket"],
        "gear reducer casing": ["gear reducer casing"],
        "sensor mount": ["sensor mount"],
        "optical encoder housing": ["optical encoder housing"],
        "bearing seat": ["bearing seat"],
        "cam follower": ["cam follower"],
        "belt tensioner": ["belt tensioner"],
        "timing pulley": ["timing pulley"],
        "linear guide rail": ["linear guide rail"],
        "lead screw": ["lead screw"],
        "ball screw nut": ["ball screw nut"],
        "machine column": ["machine column"],
        "cross-slide assembly": ["cross-slide", "cross slide"],
        "rotary table": ["rotary table"],
        "tool changer": ["tool changer"],
        "workpiece clamp": ["workpiece clamp"],
        "jig plate": ["jig plate"],
        "spacer": ["spacer"],
        "washer types": ["washer types", "spring washer", "flat washer"],
        # 81–100
        "retaining ring": ["retaining ring"],
        "snap fit joint": ["snap fit joint", "snap-fit"],
        "dowel pin": ["dowel pin"],
        "locating pin": ["locating pin"],
        "rivet": ["rivet"],
        "welded frame": ["welded frame"],
        "extruded aluminum profile": ["extruded aluminum profile", "aluminum extruded profile"],
        "mounting bracket set": ["mounting bracket set", "mounting bracket"],
        "cooling fin block": ["cooling fin block"],
        "shaft support": ["shaft support"],
        "pulley belt system": ["pulley belt system"],
        "chain tensioner": ["chain tensioner"],
        "sealing ring": ["sealing ring"],
        "bearing cage": ["bearing cage"],
        "spur gearbox assembly": ["spur gearbox"],
        "worm drive": ["worm drive"],
        "rack and pinion": ["rack and pinion"],
        "geneva wheel": ["geneva wheel"],
        "toggle clamp": ["toggle clamp"],
        "industrial fan assembly": ["industrial fan", "industrial fan assembly"],
    }

    def contains_any(low_text: str, phrases: List[str]) -> bool:
        return any(p in low_text for p in phrases)

    # Generic builders to ensure non-empty composite for any of the first 100 items
    if any(contains_any(low, phrases) for phrases in FIRST100_KEYWORDS.values()):
        # Use combinations of disks (cyl), rings (torus), shafts, and plates
        hub_r = 0.6
        plate = add_box(3.2, 3.2, 0.18, [0.0, 0.0, 0.09], None, color or "#1f2333")
        shaft = add_cyl(0.35, 2.4, [0.0, 0.0, 1.2], None, color or "#9aa7ff")
        wheel = add_torus(1.4, 0.22, [1.6, 0.0, 0.7], [math.pi / 2.0, 0.0, 0.0], "#20262f")
        disk = add_cyl(1.1, 0.3, [-1.6, 0.0, 0.15], None, color or "#b9c6ff")
        hub = add_cyl(hub_r, 0.5, [0.0, 0.0, 0.25], None, "#2b3145")
        objs.extend([plate, shaft, wheel, disk, hub])
        # Add small bolt pattern to suggest mechanical detail
        for i in range(6):
            ang = (2 * math.pi / 6) * i
            bx = math.cos(ang) * 1.0
            by = math.sin(ang) * 1.0
            objs.append(add_cyl(0.08, 0.25, [bx, by, 0.125], None, "#dfe6ff"))
        return objs

    # Add more composites over time (chair, table, house) as needed
    return []


def _seed_from_text(text: str) -> int:
    val = 1469598103934665603  # FNV-1a 64-bit offset
    for ch in text.encode("utf-8"):
        val ^= ch
        val = (val * 1099511628211) & ((1 << 64) - 1)
    return val or 1


def _rand01(seed: int) -> float:
    # xorshift64*
    x = seed & ((1 << 64) - 1)
    x ^= (x >> 12)
    x ^= (x << 25) & ((1 << 64) - 1)
    x ^= (x >> 27)
    x = (x * 2685821657736338717) & ((1 << 64) - 1)
    return (x & ((1 << 53) - 1)) / float(1 << 53)


def _generic_synthesis(text: str, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Last-resort: always return a non-empty set of primitives arranged by a seed from text.

    The goal is to ensure something renderable appears, even for unknown prompts.
    """
    seed = _seed_from_text(text)
    n = 3 + int(_rand01(seed) * 3)  # 3-5 parts
    objs: List[Dict[str, Any]] = []
    for i in range(n):
        r = _rand01(seed + i * 997)
        shape_pick = r
        if shape_pick < 0.2:
            # sphere
            radius = 0.8 + 2.2 * _rand01(seed + i * 123)
            obj = {
                "id": _generate_id("sph", spec),
                "type": "sphere",
                "params": {"radius": radius},
                "transform": {"position": [
                    -2.5 + 5.0 * _rand01(seed + i * 31),
                    -2.5 + 5.0 * _rand01(seed + i * 37),
                    0.6 + 2.0 * _rand01(seed + i * 41),
                ], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            }
        elif shape_pick < 0.55:
            # box
            w = 1.2 + 4.0 * _rand01(seed + i * 53)
            d = 1.0 + 4.0 * _rand01(seed + i * 59)
            h = 0.8 + 3.0 * _rand01(seed + i * 61)
            obj = {
                "id": _generate_id("box", spec),
                "type": "box",
                "params": {"width": w, "depth": d, "height": h},
                "transform": {"position": [
                    -2.5 + 5.0 * _rand01(seed + i * 67),
                    -2.5 + 5.0 * _rand01(seed + i * 71),
                    h / 2.0,
                ], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            }
        elif shape_pick < 0.8:
            # cylinder
            radius = 0.6 + 2.2 * _rand01(seed + i * 73)
            depth = 1.5 + 3.5 * _rand01(seed + i * 79)
            obj = {
                "id": _generate_id("cyl", spec),
                "type": "cylinder",
                "params": {"radius": radius, "depth": depth},
                "transform": {"position": [
                    -2.5 + 5.0 * _rand01(seed + i * 83),
                    -2.5 + 5.0 * _rand01(seed + i * 89),
                    depth / 2.0,
                ], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            }
        else:
            # torus
            radius = 0.9 + 2.5 * _rand01(seed + i * 97)
            tube = 0.2 + 0.6 * _rand01(seed + i * 101)
            obj = {
                "id": _generate_id("torus", spec),
                "type": "torus",
                "params": {"radius": radius, "tube": tube},
                "transform": {"position": [
                    -2.5 + 5.0 * _rand01(seed + i * 103),
                    -2.5 + 5.0 * _rand01(seed + i * 107),
                    0.8 + 2.0 * _rand01(seed + i * 109),
                ], "rotation": [math.pi / 2.0 * _rand01(seed + i * 113), 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            }
        objs.append(obj)
    return objs


def _build_new_object(text: str, spec: Dict[str, Any], numbers: List[float]) -> Dict[str, Any]:
    # Special-case: robot hand / gripper / mechanism intents map to assembly
    low = text.lower()
    if any(kw in low for kw in ("robot hand", "robotic hand", "gripper", "end effector", "bicycle", "bike")) or (
        "mechanism" in low and ("hand" in low or "finger" in low)
    ):
        obj_type = "assembly"
    else:
        obj_type = _detect_object_type(text)
    params = _default_params_for_type(obj_type, text, numbers)
    base_names = {
        "box": "box",
        "cylinder": "cyl",
        "sphere": "sph",
        "cone": "cone",
        "torus": "torus",
        "plane": "plane",
        "external_model": "model",
        "assembly": "asm",
    }
    obj_id = _generate_id(base_names.get(obj_type, "obj"), spec)
    new_obj = {
        "id": obj_id,
        "type": obj_type,
        "params": params,
        "transform": _default_transform(),
    }
    color = _color_from_text(text)
    if color:
        new_obj["params"]["color"] = color
    return new_obj


def _replace_object(
    target: Dict[str, Any],
    spec: Dict[str, Any],
    text: str,
    numbers: List[float],
) -> bool:
    new_type = _detect_object_type(text)
    if not new_type:
        return False
    current_type = str(target.get("type", ""))
    if new_type == current_type:
        return False
    params = _default_params_for_type(new_type, text, numbers)
    transform_snapshot = copy.deepcopy(_ensure_transform(target))
    color = _color_from_text(text) or target.get("params", {}).get("color")
    replacement = {
        "id": target.get("id") or _generate_id(new_type, spec),
        "type": new_type,
        "params": params,
        "transform": transform_snapshot,
    }
    if color:
        replacement["params"]["color"] = color
    try:
        index = spec["objects"].index(target)
    except (ValueError, KeyError):
        return False
    spec["objects"][index] = replacement
    return True


def have_gemini() -> bool:
    try:
        import google.generativeai as _  # type: ignore
        return bool(os.environ.get("GEMINI_API_KEY"))
    except Exception:
        return False


def run_gemini(user_text: str, existing_spec: Dict[str, Any] | None) -> Dict[str, Any]:
    import google.generativeai as genai  # type: ignore
    import time
    global _last_api_call_time
    
    # Rate limiting
    elapsed = time.time() - _last_api_call_time
    if elapsed < _min_call_interval:
        time.sleep(_min_call_interval - elapsed)
    
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    # Request strictly structured JSON to reduce parsing errors
    response_schema = {
        "type": "object",
        "properties": {
            "objects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": [
                                "box",
                                "cylinder",
                                "sphere",
                                "plane",
                                "cone",
                                "torus",
                                "torusknot",
                                "external_model",
                                "assembly"
                            ]
                        },
                        "params": {"type": "object"},
                        "transform": {
                            "type": "object",
                            "properties": {
                                "position": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3
                                },
                                "rotation": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3
                                },
                                "scale": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3
                                }
                            },
                            "required": ["position", "rotation", "scale"]
                        },
                        "children": {"type": "array"}
                    },
                    "required": ["id", "type", "params", "transform"]
                }
            }
        },
        "required": ["objects"]
    }

    # Get available model
    model_name = _get_available_model()
    if not model_name:
        raise RuntimeError("No compatible Gemini models found")
    
    model = genai.GenerativeModel(
        model_name,
        generation_config={
            "temperature": 0.3,
        },
    )

    existing_json_str = ""
    if existing_spec:
        existing_json_str = f"Current scene:\\n{json.dumps(existing_spec)}\\n\\n"
    
    prompt = f"{SYSTEM_PROMPT}\\n\\nUser request: {user_text}\\n{existing_json_str}\\nJSON:"
    _last_api_call_time = time.time()
    resp = model.generate_content(prompt)
    text = getattr(resp, "text", None)
    if not text and getattr(resp, "candidates", None):
        try:
            text = resp.candidates[0].content.parts[0].text  # type: ignore[attr-defined]
        except Exception:
            text = None
    if not text:
        raise RuntimeError("Empty response from Gemini")

    # Prefer direct JSON parse; fallback to regex extraction if needed
    try:
        data = json.loads(text)
    except Exception:
        import re as _re
        m = _re.search(r"\{[\s\S]*\}", text)
        data = json.loads(m.group(0)) if m else {"objects": []}
    if not isinstance(data, dict) or "objects" not in data:
        data = {"objects": []}
    return data


# Cache the available model to avoid repeated API calls
_cached_model_name = None
_last_api_call_time = 0
_min_call_interval = 6.0  # Minimum seconds between API calls (10 RPM = 6 seconds)

def _get_available_model():
    """Get the first available Gemini model (cached)."""
    global _cached_model_name
    if _cached_model_name:
        return _cached_model_name
    
    import google.generativeai as genai  # type: ignore
    
    # Try common model names that should work
    test_models = [
        "models/gemini-2.0-flash-exp",
        "models/gemini-1.5-flash",
        "models/gemini-1.5-pro",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]
    
    for model_name in test_models:
        try:
            # Try to create a model instance
            test_model = genai.GenerativeModel(model_name)
            # If successful, cache and return
            _cached_model_name = model_name
            print(f"Using Gemini model: {model_name}")
            return model_name
        except Exception:
            continue
    
    # Last resort: try listing models
    try:
        models = genai.list_models()
        for model in models:
            if 'generateContent' in model.supported_generation_methods:
                _cached_model_name = model.name
                print(f"Found available model: {model.name}")
                return model.name
    except Exception as e:
        print(f"Could not find any compatible models: {e}")
    
    return None


def build_script(user_text: str) -> Dict[str, str]:
    """Use Gemini to generate a self-contained JS snippet that defines a function
    `build(params)` returning a THREE.Group for rendering in the viewer.

    Returns: { "code": string }
    """
    import google.generativeai as genai  # type: ignore
    import time
    global _last_api_call_time
    
    # Rate limiting: wait if needed
    elapsed = time.time() - _last_api_call_time
    if elapsed < _min_call_interval:
        time.sleep(_min_call_interval - elapsed)
    
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string"}
        },
        "required": ["code"]
    }

    system = (
        "You are a CAD code generator. Output ONLY JSON with a single string property 'code'. "
        "The 'code' must be pure JavaScript that defines a function named build(params) { ... } "
        "which returns a THREE.Group containing the geometry. Do NOT import modules. "
        "Assume THREE and createMaterial(presetOrName, objSpec) and options are provided by the host. "
        "Use only standard THREE primitives (BoxGeometry, CylinderGeometry, TorusGeometry, SphereGeometry, TorusKnotGeometry, etc.). "
        "For high-detail or 'micro polygon' requests, use BufferGeometry, merge vertices, and prefer InstancedMesh for repeated tiny parts. "
        "Keep polycounts reasonable and bounded; avoid unbounded loops. "
        "Avoid network or DOM access. Keep execution under ~100ms."
    )

    # Get available model
    model_name = _get_available_model()
    if not model_name:
        raise RuntimeError("No compatible Gemini models found")
    
    model = genai.GenerativeModel(
        model_name,
        generation_config={
            "temperature": 0.3,
            "max_output_tokens": 4096,
        },
    )

    prompt = (
        system
        + "\nUser request: "
        + user_text
        + "\nReturn strictly: {\"code\": \"...javascript...\"}"
    )

    _last_api_call_time = time.time()
    resp = model.generate_content(prompt)
    text = getattr(resp, "text", None)
    if not text and getattr(resp, "candidates", None):
        try:
            text = resp.candidates[0].content.parts[0].text  # type: ignore[attr-defined]
        except Exception:
            text = None
    if not text:
        raise RuntimeError("Empty response from Gemini")
    try:
        data = json.loads(text)
    except Exception:
        data = {"code": text}
    if not isinstance(data, dict) or "code" not in data:
        raise RuntimeError("Malformed response from Gemini for code generation")
    return {"code": str(data["code"]) }


# Context library for common objects with standard dimensions
OBJECT_CONTEXT = {
    "chair": {"seat_height": "450mm", "seat_depth": "400-450mm", "seat_width": "450-500mm", "backrest_height": "400-500mm", "features": ["seat", "backrest", "legs"]},
    "table": {"height": "720-760mm", "min_thickness": "20mm", "leg_thickness": "40-60mm", "features": ["top", "legs"]},
    "desk": {"height": "720-760mm", "depth": "600-800mm", "width": "1000-1600mm", "features": ["top", "legs", "optional_drawers"]},
    "lamp": {"base_diameter": "150-200mm", "stem_height": "300-500mm", "features": ["base", "stem", "shade"]},
    "mug": {"height": "90-100mm", "diameter": "75-85mm", "wall_thickness": "3-5mm", "features": ["body", "handle"]},
    "bottle": {"height": "200-250mm", "diameter": "60-80mm", "neck_diameter": "25-30mm", "features": ["body", "neck", "cap"]},
    "glass": {"height": "100-180mm", "diameter": "60-85mm", "wall_thickness": "1.5-2.5mm", "features": ["bowl", "stem", "base"]},
    "vase": {"height": "200-350mm", "base_diameter": "80-120mm", "opening_diameter": "70-100mm", "features": ["body", "opening"]},
    "gear": {"module": "1-5mm", "pressure_angle": "20°", "features": ["body", "teeth", "bore"]},
    "bearing": {"inner_diameter": "8-50mm", "outer_diameter": "22-110mm", "width": "7-25mm", "features": ["inner_race", "outer_race", "balls"]},
    "bracket": {"thickness": "3-6mm", "width": "30-60mm", "features": ["mounting_holes", "reinforcement"]},
}

STYLE_MODIFIERS = {
    "modern": "Clean lines, minimal ornamentation, thin profiles, smooth surfaces, geometric simplicity",
    "industrial": "Exposed structure, metal materials, functional aesthetic, visible joints, robust proportions",
    "rustic": "Thicker elements, natural materials, visible wood grain, traditional joinery, organic forms",
    "minimalist": "Essential elements only, maximum simplicity, reduced details, pure geometry",
    "ergonomic": "Human-centered dimensions, comfort-optimized curves, accessibility considerations",
}

MANUFACTURING_CONSTRAINTS = {
    "3d printing": {
        "min_wall_thickness": "0.8-1.2mm",
        "min_feature_size": "0.5mm",
        "overhang_limit": "45°",
        "guidance": "Avoid overhangs >45° without supports. Min wall 1mm. Self-supporting curves. Consider layer orientation."
    },
    "fdm": {  # Alias for 3D printing
        "min_wall_thickness": "1.2mm",
        "min_feature_size": "0.8mm",
        "overhang_limit": "45°",
        "guidance": "FDM: 1.2mm min walls, 45° max overhang, 0.1-0.3mm layer height, avoid thin vertical walls."
    },
    "cnc": {
        "min_wall_thickness": "2mm",
        "min_internal_radius": "Tool radius dependent (typically 1.5-3mm)",
        "draft_angle": "Not required",
        "guidance": "CNC: Sharp internal corners impossible (use fillet = tool radius). Min 2mm walls. Consider tool access for all features."
    },
    "injection molding": {
        "min_wall_thickness": "0.8-3mm uniform",
        "draft_angle": "1-3°",
        "min_radius": "0.5mm",
        "guidance": "Injection molding: Uniform wall thickness critical. 1-3° draft angles. Avoid undercuts. Min 0.5mm radii on corners."
    },
    "laser cutting": {
        "min_feature_size": "0.1-0.5mm",
        "kerf": "0.1-0.3mm",
        "guidance": "Laser: 2D profiles only. Account for 0.2mm kerf. Min 0.3mm feature spacing. No overhangs (flat parts)."
    }
}

def enhance_prompt(user_text: str) -> Dict[str, str]:
    """Stage 1: Transform simple user input into detailed technical specifications.
    Returns {"enhanced": str} with comprehensive CAD specifications.
    """
    import google.generativeai as genai  # type: ignore
    import time
    global _last_api_call_time
    
    # Rate limiting: wait if needed
    elapsed = time.time() - _last_api_call_time
    if elapsed < _min_call_interval:
        time.sleep(_min_call_interval - elapsed)
    
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    schema = {"type": "object", "properties": {"enhanced": {"type": "string"}}, "required": ["enhanced"]}
    
    # Detect object type, style, and manufacturing method from user input
    lower_text = user_text.lower()
    context_hint = ""
    for obj_type, specs in OBJECT_CONTEXT.items():
        if obj_type in lower_text:
            context_hint = f"\nStandard dimensions for {obj_type}: {specs}\n"
            break
    
    style_hint = ""
    for style, desc in STYLE_MODIFIERS.items():
        if style in lower_text:
            style_hint = f"\nApply {style} style: {desc}\n"
            break
    
    manufacturing_hint = ""
    for method, constraints in MANUFACTURING_CONSTRAINTS.items():
        if method.replace(" ", "") in lower_text.replace(" ", ""):
            manufacturing_hint = (
                f"\nMANUFACTURING METHOD: {method.upper()}\n"
                f"Constraints: {constraints}\n"
                f"Apply these constraints to all specifications.\n"
            )
            break
    
    system_prompt = (
        "You are a technical CAD specification expert. Convert user prompts into detailed 3D model specifications.\n\n"
        "Generate comprehensive technical specifications including:\n"
        "1. Overall Dimensions: Precise measurements in mm (use standard dimensions for common objects)\n"
        "2. Geometric Components: Breakdown into primitive shapes (cylinders, boxes, spheres, cones, tori)\n"
        "3. Parametric Details: Key measurements, angles, radii, thicknesses, fillets\n"
        "4. Structural Details: How components connect, join types, assembly sequence\n"
        "5. Material Properties: Material type, finish, color for visualization\n"
        "6. Feature Hierarchy: Main body → secondary features → details → surface treatments\n\n"
        "CRITICAL RULES:\n"
        "- Use realistic, human-scale dimensions (furniture: hundreds of mm, small items: tens of mm)\n"
        "- Ensure structural feasibility (wall thickness ≥ 2mm, supports where needed)\n"
        "- Include assembly logic (which part goes where, in what order)\n"
        "- Specify primitive shapes that can be combined with boolean operations\n"
        "- Add connection details (how handle attaches to mug, how legs attach to table)\n\n"
        + context_hint + style_hint + manufacturing_hint +
        "DETAILED EXAMPLES:\n\n"
        "Example 1 - Coffee Mug:\n"
        "MAIN BODY (Cylinder with Shell):\n"
        "- Outer Height: 95mm, Outer Diameter: 80mm\n"
        "- Wall Thickness: 4mm (shell operation)\n"
        "- Base Thickness: 6mm (solid bottom)\n"
        "- Top Edge: 2mm fillet radius\n"
        "HANDLE (Swept Torus Section):\n"
        "- Cross-section: Ellipse 12mm × 8mm\n"
        "- Sweep Arc: 180° curve, radius 35mm from body center\n"
        "- Attachment: Boolean union at two points (15mm from rim, 35mm from base)\n"
        "- Clearance from body: 5mm\n"
        "CONSTRUCTION: 1) Create outer cylinder, 2) Shell operation for walls, 3) Create handle sweep path, 4) Boolean union handle\n\n"
        "Example 2 - Office Chair:\n"
        "SEAT (Box with rounded edges):\n"
        "- Dimensions: 450mm × 450mm × 45mm\n"
        "- Edge Fillet: 8mm radius all edges\n"
        "- Material: Padded surface\n"
        "BACKREST (Curved rectangular panel):\n"
        "- Dimensions: 450mm width × 400mm height × 40mm depth\n"
        "- Curve: 15° backward tilt\n"
        "- Attachment: 100mm below seat top, centered\n"
        "LEGS (5 cylindrical legs, star pattern):\n"
        "- Each leg: Diameter 30mm, Length 180mm\n"
        "- Arrangement: 72° spacing, radial from center\n"
        "- Base feet: Small spheres 40mm diameter at each leg end\n\n"
        "Return a plain text specification (NOT nested JSON objects). Use this format:\n"
        "OBJECT: [name]\n"
        "MAIN COMPONENT:\n- Dimensions: ...\n- Material: ...\n"
        "SECONDARY COMPONENTS:\n- [component]: dimensions, material\n"
        "ASSEMBLY: numbered steps\n\n"
        "Return strictly JSON with 'enhanced' field containing the PLAIN TEXT specification.\n"
    )

    # Get available model
    model_name = _get_available_model()
    if not model_name:
        return {"enhanced": user_text}  # Fallback to original if no model available
    
    model = genai.GenerativeModel(
        model_name,
        generation_config={
            "temperature": 0.7,
            "max_output_tokens": 2048,
        },
    )

    prompt = system_prompt + "\n\nUser Input: " + user_text + "\n\nGenerate detailed CAD specification as JSON:\n"
    _last_api_call_time = time.time()
    resp = model.generate_content(prompt)
    text = getattr(resp, "text", None)
    if not text and getattr(resp, "candidates", None):
        try:
            text = resp.candidates[0].content.parts[0].text  # type: ignore[attr-defined]
        except Exception:
            text = None
    if not text:
        return {"enhanced": user_text}  # Fallback to original
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "enhanced" in data:
            return {"enhanced": str(data["enhanced"])}
    except Exception:
        pass
    return {"enhanced": text if text else user_text}


def validate_specification(spec_text: str) -> Dict[str, Any]:
    """Stage 3: Validate enhanced specification for dimensional sanity and structural feasibility.
    Returns {"valid": bool, "warnings": [str], "enhanced": str}
    """
    warnings = []
    
    # Extract numbers from specification
    import re
    numbers = [float(n) for n in re.findall(r'\b(\d+(?:\.\d+)?)\s*mm\b', spec_text)]
    
    # Check 1: Reasonable dimension ranges
    if numbers:
        min_dim = min(numbers)
        max_dim = max(numbers)
        
        if min_dim < 0.5:
            warnings.append(f"Very small dimension detected ({min_dim}mm). Minimum 0.5mm recommended.")
        if max_dim > 5000:
            warnings.append(f"Very large dimension detected ({max_dim}mm). Check if realistic for object type.")
        if min_dim < 1 and max_dim > 1000:
            warnings.append("Extreme size variation. Verify wall thickness vs overall size.")
    
    # Check 2: Wall thickness validation
    wall_matches = re.findall(r'[Ww]all\s*[Tt]hickness[:\s]*(\d+(?:\.\d+)?)\s*mm', spec_text)
    if wall_matches:
        for thickness in wall_matches:
            thick = float(thickness)
            if thick < 1.5:
                warnings.append(f"Wall thickness {thick}mm may be too thin. Consider ≥2mm for structural integrity.")
    
    # Check 3: Fillet radius sanity
    fillet_matches = re.findall(r'[Ff]illet[:\s]*(\d+(?:\.\d+)?)\s*mm', spec_text)
    if fillet_matches and numbers:
        for fillet in fillet_matches:
            f = float(fillet)
            if f > max_dim * 0.3:
                warnings.append(f"Fillet radius {f}mm seems large relative to object size. Check proportions.")
    
    # Check 4: Connection logic
    if "attach" in spec_text.lower() or "connect" in spec_text.lower() or "join" in spec_text.lower():
        if "boolean" not in spec_text.lower() and "union" not in spec_text.lower():
            warnings.append("Attachment mentioned but no boolean operation specified. Add union/difference details.")
    
    # Check 5: Material specification
    materials = ["metal", "plastic", "wood", "glass", "ceramic", "aluminum", "steel"]
    has_material = any(mat in spec_text.lower() for mat in materials)
    if not has_material:
        warnings.append("No material type specified. Consider adding material property for visualization.")
    
    return {
        "valid": len(warnings) == 0 or all("Consider" in w or "Check" in w for w in warnings),
        "warnings": warnings,
        "enhanced": spec_text
    }


def ask_question(user_text: str) -> Dict[str, str]:
    """Use Gemini to answer a general question. Returns {"answer": str}."""
    import google.generativeai as genai  # type: ignore
    import time
    global _last_api_call_time
    
    # Rate limiting: wait if needed
    elapsed = time.time() - _last_api_call_time
    if elapsed < _min_call_interval:
        time.sleep(_min_call_interval - elapsed)
    
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    # Get available model
    model_name = _get_available_model()
    if not model_name:
        return {"answer": "Error: No compatible Gemini models found. Please check your API key and permissions."}
    
    model = genai.GenerativeModel(
        model_name,
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 2048,
        },
    )
    prompt = (
        "You are a concise senior hardware engineering assistant. "
        "Answer directly with helpful, accurate guidance and short examples when useful.\n"
        "Return strictly JSON with an 'answer' string.\n\nQuestion: "
        + user_text
        + "\nJSON:"
    )
    _last_api_call_time = time.time()
    resp = model.generate_content(prompt)
    text = getattr(resp, "text", None)
    if not text and getattr(resp, "candidates", None):
        try:
            text = resp.candidates[0].content.parts[0].text  # type: ignore[attr-defined]
        except Exception:
            text = None
    if not text:
        return {"answer": "(no response)"}
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "answer" in data:
            return {"answer": str(data["answer"]) }
    except Exception:
        pass
    return {"answer": text}

def _clone_spec(spec: Dict[str, Any] | None) -> Dict[str, Any] | None:
    return copy.deepcopy(spec) if spec is not None else None


def _apply_removal(low: str, spec: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if spec is None:
        return None
    if any(word in low for word in ("clear", "reset", "start over")):
        return {"objects": []}
    if any(word in low for word in ("remove", "delete", "drop")):
        objects: List[Dict[str, Any]] = list(spec.get("objects", []))
        if not objects:
            return spec
        removed = False
        for idx, obj in enumerate(objects):
            obj_type = str(obj.get("type", ""))
            obj_id = str(obj.get("id", ""))
            if obj_id and obj_id.lower() in low:
                objects.pop(idx)
                removed = True
                break
            if obj_type and obj_type in low:
                objects.pop(idx)
                removed = True
                break
        if not removed:
            objects.pop()
        new_spec = _clone_spec(spec) or {"objects": []}
        new_spec["objects"] = objects
        return new_spec
    return spec


def run_local(user_text: str, existing_spec: Dict[str, Any] | None) -> Dict[str, Any]:
    lowered = _normalize(user_text)
    numbers = _extract_numbers(lowered)
    position_hint = _extract_position_triplet(lowered)

    spec = _clone_spec(existing_spec)
    spec = _apply_removal(lowered, spec)
    if spec is None:
        spec = {"objects": []}
    spec.setdefault("objects", [])

    urls = re.findall(r"https?://\S+", user_text)
    if urls:
        for url in urls:
            external = _build_external_model(url, user_text, spec)
            if external:
                if spec["objects"] and not _is_add_intent(lowered):
                    spec["objects"] = [external]
                else:
                    spec["objects"].append(external)
                return spec

    numbers_for_dims = numbers.copy()
    if position_hint:
        for value in position_hint:
            try:
                numbers_for_dims.remove(value)
            except ValueError:
                continue

    targets = _find_targets(spec, lowered)
    if not targets and spec["objects"] and not _is_add_intent(lowered):
        targets = _find_targets(spec, lowered, fallback=True)

    if targets and any(keyword in lowered for keyword in CLONE_KEYWORDS):
        clones: List[Dict[str, Any]] = []
        for target in targets:
            duplicate = _duplicate_object(target, spec)
            clones.append(duplicate)
        spec["objects"].extend(clones)
        _apply_color_change(clones, lowered)
        _apply_dimension_change(clones, lowered, numbers)
        _apply_directional_move(clones, lowered, numbers)
        _apply_rotation_change(clones, lowered, numbers)
        _apply_scale_change(clones, lowered, numbers)
        return spec

    if targets and any(keyword in lowered for keyword in REPLACE_KEYWORDS):
        if _replace_object(targets[0], spec, lowered, numbers_for_dims):
            return spec

    if targets:
        changed = False
        changed |= _apply_color_change(targets, lowered)
        changed |= _apply_dimension_change(targets, lowered, numbers)
        changed |= _apply_directional_move(targets, lowered, numbers)
        changed |= _apply_rotation_change(targets, lowered, numbers)
        changed |= _apply_scale_change(targets, lowered, numbers)
        if changed:
            return spec

    add_intent = _is_add_intent(lowered) or not spec["objects"] or not targets
    if add_intent:
        composite = _build_composite_objects(user_text, spec, numbers_for_dims)
        if composite:
            spec["objects"].extend(composite)
            move_numbers = numbers if any(word in lowered for word in ("move", "shift", "slide", "raise", "lower", "position", "place")) else []
            rotation_numbers = numbers if any(word in lowered for word in ("rotate", "rotation", "twist", "spin", "turn")) else []
            _apply_directional_move(composite, lowered, move_numbers)
            _apply_rotation_change(composite, lowered, rotation_numbers)
            _apply_scale_change(composite, lowered, numbers)
            return spec

        new_obj = _build_new_object(user_text, spec, numbers_for_dims)
        spec["objects"].append(new_obj)
        move_numbers = numbers if any(word in lowered for word in ("move", "shift", "slide", "raise", "lower", "position", "place")) else []
        rotation_numbers = numbers if any(word in lowered for word in ("rotate", "rotation", "twist", "spin", "turn")) else []
        _apply_directional_move([new_obj], lowered, move_numbers)
        _apply_rotation_change([new_obj], lowered, rotation_numbers)
        _apply_scale_change([new_obj], lowered, numbers)
        return spec

    return spec


def build_spec(user_text: str, existing_spec_json: str | None) -> Dict[str, Any]:
    existing = json.loads(existing_spec_json) if existing_spec_json else None

    # Prefer Gemini when available
    if have_gemini():
        try:
            data = run_gemini(user_text, existing)
            # Post-process: if Gemini returns empty/degenerate output, synthesize a composite locally
            try:
                objs = data.get("objects", []) if isinstance(data, dict) else []
            except Exception:
                objs = []
            if not objs or (len(objs) == 1 and str(objs[0].get("type", "")).lower() == "box"):
                # Try to build a composite approximation and either replace or append
                numbers = _extract_numbers(_normalize(user_text))
                composite = _build_composite_objects(user_text, {"objects": []}, numbers)
                if composite:
                    # If there's an existing spec and the user didn't clearly ask to reset, append
                    if existing:
                        out = {"objects": list(existing.get("objects", [])) + composite}
                    else:
                        out = {"objects": composite}
                    return out

            # Fallback: if Gemini "edit" failed to change anything, try local editor
            if existing and isinstance(data, dict):
                try:
                    if data.get("objects") == existing.get("objects"):
                        # Attempt a local semantic edit
                        edited = run_local(user_text, existing)
                        return edited
                except Exception:
                    pass
            return data
        except Exception:
            # fall back to local
            pass

    # Local-only mode
    local = run_local(user_text, existing)
    try:
        if not local.get("objects"):
            composite = _build_composite_objects(user_text, {"objects": []}, _extract_numbers(_normalize(user_text)))
            if not composite:
                composite = _generic_synthesis(user_text, {"objects": []})
            return {"objects": composite}
    except Exception:
        pass

    # Ensure something non-trivial appears
    if len(local.get("objects", [])) == 1 and str(local["objects"][0].get("type", "")).lower() == "box":
        composite = _build_composite_objects(user_text, {"objects": []}, _extract_numbers(_normalize(user_text)))
        if not composite:
            composite = _generic_synthesis(user_text, {"objects": []})
        return {"objects": composite}

    return local


