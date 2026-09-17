# Security Policy

## Reporting a vulnerability

Please report security issues **privately**, not as a public issue.

Use GitHub's [private vulnerability reporting](https://github.com/rippere/tribe-social/security/advisories/new) on this repository. Include what you found, how to reproduce it, and what an attacker could do with it.

Expect an initial response within about a week. This is a research project maintained by one person, not a funded product with an on-call rotation — please size your expectations accordingly, and do not treat a slow reply as an invitation to disclose publicly.

## Credential exposure

If you find a live credential committed anywhere in this repository or its history, treat it as urgent and report it privately using the link above. Do not open an issue, do not include the credential value in a public PR, and do not test how far it gets you.

## For contributors

This repository must never contain credentials.

- `.env`, `.env.*`, and `.deploy.env` are git-ignored. Keep them that way.
- Run `bash scripts/install-hooks.sh` after cloning. It installs a pre-commit hook that blocks commits whose staged diff contains real-looking API keys (`rpa_`, `hf_`, `sk-`, `AKIA…`).
- The hook has an escape hatch — `SECRETS_OK=1 git commit` — for the case where a match is a genuine false positive. If you use it, be certain.
- New configuration keys go in `research/.env.example` with a **placeholder** value.

## Scope

This project runs third-party model inference on rented GPU infrastructure and downloads public videos with `yt-dlp`. Issues in RunPod, Hugging Face, Meta's TRIBE v2, or `yt-dlp` itself should go to those projects. Report here anything about how *this* code handles credentials, user uploads, job state, or the admin endpoint.
