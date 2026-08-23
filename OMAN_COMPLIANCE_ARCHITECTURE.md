# Oman Compliance — Architecture Reference

This document records how `oman_compliance` should be built: what it needs to do (from
[OMAN_VAT_COMPLIANCE_FINDINGS.md](OMAN_VAT_COMPLIANCE_FINDINGS.md)) and how to build it, modeled on the
[India Compliance](https://github.com/resilient-tech/india-compliance) app (`gst_india` module), which solves
the same class of problem for India's GST regime — statutory tax return generation, TRN-equivalent (GSTIN)
validation, reverse charge, and mandatory government e-invoicing with an external service-provider API. It is
the closest real-world precedent for what this app needs for Fawtara/PINT-OM, and the user has asked that this
app follow its coding standards and structure.

Sources: local clone of India Compliance (`resilient-tech/india-compliance`, package `india_compliance/`),
and the legacy `oman_vat` app already present in this bench (`apps/oman_vat`), audited in
`OMAN_VAT_COMPLIANCE_FINDINGS.md`.

---

## 1. What India Compliance does that we should copy

### 1.1 Module layout

India Compliance registers one Frappe module per functional area in `modules.txt` (`GST India`,
`Income Tax India`, `Audit Trail`), each with its own subpackage under the app root. We should do the same:

```
oman_compliance/
  hooks.py, install.py, uninstall.py, exceptions.py, boot.py
  modules.txt                  → "Oman Compliance" (extend later with a second module if e-invoicing grows large)
  oman_compliance/
    constants/                 → custom_fields.py, __init__.py (regex, static tables)
    setup/                     → __init__.py: create_custom_fields(), create_property_setters()
    overrides/                 → one file per core doctype being extended (validate/on_submit hooks)
    utils/                     → pure business logic: trn.py, vat_return/ (sections/), e_invoicing.py
    api_classes/               → HTTP client(s) for the Fawtara/OTA service-provider API
    doctype/                   → this app's own doctypes
    report/                    → script reports
    print_format/              → tax invoice / simplified tax invoice / QR templates
  patches/
    v1/
  tests/                       → before_tests() bootstrap only; feature tests colocated with code
```

**Update (Phase 1):** the module is "Oman Compliance", not "Oman VAT" as originally written above, and the
package folder is `oman_compliance/oman_compliance/`, not `oman_compliance/oman_vat/`. The original plan
collided head-on with the legacy `oman_vat` app (still physically present in this bench's `apps/` directory,
even though not installed on any site): its module "OMAN VAT" scrubs to the same internal name (`oman_vat`) as
"Oman VAT" would, and Frappe's module→app resolution is bench-wide, not per-installed-app — `bench install-app`
failed by resolving our doctypes into the *other* app's package path. See the Phase 1 status log in
OMAN_COMPLIANCE_PLAN.md for the full failure signature. Every `oman_vat/` path elsewhere in this document should
be read as `oman_compliance/` (the nested-module-folder shape below was in fact restored, not avoided, since a
distinct module name required it).

Everything the legacy `oman_vat` app scattered under `events/`, `setup/operations/`, and a flat doctype
namespace should collapse into this `overrides/` + `utils/` + `setup/` split.

### 1.2 Custom fields: 100% programmatic, no fixtures

India Compliance does **not** use the `fixtures` hooks.py mechanism (which is what caused the legacy
`oman_vat` fixture/hooks mismatch bug — fixtures reference fields that don't exist in code, findings §3). Instead:

- All custom fields are plain dict literals in `gst_india/constants/custom_fields.py`, in a `CUSTOM_FIELDS` dict
  keyed by doctype name **or a tuple of doctype names** for fields shared across several doctypes:
  ```python
  CUSTOM_FIELDS = {
      "Sales Invoice": [ {fieldname: ..., label: ..., fieldtype: ..., insert_after: ...}, ... ],
      ("Sales Invoice", "POS Invoice", "Delivery Note"): [ {...} ],
  }
  ```
- A generic, app-wide helper (`utils/custom_fields.py`) wraps Frappe's own
  `frappe.custom.doctype.custom_field.custom_field.create_custom_fields`, stamping a `module` name onto every
  field so they're attributable, plus `toggle_custom_fields()` (bulk show/hide via `frappe.db.set_value`) and
  `delete_old_fields()` for patch-time cleanup. **Update (Phase 1):** this app skipped the runtime-stamping
  wrapper — it mutated the shared `CUSTOM_FIELDS` dict in place, which a `code-review` pass flagged as fragile —
  and instead sets `"module": "Oman Compliance"` directly on each field dict in `constants/custom_fields.py`,
  calling Frappe's core `create_custom_fields` straight from `setup/__init__.py`. Revisit the wrapper if a later
  phase actually needs `toggle_custom_fields()`/`delete_old_fields()` (e.g. Phase 6 migration cleanup).
- `oman_compliance/setup/__init__.py::create_custom_fields()` merges all the field dicts and calls
  `create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)`.
- This is called from **both** `after_install` (fresh installs) and from a `patches.txt` `post_model_sync`
  line (`execute:from oman_compliance.oman_compliance.setup import create_custom_fields; create_custom_fields() #1`)
  so upgrades re-sync idempotently. The trailing `#1`/`#2`/... comment is a deliberate Frappe convention —
  patches are tracked by exact line text, so bumping the number forces a re-run when the field set changes.
- Property setters (e.g. making a core field mandatory, changing `depends_on`) follow the identical
  `get_property_setters()` → `frappe.make_property_setter()` pattern in `setup/property_setters.py`.

This directly fixes two legacy bugs: the fixtures/hooks mismatch, and the duplicate-`on_update`-key bug
(`hooks.py:92-100` in `oman_vat`, findings §3) — a single `create_custom_fields()` call per relevant hook,
never two functions competing for the same dict key.

### 1.3 DocTypes: extend-vs-own split

- Doctypes we **don't own** (Sales Invoice, Purchase Invoice, Company, Customer, Supplier, Item, Address...) —
  logic goes in `overrides/<doctype>.py` as plain functions matching the hook event signature
  `def validate(doc, method=None):`, wired via `hooks.py` `doc_events`. Shared logic that applies to many
  transaction doctypes at once (e.g. generic VAT category detection across Sales Order/Quotation/Delivery Note)
  goes in `overrides/transaction.py`, following India Compliance's `overrides/transaction.py` pattern.
- Doctypes we **do own** — put logic on the Document subclass itself. Plan:
  - `Oman VAT Settings` (Single) — replaces `OMAN VAT Setting`; enable flags, thresholds (OMR 500 simplified
    invoice threshold, OMR 38,500/19,250 registration thresholds for informational display), designated-zone
    list, and a child table `credentials` for Fawtara service-provider auth (mirrors `GST Credential`).
  - `Fawtara Credential` (child table) — company/TRN/service/username + a `Password`-fieldtype secret field
    (Frappe's native encrypted field type — **no custom encryption needed** for credential storage itself,
    matching `GST Credential`'s approach) plus hidden session-state fields (`auth_token`, `session_expiry`).
  - `TRN` — small reference/lookup doctype, direct analog of India Compliance's `GSTIN`/`PAN` doctypes, for
    caching TRN validation/status results.
  - `Oman VAT Return` — a real persisted doctype (like `GSTR-1`/`GSTR 3B Report`) representing one filed
    quarterly return: status (Draft/Filed), period, the 7 return-box totals, links to source transactions.
    Distinct from the ad-hoc analytical Script Report (see §1.6).
  - `e-Invoice Log` — one row per Fawtara submission: request/response payload, IRN-equivalent identifier,
    QR data, submission timestamp, status, retry count. Direct analog of India Compliance's `e-Invoice Log`.
  - `Designated Zone` — a small master/reference doctype listing Duqm (SEZAD), Salalah, Sohar, Al Mazunah with
    their Article 54 conditions, linkable from Address/Customer/Supplier.

### 1.4 Business logic organization (`utils/`)

Direct analogs to build, matching India Compliance's `utils/__init__.py` TRN/GSTIN validator shape:

```python
def validate_trn(trn, label="TRN"):
    if not trn: return
    trn = trn.strip()
    if len(trn) != <OTA-specified length>:
        frappe.throw(_("{0} must have N characters").format(label))
    validate_trn_check_digit(trn, label)   # if OTA publishes a checksum algorithm
    return trn
```

- `utils/trn.py` — `validate_trn()`, format/length validation, plus company/customer/supplier TRN validators
  wired into `overrides/company.py`, `overrides/party.py` (this fixes the legacy "just re-exposes `tax_id`
  read-only, no validation" gap, findings §55/90).
- `utils/vat_return/` with `sections/` split one-file-per-return-box (`domestic_supplies.py`,
  `reverse_charge_purchases.py`, `supplies_outside_oman.py`, `imports_of_goods.py`, `input_vat_credit.py`),
  mirroring India Compliance's `utils/gstr_1/sections/{b2b,b2cs,cdnr,exports,hsn,...}.py` split for the GSTR-1
  return. Each section function takes a period + company and returns its box's figures from **`base_*`
  (company-currency) fields**, not document-currency fields — the direct fix for the legacy app's "active bug"
  (findings §58: report sums `item.net_amount` instead of `base_net_amount`).
  a place to detect "supply into/out of/within" a `Designated Zone` and reclassify as zero-rated per
  Article 54, and reverse-charge detection for Purchase Invoice.
- `overrides/purchase_invoice.py` — reverse charge flag/logic (`validate_reverse_charge`,
  `set_reverse_charge_classification`), following how India Compliance splits reverse-charge handling between
  `overrides/purchase_invoice.py` and a Tax Category flag rather than one monolithic file.
- `utils/e_invoicing.py` — the Fawtara-equivalent of `utils/e_invoice.py`: build submission payload from a
  submitted Sales Invoice, call the API client, log to `e-Invoice Log`, handle the 24-hour submission window.

### 1.5 E-invoicing (Fawtara/PINT-OM) — API client architecture

This is the part of India Compliance most worth copying wholesale, since Fawtara is structurally identical
(external accredited Service Provider, government-mandated structured document, submission window, QR code):

- `api_classes/base.py::BaseAPI` — reusable base class:
  - loads `Oman VAT Settings` singleton, checks an `enable_api` flag before doing anything
  - `fetch_credentials(trn, service)` reads the matching `Fawtara Credential` child row, calls
    `get_password()` for the secret
  - `get_url(*parts)` builds the endpoint URL, auto-switching to a sandbox base path when
    `sandbox_mode` is on
  - `get/post/put` → one `_make_request()` funnel: builds the request, calls a `before_request()` hook point
    (for auth header injection), sends via `requests`, classifies HTTP errors into typed exceptions
    (429/504/5xx → specific classes), and — critically — **logs every request/response, success or failure,
    in a `finally:` block**, via Frappe's core `Integration Request` doctype, with sensitive fields
    (API key, auth token, password) redacted before persisting.
  - An **auth strategy object** (`self.auth_strategy`) is injected rather than hardcoded, so if Fawtara's
    protocol turns out to need something like NIC's encrypted-session model, only the strategy class changes,
    not `BaseAPI` itself. Start with a simple `BearerTokenAuth`/`ApiKeyAuth` strategy — expand only if the
    published PINT-OM/Fawtara API spec requires more.
- A small flat exception hierarchy in `exceptions.py`, subclassing `frappe.ValidationError` so they still
  behave like ordinary validation errors to the framework/UI while being distinguishable in code:
  `ServiceProviderError`, `ServiceProviderLimitExceededError`, `GatewayTimeoutError`, `NotApplicableError`
  (e-invoice not required for this document), `AlreadySubmittedError`.
- **Async + retry, not fire-and-forget**: a whitelisted `generate_e_invoice(docname, throw=True)` for the
  manual/single-document path; bulk generation via `frappe.enqueue(...)`, catching per-document failures with
  `frappe.log_error()` + an explicit per-document `frappe.db.commit()` so one failure doesn't roll back others.
  A **status field on the Sales Invoice itself** (`fawtara_status`: Pending/Submitted/Auto-Retry/Failed) drives
  a scheduler cron job (`scheduler_events["cron"]["*/5 * * * *"]`) that re-attempts anything left in
  "Auto-Retry" — no separate retry-queue doctype needed, matching India Compliance's approach exactly.
- 24-hour submission window logic (Fawtara requires submission to the Service Provider within 24 hours of
  issuance, per the findings doc) should live as a guard in `utils/e_invoicing.py`, checked before allowing
  submission, analogous to India Compliance's e-invoice cancellation-window checks (which use `time-machine`
  in tests to freeze/travel time across that boundary — worth adopting the same test technique).

### 1.6 Reports vs. persisted Return doctype

Two distinct things, both needed:
- **`Oman VAT Return`** (doctype) — the actual filed/generated return record, status-tracked, one per period.
- **Script Reports** (`report_type: "Script Report"`, not Query Report) for ad-hoc analysis — a
  Sales/Purchase VAT Register (fixes the legacy `oman_vat.py` report, findings §58) with the strict
  `execute(filters) → validate_filters, get_columns, get_data` shape India Compliance uses everywhere. Keep
  the `.py` file thin — real aggregation logic belongs in `utils/vat_return/sections/*.py` so the Return
  doctype and the analytical report can both call the same section functions instead of duplicating logic
  (this is exactly why India Compliance keeps GSTR-1/3B computation out of the report files).

### 1.7 Print formats & QR codes

- `print_format/<name>/` folders with `.json`/`.html`/`.css`, following India Compliance's structure.
- QR code generation via `pyqrcode` (already a legacy dependency, currently **undeclared** — findings §71,
  must be added properly to `pyproject.toml` this time), exposed to Jinja templates via the `jinja.methods`
  hooks.py entry, exactly like `get_qr_code()` in `gst_india/utils/jinja.py`. The QR payload itself should be
  read from the `e-Invoice Log` doctype in the template, not recomputed inline in the print format.
- Bilingual (EN/AR) content and the OMR 500 simplified-vs-full tax invoice switch have no India Compliance
  precedent (GST India is English-only) — this needs original design: likely a `print_format` field or
  `before_print` override that picks the template based on `grand_total < 500 and customer.is_taxable == 0`
  (or similar), and dual-language HTML blocks using `frappe._()` with an explicit `lang="ar"` override.

### 1.8 Testing conventions to adopt

- `frappe.tests.utils.FrappeTestCase`, colocated `test_<name>.py` next to the code under test (not a separate
  top-level tests tree) — e.g. `overrides/test_purchase_invoice.py` beside `overrides/purchase_invoice.py`.
  (India Compliance's current clone uses `frappe.tests.IntegrationTestCase`, but that class doesn't exist on
  this bench's Frappe v15.116.0 — only `FrappeTestCase` from `frappe.tests.utils`. Revisit if the bench upgrades
  to a Frappe version that ships `IntegrationTestCase`.)
- Mock the Fawtara HTTP API in tests with the `responses` library (`@responses.activate`,
  `responses.add(...)`), never hit a real endpoint.
- `time-machine` for date-boundary tests (24-hour submission window, quarter-end filing deadline).
- App-level `tests/__init__.py::before_tests()` bootstraps a test company (Oman, OMR currency, VAT-registered)
  the same way India Compliance's `before_tests()` runs `setup_complete()` with a hardcoded India test company.
- This directly answers the legacy app's "Missing" test-coverage finding (findings §63) — every VAT
  calculation, currency-conversion, and TRN-validation function gets a colocated test.

### 1.9 Patches

- `patches.txt` split into `[pre_model_sync]` / `[post_model_sync]`, `execute:` one-liners for idempotent
  setup calls, `dotted.module.path` for real patch files under `patches/v1/`. Use the `#<n>` trailing-comment
  convention to force re-runs when field/setup definitions change.

### 1.10 hooks.py plan for this app

Based on what India Compliance actually uses (not the full boilerplate menu):

```python
required_apps = ["frappe/erpnext"]

doc_events = {
    "Company": {"validate": "oman_compliance.oman_compliance.overrides.company.validate"},
    ("Customer", "Supplier"): {"validate": "oman_compliance.oman_compliance.overrides.party.validate_trn"},
    "Sales Invoice": {
        "validate": "oman_compliance.oman_compliance.overrides.sales_invoice.validate",
        "on_submit": "oman_compliance.oman_compliance.overrides.sales_invoice.on_submit",
    },
    "Purchase Invoice": {
        "validate": "oman_compliance.oman_compliance.overrides.purchase_invoice.validate_reverse_charge",
    },
}

scheduler_events = {
    "cron": {
        "*/5 * * * *": ["oman_compliance.oman_compliance.utils.e_invoicing.retry_failed_submissions"],
    }
}

jinja = {"methods": ["oman_compliance.oman_compliance.utils.jinja.get_qr_code"]}

after_install = "oman_compliance.install.after_install"   # calls create_custom_fields()
before_migrate = "oman_compliance.patches.check_version_compatibility.execute"
require_type_annotated_api_methods = True   # enforce type hints on every @frappe.whitelist() method
```

No `fixtures` hook. No duplicate dict keys (the exact legacy bug this avoids).

### 1.11 Coding style

Match `pyproject.toml`'s existing `ruff` config in this repo (already present — double quotes, tab indent per
this app's own settings, rule set `F, E, W, I, UP, B, RUF`). Note India Compliance itself uses spaces (an
explicit deviation from Frappe's tab convention) — **this app's `pyproject.toml` already specifies
`indent-style = "tab"`**, so keep tabs here rather than copying India Compliance's space choice; match their
other conventions instead:
- Minimal docstrings — only when explaining non-obvious *why*, one or two lines, never full docstring blocks.
- `frappe.throw(_("message"), title=_("Title"), exc=SomeTypedException)` for all user-facing errors.
- `from frappe import _` for every user-facing string.
- Absolute imports only, isort-grouped (stdlib → third-party → first-party).
- Constants in `UPPER_SNAKE_CASE`, grouped by concern under `constants/`.
- Type hints on whitelisted API methods (required once `require_type_annotated_api_methods = True` is set).

---

## 2. Mapping table: India Compliance concept → Oman Compliance equivalent

| India Compliance | Oman Compliance |
|---|---|
| GSTIN (15-char, checksum) | TRN (format per OTA spec — confirm length/checksum before implementing) |
| GST Settings (Single) | Oman VAT Settings (Single) |
| GST Credential (child table) | Fawtara Credential (child table) |
| e-Invoice Log / e-Waybill Log | e-Invoice Log (single log doctype likely sufficient — no waybill equivalent) |
| NIC / GSP API client (`api_classes/nic/`) | Fawtara Service Provider API client (`api_classes/`) |
| GSTR-1 / GSTR-3B Report (doctype) | Oman VAT Return (doctype) |
| GST Sales/Purchase Register (Script Report) | Oman VAT Sales/Purchase Register (Script Report) |
| Reverse charge on Purchase Invoice + Tax Category | Same pattern — Oman reverse charge on imported services |
| State-wise e-Waybill threshold | Designated Zone doctype (Duqm/Salalah/Sohar/Al Mazunah) |
| GSTIN status refresh (`gstin_info.py`) | TRN status/lookup (if OTA exposes a verification API) |
| `pyqrcode` print QR (ZATCA-style not used) | `pyqrcode` for Fawtara B2C QR code |
| `overrides/transaction.py` (shared transaction logic) | Same — VAT category/zone detection shared across Sales Order/Quotation/DN |

---

## 3. Open questions to resolve before implementation

These need the actual OTA/Fawtara technical specification (not yet published in full, or not yet reviewed
here) before the e-invoicing client can be built with confidence:

1. **TRN format** — exact length and whether OTA publishes a checksum algorithm (GSTIN has a documented
   mod-36 check digit; Oman's equivalent is unconfirmed).
2. **Fawtara authentication protocol** — bearer token / API key / mTLS / OAuth2, and whether an encrypted-
   session model (like NIC's) is required, or a simpler stateless auth suffices.
3. **Service Provider selection** — is there one, or many accredited providers (analogous to India's multiple
   GSPs)? Affects whether `api_classes/` needs a factory/selection layer like `EInvoiceAPI.create()`.
4. **Idempotency/duplicate-submission behavior** — does resubmitting an already-accepted invoice return the
   original result (like NIC's duplicate-IRN handling) or a hard error?
5. **PINT-OM schema specifics** — exact UBL 2.1 field mapping from ERPNext's Sales Invoice, needed to build
   `utils/transaction_data.py`-equivalent payload construction.

These should be confirmed against OTA's published Fawtara integration guide once available, ideally before the
pilot window opens (~late August 2026).
