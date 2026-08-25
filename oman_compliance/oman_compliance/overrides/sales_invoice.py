import json

import frappe
from frappe import _
from frappe.utils import flt

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
	validate_no_mixed_vat_category_per_item_code(doc)
	set_export_flag(doc)
	set_simplified_tax_invoice_flag(doc)


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


def set_simplified_tax_invoice_flag(doc, method=None):
	"""Drives the Oman Tax Invoice print format's auto-selection between its full and simplified
	layouts (Phase 4, findings §54: the legacy app's Simplified Tax Invoice print format existed but
	nothing auto-selected it). Mirrors set_export_flag's shape: always recomputed on save, since a
	later edit (discount, extra line, customer swap) can flip which layout is appropriate."""
	previous_value = bool(doc.get("is_simplified_tax_invoice"))
	new_value = is_simplified_tax_invoice_candidate(doc)

	doc.is_simplified_tax_invoice = new_value

	if previous_value != new_value:
		frappe.msgprint(
			_("Simplified Tax Invoice set to {0}, based on the Net Total and Customer TRN.").format(
				_("Yes") if new_value else _("No")
			),
			indicator="blue",
			alert=True,
		)


def is_simplified_tax_invoice_candidate(doc) -> bool:
	"""OTA permits (doesn't require) a Simplified Tax Invoice under OMR 500 excl. VAT for supplies
	to non-taxable consumers — "non-taxable" here means the Customer has no TRN on file (not VAT-
	registered), the same signal this app already uses everywhere else a taxable/non-taxable
	distinction matters, rather than introducing a second, separate "is this customer taxable"
	field. The threshold itself is read from Oman VAT Settings, not hardcoded, so a change there
	takes effect without a code change. Compares against base_net_total (company currency, excl.
	VAT), matching the threshold field's own "Grand total (excl. VAT)" description exactly. Uses
	the absolute value: a Sales Return/credit note has a negative base_net_total, and comparing the
	raw signed figure would let a large-value return through this check regardless of magnitude."""
	threshold = frappe.get_cached_doc("Oman VAT Settings").simplified_tax_invoice_threshold
	if not threshold or abs(flt(doc.get("base_net_total"))) >= flt(threshold):
		return False

	customer = doc.get("customer")
	if not customer:
		return False

	return not frappe.db.get_value("Customer", customer, "oman_trn")


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


def validate_no_mixed_vat_category_per_item_code(doc):
	"""ERPNext's `item_wise_tax_detail` (read by `utils/vat_return.get_invoice_rows()` when
	generating a VAT return/register) is keyed by item_code, not row — if the same item_code
	appears more than once on this invoice, there is no way to later recover how much of the
	combined VAT amount belongs to which row (confirmed against ERPNext's own
	`taxes_and_totals.py`: the stored rate is just whichever row was processed last, not kept per
	category). `get_invoice_rows()`'s proportional-by-net-amount allocation is only correct when
	every row sharing an item_code was actually taxed identically — so this checks both VAT
	Category AND Item Tax Template, not category alone: two rows can carry the same category yet
	use different templates configured with different rates (a same-category rate mismatch a
	category-only check would miss entirely). Blocking it here, at the source, is better than a
	return/report silently misattributing VAT between boxes months later — use a distinct Item
	Code per category/template combination instead."""
	configs_by_item_code = _get_vat_configs_by_item_code(doc.get("items") or [])

	for item_code, configs in configs_by_item_code.items():
		if len(configs) > 1:
			categories = sorted({category for category, _template in configs})
			frappe.throw(
				_(
					"Item {0} appears on more than one row with inconsistent VAT treatment (VAT"
					" Category and/or Item Tax Template differ: {1}). The same Item Code must use the"
					" same VAT Category and the same Item Tax Template throughout this invoice — VAT"
					" return figures can't be reliably split per row otherwise. Use a distinct Item"
					" Code for each category/template combination instead."
				).format(frappe.bold(item_code), ", ".join(categories)),
				title=_("VAT Category Mismatch"),
			)


def _get_vat_configs_by_item_code(item_rows) -> dict:
	configs: dict[str, set] = {}
	for row in item_rows:
		configs.setdefault(row.item_code, set()).add((row.get("vat_category"), row.get("item_tax_template")))

	return configs


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
