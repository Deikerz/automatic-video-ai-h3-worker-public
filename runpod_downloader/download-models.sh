#!/bin/sh
set -eu

volume_root="$(dirname "${H3_MODELS_ROOT:-/runpod-volume/models}")"
if [ "$volume_root" != "/runpod-volume" ]; then
  echo "H3_MODELS_ROOT must resolve directly below /runpod-volume" >&2
  exit 64
fi

mkdir -p \
  "$volume_root/models/vae" \
  "$volume_root/models/diffusion_models" \
  "$volume_root/models/text_encoders" \
  "$volume_root/.automatic-video-ai-h3-ready"

download_one() {
  relative_path="$1"
  expected_bytes="$2"
  expected_sha256="$3"
  source_url="$4"
  target="$volume_root/$relative_path"
  partial="$target.partial"

  if [ -f "$target" ] && [ "$(stat -c%s "$target")" = "$expected_bytes" ]; then
    actual_sha256="$(sha256sum "$target" | cut -d ' ' -f 1)"
    if [ "$actual_sha256" = "$expected_sha256" ]; then
      echo "H3_MODEL_ALREADY_VERIFIED $relative_path"
      return
    fi
  fi

  rm -f "$target"
  if [ -f "$partial" ] && [ "$(stat -c%s "$partial")" -gt "$expected_bytes" ]; then
    rm -f "$partial"
  fi
  if [ ! -f "$partial" ] || [ "$(stat -c%s "$partial")" -ne "$expected_bytes" ]; then
    curl --fail --location --continue-at - \
      --retry 12 --retry-delay 10 --retry-max-time 900 --retry-all-errors \
      --connect-timeout 30 --speed-time 180 --speed-limit 1048576 \
      --output "$partial" "$source_url"
  fi
  actual_bytes="$(stat -c%s "$partial")"
  if [ "$actual_bytes" != "$expected_bytes" ]; then
    echo "Size mismatch for $relative_path: got $actual_bytes, expected $expected_bytes" >&2
    exit 1
  fi
  actual_sha256="$(sha256sum "$partial" | cut -d ' ' -f 1)"
  if [ "$actual_sha256" != "$expected_sha256" ]; then
    echo "SHA-256 mismatch for $relative_path" >&2
    exit 1
  fi
  mv "$partial" "$target"
  echo "H3_MODEL_VERIFIED $relative_path"
}

download_encoder() {
  download_one \
  "models/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors" \
  "15687142551" \
  "35a88d51044231fe332301d7a62aa81e3f2cba62febeb446e2c1e3e0ef76f2c6" \
  "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
}

if [ "${H3_DOWNLOAD_ROLE:-all}" = "encoder" ]; then
  download_encoder
  encoder_ready="$volume_root/.automatic-video-ai-h3-encoder-ready"
  mkdir -p "$encoder_ready"
  grep 'models/text_encoders/' /opt/h3-models.sha256 > "$encoder_ready/sha256sums.txt.partial"
  sync "$encoder_ready/sha256sums.txt.partial"
  mv "$encoder_ready/sha256sums.txt.partial" "$encoder_ready/sha256sums.txt"
  echo "H3_ENCODER_READY"
  exec httpd -f -p 8000 -h "$encoder_ready"
fi
if [ "${H3_DOWNLOAD_ROLE:-all}" != "all" ]; then
  echo "H3_DOWNLOAD_ROLE must be all or encoder" >&2
  exit 64
fi

download_one \
  "models/vae/minimax_h3_video_vae_fp16.safetensors" \
  "5207808496" \
  "7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522" \
  "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_fp16.safetensors"
download_one \
  "models/vae/minimax_h3_audio_vae_fp32.safetensors" \
  "605254808" \
  "8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48" \
  "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors"
download_one \
  "models/diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors" \
  "20958205608" \
  "f86f2f79ebd2d76eb8eeb46091e83982e6ff51d255747e7b16e92834b392b8e9" \
  "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors"
download_encoder

(cd "$volume_root" && sha256sum -c /opt/h3-models.sha256)
marker="$volume_root/.automatic-video-ai-h3-ready/sha256sums.txt"
marker_partial="$marker.partial"
cp /opt/h3-models.sha256 "$marker_partial"
sync "$marker_partial"
mv "$marker_partial" "$marker"
echo "H3_MODELS_READY"

exec httpd -f -p 8000 -h "$volume_root/.automatic-video-ai-h3-ready"
