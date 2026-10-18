# Verification summary (2026-10-17)

## Verified in this environment

- `pytest -q backend/tests`: **20 passed**, 2 non-failing warnings.
- `python -m compileall -q backend/app scripts`: completed without errors.
- `node --check frontend/js/app.js`: completed without errors.
- Alembic `upgrade head` against fresh SQLite: completed; tables created.
- `scripts/seed_demo_model.py`: trained and deployed the **synthetic motor-only** demonstration model; performance measured against the synthetic held-out split (not valid on real insurance claims).
- PyTorch ResNet18 training checkpoint and inference: smoke-tested on a tiny in-memory synthetic image set; this verifies code functionality only, not actual classification accuracy.
- FastAPI TestClient served `frontend/index.html`, CSS and JavaScript successfully; authenticated upload-to-analysis, model deployment, duplicate checks and field provenance are included in automated tests.

## Not verified / blocked

- Direct Chromium browser E2E was attempted, but the isolated browser environment refused navigation to the local server (`ERR_BLOCKED_BY_ADMINISTRATOR`). No browser integration success is claimed.
- Docker build, Windows installation on the user's machine, external Tesseract binary, production Postgres operations and Internet-hosted deployment have not been verified.
- Full PyTorch training on real, representative labeled insurance images was not performed because no such authorized dataset was supplied.
- No production security audit, data privacy certification, real-world calibration or fraud detection effectiveness evaluation has been performed.

## Interpretation

This package is a **tested local research MVP** with source code, deliberately limited demo predictions, datasets and operational documentation. It is not a finished production-grade insurance system.

## October 18 upgrade

- Separate synthetic demo models can now be trained/deployed for all 14 insurance categories.
- Admin dashboard includes click-to-prepare three sample categories or all 14.
- Actual fictional Motor/Health/Travel PDFs are bundled and tested, including hospitalization dates and trip dates.
- Model feature coverage is shown separately from form completeness.
- New rules check invalid hospitalization/travel dates, repair estimates and document category mismatch.
- Windows setup scripts, runtime path normalization, and a smaller core install are included.
- 26 automated tests pass; 14-category standalone training was verified.
- Chromium is blocked from localhost in this execution environment; automated real-browser login/navigation was not independently verified.
