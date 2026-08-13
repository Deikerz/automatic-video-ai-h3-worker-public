# MiniMax H3 Ref2VA RunPod Worker

This worker runs the official ComfyUI Ref2VA graph with the cost-oriented weights:

- diffusion: `minimax_h3_ref2va_pruned_fp8_scaled.safetensors`;
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

The four published H3 weights occupy approximately 39 GB before ComfyUI caches and generated files. If a temporary volume is approved, use 50 GB as the absolute minimum and 64 GB for operational headroom; 10 GB is not sufficient.

Never set `H3_AUTO_DOWNLOAD_MODELS=true` on a Serverless endpoint. The worker refuses that setting because downloading approximately 39 GB while a GPU worker is billed creates an unbounded and duplicable cold-start cost. Stage and validate all four files before endpoint creation; the worker exits before ComfyUI starts if any file is absent or incomplete.

## Models

Prepare the model files off-platform or upload the four files through a storage interface before creating the endpoint. Verify the model license and commercial-use terms before publishing generated videos.

## Endpoint settings

- queue endpoint;
- minimum workers: `0`;
- maximum workers: `1` initially;
- execution timeout: no longer than the explicitly approved per-request limit (the safe example is `3600` seconds);
- primary GPU: RTX 4090 Community;
- fallback endpoint: A40 48 GB;
- attach the Network Volume in the same datacenter as the endpoint;
- use a 50–64 GB Network Volume and pre-populate all four weights before enabling the endpoint;
- keep the endpoint private and call it through the local API.

Do not route traffic to the endpoint until all four model-size checks pass. If a temporary Network Volume is used for an MVP session, create and delete it inside that same bounded deployment session; do not leave it attached or merely scale the endpoint to zero, because storage remains billable.

The local application uses `H3_PROVIDER_MODE=runpod_serverless`, submits `/run`, polls `/status/{job_id}`, downloads the returned MP4 and serves it from `/outputs`.

The current worker transport is intentionally `return_mode=base64`; URL/object-storage output is not silently accepted until an S3-compatible upload contract is configured.
