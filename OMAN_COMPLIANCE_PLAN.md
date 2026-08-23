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

- [x] `pyproject.toml`: pin real dependencies (`pyqrcode`, `pypng`, any HTTP client needs) — no undeclared
      runtime imports like the legacy app's `pyqrcode` bug (findings §71)
- [x] `hooks.py`: `required_apps = ["frappe/erpnext"]`, app metadata, `require_type_annotated_api_methods = True`
- [x] `modules.txt`: register `Oman VAT` module
- [x] `exceptions.py`: empty flat exception hierarchy stub (`ServiceProviderError`, `NotApplicableError`, etc. —
      filled in during Phase 5)
- [x] `install.py` / `uninstall.py`: `after_install` → calls `create_custom_fields()` (initially a no-op until
      Phase 1 populates it); `before_migrate` → version-compatibility check
- [x] `oman_vat/` package skeleton: `constants/`, `setup/`, `overrides/`, `utils/`, `api_classes/`, `doctype/`,
      `report/`, `print_format/`
- [x] `tests/__init__.py::before_tests()` — bootstrap an Oman test company (OMR currency, VAT-registered) per
      §1.8 of the architecture doc
- [x] `license.txt` with real AGPL-3.0 text (legacy app had a one-line placeholder, findings §76)
- [x] `patches.txt` with `[pre_model_sync]` / `[post_model_sync]` sections, empty to start

---

## Phase 1 — Core masters & settings

No transaction logic yet — just the reference data and settings everything else depends on.

- [x] `TRN` doctype (reference/lookup doctype, analog of India Compliance's `GSTIN`)
- [x] `utils/trn.py::validate_trn()` — format/length validation (provisional format: "OM" + 10 digits, since
      OTA's TRN spec is still unconfirmed, see architecture doc §3, open question 1); wired into
      `overrides/company.py` and `overrides/party.py` against a dedicated `oman_trn` custom field (**not** the
      core `tax_id` field — see the custom-fields bullet below for why that changed mid-phase)
- [x] `Oman VAT Settings` (Single doctype) — replaces legacy `OMAN VAT Setting`; OMR 500 simplified-invoice
      threshold, registration thresholds (informational). No enable flags/designated-zone list field added yet —
      deferred to whichever later phase actually consumes them (Phase 5 for `enable_api`), rather than shipping
      unused toggles now; the zone list itself lives on the `Designated Zone` doctype's own list view.
- [x] `Designated Zone` doctype, seeded with Duqm (SEZAD), Salalah, Sohar, Al Mazunah + an Article 54 conditions
      note (deliberately a pointer to confirm against current OTA/zone-authority guidance, not asserted legal text)
- [x] `constants/custom_fields.py`: bilingual fields (`company_name_in_arabic`, `address_in_arabic`,
      `customer_name_in_arabic`, `supplier_name_in_arabic`) applied via `setup/__init__.py::create_custom_fields()`
      — no `fixtures` hook (avoids findings §73's mismatch bug). "TRN fields" turned out to mean a genuinely new
      `oman_trn` custom field on Company/Customer/Supplier, **not** a re-expose of `tax_id` — an earlier pass of
      this phase tried relabeling the existing `tax_id` field via a property setter instead of adding a field,
      reasoning that duplicating it was exactly the legacy bug findings §55 flagged. A `code-review` pass caught
      that this was wrong: `tax_id` is a *shared* core field, and this app was installed on the shared
      `dev.localhost` bench alongside unrelated client apps — the property setter relabeled their `tax_id` field
      too, and `overrides/company.py`/`overrides/party.py` would have thrown on every one of their non-Oman
      tax IDs on save. Confirmed against India Compliance's actual GSTIN handling: it uses a dedicated `gstin`
      custom field, never the shared `tax_id`/`pan` fields, for exactly this reason. Fixed by adding `oman_trn`
      as a real custom field instead and deleting the property setter approach entirely (no
      `setup/property_setters.py` file exists in the shipped code). `module` is now set directly on each field
      dict in `constants/custom_fields.py` rather than stamped at runtime by a wrapper (`utils/custom_fields.py`,
      since removed) — a further `code-review` pass caught that the wrapper mutated the shared `CUSTOM_FIELDS`
      module-level dict in place on every call, which is fragile shared-state coupling even though it happened
      to be idempotent. `setup/__init__.py::create_custom_fields()` now calls Frappe's core
      `create_custom_fields` directly.
- [x] Tests: `overrides/test_company.py`, `overrides/test_party.py`, `doctype/trn/test_trn.py`,
      `doctype/designated_zone/test_designated_zone.py`, `doctype/oman_vat_settings/test_oman_vat_settings.py`

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
- 2026-08-23 — Phase 0 complete: package skeleton (`oman_vat/` subpackage with `constants/`, `setup/`,
  `overrides/`, `utils/`, `api_classes/`, `doctype/`, `report/`, `print_format/`), `hooks.py`
  (`required_apps`, `require_type_annotated_api_methods`, `after_install`, `before_uninstall`,
  `before_migrate`, `before_tests`), `modules.txt` → `Oman VAT`, `exceptions.py` stub hierarchy,
  `install.py`/`uninstall.py`, `patches/check_version_compatibility.py`, `tests/__init__.py::before_tests()`
  (Oman/OMR test company), `pyproject.toml` deps (`pyqrcode`, `pypng`). Removed the default
  `oman_compliance/oman_compliance/` module folder scaffolded by `bench new-app` since the app now registers
  the `Oman VAT` module instead. `license.txt` and `patches.txt` were already correct from initial scaffold.
  Validated with `ast.parse` + `ruff check`/`ruff format` only — not yet installed on a live site, since the
  only available bench site (`dev.localhost`) is shared with several unrelated client apps; live
  install/migrate verification should happen on a dedicated site before Phase 1 lands doctypes.
- 2026-08-23 — Independent review agent (`code-review` skill) caught two Phase 0 issues, both fixed:
  `tests/__init__.py::before_tests()` was unconditionally pointing `Global Defaults.default_company` at the
  test company even when `setup_complete()` was skipped (an existing `Company` row on a shared bench) —
  crashed with a Link validation error; now gated on `frappe.db.exists("Company", TEST_COMPANY)`. Also flagged
  that `require_type_annotated_api_methods` is a silent no-op on this bench's Frappe v15 (it's a v16+ hook) —
  kept it for forward-compat with the architecture doc's intent but added a comment explaining why it's
  currently inert.
- 2026-08-23 — Added a `.claude` Stop hook (`check-reviewed.sh` + `mark-reviewed.sh` + `diff-hash.sh`) that
  blocked Claude from ending a turn with an unreviewed diff in the working tree, so an independent
  `code-review` pass runs on every change, not just when asked. A `code-review` pass over that hook's own diff
  (dogfooding it before first use) caught two more Phase 0 issues, both fixed: the version-compatibility check
  was wired only to `before_migrate`, not `before_install`, so a fresh install on an incompatible Frappe
  version wasn't blocked at install time (now wired to both); and `check_version_compatibility.py` used a bare
  `int(frappe.__version__.split(".")[0])` with no handling for a non-numeric leading version segment (now uses
  a regex match with a safe fallback).
- 2026-08-23 — Replaced the Stop hook above with a `PreToolUse` hook (`.claude/settings.json`, matcher `Bash`)
  scoped to `git push`: `check-before-push.sh` blocks an actual push (via `permissionDecision: "deny"`) when
  the diff between HEAD and its upstream/`origin/<branch>` (falling back to `origin/main`/`master`/`develop`)
  doesn't match the hash last recorded by `mark-reviewed.sh`; `diff-hash.sh` now hashes committed history
  rather than the working tree. `check-reviewed.sh` was removed. A `code-review` pass over this change caught
  a real bug (fixed): the script trusted `settings.json`'s `if` filter to have already scoped it to `git push`
  commands and applied the gate unconditionally, so it wrongly denied unrelated `git` commands (e.g. `git
  status`, `git rev-parse`) whenever `if` matched more broadly than expected — confirmed by direct testing.
  The script now independently parses `tool_input.command` from stdin (segment-split on `;`/`&`/`|`/newline,
  matched against `^git\s+push\b` per segment) and only ever denies for an actual `git push` invocation,
  regardless of what `if` does. Also added a comment to `tests/__init__.py::before_tests()` documenting that,
  on a shared bench with a pre-existing `Company` (like this one), `TEST_COMPANY` is never created — a
  limitation inherited from the India Compliance convention this app follows, not something Phase 0 fixes.
- 2026-08-23 — Phase 1 complete: `TRN` doctype, `Oman VAT Settings` (Single), `Designated Zone` doctype (seeded
  with Duqm/Salalah Free Zone/Sohar Free Zone/Al Mazunah Free Zone), bilingual custom fields on
  Company/Customer/Supplier/Address, and a dedicated `oman_trn` custom field on Company/Customer/Supplier. TRN
  format validation (`utils/trn.py::validate_trn()`) wired into `overrides/company.py` and `overrides/party.py`
  against `oman_trn`. Three real bugs were caught during this phase — the first two by live install/migrate
  verification, the third by a `code-review` pass, none by `ast.parse`/`ruff`, which passed cleanly throughout —
  and all three fixed before landing:
  1. **Module-name collision with the legacy app.** This app's module was originally registered as "Oman VAT"
     (per the architecture doc's original plan), which Frappe's module-to-app resolution scrubs to `oman_vat` —
     identical to the legacy `oman_vat` app's own module "OMAN VAT" (also present in this bench's `apps/`
     directory and `sites/apps.txt`, even though not installed on any site). Frappe's `module_app` reverse
     mapping is built bench-wide, not per-installed-app, so `bench install-app oman_compliance` failed outright
     with `ImportError: No module named 'oman_vat.oman_vat.doctype...'` — it resolved our doctypes' module to
     the *other* app's package path. Fixed by renaming this app's module to "Oman Compliance" and moving the
     package folder from `oman_compliance/oman_vat/` to `oman_compliance/oman_compliance/` (restoring the
     nested-module-folder shape Phase 0 had deliberately removed, since avoiding it is no longer possible once
     the module needed a distinct name). Doctype *names* like "Oman VAT Settings" are unaffected — only the
     `module` field/registration changed. `OMAN_COMPLIANCE_ARCHITECTURE.md` still shows the old `oman_vat/`
     folder path in places; treat `oman_compliance/oman_compliance/` as current.
  2. **`frappe.tests.IntegrationTestCase` doesn't exist on this bench's Frappe (v15.116.0)** — only
     `frappe.tests.utils.FrappeTestCase`. The architecture doc's §1.8 testing convention was written against a
     newer India Compliance clone; all test files here use `FrappeTestCase` instead. Revisit if/when this bench
     upgrades to a Frappe version that ships `IntegrationTestCase`.
  3. **Reused the shared core `tax_id` field instead of a dedicated one.** The first pass validated/normalized
     `Company.tax_id`/`Customer.tax_id`/`Supplier.tax_id` directly and relabeled them to "TRN" via a property
     setter. Since this app is installed on the shared `dev.localhost` bench alongside unrelated client apps
     (wahni_it, orgflow, galfar, cosec), that relabeled *their* `tax_id` field too and would have thrown a
     validation error on every one of their non-Oman-format tax IDs on save — confirmed live, then fixed by
     switching to a dedicated `oman_trn` custom field and deleting the property-setter approach entirely, matching
     how India Compliance itself never reuses `tax_id`/`pan` for GSTIN.
  4. **`TRN.before_naming()` only covers the insert path.** A background `code-review` correctness pass pointed
     out that `before_naming` runs solely during `insert()`; renaming an existing `TRN` record (e.g. via the Desk
     rename dialog, which calls `frappe.rename_doc` directly) skipped format validation/normalization entirely.
     Direct in-place edits to the `trn` field on an existing record were already safe — `_sync_autoname_field()`
     silently reverts them back to `self.name` on save, standard Frappe behavior for any `autoname: "field:x"`
     doctype — but an actual rename had no equivalent guard. Fixed by adding `TRN.before_rename(old, new, merge)`,
     which validates/normalizes `new` and returns it as the value Frappe actually renames to.
  Also found via live testing (not a bug in the shipped code, just a Frappe behavior to know for future
  doctypes): for a doctype with `autoname: "field:x"`, `Document._sync_autoname_field()` re-derives field `x`
  from `self.name` *after* `validate()` runs on every save, since naming happens before `run_before_save_methods`
  but the sync-back happens after. Normalizing `x` inside `validate()` gets silently overwritten. `TRN.py`
  normalizes in `before_naming()` instead, which runs before naming. Separately, `frappe.rename_doc()` was found
  to break `FrappeTestCase`'s per-test rollback isolation (mid-run duplicate-key errors appeared when two test
  methods each inserted the same TRN value) — the rename tests call `TRN.before_rename()` directly instead of
  going through a real rename, avoiding the DB entirely for that assertion.
  Live-verified on a dedicated concern: no spare bench had a working MariaDB root password available this
  session, so — with explicit user sign-off accepting the risk — install/migrate/tests ran on the shared
  `dev.localhost` bench instead of an isolated site. A full `bench --site dev.localhost backup` was taken
  immediately beforehand, and the stray `Property Setter` records from bug 3 were deleted directly once the fix
  landed (never having shipped anywhere else). Result: `bench install-app oman_compliance`, `bench migrate` (run
  four times across three rounds of fixes, to confirm the custom-fields/designated-zone seed stays idempotent —
  verified no duplicates each time), and `bench run-tests --app oman_compliance` (13/13 passing) all succeeded.
  Per user decision, the app is being left installed on dev.localhost rather than uninstalled after verification.
- 2026-08-23 — Three more `code-review` findings addressed: (1) `TRN_PATTERN` used `\d`, which matches any
  Unicode decimal digit (e.g. Arabic-Indic), not just ASCII 0-9 — changed to `[0-9]`. (2) `Oman VAT Settings`'
  three Currency fields had no `options`, so they rendered in the *site's* default currency rather than OMR
  (confirmed live on dev.localhost, whose default currency is INR) — added a hidden `settings_currency` field
  (deliberately not named `currency`, since Frappe treats that exact fieldname as a sitewide-default lookup key
  that overrides a DocField's own static `default` — confirmed live before renaming) and pointed the three
  amount fields' `options` at it. Since a Single doctype's field `default` only applies to a document that's
  never been persisted, `setup/__init__.py::set_default_settings_currency()` backfills it for the
  already-existing `Oman VAT Settings` singleton on dev.localhost (wired into `after_install` and
  `patches.txt` like the other seed functions). (3) A separate review round had proposed making
  `create_designated_zones()` overwrite `authority`/`article_54_conditions` on existing records so corrected
  wording reaches already-migrated sites — reverted that: there's no way to distinguish a still-default record
  from one an admin deliberately edited, so a blanket overwrite risked destroying local corrections. Back to
  insert-only; a future wording fix belongs in an explicit dated patch instead. `bench run-tests --app
  oman_compliance` (15/15 passing).
