FROM runpod/worker-comfyui:5.8.6-base

# The base image predates MiniMax H3 support (merged 2026-08-03). Pin an
# immutable official ComfyUI release that contains the Ref2VA node instead of
# tracking master or relying on a mutable base-image installation.
ARG COMFYUI_COMMIT=c2bcbecd82ec5ae66594340b395c24ef0217b238

RUN git -C /comfyui fetch --depth 1 origin "${COMFYUI_COMMIT}" \
    && git -C /comfyui checkout --detach "${COMFYUI_COMMIT}" \
    && python -m pip install --no-cache-dir -r /comfyui/requirements.txt \
    && test -f /comfyui/comfy_extras/nodes_minimax_h3.py \
    && grep -q 'class MiniMaxH3ReferenceToVideo' /comfyui/comfy_extras/nodes_minimax_h3.py \
    && cd /comfyui \
    && timeout 300 python main.py --quick-test-for-ci --cpu

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    COMFYUI_ROOT=/comfyui \
    COMFYUI_PORT=8188 \
    H3_WORKFLOW_PATH=/workspace/workflows/minimax-h3-ref2va-api.json \
    H3_MODELS_ROOT=/runpod-volume/models \
    H3_AUTO_DOWNLOAD_MODELS=false \
    H3_NATIVE_WIDTH=608 \
    H3_NATIVE_HEIGHT=352 \
    H3_MAX_INPUT_BYTES=8388608 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY runpod_worker/requirements.txt /tmp/runpod-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/runpod-requirements.txt
COPY runpod_worker/handler.py /workspace/handler.py
COPY runpod_worker/comfy_runner.py /workspace/comfy_runner.py
COPY runpod_worker/entrypoint.sh /workspace/entrypoint.sh
COPY workflows/minimax-h3-ref2va-api.json /workspace/workflows/minimax-h3-ref2va-api.json
RUN chmod +x /workspace/entrypoint.sh

ENTRYPOINT ["/workspace/entrypoint.sh"]
