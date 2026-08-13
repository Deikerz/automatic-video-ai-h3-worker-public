from __future__ import annotations

import copy
import json
import logging
import mimetypes
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

import httpx


def ref2va_prompt(prompt: str, dialogue: str, has_audio: bool, reference_count: int) -> str:
    """Wrap the app's concise brief in the official Ref2VA rewrite structure."""
    picture_labels = ", ".join(f"<Picture {index}>" for index in range(1, reference_count + 1))
    audio_definition = (
        "<Audio 1> is the voice-timbre reference for the Spanish speaker (S1)."
        if has_audio
        else "No external audio reference is provided; generate natural synchronized Spanish scene audio."
    )
    dialogue_line = (
        f"The first-person narrator (S1) speaks exactly <d>[Spanish] {dialogue}</d>."
        if dialogue
        else "There is no required spoken line; preserve natural diegetic sound and synchronized motion."
    )
    return "\n".join(
        [
            "subject_definitions:",
            f"<Subject 1> is the strict first-person camera viewpoint anchored by {picture_labels}.",
            audio_definition,
            "summary:",
            "[reference generation + keyframe completion + audio reference] Generate an entertaining cinematic documentary moment in strict first-person POV, beginning from <Picture 1> and using the other references only for identity, environment, props, style, or continuity.",
            "retention_analysis:",
            "<Picture 1> (opening frame): fully_preserved - begin the shot from the supplied first-person frame.",
            f"{picture_labels} (reference guidance): partially_preserved - preserve relevant identity, environment, lighting, and prop details without copying a flat slideshow.",
            f"<Audio 1>: reference - use the voice timbre and delivery only; do not copy unrelated source words." if has_audio else "No external audio reference is retained.",
            "detailed_description:",
            "Use a continuous, immersive first-person camera with only the operator's hands or forearms entering frame. Show clear physical actions, readable spatial continuity, motivated camera movement, and a strong visual beat. Never show an external camera, third-person protagonist, subtitles, captions, title cards, or the narrator's face.",
            prompt,
            dialogue_line,
            "overall_soundscape:",
            "Use realistic synchronized Spanish diegetic sound effects and room tone that evolve with the visible action.",
            "non_diegetic_music:",
            "Use restrained cinematic music under the scene, ducked beneath speech, without captions or on-screen text.",
        ]
    )


class ComfyRunner:
    def __init__(self, root: Path, workflow_path: Path, port: int = 8188) -> None:
        self.root = root
        self.workflow_path = workflow_path
        self.base_url = f"http://127.0.0.1:{port}"
        self.http = httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0))
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        try:
            response = self.http.get(f"{self.base_url}/system_stats")
            if response.is_success:
                return
        except httpx.HTTPError:
            pass
        port = self.base_url.rsplit(":", 1)[1]
        log_path = Path("/tmp/comfyui.log")
        with log_path.open("w", encoding="utf-8") as log:
            self.process = subprocess.Popen(
                ["python", str(self.root / "main.py"), "--listen", "127.0.0.1", "--port", port, "--disable-auto-launch"],
                cwd=self.root,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                detail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
                raise RuntimeError(f"ComfyUI exited during startup:\n{detail}")
            try:
                response = self.http.get(f"{self.base_url}/system_stats")
                if response.is_success:
                    return
            except httpx.HTTPError:
                time.sleep(1)
        if self.process.poll() is None:
            self.process.terminate()
        detail = log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
        raise TimeoutError(f"ComfyUI did not become ready within 300 seconds:\n{detail}")

    def upload(self, path: Path, kind: str) -> str:
        # ComfyUI's built-in uploader is /upload/image for every input asset;
        # LoadAudio reads the uploaded file from the same input directory.
        # There is no stable /upload/audio route in the server API.
        endpoint = "/upload/image"
        field = "image"
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as stream:
            response = self.http.post(
                f"{self.base_url}{endpoint}",
                files={field: (path.name, stream, mime)},
                data={"type": "input", "subfolder": "automatic-video-ai", "overwrite": "true"},
            )
        response.raise_for_status()
        payload = response.json()
        return f"{payload.get('subfolder', '').strip('/')}/{payload.get('name', path.name)}".strip("/")

    @staticmethod
    def _unlink_scoped(base: Path, relative: str) -> None:
        base = base.resolve()
        target = (base / relative).resolve()
        try:
            target.relative_to(base)
        except ValueError:
            logging.warning("Refusing to delete a ComfyUI path outside %s: %s", base, target)
            return
        try:
            target.unlink(missing_ok=True)
        except OSError:
            logging.warning("Could not remove temporary ComfyUI file %s", target, exc_info=True)

    def cleanup_inputs(self, names: list[str]) -> None:
        for name in names:
            self._unlink_scoped(self.root / "input", name)

    def _cleanup_output(self, info: dict[str, str]) -> None:
        roots = {
            "output": self.root / "output",
            "temp": self.root / "temp",
            "input": self.root / "input",
        }
        base = roots.get(info.get("type", "output"))
        if base is None:
            return
        relative = str(Path(info.get("subfolder", "")) / info["filename"])
        self._unlink_scoped(base, relative)

    def _graph(self) -> dict[str, Any]:
        graph = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        if not isinstance(graph, dict):
            raise ValueError("H3 workflow must be a ComfyUI API graph")
        return graph

    def prepare_graph(self, *, first_frame: str, reference_images: list[str], reference_audio: str | None, prompt: str, duration_seconds: float, width: int, height: int, seed: int) -> dict[str, Any]:
        graph = copy.deepcopy(self._graph())
        ref = graph["ref2va"]["inputs"]
        ref.update({"prompt": prompt, "width": width, "height": height})
        graph["duration"]["inputs"]["value"] = float(duration_seconds)
        graph["noise"]["inputs"]["noise_seed"] = int(seed)
        all_images = [first_frame, *reference_images]
        if len(all_images) > 9:
            raise ValueError("Ref2VA accepts at most 9 images")
        for index, filename in enumerate(all_images):
            node_id = f"ref_image_{index}"
            graph[node_id] = {"inputs": {"image": filename}, "class_type": "LoadImage"}
            ref[f"ref_images.ref_image_{index}"] = [node_id, 0]
        if reference_audio:
            graph["ref_audio_0"] = {"inputs": {"audio": reference_audio}, "class_type": "LoadAudio"}
            ref["ref_audios.ref_audio_0"] = ["ref_audio_0", 0]
        graph["save_video"]["inputs"]["filename_prefix"] = f"video/automatic-video-ai/{uuid.uuid4().hex}"
        return graph

    @staticmethod
    def _find_video(value: Any) -> dict[str, str] | None:
        if isinstance(value, dict):
            filename = value.get("filename")
            if isinstance(filename, str) and Path(filename).suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
                return {"filename": filename, "subfolder": str(value.get("subfolder", "")), "type": str(value.get("type", "output"))}
            for child in value.values():
                found = ComfyRunner._find_video(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = ComfyRunner._find_video(child)
                if found:
                    return found
        return None

    def generate(self, graph: dict[str, Any]) -> bytes:
        response = self.http.post(f"{self.base_url}/prompt", json={"prompt": graph, "client_id": str(uuid.uuid4())})
        response.raise_for_status()
        prompt_id = response.json().get("prompt_id")
        if not prompt_id:
            raise RuntimeError("ComfyUI did not return prompt_id")
        deadline = time.monotonic() + int(os.environ.get("H3_COMFY_TIMEOUT_SECONDS", "7200"))
        while time.monotonic() < deadline:
            history = self.http.get(f"{self.base_url}/history/{prompt_id}")
            history.raise_for_status()
            payload = history.json()
            entry = payload.get(prompt_id, {}) if isinstance(payload, dict) else {}
            status = entry.get("status", {}) if isinstance(entry, dict) else {}
            if status.get("status_str") == "error":
                raise RuntimeError(json.dumps(status, ensure_ascii=False))
            if status.get("completed") is True:
                info = self._find_video(entry.get("outputs", {}))
                if not info:
                    raise RuntimeError("ComfyUI completed without a video output")
                media = self.http.get(f"{self.base_url}/view", params=info)
                media.raise_for_status()
                content = media.content
                self._cleanup_output(info)
                return content
            time.sleep(2)
        raise TimeoutError(f"ComfyUI prompt {prompt_id} exceeded timeout")
