import json

import frappe
from frappe.utils import flt


def get_output_vat_account(company: str | None) -> str | None:
	"""The given company's configured Output VAT account (Oman VAT Settings' per-company
	`vat_accounts` table) — the account it posts ordinary sales VAT and self-accounted Reverse
	Charge output VAT liability to."""
	return _get_vat_account(company, "output_vat_account")


def get_input_vat_account(company: str | None) -> str | None:
	"""The given company's configured Input VAT account — the account it posts recoverable input
	VAT to, including the offsetting credit for a self-accounted Reverse Charge purchase. Only
	relevant for Reverse Charge; ordinary Sales Invoice validation never needs this."""
	return _get_vat_account(company, "input_vat_account")


def _get_vat_account(company: str | None, fieldname: str) -> str | None:
	"""Explicitly configured rather than guessed from account type, since ERPNext's generic
	account types (Chargeable, Expense Account, ...) are shared with unrelated charges (freight,
	discount, withholding, ...) and can't reliably tell them apart. Matches how India Compliance's
	GST Settings names its GST accounts explicitly, per company (`gst_accounts`), instead of
	inferring them from account type."""
	if not company:
		return None

	settings = frappe.get_cached_doc("Oman VAT Settings")
	for row in settings.vat_accounts:
		if row.company == company:
			return row.get(fieldname)

	return None


def is_output_vat_account(account_head: str | None, company: str | None) -> bool:
	"""Whether a Taxes and Charges row's account is the given company's configured Output VAT
	account."""
	if not account_head:
		return False

	return account_head == get_output_vat_account(company)


def is_input_vat_account(account_head: str | None, company: str | None) -> bool:
	"""Whether a Taxes and Charges row's account is the given company's configured Input VAT
	account."""
	if not account_head:
		return False

	return account_head == get_input_vat_account(company)


def get_output_vat_amount(doc) -> float | None:
	"""Sum of only the Taxes and Charges rows posted to the company's configured Output VAT
	Account, in document currency — matching how net_total/grand_total are already shown on the
	printed invoice. `total_taxes_and_charges` (a Sales Invoice's total of *every* charge row) is
	the wrong figure to label "VAT" on a document that also carries freight, a discount, a
	withholding deduction, or another non-VAT charge — exposed via `jinja.methods` for the Tax
	Invoice print formats, which had exactly this bug (Greptile review on the PR that introduced
	them).

	Returns None — not 0 — when the company has no Output VAT Account configured at all: those are
	two different facts, and collapsing them into the same "0" a genuinely all-zero-rated invoice
	would also show is itself misleading on a legal document (a second Greptile review round on
	that same PR: a company with real VAT charged but no Output VAT Account configured yet would
	otherwise print/encode "0" VAT, understating what's actually owed). Callers must render this
	distinctly (e.g. a configuration warning), not silently substitute 0."""
	company = doc.get("company")
	if not get_output_vat_account(company):
		return None

	return sum(
		flt(tax.get("tax_amount"))
		for tax in doc.get("taxes") or []
		if is_output_vat_account(tax.get("account_head"), company)
	)


def get_item_wise_vat_rates(tax_rows, company: str | None) -> dict[str, float]:
	"""Sums `item_wise_tax_detail` VAT *rates* (`detail_row[0]`) for tax rows posting to the
	company's configured Output VAT Account, keyed by item_code — a Sales/Purchase Taxes and
	Charges table can just as easily hold an unrelated charge (freight, discount, withholding, ...)
	with its own nonzero item-wise rate, which must never be misread as VAT applied to that item.
	If no Output VAT Account is configured for this company yet, nothing here can be identified as
	VAT, so this returns no rates at all rather than guessing. Shared by
	`overrides/sales_invoice.py`'s VAT-category-mismatch check and the Tax Invoice print formats'
	per-item VAT rate display — previously two independent copies of this exact parse."""
	rates: dict[str, float] = {}

	for tax in tax_rows:
		if not is_output_vat_account(tax.get("account_head"), company):
			continue

		detail = tax.get("item_wise_tax_detail")
		if not detail:
			continue

		parsed = json.loads(detail) if isinstance(detail, str) else detail
		for item_code, detail_row in parsed.items():
			rates[item_code] = rates.get(item_code, 0) + detail_row[0]

	return rates


def get_item_wise_vat_amounts(tax_rows, company: str | None, is_matching_account) -> dict[str, float]:
	"""Sums `item_wise_tax_detail` VAT *amounts* (`detail_row[1]`, already base/company-currency —
	see OMAN_COMPLIANCE_PLAN.md's Phase 2/3 alignment note) for tax rows posting to whichever
	account `is_matching_account` identifies (`is_output_vat_account` or `is_input_vat_account`),
	keyed by item_code. Sibling to `get_item_wise_vat_rates` above, which reads `detail_row[0]`
	(the rate) instead of the amount — kept separate rather than merged since the two calls read
	different halves of the same tuple for different purposes, but factored out here so every
	`utils/vat_return` section function shares one `item_wise_tax_detail` parse instead of five
	independent copies of this currency-sensitive logic."""
	amounts: dict[str, float] = {}

	for tax in tax_rows:
		if not is_matching_account(tax.get("account_head"), company):
			continue

		detail = tax.get("item_wise_tax_detail")
		if not detail:
			continue

		parsed = json.loads(detail) if isinstance(detail, str) else detail
		for item_code, detail_row in parsed.items():
			amounts[item_code] = amounts.get(item_code, 0) + detail_row[1]

	return amounts
