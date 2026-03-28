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
    return {
        "subset": list(arrangement.subset),
        "positions": {
            str(int(idx)): [float(pos[0]), float(pos[1])]
            for idx, pos in arrangement.positions.items()
        },
    }


def _deserialize_trial_arrangement(payload: dict[str, Any]) -> TrialArrangement:
    positions = {
        int(idx): (float(values[0]), float(values[1]))
        for idx, values in (payload.get("positions") or {}).items()
    }
    return TrialArrangement(
        subset=[int(idx) for idx in payload.get("subset") or []],
        positions=positions,
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

