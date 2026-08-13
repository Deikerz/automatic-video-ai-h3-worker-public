FROM runpod/worker-comfyui:5.8.6-base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    COMFYUI_ROOT=/comfyui \
    COMFYUI_PORT=8188 \
    H3_WORKFLOW_PATH=/workspace/workflows/minimax-h3-ref2va-api.json \
    H3_MODELS_ROOT=/runpod-volume/models \
    H3_AUTO_DOWNLOAD_MODELS=false \
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
