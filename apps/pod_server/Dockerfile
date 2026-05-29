# Warm TRIBE v2 inference server for a PERSISTENT RunPod GPU pod (A100 80GB).
# Models are NOT baked — they download once to the pod's persistent disk on first
# boot and stay cached. The server loads them into VRAM at startup and stays warm.
FROM runpod/pytorch:1.0.0-cu1290-torch260-ubuntu2204

RUN pip install runpod numpy fastapi "uvicorn[standard]"
RUN pip install git+https://github.com/facebookresearch/tribev2

# HF_TOKEN is NOT baked in — it's passed as a pod env var at runtime so the
# token never lands in a (public) image layer.
ENV HF_HUB_DOWNLOAD_TIMEOUT=300
ENV HF_HUB_ENABLE_HF_TRANSFER=0
ENV TRIBE_CACHE=/workspace/cache

WORKDIR /workspace
COPY run_and_save.py .
COPY server.py .

EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
