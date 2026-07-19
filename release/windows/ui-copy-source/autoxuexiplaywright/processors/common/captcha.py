"""Shared helpers for local slider captcha recognition and mouse tracks."""

from __future__ import annotations

from base64 import b64encode
from json import dumps, loads
from math import isfinite
from random import uniform
from typing import Any, Iterator
from urllib.request import Request, urlopen

_DISTANCE_KEYS = ("distance", "offset", "target_x", "slide_distance")
_NESTED_KEYS = ("data", "result")


def build_local_slider_payload(
    image: bytes,
    width: float | None = None,
    height: float | None = None,
    page_url: str = "",
) -> dict[str, Any]:
    """Build the JSON payload accepted by the local slider service."""
    encoded = b64encode(image).decode("ascii")
    payload: dict[str, Any] = {
        "type": "slider",
        "image": encoded,
        "image_base64": encoded,
    }
    if width is not None:
        payload["width"] = width
    if height is not None:
        payload["height"] = height
    if page_url:
        payload["url"] = page_url
    return payload


def request_local_slider_distance(
    endpoint: str,
    payload: dict[str, Any],
    token: str = "",
    timeout_secs: float = 10.0,
) -> tuple[float | None, float | None]:
    """Call a local HTTP solver and return ``(distance, confidence)``."""
    endpoint = endpoint.strip()
    if not endpoint:
        raise ValueError("本地滑块接口地址为空")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token.strip():
        headers["Authorization"] = "Bearer " + token.strip()
        headers["X-API-Key"] = token.strip()
    request = Request(
        endpoint,
        data=dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urlopen(request, timeout=max(1.0, float(timeout_secs))) as response:
        raw = response.read().decode("utf-8", errors="replace")
    result = loads(raw)
    if isinstance(result, bool):
        return None, None
    if isinstance(result, (int, float)) and isfinite(float(result)):
        return float(result), None
    distance = _extract_number(result, _DISTANCE_KEYS)
    confidence = _extract_number(result, ("confidence", "score", "probability"))
    return distance, confidence


def _extract_number(value: Any, keys: tuple[str, ...]) -> float | None:
    for mapping in _iter_mappings(value):
        for key in keys:
            number = mapping.get(key)
            if isinstance(number, bool):
                continue
            if isinstance(number, (int, float)):
                converted = float(number)
            elif isinstance(number, str):
                try:
                    converted = float(number.strip())
                except ValueError:
                    continue
            else:
                continue
            if isfinite(converted):
                return converted
    return None


def _iter_mappings(value: Any) -> Iterator[dict[str, Any]]:
    if not isinstance(value, dict):
        return
    yield value
    for key in _NESTED_KEYS:
        nested = value.get(key)
        if isinstance(nested, dict):
            yield from _iter_mappings(nested)



def calculate_slider_max_distance(
    slider_box: dict[str, float],
    target_box: dict[str, float],
) -> float:
    """Return the CSS-pixel distance that aligns the slider with track right."""
    return max(
        0.0,
        float(target_box["x"]) + float(target_box["width"])
        - float(slider_box["x"]) - float(slider_box["width"]),
    )

def build_drag_positions(
    start_x: float,
    start_y: float,
    distance: float,
    steps: int = 58,
) -> list[tuple[float, float]]:
    """Generate a smooth, slightly irregular track ending exactly on target."""
    distance = max(0.0, float(distance))
    steps = max(8, int(steps))
    positions: list[tuple[float, float]] = []
    for index in range(1, steps + 1):
        progress = index / steps
        # Smooth acceleration/deceleration avoids a single synthetic jump at
        # the endpoint while keeping the final coordinate exact.
        eased = 3.0 * progress * progress - 2.0 * progress * progress * progress
        x = start_x + distance * eased
        y = start_y if index == steps else start_y + uniform(-1.25, 1.25)
        positions.append((x, y))
    positions[-1] = (start_x + distance, start_y)
    return positions
