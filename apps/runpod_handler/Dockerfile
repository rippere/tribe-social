FROM runpod/pytorch:1.0.0-cu1290-torch260-ubuntu2204

RUN pip install runpod numpy
# TODO(operator): pin TRIBEV2_REF to a real commit SHA for reproducible scores —
# `main` floats and will silently change model/scoring behaviour between builds.
ARG TRIBEV2_REF=main
RUN pip install git+https://github.com/facebookresearch/tribev2@${TRIBEV2_REF}

# HF_TOKEN is NOT baked into the image — the RunPod template injects it as a
# runtime env var (see deploy.sh saveTemplate env), so the token never lands in
# a (public) image layer.
ENV HF_HUB_DOWNLOAD_TIMEOUT=300
# Base image sets HF_HUB_ENABLE_HF_TRANSFER=1, but hf_transfer isn't installed —
# whisperx (spawned by TRIBE v2 to transcribe audio) inherits the flag and dies
# fetching the faster-whisper model. Force it off → standard HF downloader.
ENV HF_HUB_ENABLE_HF_TRANSFER=0

# Build context is the MONOREPO ROOT (not this app dir), so the shared
# scoring package can be copied in alongside the handler.
#   docker build -f apps/runpod_handler/Dockerfile -t <tag> .
WORKDIR /workspace
COPY packages/tribe_scoring ./tribe_scoring
COPY apps/runpod_handler/handler.py .

CMD ["python3.13", "handler.py"]
