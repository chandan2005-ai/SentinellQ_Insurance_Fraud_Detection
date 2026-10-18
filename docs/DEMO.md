# IBM Datathon — six demonstration scenarios

**Safety notice:** every file in `sample_data` is SYNTHETIC. The motor model is synthetic and unvalidated. Demonstrate patterns, not proof of fraud.

### A. Ordinary insurance case

1. Create `motor` case, enter `policy_number=DEMO-MOTOR-001`, `incident_date=2026-07-08`, `reported_date=2026-07-09`, `policy_start=2026-01-01`, `policy_end=2026-12-31`, `claim_amount=18000`, `invoice_total=18000`, `coverage_amount=100000`, `prior_claims=0`.
2. Upload `sample_data/demo_evidence/motor_ordinary_SYNTHETIC.pdf` and review fields. Save the case form again.
3. Analyze. Evidence extraction and data quality should be available. A numeric score is shown **only if synthetic motor model was seeded and input is within its training range**.

### B. Conflicting evidence

1. Create a fresh motor case with similar manual values, adjusting the reference ID.
2. Upload `sample_data/demo_evidence/motor_conflicting_invoice_SYNTHETIC.pdf`.
3. Leave verified manual amount `18000` and invoice `18000`; save corrections and analyze. Observe `source_field_conflict` with exact document ID, page, extracted and reviewed values. This is a verification indicator, not a fraud verdict.

### C. Identical evidence used in two cases

1. Create two separate motor cases owned by the same analyst.
2. Upload `motor_evidence_reuse_A_SYNTHETIC.png` to one and `motor_evidence_reuse_B_SYNTHETIC.png` to the other (file contents are deliberately identical).
3. Analyze the second case; view `duplicate_evidence_across_cases` with document and case IDs. Go to Case Details → downloads or use `/related`. Hash equality **alone** does not prove fraudulent reuse.

### D. Manual entry without documents

1. Create a motor case with valid required fields and no uploads.
2. Analyze. See data-completeness and absent document evidence. The model does not retrain on the new record.

### E. Insufficient category data

1. Create a `health`, `life`, `cyber` or other non-motor case.
2. Analyze. `fraud_suspicion_score: null`, `underwriting_risk_score: null`, with honest model-unavailable explanation. This is deliberate abstention.

### F. New unseen motor case and persistence

1. Prepare category-specific synthetic demonstration models with `python scripts/prepare_demo_models.py motor health travel` (or Admin & audit).
2. Create a new motor case not present in the training CSV, using reasonable input values; analyze.
3. Note the model version and elapsed_ms. Refresh the page, open Case Manager and inspect the saved analysis from SQLite. The deployed artifact timestamp remains unchanged: **inference is not retraining**.

## Discussion points for judges

- Explain the distinction between verified outcomes, model-generated suspicions and rule discrepancies.
- Explain the seven tabular features and why protected attributes are excluded.
- Show extracted-field provenance and corrected-value indicators.
- Show separate Python scikit-learn/XGBoost model selection and PyTorch evidence-image classification *code path*. Do **not** claim the image classifier was trained unless it actually was on a suitable labeled image dataset.
- Explain group-aware splits, held-out evaluation, data limitations and rollback.
- Explain why a high false-positive rate can cause harmful accusations, and why a human reviewer must make critical decisions.
