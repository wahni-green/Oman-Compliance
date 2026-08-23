# Oman Compliance — Phased Development Plan

Tracks implementation of `oman_compliance` against the architecture in
[OMAN_COMPLIANCE_ARCHITECTURE.md](OMAN_COMPLIANCE_ARCHITECTURE.md) and the gaps identified in
[OMAN_VAT_COMPLIANCE_FINDINGS.md](OMAN_VAT_COMPLIANCE_FINDINGS.md). Phases are ordered by dependency, not
strictly by priority — later phases assume earlier ones are in place (e.g. e-invoicing needs TRN validation
and VAT categorization to already exist).

Check items off as they land. Add a short dated note under a phase when scope changes.

**Regulatory deadlines to plan around** (from the findings doc):
- Fawtara voluntary pilot begins **~late August 2026**
- Mandatory for taxpayers with annual supplies over OMR 5 million from **1 April 2027**
- Mandatory for all other VAT-registered businesses from **1 October 2027**

Phases 0–4 have no external deadline pressure. Phase 5 (e-invoicing) is the time-sensitive one and should be
functional well ahead of the pilot window if this app is meant to be pilot-ready.

---

## Phase 0 — Foundation & packaging hygiene

Fixes the legacy app's packaging gaps (findings §76) and sets up the skeleton everything else builds on.

- [ ] `pyproject.toml`: pin real dependencies (`pyqrcode`, `pypng`, any HTTP client needs) — no undeclared
      runtime imports like the legacy app's `pyqrcode` bug (findings §71)
- [ ] `hooks.py`: `required_apps = ["frappe/erpnext"]`, app metadata, `require_type_annotated_api_methods = True`
- [ ] `modules.txt`: register `Oman VAT` module
- [ ] `exceptions.py`: empty flat exception hierarchy stub (`ServiceProviderError`, `NotApplicableError`, etc. —
      filled in during Phase 5)
- [ ] `install.py` / `uninstall.py`: `after_install` → calls `create_custom_fields()` (initially a no-op until
      Phase 1 populates it); `before_migrate` → version-compatibility check
- [ ] `oman_vat/` package skeleton: `constants/`, `setup/`, `overrides/`, `utils/`, `api_classes/`, `doctype/`,
      `report/`, `print_format/`
- [ ] `tests/__init__.py::before_tests()` — bootstrap an Oman test company (OMR currency, VAT-registered) per
      §1.8 of the architecture doc
- [ ] `license.txt` with real AGPL-3.0 text (legacy app had a one-line placeholder, findings §76)
- [ ] `patches.txt` with `[pre_model_sync]` / `[post_model_sync]` sections, empty to start

---

## Phase 1 — Core masters & settings

No transaction logic yet — just the reference data and settings everything else depends on.

- [ ] `TRN` doctype (reference/lookup doctype, analog of India Compliance's `GSTIN`)
- [ ] `utils/trn.py::validate_trn()` — format/length validation (blocked on confirming OTA's TRN spec, see
      architecture doc §3, open question 1); wire into `overrides/company.py` and `overrides/party.py`
- [ ] `Oman VAT Settings` (Single doctype) — replaces legacy `OMAN VAT Setting`; enable flags, OMR 500
      simplified-invoice threshold, registration thresholds (informational), designated-zone list
- [ ] `Designated Zone` doctype, seeded with Duqm (SEZAD), Salalah, Sohar, Al Mazunah + Article 54 conditions
- [ ] `constants/custom_fields.py`: bilingual fields (`company_name_in_arabic`, `address_in_arabic`,
      `customer_name_in_arabic`, `supplier_name_in_arabic`) + TRN fields, applied via
      `setup/__init__.py::create_custom_fields()` — no `fixtures` hook (avoids findings §73's mismatch bug)
- [ ] Property setters (if any needed) in `setup/property_setters.py`
- [ ] Tests: `overrides/test_company.py`, `doctype/trn/test_trn.py` for validation logic

---

## Phase 2 — Transaction-level VAT logic

- [ ] Custom fields: VAT category (standard-rated / zero-rated / exempt / **out-of-scope** — the category
      entirely missing from the legacy app, findings §51/85) on Sales/Purchase Invoice and their child items
- [ ] `overrides/transaction.py` — shared VAT-category and designated-zone detection across Sales
      Order/Quotation/Delivery Note/Sales Invoice
- [ ] `overrides/sales_invoice.py` — category validation, zone-based zero-rating per Article 54
- [ ] `overrides/purchase_invoice.py` — reverse charge flag + self-accounting logic (findings §56/86: entirely
      missing in the legacy app)
- [ ] Currency correctness: every VAT-relevant calculation reads `base_*` (company-currency) fields, never
      document-currency fields — the direct fix for the legacy app's active bug (findings §58)
- [ ] Exchange-rate disclosure: surface the conversion rate used on foreign-currency invoices (Central Bank of
      Oman rate on the tax due date, per findings §30/88)
- [ ] Tests: `overrides/test_sales_invoice.py`, `overrides/test_purchase_invoice.py` — reverse charge,
      zero-rating, out-of-scope classification, currency conversion cases

---

## Phase 3 — VAT Return & reports

- [ ] `utils/vat_return/sections/` — one file per return box: `domestic_supplies.py`,
      `reverse_charge_purchases.py`, `supplies_outside_oman.py`, `imports_of_goods.py`, `input_vat_credit.py`,
      plus totals (`total_vat_due`, `net_tax_liability`)
- [ ] `Oman VAT Return` doctype — persisted per-period return record (status: Draft/Filed), built from the
      section functions above — replaces the legacy two-section ledger entirely (findings §50)
- [ ] `Oman VAT Sales/Purchase Register` Script Report — ad-hoc analytical report, thin `.py` calling the same
      section functions, `execute(filters) → validate_filters, get_columns, get_data` shape
- [ ] Tests: section-by-section unit tests with known invoice fixtures, cross-checked against manually
      computed 7-box totals

---

## Phase 4 — Tax invoice compliance (print formats)

- [ ] Full "Tax Invoice" print format — bilingual EN/AR, supplier name/address/TRN, all OTA-mandatory fields
      (findings §53 lists the legacy app's gaps here)
- [ ] "Simplified Tax Invoice" print format, auto-selected when grand total < OMR 500 excl. VAT and the
      customer is non-taxable (findings §54 — legacy app has the format but no auto-selection logic)
- [ ] QR code via `pyqrcode`, exposed through the `jinja.methods` hook, payload read from `e-Invoice Log` once
      Phase 5 exists (placeholder/manual QR acceptable until then if a standalone QR is needed sooner)
- [ ] Tests: print-format rendering smoke tests, threshold-switch logic test

---

## Phase 5 — E-invoicing (Fawtara/PINT-OM) — time-sensitive

**Blocked on open questions in architecture doc §3** (TRN checksum, Fawtara auth protocol, service-provider
model, duplicate-submission behavior, PINT-OM field mapping) — confirm against OTA's published integration
spec before starting. Target: functional ahead of the ~August 2026 pilot if this app is meant to participate.

- [ ] `Fawtara Credential` child table on `Oman VAT Settings` (TRN/service/username + `Password`-fieldtype
      secret — no custom encryption needed, per architecture doc §1.5)
- [ ] `exceptions.py` — fill in `ServiceProviderError`, `ServiceProviderLimitExceededError`,
      `GatewayTimeoutError`, `NotApplicableError`, `AlreadySubmittedError`
- [ ] `api_classes/base.py::BaseAPI` — request/response funnel, auth-strategy injection point, sensitive-field
      redaction, logging to `Integration Request`
- [ ] Auth strategy class (start simple — bearer token or API key; only add an encrypted-session model if
      Fawtara's spec requires it)
- [ ] `utils/transaction_data.py`-equivalent — map a submitted Sales Invoice to the UBL 2.1 / PINT-OM XML
      payload
- [ ] `utils/e_invoicing.py::generate_e_invoice()` — single-document manual path; bulk path via
      `frappe.enqueue()` with per-document commit/error isolation
- [ ] `fawtara_status` field on Sales Invoice (Pending/Submitted/Auto-Retry/Failed) driving a
      `scheduler_events["cron"]` retry job — no separate retry-queue doctype
- [ ] `e-Invoice Log` doctype — one row per submission (payload, response, QR data, status)
- [ ] Human-readable PDF/A-3 output alongside the structured XML
- [ ] 24-hour submission-window guard in `utils/e_invoicing.py`
- [ ] B2C QR code generation on the human-readable invoice (mandatory per findings §41)
- [ ] Tests: `responses`-mocked API tests, `time-machine`-based window-boundary tests

---

## Phase 6 — Migration from legacy `oman_vat`

Only relevant for sites that currently run `oman_vat` and need to move to this app without data loss.

- [ ] Patch: migrate `OMAN VAT Setting` → `Oman VAT Settings` + `Designated Zone`/`TRN` records
- [ ] Patch: migrate any `is_zero_rated`/`is_exempt` custom field data on Item to the new VAT-category fields
- [ ] Decide and document: `oman_vat` uninstall path, or side-by-side coexistence period
- [ ] Tests: `patches/test_patches.py`-style meta-test validating migration patch correctness

---

## Phase 7 — Hardening & release readiness

- [ ] Full test coverage audit across all phases (legacy app shipped with empty stub tests, findings §63 —
      don't repeat that)
- [ ] CI green on `ci.yml` / `linter.yml` (already scaffolded in this repo)
- [ ] README updated with real setup/usage instructions (beyond the current bench-install boilerplate)
- [ ] Record-retention guidance documented (10 years general / 15 years real-estate, findings §31) — a process
      note, not a feature, per the findings doc
- [ ] Final pass against the OTA mandatory-field checklist for tax invoices before pilot participation

---

## Status log

- 2026-08-23 — Plan created. Phases 0–7 scoped. No implementation started yet.
