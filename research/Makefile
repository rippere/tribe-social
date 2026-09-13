.PHONY: demo setup fetch analyze open help score-corpus score-corpus-dry score-corpus-existing

PYTHON = .venv/bin/python
STREAMLIT = .venv/bin/streamlit
YT_DLP = $(shell which yt-dlp 2>/dev/null || echo "yt-dlp")
URLS_FILE = urls_demo.txt
REELS_DIR = reels

## demo   — launch the Streamlit dashboard with pre-scored corpus (zero credentials needed)
demo: _check_venv
	@echo "Launching TRIBE Social Lab → http://localhost:8501"
	@echo "Select 'Real corpus (scores.csv)' in the sidebar to view the 24-video pre-scored dataset."
	$(STREAMLIT) run demo.py

## setup  — create venv and install dependencies (requires uv)
setup:
	uv venv
	uv pip install -e .

_check_venv:
	@if [ ! -f "$(STREAMLIT)" ]; then \
		echo ""; \
		echo "  ERROR: .venv not found. Run 'make setup' first."; \
		echo "         Requires: uv  (install: curl -Lsf https://astral.sh/uv/install.sh | sh)"; \
		echo ""; \
		exit 1; \
	fi

## fetch  — download viral Shorts from urls_demo.txt into reels/
fetch:
	@mkdir -p $(REELS_DIR)
	@echo "Downloading URLs from $(URLS_FILE) → $(REELS_DIR)/"
	@grep -v '^\s*#' $(URLS_FILE) | grep -v '^\s*$$' | while read url; do \
		$(YT_DLP) \
			--format "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]" \
			--merge-output-format mp4 \
			--output "$(REELS_DIR)/%(id)s.%(ext)s" \
			--no-playlist \
			--skip-download-archive \
			"$$url" || true; \
	done
	@echo "Done. Files in $(REELS_DIR)/:"
	@ls -lh $(REELS_DIR)/*.mp4 2>/dev/null | tail -20 || echo "(none yet)"

## analyze — run Phase 1b correlation analysis and save figures
analyze:
	$(PYTHON) phase1b_correlation.py

## open   — open the dashboard in the default browser
open:
	@open http://localhost:8501 2>/dev/null || xdg-open http://localhost:8501

## score-corpus       — full E2E: load reels/ → RunPod scoring → ranked output
score-corpus:
	$(PYTHON) score_corpus.py --corpus $(REELS_DIR)

## score-corpus-dry   — validate pipeline inputs without touching RunPod (no cost)
score-corpus-dry:
	$(PYTHON) score_corpus.py --corpus $(REELS_DIR) --dry-run

## score-corpus-existing — score the pre-fetched reels/ corpus (same dir as score-corpus; kept as an explicit alias)
score-corpus-existing:
	$(PYTHON) score_corpus.py --corpus reels

## help   — print this message
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
