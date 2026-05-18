.PHONY: demo fetch analyze open help

PYTHON = .venv/bin/python
STREAMLIT = .venv/bin/streamlit
YT_DLP = $(shell which yt-dlp 2>/dev/null || echo "yt-dlp")
URLS_FILE = urls_demo.txt
REELS_DIR = reels_new

## demo   — launch the Streamlit dashboard (real corpus mode)
demo:
	@echo "Starting TRIBE Social Lab on http://localhost:8501 ..."
	$(STREAMLIT) run demo.py

## fetch  — download viral Shorts from urls_demo.txt into reels_new/
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

## help   — print this message
help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
