# Model readiness report by insurance category

All 14 bundled tabular CSVs are **synthetic**. All 14 categories may be activated for synthetic demo use only through the explicit `python scripts/prepare_demo_models.py --all` command or the administrator dashboard. Independently validated models require authorized labeled data, thorough evaluation and manual approval. In all categories underwriting and manipulation detection remain unavailable. The installed model registry reflects actual deployment state.

| Category | Typed forms | Synthetic sample CSV | Default fraud model | Underwriting model | Image manipulation model |
|---|---|---|---|---|---|
| Motor | Yes | Yes | Optional synthetic demo | None | None |
| Health | Yes | Yes | Unavailable | None | None |
| Life | Yes | Yes | Unavailable | None | None |
| Property | Yes | Yes | Unavailable | None | None |
| Travel | Yes | Yes | Unavailable | None | None |
| Commercial | Yes | Yes | Unavailable | None | None |
| Marine | Yes | Yes | Unavailable | None | None |
| Crop | Yes | Yes | Unavailable | None | None |
| Personal accident | Yes | Yes | Unavailable | None | None |
| Liability | Yes | Yes | Unavailable | None | None |
| Cyber | Yes | Yes | Unavailable | None | None |
| Pet | Yes | Yes | Unavailable | None | None |
| Gadget | Yes | Yes | Unavailable | None | None |
| Workers' compensation | Yes | Yes | Unavailable | None | None |

Image **technical quality and duplicate detection** runs for all raster uploads regardless of insurer category; ResNet18 classifier requires a separately trained and evaluated checkpoint for each category. This default classifier is evidence-type classification, not fraud/tampering.

## Real data requirements

For each category, obtain consented/licensed records and precise confirmed-outcome labels, e.g. claims finalized by fraud investigation with reliable outcomes. Include legitimate cases, confirmed fraud, unresolved cases (excluded from supervised binary label), varying claim sizes, historical dates, claim types, invoice amounts, prior claims and incident reporting delays. Where legally justified, study documents, image reuse, and cross-document consistency; avoid unconsented sensitive identifiers. Split by unique entity and/or time so the same customer/claim cannot appear on both sides. Track representativeness, calibration, fairness, data drift, false-accusation costs and recall under the target workflow.
