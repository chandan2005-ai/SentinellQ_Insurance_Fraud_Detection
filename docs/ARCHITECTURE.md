# Architecture, data flow and controls

## Components and flow

```text
Browser SPA (HTML/CSS/JS, Chart.js when reachable)
  ↓ Authorization: signed JWT
FastAPI routes → SQLAlchemy case and audit store (SQLite local / PostgreSQL-compatible ORM)
  ↓                      ↑                         ↘ Model admin
Document processor      Case service                Dataset import and registry
PDF text / OCR / DOCX   ← reviewed user values       ↓ sklearn/XGBoost training
  ↓                                                   ↓ held-out reports
provenance-backed extracted fields                   Versioned model artifacts
  ↓                                                         ↓
Deterministic rules / cross-document consistency ← Trained category-specific model
  ↓                                          ↘ Isolation Forest novelty indicator
Data quality, uncertainty, decision-support analysis (no binding decision)
  ↓
Analysis saved to DB → dashboard / human review / audit history
```

New input is **inference only**. No hidden label updates or retraining. File bytes remain outside public static directories; downloads use authenticated authorization. Passwords use PBKDF2 400k iterations with per-user salt; JWT signatures use a user-configured secret, and tokens expire. Access to cases defaults to case owner unless admin. Dataset/train/deploy/audit changes are admin-only.

## Supported data types

- Structured data: numeric amounts, coverage, claim timing, prior claims, policy identifiers and category-specific fields.
- Embedded text PDF, scanned PDF and raster images via external Tesseract OCR, and DOCX text. Extracted fields maintain source document/page/text offsets, extraction method and human-validation flags.
- Image bytes: resolution and Laplacian blur measure, SHA-256 exact duplicate and difference-hash near-duplicate. Blurry image or duplicate evidence is **not** proof of manipulation.
- CSV supervised training datasets: fixed seven-feature numerical feature contract plus binary verified fraud label, optionally `entity_group` for leakage-aware group splits.
- PyTorch classifier: user-provided labeled image folders, transfer learning when ImageNet weights are requested; inference only after a checkpoint is created.

## Insurance registry

`motor`, `health`, `life`, `property`, `travel`, `commercial`, `marine`, `crop`, `personal_accident`, `liability`, `cyber`, `pet`, `gadget`, `workers_comp`.

The registry defines different forms and required fields. Shared tabular features do not imply models generalize between insurance categories. Model readiness is a *separate* status for each category.

## Scoring methodology (demo only)

Rules derive specific values and source references; several correlated rules are NOT summed. With a deployed model in its training distribution:

`demo_suspicion_index = clip(0.80 * uncalibrated_model_index + 0.20 * maximum_rule_severity, 0, 100)`

No deployed model or out-of-distribution input → `fraud_suspicion_score = null`. The admin may change the 80/20 weights and the provisional low/moderate/high boundaries through audited settings. Defaults: low below 25, moderate below 50, high below 75, and critical 75 or above. These **must not** be interpreted as validated thresholds or fraud probabilities. No underwriting model exists by default; underwriting risk is `null`. Rules and data completeness remain available without a model. Human verification is required for consequential decisions.

## ML and training

1. Require label definition/provenance and a seven-feature CSV schema.
2. Remove exactly duplicate rows and inspect missingness/label balance.
3. Separate train/validation/test (60/20/20); optionally use group-disjoint identity splits.
4. Fit preprocessing on training data only; train a scikit-learn logistic baseline and an XGBoost alternative when installed.
5. Compare validation PR-AUC to select candidate; report independent held-out precision/recall/F1/ROC-AUC/PR-AUC/confusion matrix/FPR/FNR/Brier.
6. Train Isolation Forest on training observations; report novelty separately from fraud classification.
7. Version the model checkpoint; deploy only after deliberate admin action. An older version can be redeployed to roll back.
8. For numeric inputs well outside training min/max, abstain and request review.

PyTorch image classifier has independent input transforms, ResNet18 classifier head, class-level validation, checkpoint serialization, versioned inference, and threshold-based abstention. It is **not** an insurance fraud or tampering predictor by default.

## Non-goals / required extension work

Real-world policy coverage adjudication, clinical interpretation, validated fraudulent-image detection, signed document authenticity, explainable local SHAP attributions, background job queues, full enterprise retention controls and clinical-grade privacy controls are **not implemented**. See `docs/LIMITATIONS.md`.
