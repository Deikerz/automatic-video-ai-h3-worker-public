# MiniMax H3 Ref2VA RunPod Worker

Public source package for the production worker used by `automatic-video-ai`.
The container is published to GitHub Container Registry and contains no API
keys or model weights. Models are loaded from an attached, pre-populated RunPod
Network Volume at `/runpod-volume/models`.

The worker supports an initial frame, up to eight additional reference images,
optional reference audio, Spanish dialogue, strict first-person POV prompting,
and MP4 output as Base64.

Published model set:

- `minimax_h3_ref2va_pruned_int8_convrot.safetensors`
- `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- `minimax_h3_video_vae_fp16.safetensors`
- `minimax_h3_audio_vae_fp32.safetensors`

The attached Network Volume must have at least 50 GB; 64 GB is recommended.
The worker never downloads model files and enables Hugging Face/Transformers
offline mode. Missing or incomplete weights make the container fail before it
starts accepting jobs. Use only temporary volumes with an independent cleanup
deadline; deleting an endpoint does not delete its volume.
