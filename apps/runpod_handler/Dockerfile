FROM runpod/pytorch:1.0.0-cu1290-torch260-ubuntu2204

RUN pip install runpod numpy
# Pinned for reproducible scores: `main` floats and would silently change model and
# scoring behaviour between builds. 34f5234 is the commit in the image that served
# the pilot (rippere/tribe-v2-inference:latest, built 2026-05-27).
ARG TRIBEV2_REF=34f52344e5ba96660fac877393e1954e399d3ef3
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
#   docker build --network host -f apps/runpod_handler/Dockerfile -t <tag> .
# Push a new tag per change (not just :latest) and point the RunPod template at it.
WORKDIR /workspace
COPY packages/tribe_scoring ./tribe_scoring
COPY apps/runpod_handler/handler.py .

CMD ["python3.13", "handler.py"]
