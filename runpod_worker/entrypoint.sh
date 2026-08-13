#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${H3_MODELS_ROOT}/vae" "${H3_MODELS_ROOT}/diffusion_models" "${H3_MODELS_ROOT}/text_encoders"
mkdir -p "${COMFYUI_ROOT}/models/vae" "${COMFYUI_ROOT}/models/diffusion_models" "${COMFYUI_ROOT}/models/text_encoders"

required_models=(
  "vae/minimax_h3_video_vae_fp16.safetensors"
  "vae/minimax_h3_audio_vae_fp32.safetensors"
  "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"
  "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
)
for model in "${required_models[@]}"; do
  if [ ! -f "${H3_MODELS_ROOT}/${model}" ]; then
    echo "Missing required H3 model: ${H3_MODELS_ROOT}/${model}" >&2
    exit 1
  fi
done

for folder in vae diffusion_models text_encoders; do
  if [ -d "${H3_MODELS_ROOT}/${folder}" ]; then
    cp -sfn "${H3_MODELS_ROOT}/${folder}"/* "${COMFYUI_ROOT}/models/${folder}/" 2>/dev/null || true
  fi
done

python -u "${COMFYUI_ROOT}/main.py" \
  --listen 127.0.0.1 \
  --port "${COMFYUI_PORT}" \
  --disable-auto-launch \
  > /tmp/comfyui.log 2>&1 &

exec python /workspace/handler.py
