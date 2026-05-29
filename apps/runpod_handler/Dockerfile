FROM runpod/pytorch:1.0.0-cu1290-torch260-ubuntu2204

RUN pip install runpod numpy
RUN pip install git+https://github.com/facebookresearch/tribev2

ARG HF_TOKEN=""
ENV HF_TOKEN=$HF_TOKEN
ENV HF_HUB_DOWNLOAD_TIMEOUT=300
# Base image sets HF_HUB_ENABLE_HF_TRANSFER=1, but hf_transfer isn't installed —
# whisperx (spawned by TRIBE v2 to transcribe audio) inherits the flag and dies
# fetching the faster-whisper model. Force it off → standard HF downloader.
ENV HF_HUB_ENABLE_HF_TRANSFER=0

WORKDIR /workspace
COPY run_and_save.py .
COPY handler.py .

CMD ["python3.13", "handler.py"]
