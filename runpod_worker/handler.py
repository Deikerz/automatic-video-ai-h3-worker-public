from __future__ import annotations

import base64
import binascii
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import runpod

from comfy_runner import ComfyRunner, ref2va_prompt


ROOT = Path(os.environ.get("COMFYUI_ROOT", "/comfyui"))
WORKFLOW = Path(os.environ.get("H3_WORKFLOW_PATH", "/workspace/workflows/minimax-h3-ref2va-api.json"))
RUNNER: ComfyRunner | None = None
MAX_INPUT_BYTES = int(os.environ.get("H3_MAX_INPUT_BYTES", str(8 * 1024 * 1024)))
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def _runner() -> ComfyRunner:
    global RUNNER
    if RUNNER is None:
        RUNNER = ComfyRunner(ROOT, WORKFLOW, int(os.environ.get("COMFYUI_PORT", "8188")))
        RUNNER.start()
    return RUNNER


def _write_encoded(folder: Path, payload: dict[str, Any], stem: str) -> Path:
    encoded = payload.get("data_base64")
    if not isinstance(encoded, str):
        raise ValueError(f"missing data_base64 for {stem}")
    suffix = Path(str(payload.get("filename", ""))).suffix.lower() or ".bin"
    allowed = AUDIO_SUFFIXES if stem == "reference-audio" else IMAGE_SUFFIXES
    if suffix not in allowed:
        raise ValueError(f"unsupported {stem} file type: {suffix}")
    if len(encoded) > ((MAX_INPUT_BYTES + 2) // 3) * 4:
        raise ValueError(f"encoded {stem} exceeds H3_MAX_INPUT_BYTES")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError(f"invalid base64 for {stem}") from exc
    if not data or len(data) > MAX_INPUT_BYTES:
        raise ValueError(f"decoded {stem} is empty or exceeds H3_MAX_INPUT_BYTES")
    target = folder / f"{stem}{suffix}"
    target.write_bytes(data)
    return target


def handler(job: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    data = job.get("input") or {}
    first = data.get("first_frame")
    if not isinstance(first, dict):
        raise ValueError("input.first_frame is required")
    requested_duration = float(data.get("duration_seconds", 6.0))
    if not math.isfinite(requested_duration):
        raise ValueError("input.duration_seconds must be finite")
    duration = max(5.0, min(requested_duration, float(os.environ.get("H3_MAX_DURATION_SECONDS", "15"))))
    width = int(data.get("width", 608))
    height = int(data.get("height", 352))
    seed = int(data.get("seed", 42))
    prompt = str(data.get("prompt", "")).strip()
    dialogue = str(data.get("dialogue", "")).strip()
    return_mode = str(data.get("return_mode", "base64")).strip().lower()
    if return_mode != "base64":
        raise ValueError("this worker currently supports input.return_mode=base64 only")
    if not prompt:
        raise ValueError("input.prompt is required")
    if len(prompt) > 20_000 or len(dialogue) > 2_000:
        raise ValueError("prompt or dialogue exceeds the worker limit")
    native_width = int(os.environ.get("H3_NATIVE_WIDTH", "608"))
    native_height = int(os.environ.get("H3_NATIVE_HEIGHT", "352"))
    if (width, height) != (native_width, native_height):
        raise ValueError(f"this bounded worker only permits {native_width}x{native_height}")
    if seed < 0 or seed >= 2**64:
        raise ValueError("input.seed must be an unsigned 64-bit integer")
    reference_count = len(data.get("reference_images") or []) + 1
    if reference_count > 9:
        raise ValueError("input.reference_images supports at most 8 additional images")
    prompt = ref2va_prompt(
        prompt,
        dialogue,
        isinstance(data.get("reference_audio"), dict),
        reference_count,
    )
    with tempfile.TemporaryDirectory(prefix="h3-ref2va-") as temp:
        folder = Path(temp)
        first_path = _write_encoded(folder, first, "first-frame")
        refs = [_write_encoded(folder, item, f"reference-{index:02d}") for index, item in enumerate(data.get("reference_images") or [], start=1)]
        audio = data.get("reference_audio")
        audio_path = _write_encoded(folder, audio, "reference-audio") if isinstance(audio, dict) else None
        runner = _runner()
        uploaded: list[str] = []
        try:
            first_name = runner.upload(first_path, "image")
            uploaded.append(first_name)
            ref_names = []
            for path in refs:
                ref_name = runner.upload(path, "image")
                uploaded.append(ref_name)
                ref_names.append(ref_name)
            audio_name = runner.upload(audio_path, "audio") if audio_path else None
            if audio_name:
                uploaded.append(audio_name)
            graph = runner.prepare_graph(first_frame=first_name, reference_images=ref_names, reference_audio=audio_name, prompt=prompt, duration_seconds=duration, width=width, height=height, seed=seed)
            video = runner.generate(graph)
        finally:
            runner.cleanup_inputs(uploaded)
        return {"video_base64": base64.b64encode(video).decode("ascii"), "mime_type": "video/mp4", "duration_seconds": duration, "width": width, "height": height, "seed": seed, "provider": "minimax-h3-ref2va", "quantization": "int8-diffusion+nvfp4-awq-encoder", "execution_seconds": round(time.monotonic() - started, 3)}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
