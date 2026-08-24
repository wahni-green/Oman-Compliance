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

- [x] Custom fields: VAT category (standard-rated / zero-rated / exempt / **out-of-scope** — the category
      entirely missing from the legacy app, findings §51/85) on Sales/Purchase Invoice and their child items —
      shipped on all five sales/purchase-cycle item child tables (Sales Order/Quotation/Delivery Note/Sales
      Invoice/Purchase Invoice Item, all sharing `item_tax_template` as the anchor field), not just the two
      invoice doctypes literally named in this bullet — needed for the value to survive `get_mapped_doc` when
      a Sales Invoice is created from a Delivery Note/Sales Order rather than from scratch. Left with no field-
      level `default`, so `overrides/transaction.py`/`sales_invoice.py`/`purchase_invoice.py` can tell "blank,
      needs a default" apart from "user deliberately chose Standard Rated" — a hardcoded JSON default would
      have made that impossible. Also added a `designated_zone` Link (to `Designated Zone`) custom field on
      `Address`, which §1.3 called for ("linkable from Address/Customer/Supplier") but Phase 1 hadn't actually
      shipped yet — needed as the detection signal for the zone-based zero-rating bullet below.
- [x] `overrides/transaction.py` — shared `set_vat_category_defaults()` wired to Sales Order/Quotation/Delivery
      Note/Sales Invoice `validate`; only fills a blank `vat_category` row, defaulting to Zero Rated if either
      the billing (`customer_address`) or shipping (`shipping_address_name`) address links to an *active*
      Designated Zone, else Standard Rated — a suggested default, not an enforced classification, consistent
      with this app's existing stance that Article 54 eligibility needs case-by-case confirmation (matches how
      `Designated Zone.article_54_conditions` and the VAT Settings thresholds are already treated as
      informational, not authoritative).
- [x] `overrides/sales_invoice.py` — `validate()` calls the shared defaulting above, then
      `validate_vat_category_tax_consistency()`: blocks a Zero Rated/Exempt/Out of Scope row that actually had
      VAT applied to it (read from each Sales Taxes and Charges row's `item_wise_tax_detail`, using its *rate*
      component rather than its amount — currency-agnostic by construction, sidestepping the currency-
      correctness bullet below entirely for this check). Only checks the direction that overstates output VAT
      due; a Standard Rated row taxed at 0% under a valid template is not flagged. Two rows sharing an
      `item_code` with different categories are skipped rather than checked, since ERPNext's own
      `item_wise_tax_detail` is keyed by item_code, not row, and can't tell them apart — documented as a known
      limitation rather than risking a false positive against a legitimate mixed-category invoice.
- [x] `overrides/purchase_invoice.py` — `validate_reverse_charge()` defaults blank `vat_category` rows to
      Standard Rated (no zone-based detection attempted on the purchase side, since that's box 3/4 territory
      for Phase 3, not this bullet), plus a new `is_reverse_charge` Check custom field on Purchase Invoice; if
      checked, requires at least one Purchase Taxes and Charges row to exist — the concrete, defensible slice
      of "self-accounting logic" implementable now (the actual output-VAT-liability + input-VAT-recoverable GL
      rows come from the user's own tax template configuration, exactly how India Compliance splits this
      between the override file and a template/Tax Category mechanism per architecture doc §1.3, rather than
      this app generating tax rows itself). No automatic `is_reverse_charge` detection heuristic (e.g. off
      supplier country) was added — reverse charge applies specifically to imported *services*, and any address-
      based heuristic would also fire on imported *goods* (which go through the separate box 4, not box 2),
      so guessing would risk misclassifying a real return box.
- [x] Currency correctness: no VAT amount aggregation exists yet in this phase (that's Phase 3's VAT return) —
      the one place Phase 2 reads a tax figure at all (the sales-invoice consistency check above) is currency-
      agnostic by using a rate, not an amount. Confirmed while reading `taxes_and_totals.py` for that check:
      `item_wise_tax_detail`'s stored amount is actually already in company currency
      (`current_tax_amount * self.doc.conversion_rate`, i.e. doc-currency × rate = base/company currency) —
      worth knowing for Phase 3's section functions, which will read amounts from it directly.
- [x] Exchange-rate disclosure: `utils/currency.py::get_exchange_rate_disclosure()` — returns a formatted "1
      {doc currency} = {rate} {company currency}" string for a foreign-currency Sales/Purchase Invoice, `None`
      for a company-currency one. Exposed via a new `jinja.methods` hooks.py entry now, ahead of Phase 4's print
      formats actually consuming it — no schema change, so shipping the hook now cost nothing and there was no
      reason to wait.
- [x] Tests: `overrides/test_transaction.py`, `overrides/test_sales_invoice.py`,
      `overrides/test_purchase_invoice.py`, `utils/test_currency.py` — zero-rating defaults (plain, zone-
      detected, deactivated-zone, mixed billing/shipping addresses), no-clobber-of-explicit-value, category/tax
      mismatch rejection and its duplicate-item-code exception, reverse-charge tax-row requirement, exchange-
      rate disclosure for same- vs. foreign-currency documents. All built on lightweight `frappe._dict`/`
      frappe.get_doc(...).insert()` mocks matching Phase 1's existing test style — no full Sales/Purchase
      Invoice fixtures needed, since every override function here operates on already-validated doc data.
- [x] `Oman VAT Account` child doctype (`company` + `output_vat_account`) on a new `Oman VAT Settings.vat_accounts`
      table — explicitly configured per company, replacing an earlier account-type-heuristic approach entirely
      (see status log). Matches India Compliance's GST Settings `gst_accounts` child table pattern exactly.
- [x] Item Tax Template validation against the configured Output/Input VAT Accounts —
      `overrides/item_tax_template.py::validate_vat_category_tax_consistency()`, wired to `Item Tax Template`'s
      `validate` doc_event. Catches a Zero Rated/Exempt/Out of Scope template that still posts a nonzero rate to
      the company's configured Output or Input VAT Account, at template-definition time rather than only
      discovering it later on an invoice.
- [x] A "Fetch VAT Accounts" button on Item Tax Template — a new `fetch_vat_accounts` Button custom field
      (`constants/custom_fields.py`) plus `client_scripts/item_tax_template.js` (wired via `hooks.py`'s
      `doctype_js`), calling the new whitelisted `overrides/item_tax_template.py::get_vat_accounts_for_template()`
      to add whichever of the company's configured Output/Input VAT Accounts are missing from the template's
      own `taxes` rows (new row's rate left at 0 — no assumed VAT rate exists anywhere to default it from).
      Mirrors India Compliance's `gst_india/client_scripts/item_tax_template.js` +
      `overrides/item_tax_template.py::get_valid_gst_accounts()` exactly, including the "missing accounts"
      dashboard banner shown on form refresh.

---

## Phase 3 — VAT Return & reports

**2026-08-23 — Phase 2/3 alignment check** (done while still finishing Phase 2, at the user's request, against
the legacy `oman_vat` app's report at `apps/oman_vat/oman_vat/oman_vat/report/oman_vat/oman_vat.py`):

- **Confirmed ready:** `vat_category` now lives on both the item row *and* its `Item Tax Template` (Phase 2),
  which is the same idea the legacy report used (`OMAN VAT Sales/Purchase Account` child rows mapping one
  `item_tax_template` to one report line) — except ours is auto-derivable from the template itself rather than
  a manually maintained mapping table the admin has to keep in sync. Section functions can group by
  `item_tax_template.vat_category` directly. `is_reverse_charge` (Phase 2) is ready to feed the reverse-charge
  purchases box. TRN, Designated Zone, and the OMR-fixed thresholds (Phase 1) need no changes for Phase 3.
- **Confirmed the currency bug mechanism, precisely:** the legacy report sums `item.net_amount` (document
  currency) for the taxable-amount column, findings §58's exact bug — but separately reads its VAT-amount
  column from `item_wise_tax_detail`, whose stored figure is *already* base/company currency (`current_tax_amount
  * conversion_rate` in ERPNext's `taxes_and_totals.py`, confirmed reading that source during Phase 2). So the
  legacy report's two columns were silently on two different currency bases against each other, not just wrong
  in one direction. Phase 3's section functions must read `base_net_amount` (or equivalent `base_*` field) for
  every taxable-amount figure, matching how the VAT-amount figure already needs to be read.
- **Gap 1 resolved same-round (2026-08-23):** "No signal at all for 'imports of goods' (box 4)" — a distinct
  box from reverse-charge purchases (box 2: reverse charge covers imported *services*; imports of goods is
  customs-driven) — was closed the same day this alignment note was written: a read-only `is_import_of_goods`
  Check field now exists on Purchase Invoice, auto-computed from the Dispatch Address's country vs. the
  Company's own country (`overrides/purchase_invoice.py::set_import_of_goods_flag()`). See this phase's
  bullets and status log below for the full detail — Phase 3's `imports_of_goods.py` can read this field
  directly; no further field work needed for it specifically.
- **"Out of Scope" vs. return box 3 — resolved (2026-08-23), against a primary source: OTA's own "VAT Taxpayer
  Guide — VAT Return Filing" (V1, June 2021).** They are **not** the same concept, and the plan's original
  `supplies_outside_oman.py` framing was itself slightly off — the actual official return has no "out of
  scope" box at all:
  - **"Out of Scope" supplies are excluded from the VAT return entirely** — not reported in any box. The
    guide's own definition (§3.1): supplies made outside Oman (place of supply outside Oman), supplies not
    made by a Taxable Person, or supplies not made in the course of economic activity. Both box 1(c) (exempt)
    and box 3(a) (exports) explicitly state "Excludes any out of scope supplies" in the guide's field
    descriptions.
  - **The actual box 3, "Supplies to countries outside of Oman," has exactly one line: 3(a) Exports** — "total
    value of supplies of goods and services exported on which zero rating for exportation applies." This is a
    **Zero Rated** supply (the place of supply is still Oman — an Omani taxable person exporting), not an "Out
    of Scope" one. So `vat_category = "Zero Rated"` alone is *not* enough to route a line item to the right
    box: it can land in either box 1(b) (domestic zero-rated) or box 3(a) (export), and nothing currently
    distinguishes those two cases — needs an export/domestic-delivery signal (likely derived from the
    customer/shipping country, mirroring how `is_import_of_goods` derives from Dispatch Address country on the
    purchase side) before `domestic_supplies.py`/a new `exports.py` can be split correctly.
  - **The real return's official structure, for reference when building the section files** (box : description):
    1(a) standard-rated domestic, 1(b) zero-rated domestic, 1(c) exempt domestic (excl. out of scope), 1(d)/1(e)
    intra-GCC reverse-charge supplies (not yet activated by the OTA), 1(f) profit-margin-scheme goods; 2(a)
    intra-GCC reverse-charge purchases (not yet activated), 2(b) non-GCC reverse-charge purchases; 3(a) exports;
    4(a) import of goods with postponed payment, 4(b) total goods imported; 5 total VAT due; 6 input VAT credit
    (split: ordinary purchases, imports, fixed assets, adjustments); 7 net tax liability. Two refinements this
    reveals for later Phase 3 work, beyond the export/domestic split above: (a) reverse charge purchases split
    GCC vs. non-GCC (box 2a/2b) — `is_reverse_charge` doesn't currently distinguish this; (b) imports of goods
    split by postponed-payment status (box 4a/4b) — `is_import_of_goods` doesn't currently distinguish this
    either. Neither blocks Phase 2 (the flags are still the correct starting signal), but the return-section
    functions will need more than just these two flags to populate every box correctly.
  - Source: [VAT Taxpayer Guide – VAT Return Filing](https://tms.taxoman.gov.om/portal/documents/20126/1414820/VAT+Taxpayer+Guide+-+VAT+Return+Filing.pdf), pages 7 and 10–11 (fetched and read directly, not summarized secondhand).
- **Also noted, not yet decided:** credit/debit notes (`is_return`) — the legacy report kept returned amounts
  in a separate "adjustment" column rather than netting them into the main figure, for auditability. Worth
  deciding deliberately in Phase 3 rather than defaulting to whichever ERPNext's `is_return` sign convention
  makes easiest.

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
- 2026-08-23 — Phase 2 complete: `vat_category` custom field on all five sales/purchase-cycle item child
  tables, `designated_zone` Link custom field on Address, `is_reverse_charge` Check on Purchase Invoice,
  `overrides/transaction.py` (shared zone-aware VAT-category defaulting), `overrides/sales_invoice.py`
  (category/tax consistency validation), `overrides/purchase_invoice.py` (reverse-charge tax-row requirement),
  `utils/currency.py::get_exchange_rate_disclosure()` (wired as a `jinja.methods` hook). See the phase's own
  bullets above for the reasoning behind each scope decision (field placement beyond the literal checklist
  text, no field-level default, no automatic reverse-charge heuristic, etc.).
  Live-verified on the same shared `dev.localhost` bench as Phase 1 (a fresh `bench --site dev.localhost
  backup` was taken immediately before migrating, per the same standing risk acceptance). One real bug caught
  during that verification, not by `ruff`/`ast.parse`: `bench migrate` initially did *not* create any of the
  new custom fields, because `patches.txt`'s `execute:...create_custom_fields() #2` line's trailing version
  marker was unchanged, so Frappe's patch tracker treated it as an already-applied no-op despite the
  underlying `CUSTOM_FIELDS` dict having new entries — exactly the re-run convention `patches.txt`'s own header
  comment documents. Fixed by bumping the marker to `#3`; a second `bench migrate` then created all seven new
  fields, confirmed via a direct `tabCustom Field` query (safer than `bench console`, which hung this session
  on an interactive exit prompt when fed a multi-line heredoc — noted for future sessions: use `bench execute`
  or a direct SQL/script check instead of piping multi-line input into `bench console`).
  A `code-review` pass over the diff caught three more real issues, all fixed before landing: (1)
  `_is_designated_zone_transaction()` used `customer_address or shipping_address_name`, so a zone shipping
  address was silently ignored whenever a non-zone billing address was also set — changed to check both
  addresses independently. (2) The same function never read `Designated Zone.is_active`, so deactivating a
  zone had no effect on already-linked addresses still driving the Zero Rated default — fixed by checking it.
  (3) `sales_invoice.py`'s tax-consistency check aggregated charged VAT rate by `item_code` across the whole
  invoice (matching how ERPNext's own `item_wise_tax_detail` is keyed), so two rows sharing an item code with
  different VAT categories got checked against a merged rate — could false-positive-reject a legitimately
  mixed-category invoice; fixed by skipping the check for any item_code that appears with more than one
  distinct category on the same document, with a comment documenting why. `bench run-tests --app
  oman_compliance` (33/33 passing) and a second `bench migrate` (idempotency re-check, no duplicate `Custom
  Field` rows) both confirmed after the fixes.
- 2026-08-23 — At the user's request: linked VAT Category onto `Item Tax Template` itself (a new `vat_category`
  Select custom field there), since a template's own tax rate can't distinguish Zero Rated from Exempt from
  Out of Scope (all commonly 0%) the way an explicit category on the template can. `utils/vat_category.py::
  get_item_tax_template_category()` is now the shared lookup: `overrides/transaction.py` and
  `overrides/purchase_invoice.py` prefer it over the zone/Standard-Rated default when a row's own
  `item_tax_template` declares one, and `overrides/sales_invoice.py` added a new direction-agnostic check
  (row category contradicts its template's declared category, in *either* direction — stronger than the
  existing rate-based check, which only ever caught the no-tax-categories-but-taxed direction).
  Also answered the user's second question (do we store VAT amount on item rows): no — ERPNext's
  `item_tax_amount` field on Purchase Invoice Item is unrelated (valuation-inclusion amount for stock costing,
  confirmed by reading `buying_controller.py`, not a general VAT figure), and Sales Invoice Item has no
  equivalent field at all. The actual applied VAT amount per item is derivable from each tax row's
  `item_wise_tax_detail` (see the Phase 2/3 alignment note above on why that figure is already base-currency)
  — nothing currently stores it redundantly on the row itself, and Phase 3 doesn't need it to either.
  This round surfaced a significant latent bug via `test_template_without_category_returns_none` unexpectedly
  returning `"Standard Rated"` instead of `None`: Frappe auto-fills any Select field with no explicit `default`
  to its *first listed option* on every new document/child row
  (`frappe.model.create_new.get_static_default_value`), running before any `validate()` hook. Every
  `vat_category` field (on the five item child tables *and* the new Item Tax Template field) was silently
  arriving at our own defaulting/validation logic already set to "Standard Rated" — never actually blank — which
  would have made the zone-based and template-based defaulting dead code in real usage despite all the
  `frappe._dict`-based unit tests passing (those bypass `frappe.new_doc()` entirely, so they never exercised
  this). Fixed with the same leading-blank-option idiom Frappe/ERPNext's own optional Select fields use:
  `constants/VAT_CATEGORY_SELECT_OPTIONS = "\n" + "\n".join(VAT_CATEGORIES)`, replacing the plain joined string
  everywhere it was used. `create_custom_fields()`'s `update=True` default confirmed to actually patch already-
  existing Custom Field rows' `options` in place (not just skip them) once the patch marker was bumped again —
  verified directly via `tabCustom Field` query, not just import-time inspection.
  A further `code-review` pass caught one more real gap: `_is_designated_zone_transaction()` checked
  `customer_address`/`shipping_address_name` but not `dispatch_address_name` (present on Sales Order/Delivery
  Note/Sales Invoice, not Quotation) — the exact "supply out of a zone" case the function's own comment had
  claimed was undetectable, when in fact the per-transaction dispatch address was already available and simply
  unused. Fixed by checking it alongside the other two. `bench migrate` (idempotent, fields updated in place,
  no duplicates) and `bench run-tests --app oman_compliance` (41/41 passing) both confirmed after all fixes.
- 2026-08-23 — Two more user-directed additions, done together since the second surfaced while doing the
  Phase 2/3 alignment check for the first (see that note earlier in this file):
  1. **Oman-company gating, retroactively applied to every Phase 2 transaction override.** New
     `utils/company.py::is_oman_company()` (checks `Company.country == "Oman"`), now the first thing checked
     in `transaction.set_vat_category_defaults()`, `sales_invoice.validate()`, and the new
     `purchase_invoice.validate()` — each no-ops entirely for a non-Oman company. This closes a real gap: none
     of Phase 2's logic had ever checked the company before, so on this shared bench (whose only real Company,
     "Dev Server", is registered in India) every one of those hooks was silently running against — and, for
     `sales_invoice.py`'s validation, capable of blocking — an unrelated company's ordinary transactions. Exactly
     the same class of cross-company leakage as Phase 1's `tax_id`/property-setter incident, just not yet
     caught this time because nothing had exercised it. `oman_compliance/tests/__init__.py::
     get_oman_test_company()` added (creates a minimal uncommitted Oman-country Company for tests, reused if
     one already exists) since this bench has no real Oman company to test against otherwise; every existing
     Phase 2 test needed `company=` added to its mock doc, plus new tests confirming a non-Oman company (and a
     blank company) is left untouched.
  2. **`is_import_of_goods` on Purchase Invoice** (VAT return box 4 — distinct from Reverse Charge/box 2, which
     is imported *services*, not goods): a new read-only Check field, auto-computed in
     `purchase_invoice.py::set_import_of_goods_flag()` from the Dispatch Address's country vs. the Company's
     own country (blank Dispatch Address ⇒ not an import, per explicit user instruction). Unlike Reverse
     Charge, this isn't a manual flag — it's always recomputed on save, and the user is notified via
     `frappe.msgprint()` specifically when the computed value *changes* (not on every save), since the field
     itself isn't user-editable. `purchase_invoice.py` gained a top-level `validate()` that runs this alongside
     `validate_reverse_charge()`, gated by `is_oman_company()`; `hooks.py`'s Purchase Invoice `validate` hook now
     points there instead of `validate_reverse_charge` directly.
     Which address field to read was a real fork worth getting right: ERPNext's Purchase Invoice has both
     `shipping_address` (destination — the company's own receiving location, always domestic for an ordinary
     purchase) and `dispatch_address` (origin — where the supplier actually ships from). The user was asked
     directly and chose `dispatch_address`, correctly — origin is what determines whether goods are crossing
     into Oman from abroad; destination wouldn't have detected anything.
  A `code-review` pass caught one documentation bug (not a code bug): the Phase 2/3 alignment note above had
  been written *before* this round's work and still described "imports of goods" as an unresolved gap needing
  a future field, even though this same round shipped exactly that — fixed by updating the note in place.
  `bench migrate` (idempotent) and `bench run-tests --app oman_compliance` (51/51 passing) confirmed after all
  of the above.
- 2026-08-24 — Three more review rounds on `purchase_invoice.py`'s reverse-charge check and
  `sales_invoice.py`'s VAT-consistency check, escalating until the actual right fix was found:
  1. First round: tightened `_has_recipient_output_vat_row()` from "any nonempty Taxes and Charges table" to
     requiring a VAT-bearing "Add" row and a VAT-bearing "Deduct" row (using `add_deduct_tax`), since a single
     row is exactly what an ordinary domestic purchase's plain input VAT already looks like.
  2. Second round: that still accepted an unrelated Add row (ordinary input VAT) and an unrelated Deduct row
     (e.g. a withholding deduction) that just happened to post to a VAT-bearing-*typed* account — tightened
     further to require the Add and Deduct rows to share an identical nonzero *rate*, since genuine self-
     accounting is the same VAT recorded twice.
  3. Third round found the rate-matching heuristic itself was still gameable (an ordinary input-VAT Add row
     and an unrelated same-rate Deduct row could coincidentally match) and, per the user's prompt, checked how
     India Compliance actually solves this class of problem — it doesn't use account-type or rate heuristics at
     all. `GST Settings` has an explicit `gst_accounts` child table (keyed by `company` + `account_type`) naming
     the exact CGST/SGST/IGST/Cess ledger accounts, and `gst_india/overrides/purchase_invoice.py::
     validate_reverse_charge()` doesn't inspect tax rows at all — it just enforces "reverse charge isn't
     applicable to Import of Goods." Rebuilt around this instead of continuing to patch heuristics:
     - New `Oman VAT Account` child doctype (`company`, `output_vat_account`) and `Oman VAT Settings.vat_accounts`
       table — one row per company, directly mirroring `gst_accounts`' shape (simplified: Oman's flat single-
       rate VAT needs only one account per company, not GST's CGST/SGST/IGST/Cess split). `Oman VAT Settings`
       gained `validate_unique_vat_account_per_company()` rejecting a duplicate company row.
     - `utils/tax_account.py` rewritten: `VAT_BEARING_ACCOUNT_TYPES`/`is_vat_bearing_account()` deleted
       entirely (dead code once nothing used account-type heuristics anymore) and replaced with
       `get_output_vat_account(company)` / `is_output_vat_account(account_head, company)`, both reading the new
       per-company table via `frappe.get_cached_doc("Oman VAT Settings")`, matching how India Compliance's own
       `get_gst_accounts_by_type()` loads its cached GST Settings doc rather than querying the child table
       directly.
     - `purchase_invoice.py::_has_recipient_output_vat_row()` simplified back down to "at least one nonzero-
       rate/amount row posted to this company's configured Output VAT Account" — no Add/Deduct pairing needed
       at all, since that pairing turned out to be an assumption of my own invention, not something OTA or the
       actual VAT return (box 2 just needs taxable base + VAT due) requires to be structured that way on the
       same document. `validate_reverse_charge()` now throws a distinct, more actionable error when the
       company's Output VAT Account isn't configured at all vs. configured but missing from this invoice.
     - `sales_invoice.py::_get_item_wise_tax_rates()` updated the same way — filters by the company's
       configured Output VAT Account instead of a generic account-type set. If unconfigured, the mismatch check
       simply doesn't fire (returns no rates) rather than guessing, consistent with this app's existing
       informational-until-configured pattern elsewhere.
     - The **first design of this fix was itself not multi-company safe** — a single global `output_vat_account`
       Link field directly on the Single `Oman VAT Settings` doctype, since ERPNext accounts are always
       company-specific and a lone global field could only ever be correct for one company. Caught when the
       user asked directly ("Is it multi-company safe though?") before it was ever committed; replaced with the
       per-company child table described above before landing.
     - All three existing test files (`test_purchase_invoice.py`, `test_sales_invoice.py`,
       `utils/test_tax_account.py`) rewritten around the new `set_output_vat_account()` test helper (added to
       `tests/__init__.py`) instead of the account-type/Add-Deduct fixtures; `test_oman_vat_settings.py` gained
       coverage for the duplicate-company rejection. `bench migrate` (new doctype + settings schema, idempotent)
       and `bench run-tests --app oman_compliance` (71/71 passing) confirmed throughout.
  - **Two follow-up TODOs deliberately not implemented yet** (explicit user instruction: "only add ToDo for
    now"), tracked here and as a code comment in `utils/tax_account.py`: (1) validating an Item Tax Template's
    own `taxes` rows against the company's configured Output VAT Account, mirroring India Compliance's
    `item_tax_template.py::validate_tax_rates()`; (2) a "Fetch Account" button on Item Tax Template that
    auto-adds the missing row, mirroring India Compliance's `client_scripts/item_tax_template.js` +
    `get_valid_gst_accounts()`. See Phase 2's checklist above for both.
- 2026-08-24 — Split `Oman VAT Account`'s single `output_vat_account` field into separate **Output VAT
  Account** (unchanged, still `reqd`) and **Input VAT Account** (new, optional — only needed by companies
  that use Reverse Charge) columns, at the user's request after discussing whether one shared account was
  enough. `utils/tax_account.py` gained `get_input_vat_account(company)` / `is_input_vat_account(account_head,
  company)` alongside the existing output-side pair, both now routed through a shared `_get_vat_account()`
  helper. `purchase_invoice.py::validate_reverse_charge()` now requires *both* accounts to be configured (one
  combined error listing whichever is missing) and *both* a nonzero row on the Output VAT Account (the
  self-accounted output liability) and a separate nonzero row on the Input VAT Account (the offsetting input
  credit) — restoring the two-sided rigor the earlier Add/Deduct/rate-matching heuristics were reaching for,
  but now correctly grounded in explicit per-account configuration rather than a guess. Sales Invoice is
  unaffected — it has no "input" side to check. Test helper renamed `set_output_vat_account()` →
  `set_vat_accounts(company, output_account=None, input_account=None)`; all call sites and the
  `TestPurchaseInvoiceReverseCharge` suite rewritten around the two-account requirement (new cases: only one
  of the two configured, only one of the two rows present, a different company's accounts). New
  `TestInputVatAccount` test class mirrors the existing `TestOutputVatAccount` one. `bench migrate` (new
  column, idempotent) and `bench run-tests --app oman_compliance` (80/80 passing) confirmed.
- 2026-08-24 — Confirmed, at the user's prompting, that a company configuring the *same* account for both
  Output and Input VAT Account is supported, and a single tax row against it is deliberately enough — not
  requiring two rows in that case. Reasoning: `is_output_vat_account()`/`is_input_vat_account()` are
  independent equality checks against the same account value, so this already worked without any code
  change; the actual decision was whether to *add* a stricter two-row requirement for the shared-account case,
  and the call was not to, since this app doesn't verify `add_deduct_tax` pairing or net GL effect even when
  the two accounts differ — the VAT return (box 2) only needs the taxable base and VAT amount, not a specific
  ledger structure, so requiring two rows only when the accounts happen to coincide would have been an
  arbitrary asymmetry rather than a principled rule. Added a code comment at the point in
  `purchase_invoice.py::validate_reverse_charge()` where this could look like an unclosed loophole, plus
  `test_reverse_charge_with_shared_output_and_input_account_accepts_a_single_row()` to lock the behavior in as
  intentional rather than leaving it as an untested side effect. `bench run-tests --app oman_compliance`
  (81/81 passing) confirmed.
- 2026-08-24 — Completed both TODOs deferred earlier in Phase 2 (marked "ToDo" at the time on explicit
  instruction not to implement yet):
  1. `overrides/item_tax_template.py::validate()` — a new `Item Tax Template` `validate` doc_event, checking
     the same VAT-category/tax-rate consistency `sales_invoice.py` already checks, but at template-definition
     time. Re-checked against a real Item Tax Template doc (not just `frappe._dict` mocks, since the field
     access pattern — `doc.get("taxes")` rows with a plain `.tax_rate` attribute — matches how a real
     controller doc behaves) via the new colocated `test_item_tax_template.py`.
  2. A new `fetch_vat_accounts` Button custom field on Item Tax Template plus
     `client_scripts/item_tax_template.js`, wired via `hooks.py`'s `doctype_js`. Verified the exact file
     resolution mechanism before trusting it — read Frappe core's
     `frappe.desk.form.meta.get_code_files_via_hooks()` (resolves each `doctype_js` path via
     `frappe.get_app_path(app_name, *path_parts)`, i.e. relative to the app's *top-level* Python package
     folder) and confirmed with `bench execute frappe.desk.form.meta.get_code_files_via_hooks --args
     '["doctype_js", "Item Tax Template"]'` that `"oman_compliance/client_scripts/item_tax_template.js"`
     resolves to the actual file path in this app's nested module folder before assuming it would just work.
     Unlike India Compliance's version (which computes a per-row rate from the template's own `gst_rate`
     field, split for intra-state CGST+SGST vs. inter-state IGST), this app has no such template-level rate
     field and no confirmed "the standard rate is X%" setting anywhere to default from — new rows the button
     adds are left at 0% rate for the user to fill in, rather than guessing a percentage.
  `bench migrate` (new custom field + doc_events + doctype_js hook, idempotent) and `bench run-tests --app
  oman_compliance` (89/89 passing) confirmed.
- 2026-08-24 — Two review findings on `get_vat_accounts_for_template()`, both confirmed real and fixed:
  1. Returned `[output_account, input_account]` unconditionally — when a company deliberately configures the
     *same* account for both (a supported case, see the entry above on shared accounts), this returned the
     same account twice, and the client's `filter()` doesn't de-duplicate, so the "Fetch VAT Accounts" button
     added two identical child rows. Fixed with `dict.fromkeys(...)` to de-duplicate while preserving order.
  2. Only checked doctype-level `Item Tax Template: read` permission, not whether the calling user may
     actually read the specific `company` passed in — any user with generic Item Tax Template read access
     could pass an arbitrary company name and get that company's configured VAT account names back,
     bypassing Frappe's per-company User Permission restrictions entirely. This exact gap is inherited
     directly from India Compliance's own `get_valid_gst_accounts()`, which has the identical pattern — not an
     excuse to keep it. Fixed by adding `frappe.has_permission("Company", "read", doc=company, throw=True)`.
     New test creates a real restricted user (Accounts User role + a `User Permission` limiting them to a
     *different* company) and confirms `get_vat_accounts_for_template()` now raises `frappe.PermissionError`
     for a company outside their permission scope — rather than just asserting some permission error occurs,
     to actually exercise the specific gap being closed.
  `bench run-tests --app oman_compliance` (91/91 passing) confirmed; no schema change this round.
- 2026-08-24 — Four more review findings, three confirmed real and fixed, one already stale:
  1. `client_scripts/item_tax_template.js`'s Prettier flag was already fixed in the prior round (verified
     clean with `npx prettier@2.7.1 --check` again) — stale, skipped.
  2. A real race: clicking "Fetch VAT Accounts" twice before the first server round-trip resolves let both
     invocations read `frm.doc.taxes` before either had added a row, see the same accounts as missing, and
     each `add_child()` a duplicate row for the same account. Fixed with an in-flight guard flag
     (`frm._fetching_vat_accounts`) around the mutating handler.
  3. Setup order's step 6 (reverse charge) only mentioned the Output VAT Account, not the Input VAT Account
     `purchase_invoice.py::validate_reverse_charge()` actually also requires — updated to mention both.
  4. `TestPurchaseInvoiceReverseCharge.setUp()` and `TestInputVatAccount.setUp()` unconditionally discovered
     a second, distinct account and `skipTest()`-ed the *entire class* if the bench didn't have one — even
     for tests that never touch a second account at all (missing-configuration, blank-input, defaulting
     tests). Moved that discovery+skip into a per-class helper method (`_get_distinct_input_account()` /
     `_configure_distinct_input_account()`) called only by the specific tests that need a genuinely distinct
     account, so the rest keep running regardless of what accounts happen to exist on a given bench.
  `bench run-tests --app oman_compliance` (91/91 passing, same count — no tests added or removed, only
  re-scoped) confirmed; no schema change.
