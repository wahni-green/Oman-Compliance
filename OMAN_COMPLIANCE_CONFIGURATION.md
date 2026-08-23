# Oman Compliance — Configuration Guide

How to set up and use what's shipped so far (Phases 0–2). See `OMAN_COMPLIANCE_PLAN.md` for what's still
pending and `OMAN_COMPLIANCE_ARCHITECTURE.md` for the underlying design.

---

## Scope: Oman companies only

Every transaction-level behavior described below (VAT Category defaulting/validation, Reverse Charge, Import
of Goods) only ever runs for a Company whose **Country** is set to **Oman**. This app is commonly installed
alongside other companies' own apps on a shared bench, and none of this should ever touch an unrelated
company's transactions — a non-Oman company's Sales/Purchase documents are left completely untouched, not
just defaulted differently. TRN validation (below) is the one exception, since it's optional and harmless
either way — it only ever validates a field the user has actually filled in.

## TRN (Tax Registration Number)

- **Where:** Company, Customer, and Supplier each have a dedicated **TRN** field (`oman_trn`), placed next to
  the core **Tax ID** field. Use this field, not Tax ID — Tax ID is shared with other compliance apps that may
  be installed on the same site.
- **Format:** `OM` followed by 10 ASCII digits (e.g. `OM1234567890`), validated and normalized (upper-cased,
  trimmed) automatically on save. This is a provisional format pending OTA's published TRN specification — see
  architecture doc §3.
- A **TRN** doctype (Desk → TRN) also exists as a lookup/reference list, independent of the fields above.

## Oman VAT Settings

Desk → **Oman VAT Settings** (a single settings page). All three thresholds are fixed in **OMR regardless of
the site's default currency**:

| Field | Default | Purpose |
|---|---|---|
| Simplified Tax Invoice Threshold | OMR 500 | Below this (excl. VAT), a Simplified Tax Invoice may be used for a non-taxable customer. Informational for now — auto-selection lands in Phase 4. |
| Mandatory VAT Registration Threshold | OMR 38,500 | Informational display only. |
| Voluntary VAT Registration Threshold | OMR 19,250 | Informational display only. |

## VAT Accounts (Oman VAT Settings)

Desk → **Oman VAT Settings** → **VAT Accounts** table — one row per company, naming that company's **Output
VAT Account**. This is what identifies a Sales/Purchase Taxes and Charges row as genuinely VAT, rather than
guessing from the account's generic type (Chargeable, Expense Account, ...), which is also shared by unrelated
charges like freight, discount, or withholding. Matches how India Compliance's GST Settings names its GST
accounts explicitly per company, instead of inferring them.

- **Configure this before relying on VAT Category validation or Reverse Charge** (below) — without a row for a
  company, neither check can identify VAT at all: the VAT Category mismatch check simply won't fire, and
  Reverse Charge Applicable will refuse to save at all until it's configured.
- One row per company — a duplicate company row is rejected on save.

## Designated Zones

Desk → **Designated Zone** list. Duqm (SEZAD), Salalah Free Zone, Sohar Free Zone, and Al Mazunah Free Zone are
seeded automatically on install/migrate.

- **Linking an address to a zone:** open the Address record and set its **Designated Zone** field (placed
  after Country) to the relevant zone. This is what drives the VAT Category auto-defaulting below.
- **Deactivating a zone:** uncheck **Is Active** on the Designated Zone record. Addresses still linked to a
  deactivated zone stop getting the automatic Zero Rated default on *new* transactions — existing records are
  left untouched.
- **Article 54 Conditions** on each zone record is a reference note only, not enforced by the app — confirm
  current conditions against OTA/zone-authority guidance before relying on zero-rating for a real transaction.

## VAT Category on transactions and on Item Tax Template

A **VAT Category** field (Standard Rated / Zero Rated / Exempt / Out of Scope) is available on item rows of
Sales Order, Quotation, Delivery Note, Sales Invoice, and Purchase Invoice — and on **Item Tax Template**
itself.

- **Set it on your Item Tax Templates first.** A template's tax rate alone can't tell Zero Rated apart from
  Exempt or Out of Scope (all are commonly 0%), so if you maintain templates like "Oman VAT 5%", "Oman VAT 0% -
  Zero Rated", "Oman VAT 0% - Exempt", set each template's own **VAT Category** field to match. This is the
  strongest signal the app uses — it drives both defaulting and validation below — but it's optional; a
  template can be left without one (e.g. non-Oman templates on a shared site).
- **Auto-default, in priority order:** if a row's VAT Category is left blank, it's set from (1) its own **Item
  Tax Template**'s VAT Category, if that template declares one; else (2) **Zero Rated**, if the transaction's
  billing address, shipping address, or dispatch address links to an *active* Designated Zone; else (3)
  **Standard Rated**. This is a suggested default except when it comes from an explicit template category —
  always confirm actual Article 54 eligibility for the zone-based case, and override the field manually
  whenever it doesn't apply.
- **Never overwritten once set:** whether you set it explicitly or it was auto-defaulted on an earlier save,
  the app will not change it again — safe to correct manually at any point.
- **Validation (Sales Invoice only):**
  - Blocked if a row's category contradicts its own Item Tax Template's declared category, in either
    direction (e.g. row says Standard Rated but the template is set up as Exempt) — the strongest, most
    direct check, since it only fires when you've actually declared a category on the template.
  - Also blocked if a row marked Zero Rated, Exempt, or Out of Scope actually had VAT applied to it — checked
    against the company's configured **Output VAT Account** (see below), not against any generic tax/charge
    account. Without that account configured for the company, this fallback check can't identify VAT at all
    and simply doesn't fire. The reverse — Standard Rated taxed at 0% — is not flagged, since that's a valid
    outcome of many ordinary tax templates.
  - Known limitation: if the same item code appears on two rows with different VAT categories on one invoice,
    the tax-charged fallback check (not the template check) is skipped for that item code, since ERPNext's own
    tax-detail tracking can't tell such rows apart — use distinct item codes/variants if you need that check to
    cover a mixed-category line.

## Reverse Charge (Purchase Invoice)

A **Reverse Charge Applicable** checkbox is available on Purchase Invoice, next to the core **Tax Category**
field — for imported services and other reverse-charge supplies where this company must self-account for
output VAT as the recipient (return box 2).

- Checking it **requires the company's Output VAT Account to be configured** (Oman VAT Settings → VAT
  Accounts, above) and **at least one nonzero VAT row posted to that exact account** on the invoice's Taxes
  and Charges table. The app does not generate this row itself — set up a Purchase Taxes and Charges template
  (or Tax Category) that posts to the configured Output VAT Account, the same way you would configure any
  other self-accounting tax scenario.
- No automatic detection: the app does not guess this checkbox from the supplier's country or any other
  heuristic, since reverse charge applies specifically to imported *services* — an address-based guess would
  also misfire on imported *goods*, which belong in a different return box (imports of goods, not reverse
  charge).

## Import of Goods (Purchase Invoice)

An **Import of Goods** checkbox is available on Purchase Invoice, next to **Reverse Charge Applicable** — for
VAT return box 4 (imports of goods), which is distinct from Reverse Charge/box 2 (imported *services*).

- **Read-only and fully automatic** — unlike Reverse Charge, you never set this yourself. It's recomputed on
  every save from the **Dispatch Address**'s country: if that address's country differs from the Company's own
  country, the invoice is treated as an import of goods. A blank Dispatch Address is always treated as *not*
  an import.
- **You'll be notified whenever the value changes** — a message appears specifically when the computed value
  flips (e.g. you change the Dispatch Address from a domestic to a foreign one, or vice versa), not on every
  save, since the field itself isn't user-editable.
- Uses **Dispatch Address**, not **Shipping Address** — Shipping Address is where your company *receives* the
  goods (normally always domestic), Dispatch Address is where the supplier actually ships *from*. Make sure
  Dispatch Address is filled in on cross-border purchases for this to detect them correctly.

## Exchange rate disclosure

Not yet a Desk field or print-format element — that lands with Phase 4's tax invoice print formats. Available
now as a Jinja method for anyone building or customizing a print format ahead of that:

```jinja
{{ get_exchange_rate_disclosure(doc) }}
```

Returns a string like `Exchange rate: 1 USD = 0.385 OMR (as on 23-08-2026)` for a foreign-currency Sales or
Purchase Invoice, or nothing (`None`) for a company-currency (OMR) document.

## Suggested setup order for a new company

1. Set the Company's **TRN**.
2. Add a row for the Company in Oman VAT Settings' **VAT Accounts** table, naming its **Output VAT Account** —
   required before VAT Category validation or Reverse Charge Applicable will do anything useful.
3. Review the **Oman VAT Settings** thresholds (defaults are usually correct; they're OMR-fixed regardless of
   company currency).
4. Tag any **Address** that sits inside a designated zone with its **Designated Zone** link.
5. Leave **VAT Category** to auto-default on transactions, correcting it manually wherever the default doesn't
   match the actual supply.
6. For imported services under reverse charge, check **Reverse Charge Applicable** on the Purchase Invoice and
   make sure its tax template posts to the configured Output VAT Account.
7. For purchases from abroad, make sure **Dispatch Address** is set on the Purchase Invoice so **Import of
   Goods** is detected correctly.
