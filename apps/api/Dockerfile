FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# TODO(operator): bump YTDLP_VERSION deliberately to a recent release tag
# (https://github.com/yt-dlp/yt-dlp/releases). Pinning avoids `releases/latest`
# silently changing the binary between builds; yt-dlp needs regular bumps to keep
# up with site changes, so treat this as an intentional, reviewed update.
ARG YTDLP_VERSION=2025.08.11
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/download/${YTDLP_VERSION}/yt-dlp \
    -o /usr/local/bin/yt-dlp && chmod +x /usr/local/bin/yt-dlp

RUN pip install uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .

EXPOSE 8080
CMD ["/bin/sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
