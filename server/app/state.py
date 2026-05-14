"""
Serialization helpers for durable session state.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ma_core import TrialArrangement


SESSION_STATE_KEYS = {
    "batches",
    "pairs",
    "D",
    "W_raw",
    "W_sched",
    "trial_arrangements",
    "seen",
    "recent",
    "inclusion_counts",
    "durations",
    "last_subset",
    "last_anchor_pair",
    "long_clip_mask",
    "pairwise_ratings",
}


def _encode_pairwise_ratings(value: dict[Any, list[Any]] | None) -> dict[str, list[Any]]:
    if not value:
        return {}
    encoded: dict[str, list[Any]] = {}
    for key, ratings in value.items():
        if isinstance(key, tuple):
            encoded[f"{int(key[0])}:{int(key[1])}"] = list(ratings)
        else:
            encoded[str(key)] = list(ratings)
    return encoded


def _decode_pairwise_ratings(value: dict[str, list[Any]] | None) -> dict[tuple[int, int], list[Any]]:
    if not value:
        return {}
    decoded: dict[tuple[int, int], list[Any]] = {}
    for key, ratings in value.items():
        if ":" in key:
            left, right = key.split(":", 1)
            decoded[(int(left), int(right))] = list(ratings)
    return decoded


def _serialize_trial_arrangement(arrangement: TrialArrangement) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subset": list(arrangement.subset),
        "positions": {
            str(int(idx)): [float(pos[0]), float(pos[1])]
            for idx, pos in arrangement.positions.items()
        },
    }
    arena_center = getattr(arrangement, "arena_center", None)
    arena_radius = getattr(arrangement, "arena_radius", None)
    if arena_center is not None:
        payload["arena_center"] = [float(arena_center[0]), float(arena_center[1])]
    if arena_radius is not None:
        payload["arena_radius"] = float(arena_radius)
    return payload


def _deserialize_trial_arrangement(payload: dict[str, Any]) -> TrialArrangement:
    positions = {
        int(idx): (float(values[0]), float(values[1]))
        for idx, values in (payload.get("positions") or {}).items()
    }
    arena_center_raw = payload.get("arena_center")
    arena_center = None
    if isinstance(arena_center_raw, (list, tuple)) and len(arena_center_raw) >= 2:
        arena_center = (float(arena_center_raw[0]), float(arena_center_raw[1]))
    arena_radius_raw = payload.get("arena_radius")
    arena_radius = float(arena_radius_raw) if arena_radius_raw is not None else None
    return TrialArrangement(
        subset=[int(idx) for idx in payload.get("subset") or []],
        positions=positions,
        arena_center=arena_center,
        arena_radius=arena_radius,
    )


def serialize_session_state(session: dict[str, Any]) -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key in SESSION_STATE_KEYS:
        value = session.get(key)
        if key == "trial_arrangements":
            state[key] = [_serialize_trial_arrangement(item) for item in value or []]
        elif key == "pairwise_ratings":
            state[key] = _encode_pairwise_ratings(value)
        elif isinstance(value, np.ndarray):
            state[key] = value.tolist()
        elif isinstance(value, tuple):
            state[key] = list(value)
        else:
            state[key] = value
    return state


def load_session_state(base: dict[str, Any], state: dict[str, Any] | None) -> dict[str, Any]:
    state = state or {}
    loaded = dict(base)
    for key, value in state.items():
        if key in {"D", "W_raw", "W_sched"}:
            loaded[key] = np.array(value, dtype=float) if value is not None else None
        elif key == "seen":
            loaded[key] = np.array(value, dtype=bool) if value is not None else None
        elif key == "recent":
            loaded[key] = np.array(value, dtype=float) if value is not None else None
        elif key == "inclusion_counts":
            loaded[key] = np.array(value, dtype=int) if value is not None else None
        elif key == "durations":
            loaded[key] = np.array(value, dtype=float) if value is not None else None
        elif key == "long_clip_mask":
            loaded[key] = np.array(value, dtype=bool) if value is not None else None
        elif key == "trial_arrangements":
            loaded[key] = [_deserialize_trial_arrangement(item) for item in value or []]
        elif key == "last_anchor_pair":
            loaded[key] = tuple(value) if value is not None else None
        elif key == "pairwise_ratings":
            loaded[key] = _decode_pairwise_ratings(value)
        else:
            loaded[key] = value
    return loaded

