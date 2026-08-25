import json

import frappe
from frappe import _

from oman_compliance.oman_compliance.constants import NO_TAX_VAT_CATEGORIES
from oman_compliance.oman_compliance.overrides.transaction import set_vat_category_defaults
from oman_compliance.oman_compliance.utils.company import is_oman_company
from oman_compliance.oman_compliance.utils.tax_account import is_output_vat_account
from oman_compliance.oman_compliance.utils.vat_category import get_item_tax_template_category


def validate(doc, method=None):
	if not is_oman_company(doc.get("company")):
		return

	set_vat_category_defaults(doc)
	validate_vat_category_tax_consistency(doc)
	set_export_flag(doc)


def set_export_flag(doc, method=None):
	"""VAT return box 3(a) exports vs box 1(b) domestic zero-rated — mirrors
	purchase_invoice.set_import_of_goods_flag's shape, on the sales side. Shipping Address is the
	better signal for "where does this actually go" than Customer Address alone (a domestic
	customer can be billed at a foreign address for unrelated reasons), so it's checked first;
	Customer Address is only the fallback for invoices with no distinct shipping address set."""
	previous_value = bool(doc.get("is_export"))
	new_value = is_export_candidate(doc)

	doc.is_export = new_value

	if previous_value != new_value:
		frappe.msgprint(
			_("Export set to {0}, based on the Shipping/Customer Address's country.").format(
				_("Yes") if new_value else _("No")
			),
			indicator="blue",
			alert=True,
		)


def is_export_candidate(doc) -> bool:
	address = doc.get("shipping_address_name") or doc.get("customer_address")
	if not address:
		return False

	address_country = frappe.db.get_value("Address", address, "country")
	if not address_country:
		return False

	company_country = frappe.get_cached_value("Company", doc.company, "country")
	if not company_country:
		return False

	return address_country != company_country


def validate_vat_category_tax_consistency(doc):
	"""Catch the legacy app's exact bug class (findings §51/85, §58): a Zero Rated/Exempt/Out of
	Scope item must not actually have VAT applied to it, or output VAT due is overstated. Only
	checks that direction — the reverse (Standard Rated with a 0% net rate) is a valid outcome of
	many ordinary tax templates and isn't flagged. Reads the rate out of `item_wise_tax_detail`
	rather than an amount, so this is currency-agnostic by construction (percentages, not money) —
	no base_*/document-currency confusion possible here (findings §58)."""
	charged_rates = _get_item_wise_tax_rates(doc.get("taxes") or [], doc.get("company"))
	categories_by_item_code = _get_vat_categories_by_item_code(doc.get("items") or [])

	for row in doc.get("items", []):
		category = row.get("vat_category")

		# Authoritative when present: an explicit Item Tax Template mismatch is checked in both
		# directions (unlike the rate-based fallback below), since a template that names its own
		# category is a stronger signal than a bare 0%/nonzero rate can ever be.
		template_category = get_item_tax_template_category(row.get("item_tax_template"))
		if template_category and template_category != category:
			frappe.throw(
				_(
					"Row #{0}: item {1} is marked {2} but its Item Tax Template ({3}) is set up for {4}."
				).format(
					row.idx, frappe.bold(row.item_code), category, row.item_tax_template, template_category
				),
				title=_("VAT Category Mismatch"),
			)

		if category not in NO_TAX_VAT_CATEGORIES:
			continue

		if len(categories_by_item_code[row.item_code]) > 1:
			# ERPNext's item_wise_tax_detail is keyed by item_code, not row, so two rows sharing
			# an item code can't be told apart here if they carry different VAT categories.
			# Skip rather than risk a false positive against one of a legitimately mixed set.
			continue

		rate = charged_rates.get(row.item_code, 0)
		if rate:
			frappe.throw(
				_("Row #{0}: item {1} is marked {2} but a {3}% VAT rate was applied to it.").format(
					row.idx, frappe.bold(row.item_code), category, rate
				),
				title=_("VAT Category Mismatch"),
			)


def _get_vat_categories_by_item_code(item_rows) -> dict:
	categories: dict[str, set] = {}
	for row in item_rows:
		categories.setdefault(row.item_code, set()).add(row.get("vat_category"))

	return categories


def _get_item_wise_tax_rates(tax_rows, company) -> dict:
	"""Only aggregates rows posting to the company's configured Output VAT Account (Oman VAT
	Settings) — a Sales Taxes and Charges table can just as easily hold an unrelated charge
	(freight, discount, withholding, ...) with its own nonzero item-wise rate, which must never be
	misread as VAT applied to that item. If no Output VAT Account is configured for this company
	yet, nothing here can be identified as VAT, so this returns no rates at all rather than
	guessing — the mismatch check below simply doesn't fire until it's configured."""
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
