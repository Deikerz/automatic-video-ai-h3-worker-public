#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${H3_MODELS_ROOT}/vae" "${H3_MODELS_ROOT}/diffusion_models" "${H3_MODELS_ROOT}/text_encoders"
mkdir -p "${COMFYUI_ROOT}/models/vae" "${COMFYUI_ROOT}/models/diffusion_models" "${COMFYUI_ROOT}/models/text_encoders"

model_specs=(
  "vae/minimax_h3_video_vae_fp16.safetensors|5207808496"
  "vae/minimax_h3_audio_vae_fp32.safetensors|605254808"
  "diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors|20958205608"
  "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors|15687142551"
)

if [ "${H3_AUTO_DOWNLOAD_MODELS:-false}" = "true" ]; then
  echo "H3_AUTO_DOWNLOAD_MODELS is disabled: downloading 39 GB during a billed Serverless cold start is unsafe" >&2
  exit 64
fi

for spec in "${model_specs[@]}"; do
  IFS='|' read -r model expected_bytes <<< "${spec}"
  target="${H3_MODELS_ROOT}/${model}"
  if [ ! -f "${target}" ] || [ "$(stat -c%s "${target}")" -ne "${expected_bytes}" ]; then
    echo "Missing or size-mismatched required H3 model: ${target}; expected exactly ${expected_bytes} bytes" >&2
    exit 1
  fi
done

for folder in vae diffusion_models text_encoders; do
  if [ -d "${H3_MODELS_ROOT}/${folder}" ]; then
    cp -sfn "${H3_MODELS_ROOT}/${folder}"/* "${COMFYUI_ROOT}/models/${folder}/" 2>/dev/null || true
  fi
done

exec python /workspace/handler.py
