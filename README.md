<<<<<<< HEAD
# SentinelIQ — AI-Powered Multi-Insurance Evidence & Risk Decision Support

**IBM Datathon topic:** Real-Time AI for Critical Decisions.

A **runnable research/demo** full-stack application, not a claim-adjudication system. Handles fourteen insurance-type form schemas; includes document extraction, evidence comparison, an authenticated database-backed dashboard, labeled CSV import, genuine scikit-learn/XGBoost training, a PyTorch image-classification training/inference path, versioned model deployment, audit logs, and automated tests. **All bundled cases and datasets are SYNTHETIC.** No fraud, underwriting, or image manipulation model is represented as externally validated.

## Start on Windows 11 (Python 3.12 recommended)

Open PowerShell in `insurance-risk-platform`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -c "from pathlib import Path; import secrets; p=Path('.env'); p.write_text(p.read_text().replace('REPLACE_WITH_UNIQUE_RANDOM_SECRET_AT_LEAST_32_CHARACTERS', secrets.token_urlsafe(48)))"
alembic -c backend/alembic.ini upgrade head
python scripts/create_admin.py --email admin@example.com
python scripts/generate_synthetic.py
python scripts/generate_demo_docs.py
python scripts/prepare_demo_models.py motor health travel
uvicorn app.main:app --app-dir backend --reload
```

**Open:** http://127.0.0.1:8000 and sign in using the email/password chosen with `create_admin.py`. API docs: http://127.0.0.1:8000/docs. Stop with `Ctrl+C`.

**If `py -3.12` is unavailable:** install Python 3.12 from python.org, then reopen PowerShell. PyTorch wheels may be unavailable on some Python versions. For PowerShell activation policy errors, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal, or use `.venv\Scripts\python.exe` explicitly. Use **PowerShell**, not the `>>>` Python interpreter.

**Do not omit the password step.** The application does not create public default login credentials. There is no unauthenticated web registration endpoint.

**OCR:** embedded-text PDFs work immediately. For scanned PDFs and pictures, install the external Tesseract OCR executable and add it to PATH. On Windows, ensure `tesseract --version` works before starting the API. If Tesseract is unavailable, upload still works for valid image files but returns an OCR limitation; no extracted values are invented.

## Quick start with Docker

Docker image includes Tesseract and pinned Python dependencies, but PyTorch makes the image large. Install Docker Desktop and from the project root:

```bash
cp .env.example .env
python -c "from pathlib import Path; import secrets; p=Path('.env'); p.write_text(p.read_text().replace('REPLACE_WITH_UNIQUE_RANDOM_SECRET_AT_LEAST_32_CHARACTERS', secrets.token_urlsafe(48)))"
docker compose up --build -d
docker compose exec app python scripts/create_admin.py --email admin@example.com
docker compose exec app python scripts/prepare_demo_models.py motor health travel
```

Open http://127.0.0.1:8000. **The Compose configuration intentionally binds to 127.0.0.1 only**. If accessing from another device, use an authenticated HTTPS reverse proxy and apply the production controls in `docs/LIMITATIONS.md` first.

## Important design boundaries

- The 14 insurance-type registry entries are **form/data-schema support**, not 14 validated fraud models.
- All 14 training CSV files under `sample_data/*_SYNTHETIC.csv` are artificial simulations with documented label generation; they are not public or real claims.
- **Synthetic demonstration models are installed only after explicit opt-in** with `scripts/prepare_demo_models.py` or the administrator interface. All 14 categories can be trained from bundled synthetic CSVs; these do not represent validated fraud models.
- Fraud-model index and anomaly results are **not** calibrated probabilities or proof of fraud. The 0–100 combination is a provisional research setting.
- Underwriting score and manipulation-detector output stay **unavailable** until independently suitable labels, trained models and validation are provided.
- Image uploads always receive image quality and dHash-based duplicate checks. A genuine PyTorch ResNet18 classifier is available through `scripts/train_image.py`; it only runs after a compatible checkpoint is trained.
- The model never retrains during case analysis. Human analysts review field extraction and all consequential decisions.

## User workflow

1. Sign in to dashboard. Choose **New analysis**.
2. Select category, enter policy/claim fields, click **Save new case**.
3. Upload a PDF, PNG, JPEG or DOCX. Check automatically extracted values and save corrections to record human review.
4. Click **Analyze saved case**; inspect rule evidence, score availability, OOD warnings, missing fields, and recommended verification.
5. Use **Case manager** to search saved cases, download evidence, correct values, delete evidence, and reanalyze.
6. Admin: import **CSV datasets**, review quality, train candidate scikit-learn and XGBoost models, inspect held-out metrics, **deploy a version** or deploy an older version to roll back. Edit and audit provisional decision thresholds. Record a verified investigation outcome separately from alerts.
7. Open **Model readiness** for category-by-category support and validation caveats.

See `docs/DEMO.md` for six scripted demonstrations and ready-to-upload files.

## Files and responsibilities

| Location | Purpose |
|---|---|
| `frontend/index.html`, `frontend/css/main.css`, `frontend/js/app.js` | Responsive authenticated web dashboard, upload/review, case and model management |
| `backend/app/main.py` | OpenAPI/FastAPI REST endpoints, authorization, persistence orchestration |
| `backend/app/database/` | SQLAlchemy engine and schemas for cases, documents, analyses, models, audits |
| `backend/app/document_processing/processor.py` | Verified file signatures, PDF text, OCR, DOCX, conservative regex fields, image hashes |
| `backend/app/insurance_types/registry.py` | 14 category schema definitions and required fields |
| `backend/app/services/scoring.py` | Source-attributed rules, cross-document and cross-case checks, limited-score methodology |
| `backend/app/training/tabular.py` | Dataset validation, leakage-aware splits, sklearn/XGBoost models, Isolation Forest, evaluation, OOD |
| `backend/app/image_classifier/model.py` | PyTorch ResNet18 image preprocessing, train/validation, checkpoint, abstention and inference |
| `backend/app/security/auth.py` | Password hashing, JWT verification, protected endpoints and roles |
| `backend/migrations` | Alembic baseline schema migrations |
| `scripts/` | Account creation, synthetic datasets, demo evidence and optional model training |
| `backend/tests/` | API, rule, upload, security, ML and deployment regression tests |
| `sample_data/` | **Clearly labeled synthetic** CSVs and PDF/image evidence |
| `docs/` | Architecture, API, method, readiness, limitations, demo instructions |
| `runtime/` | SQLite DB, uploads, datasets and trained artifacts (git-ignored) |

Full individual file list: `FILE_MANIFEST.md`.

## Database: where cases are stored

With default local configuration the actual database is `runtime/insurance.db` (SQLite). Open it in **DB Browser for SQLite** or via SQL:

```sql
SELECT id, category, status, outcome, created_at FROM cases;
SELECT id, case_id, original_name, sha256 FROM documents;
SELECT case_id, result, created_at FROM analyses;
SELECT category, approval_status, deployed, metrics FROM model_versions;
SELECT action, at FROM audit_events;
```

Upload binaries are private files under `runtime/uploads/`; only relative storage names are in the database. CSVs are in `runtime/datasets/`, models in `runtime/model_artifacts/`. **These contain potentially sensitive information; do not upload `runtime/` to GitHub.**

## Tests / verification

```powershell
pytest -q backend/tests
python -m compileall -q backend/app scripts
```

The suite validates API authentication/permissions, 14 type schemas, manual fields, PDF extraction, corrupted/oversized file rejection, duplicate evidence, image quality/hashes, policy-date and amount discrepancies, field-correction provenance, admin training/deployment, test metrics, unavailable predictions and rollback. The PyTorch training path needs labeled class folders and is not presented as externally evaluated by the included automated tests.

See `docs/API.md` and Swagger at `/docs` for detailed request contracts. See `docs/LIMITATIONS.md` before using any real insurance data.

## Troubleshooting

- **`ModuleNotFoundError: app`**: use `uvicorn app.main:app --app-dir backend --reload` exactly from the project root.
- **`Could not import module`**: activate the virtual environment, verify package installation and run `python -m compileall -q backend/app`.
- **`JWT_SECRET` error**: copy `.env.example` and replace placeholder with a fresh random secret.
- **Invalid PDF/image**: use a real PDF or PNG/JPEG, not renamed text; encrypted/corrupt/oversized input is rejected intentionally.
- **Missing OCR**: install the Tesseract binary and PATH entry; `pytesseract` alone is not enough.
- **Database is locked**: do not run concurrent writes with SQLite under production load; use PostgreSQL and review migration configuration.
- **Missing category model**: run `python scripts/prepare_demo_models.py motor health travel` for the three sample categories, or enable models in **Admin & audit**. Every numerical prediction remains a **synthetic demo index**.
- **Empty model score**: expected for unsupported categories, absent models and out-of-distribution cases.
- **Port 8000 occupied**: run `uvicorn app.main:app --app-dir backend --port 8001` and browse port 8001.
- **First setup on Python 3.14**: for compatible pinned ML wheels, use a Python 3.12 virtual environment.

## Sources and real-world data

No private, unlicensed, or real insurance records are bundled. To evaluate a model for real use, obtain an appropriately licensed dataset with **independently verified fraud labels**, document the population and policy scope, remove protected variables and leakage, split by identity/time as appropriate, evaluate calibration and fairness, secure approvals, and monitor performance. Synthetic label performance cannot establish real-world fraud accuracy.

## October 2026 fix: Health/Travel/Motor score unavailable

The original `seed_demo_model.py` created **only a synthetic Motor model**, so Health
and Travel cases displayed `No deployed category-specific fraud model`. A "100%"
form completeness result meant only that the **three mandatory form fields** were
provided, not that the seven model inputs were present.

**Updated ZIP quick install for Windows:**

1. Install Python 3.12 if missing: `winget install --id Python.Python.3.12 -e` in PowerShell, reopen the terminal.
2. Extract this whole ZIP to a writable folder. **Do not delete or replace an existing `runtime/` folder** if updating a prior install. Back it up first.
3. Double-click `SETUP_WINDOWS.bat`. This installs core dependencies, creates or reuses `.env`, initializes the database, and **explicitly installs synthetic demo models for Motor, Health and Travel**. It prompts to create an administrator on first setup.
4. Double-click `RUN_WINDOWS.bat`; open http://127.0.0.1:8000 and sign in with the admin credentials you created.
5. For an existing claim: **Case manager → open case → Re-run analysis**. Old analyses are snapshots and are not rewritten when models are deployed.
6. To enable additional synthetic categories: **Admin & audit → Prepare all 14 categories**. Or run `python scripts/prepare_demo_models.py --all` with your activated venv. This command is idempotent, only fills categories with no active model, and preserves already deployed models.

### Exact PDF testing workflow

Three fictional claim PDFs are located in `sample_data/claim_papers/`:

| Insurance | Policy | Claim amount | Key dates |
|---|---|---:|---|
| Motor | DEMO-MOTOR-001 | ₹18,000 | Incident 2026-07-08 |
| Health | DEMO-HEALTH-001 | ₹24,500 | Admission 2026-06-14, discharge 2026-06-16 |
| Travel | DEMO-TRAVEL-001 | ₹12,500 | Trip 2026-08-10 to 2026-08-20 |

Open **New analysis**, select the matching category and create a case with policy number,
incident date and claim amount. Upload the corresponding PDF. The extractor fills
reported date, policy dates, invoice values, coverage, prior claims, and relevant
hospital/trip/vehicle details. Check each populated field, then choose **Save new case**
or **Analyze saved case**, confirming you reviewed those values. Reopen the case to view
evidence comparisons, feature completeness, and synthetic demonstration index.
If the document conflicts with the saved values, discrepancy alerts appear; consistent
papers appropriately have **zero evidence discrepancies**, which does not prove legitimacy.

**Important limitations of the fix:** These demonstration index numbers come from separate
trained models with artificially simulated labels. They are neither proven fraud rates nor
real-world performance. Underwriting risk **remains unavailable** because no independently
trained underwriting model or ground truth is provided by these claim PDFs. An out-of-range
case may still correctly abstain instead of returning a numerical index. Real claims
require licensed, independently labeled data and domain validation.

### Fix ambiguous SQLite locations

The default SQLite file is always rooted at `<project>/runtime/insurance.db`, even
if you launch from a different working directory. Default `DATA_DIR=./runtime`
and `DATABASE_URL=sqlite:///./runtime/insurance.db` are normalized relative to
the project root. If your previous setup has another database in `backend/runtime/`,
**do not delete it**. Back up both files and decide which one contains the original
claims before migrating data. The update does not silently merge different databases.

### Smaller core installation

`requirements-core.txt` installs everything needed to run the website, PDF and OCR
processing, training, and model inference; it does **not** include PyTorch. Install
`requirements.txt` only when you want to train or run the optional image classifier.
Image uploads still receive image-quality/hash analysis without PyTorch. Scanned image OCR
still requires the Tesseract executable.
=======
# SentinellQ_Insurance_Fraud_Detection
>>>>>>> 95b1427feb4b36a9612167742daa0c151a02dd3a
