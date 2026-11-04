"""Luma-Winslow Folio Engine (LWFE)

A small, dependency-free procedural audio renderer. JSON describes sound
materials, gestures, resonance, texture and pressure; the engine paints those
instructions into PCM WAV files.
"""
from __future__ import annotations

import json
import math
import random
import struct
import wave
from pathlib import Path
from typing import Any

ENGINE_VERSION = "0.1.1"
DEFAULT_SAMPLE_RATE = 48_000


class LWFEError(Exception):
    """Raised when a sound folio cannot be read or rendered."""


def load_library(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LWFEError(f"The sound folio was not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LWFEError(f"lwfe.json has invalid JSON near line {exc.lineno}, column {exc.colno}.") from exc

    sounds = data.get("sounds")
    if not isinstance(sounds, list) or not sounds:
        raise LWFEError("lwfe.json must contain a non-empty 'sounds' list.")

    seen: set[str] = set()
    for sound in sounds:
        if not isinstance(sound, dict):
            raise LWFEError("Every sound entry must be a JSON object.")
        sound_id = str(sound.get("id", "")).strip()
        if not sound_id:
            raise LWFEError("Every sound needs a non-empty 'id'.")
        if sound_id in seen:
            raise LWFEError(f"Duplicate sound id: {sound_id}")
        seen.add(sound_id)
        if not isinstance(sound.get("strokes"), list) or not sound["strokes"]:
            raise LWFEError(f"'{sound_id}' needs at least one sound-painting stroke.")
    return data


def output_path_for(
    sound: dict[str, Any],
    project_root: Path,
    output_root: Path | None = None,
) -> Path:
    """Resolve a folio output within its assigned workspace.

    output_root is the active archive for a desktop-app session. It is
    optional for backwards compatibility with callers that intentionally
    render directly into project_root.
    """
    workspace_root = (output_root if output_root is not None else project_root).resolve()
    relative = str(sound.get("output", f"sounds/{sound['id']}_LWFE.WAV"))
    candidate = (workspace_root / relative).resolve()
    try:
        candidate.relative_to(workspace_root)
    except ValueError as exc:
        raise LWFEError(
            f"Output path for '{sound['id']}' must stay inside its LWFE workspace."
        ) from exc
    return candidate


def _curve_value(points: list[list[float]] | None, position: float, default: float) -> float:
    if not points:
        return default
    clean = sorted((float(p[0]), float(p[1])) for p in points if len(p) >= 2)
    if not clean:
        return default
    if position <= clean[0][0]:
        return clean[0][1]
    if position >= clean[-1][0]:
        return clean[-1][1]
    for (t0, v0), (t1, v1) in zip(clean, clean[1:]):
        if t0 <= position <= t1:
            if t1 == t0:
                return v1
            amount = (position - t0) / (t1 - t0)
            return v0 + (v1 - v0) * amount
    return clean[-1][1]


def _formant_weight(frequency: float, formants: list[dict[str, Any]]) -> float:
    if not formants:
        return 1.0
    response = 0.035
    for formant in formants:
        center = max(1.0, float(formant.get("center_hz", 700.0)))
        width = max(30.0, float(formant.get("width_hz", 240.0)))
        gain = max(0.0, float(formant.get("gain", 1.0)))
        distance = (frequency - center) / width
        response += gain * math.exp(-0.5 * distance * distance)
    return response


def _noise_sample(rng: random.Random, state: float, color: str, alpha: float) -> tuple[float, float]:
    white = rng.uniform(-1.0, 1.0)
    state += alpha * (white - state)
    if color == "dark":
        result = state
    elif color == "bright":
        result = white - state
    elif color == "gritty":
        result = 0.55 * white + 0.45 * (white - state)
    else:  # airy / neutral
        result = white
    return result, state


def _render_stroke(mix: list[float], stroke: dict[str, Any], sample_rate: int, seed: int) -> None:
    start_seconds = max(0.0, float(stroke.get("start", 0.0)))
    duration = max(0.015, float(stroke.get("duration", 0.15)))
    start = int(start_seconds * sample_rate)
    count = max(1, int(duration * sample_rate))
    end = min(len(mix), start + count)
    if start >= len(mix) or end <= start:
        return

    brush = str(stroke.get("brush", "voice")).lower()
    pressure = stroke.get("pressure", [[0.0, 0.0], [0.08, 1.0], [1.0, 0.0]])
    contour = stroke.get("contour", [[0.0, 180.0], [1.0, 120.0]])
    tone = stroke.get("tone", {})
    grain = stroke.get("grain", {})
    motion = stroke.get("motion", {})
    formants = tone.get("formants", [])
    partials = tone.get("partials", [1.0, 0.55, 0.30, 0.18, 0.10, 0.06])
    rolloff = max(0.1, float(tone.get("rolloff", 1.0)))
    noise_mix = max(0.0, min(1.0, float(grain.get("noise_mix", 0.0))))
    noise_color = str(grain.get("color", "airy")).lower()
    noise_alpha = max(0.01, min(1.0, float(grain.get("filter_alpha", 0.16))))
    pitch_wobble = max(0.0, float(grain.get("pitch_wobble", 0.0)))
    vibrato_rate = max(0.0, float(motion.get("vibrato_rate", 0.0)))
    vibrato_depth = max(0.0, float(motion.get("vibrato_depth", 0.0)))
    rng = random.Random(seed)
    noise_state = 0.0
    phase = 0.0
    resonance_hz = max(20.0, float(stroke.get("resonance_hz", 1100.0)))
    ring_decay = max(0.1, float(stroke.get("ring_decay", 24.0)))

    partial_values = [max(0.0, float(value)) for value in partials]
    partial_sum = sum(partial_values) or 1.0

    for index in range(start, end):
        local = (index - start) / max(1, count - 1)
        elapsed = local * duration
        pressure_value = max(0.0, _curve_value(pressure, local, 0.0))
        pitch = max(20.0, _curve_value(contour, local, 160.0))
        pitch *= 1.0 + math.sin(2.0 * math.pi * vibrato_rate * elapsed) * vibrato_depth
        if pitch_wobble:
            pitch *= 1.0 + rng.uniform(-pitch_wobble, pitch_wobble)

        noise, noise_state = _noise_sample(rng, noise_state, noise_color, noise_alpha)

        if brush == "air":
            sample = noise
        elif brush == "impact":
            decay = math.exp(-ring_decay * elapsed)
            ring = math.sin(2.0 * math.pi * resonance_hz * elapsed) * decay
            sample = ring * (1.0 - noise_mix) + noise * noise_mix
        else:  # voiced / throat / beak / other pitched materials
            phase += (2.0 * math.pi * pitch) / sample_rate
            voiced = 0.0
            for harmonic, partial_gain in enumerate(partial_values, start=1):
                harmonic_frequency = pitch * harmonic
                resonance = _formant_weight(harmonic_frequency, formants)
                falloff = 1.0 / (harmonic ** rolloff)
                voiced += math.sin(phase * harmonic) * partial_gain * falloff * resonance
            voiced /= max(0.5, partial_sum)
            sample = voiced * (1.0 - noise_mix) + noise * noise_mix

        mix[index] += sample * pressure_value * float(stroke.get("gain", 1.0))


def render_sound(
    sound: dict[str, Any],
    project_root: Path,
    output_root: Path | None = None,
) -> Path:
    """Render one sound into output_root (the active session archive).

    If output_root is omitted, the legacy project-root behavior is retained
    for non-UI callers. The LWFE desktop app always supplies its startup
    archive explicitly.
    """
    canvas = sound.get("canvas", {})
    sample_rate = int(canvas.get("sample_rate", DEFAULT_SAMPLE_RATE))
    sample_rate = max(22_050, min(96_000, sample_rate))
    duration = max(0.05, min(8.0, float(canvas.get("duration", 0.7))))
    frame_count = int(sample_rate * duration)
    mix = [0.0] * frame_count

    for index, stroke in enumerate(sound.get("strokes", [])):
        if not isinstance(stroke, dict):
            raise LWFEError(f"A stroke in '{sound.get('id', 'unknown')}' is not an object.")
        _render_stroke(mix, stroke, sample_rate, 104729 + (index * 7919))

    master_gain = max(0.0, float(canvas.get("master_gain", 0.82)))
    peak = max((abs(value) for value in mix), default=0.0)
    if peak < 1e-9:
        raise LWFEError(f"'{sound.get('name', sound.get('id'))}' produced silence. Check its strokes and pressure curves.")

    target_peak = max(0.1, min(0.98, float(canvas.get("target_peak", 0.88))))
    scale = target_peak / peak
    output = bytearray()
    for value in mix:
        # Gentle saturation rounds layer sums instead of hard-clipping them.
        shaped = math.tanh(value * scale * master_gain)
        sample = int(max(-1.0, min(1.0, shaped)) * 32767.0)
        output.extend(struct.pack("<h", sample))

    destination = output_path_for(sound, project_root, output_root=output_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with wave.open(str(destination), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(output)
    except OSError as exc:
        raise LWFEError(f"Could not write {destination}: {exc}") from exc
    return destination
