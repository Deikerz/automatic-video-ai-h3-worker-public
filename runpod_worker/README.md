# MiniMax H3 Ref2VA RunPod Worker

This worker runs the official ComfyUI Ref2VA graph with the cost-oriented weights:

- diffusion: `minimax_h3_ref2va_pruned_int8_convrot.safetensors`;
- text encoder: `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`;
- video VAE: FP16;
- audio VAE: FP32.

The handler accepts one 5–15 second clip per job. Inputs are base64 JSON objects produced by the local FastAPI client: `first_frame`, `reference_images`, optional `reference_audio`, `prompt`, `dialogue`, `duration_seconds`, `width`, `height` and `seed`.

## Build

From the repository root:

```powershell
.\scripts\build-runpod-worker.ps1 -RegistryImage <registry>/<user>/automatic-video-ai
```

The Docker image uses the public `runpod/worker-comfyui:5.8.6-base` image and adds the H3 handler/workflow. Model files should live on an attached RunPod Network Volume under `/runpod-volume/models/{vae,diffusion_models,text_encoders}`. This prevents model downloads during every worker cold start.

The four published H3 weights occupy approximately 39 GB before ComfyUI caches and generated files. Use a 50 GB volume as the absolute minimum and 64 GB for operational headroom; the existing 10 GB volume is not sufficient.

Set `H3_AUTO_DOWNLOAD_MODELS=true` on the endpoint for the first deployment. The worker resumes the four official Hugging Face downloads into the persistent volume and validates their minimum sizes before starting ComfyUI. Keep the volume attached for subsequent scale-to-zero workers so downloads happen only once.

## Models

Run `scripts/prepare-runpod-models.ps1` against a mounted volume or upload the four files through the RunPod S3-compatible API. Verify the model license and commercial-use terms before publishing generated videos.

## Endpoint settings

- queue endpoint;
- minimum workers: `0`;
- maximum workers: `1` initially;
- execution timeout: at least `7200` seconds;
- primary GPU: RTX 4090 Community;
- fallback endpoint: A40 48 GB;
- attach the Network Volume in the same datacenter as the endpoint;
- use a 50–64 GB Network Volume and pre-populate all four weights before enabling the endpoint;
- keep the endpoint private and call it through the local API.

The local application uses `H3_PROVIDER_MODE=runpod_serverless`, submits `/run`, polls `/status/{job_id}`, downloads the returned MP4 and serves it from `/outputs`.

The current worker transport is intentionally `return_mode=base64`; URL/object-storage output is not silently accepted until an S3-compatible upload contract is configured.
