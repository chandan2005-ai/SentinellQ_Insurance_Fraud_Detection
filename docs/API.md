# REST API (OpenAPI at `/docs`)

Base address: `http://127.0.0.1:8000`. After login, set `Authorization: Bearer <token>` on all protected endpoints. Auth token TTL defaults to 90 minutes.

| Method | Path | Purpose | Role |
|---|---|---|---|
| POST | `/api/auth/login` | Authenticate and return JWT | Public (rate-limited) |
| GET | `/api/auth/me` | Identify authenticated account | Analyst/Admin |
| GET | `/api/insurance-types` | Category-specific dynamic schemas and model readiness | Analyst/Admin |
| POST | `/api/cases` | Create case with validated manual entries | Analyst/Admin |
| GET | `/api/cases?limit=25&offset=0&q=&category=&status=` | Search and paginate visible cases | Analyst/Admin |
| GET | `/api/cases/{id}` | Full case record, evidence and analysis versions | Case owner/Admin |
| PATCH | `/api/cases/{id}` | Review/correct field values (preserves extraction provenance) | Case owner/Admin |
| POST | `/api/cases/{id}/documents` | Upload PDF/PNG/JPG/DOCX (`multipart file`) and extract | Case owner/Admin |
| GET | `/api/documents/{id}/download` | Download authenticated original evidence | Case owner/Admin |
| DELETE | `/api/documents/{id}` | Permanently delete evidence bytes/metadata | Case owner/Admin |
| POST | `/api/cases/{id}/analyze` | Record new case-scoring result | Case owner/Admin |
| GET | `/api/cases/{id}/related` | Other visible cases sharing identical evidence | Case owner/Admin |
| POST | `/api/cases/{id}/outcome` | Record human outcome (`multipart outcome`) | Admin |
| GET | `/api/dashboard` | Counts, latest bands and latency | Analyst/Admin |
| POST | `/api/admin/datasets` | Import CSV with category, source, label definition, permission, synthetic flag | Admin |
| GET | `/api/admin/datasets` | Inspect dataset inventory/quality | Admin |
| POST | `/api/admin/train/{dataset_id}` | Train candidate model and evaluate | Admin |
| GET | `/api/models` | Versions, metrics and deployment states | Analyst/Admin |
| POST | `/api/admin/models/{model_id}/deploy` | Approve/demo deploy and roll back by deploying old version | Admin |
| GET/POST | `/api/admin/settings` | Review/update provisional weights and decision bands (form fields: `model_weight`, `low`, `moderate`, `high`) | Admin |
| GET | `/api/admin/audit` | Audited sensitive operations | Admin |
| GET | `/api/health` | Health check | Public |

### Example create case

```http
POST /api/cases
Authorization: Bearer <JWT>
Content-Type: application/json

{"category":"motor","kind":"claim","external_ref":"DEMO-1",
 "data":{"policy_number":"DEMO-MOTOR-001","incident_date":"2026-07-08",
 "reported_date":"2026-07-09","claim_amount":18000,"invoice_total":18000,
 "coverage_amount":100000,"prior_claims":0}}
```

Output includes a new UUID. Upload `/sample_data/demo_evidence/motor_ordinary_SYNTHETIC.pdf` to the returned case. PATCH corrected fields, then POST `/api/cases/{id}/analyze`.

### Analysis output semantics

- `fraud_suspicion_score`: number only when category model is deployed and input is in range; else null.
- `fraud_score_interpretation`: explicitly demo-only and uncalibrated when numeric.
- `underwriting_risk_score`: null until an independent underwriting task is supported.
- `rules[]`: exact deterministic evidence, severity and reasoning; **not convictions**.
- `model`: artifact version, feature values, algorithm and out-of-domain status.
- `data_completeness_pct`: present / required schema fields, independent of model score.
- `recommendation`: advisory human-review step, never binding denial.

### Errors

`401` no/invalid authentication, `403` forbidden role, `404` unavailable/inaccessible case, `409` duplicate reference or missing model artifact, `413` file oversized, `422` field/file/dataset invalid, `429` too many login attempts. FastAPI publishes the full JSON schemas in Swagger.

## One-click synthetic demo-model setup (updated)

`POST /api/admin/demo-models` — **administrator authentication required**, JSON body:

```json
{ "categories": ["motor", "health", "travel"] }
```

Returns `results` with per-category statuses `trained_and_deployed` or
`already_active`. It trains from bundled synthetic CSV files and deploys only
for categories without an active model; it does not silently overwrite a real
model. The operation is an explicit demo opt-in and does **not** validate fraud.

Analyses now include `model_input_completeness_pct`, `model_inputs_present`,
`missing_model_inputs`, `minimum_model_inputs`, and `next_steps` so users can
distinguish completeness of required case fields from model-input availability.
