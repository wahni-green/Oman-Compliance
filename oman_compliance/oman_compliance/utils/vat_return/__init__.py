import frappe

from oman_compliance.oman_compliance.utils.tax_account import (
	get_item_wise_vat_amounts,
	is_input_vat_account,
	is_output_vat_account,
)

# Out of Scope supplies are excluded from the Oman VAT return entirely, not just left
# uncategorized (OMAN_COMPLIANCE_PLAN.md's Phase 2/3 alignment note, reading OTA's own VAT Return
# Filing guide) — filtered out once here, in the shared row fetch, so no section function gets a
# chance to omit the exclusion by hand-listing categories inconsistently.
REPORTABLE_VAT_CATEGORIES = ("Standard Rated", "Zero Rated", "Exempt")

_PARENT_FIELDS = {
	"Sales Invoice": ("is_export",),
	"Purchase Invoice": (
		"is_reverse_charge",
		"is_gcc_supplier",
		"is_import_of_goods",
		"is_postponed_import_vat",
	),
}


def get_invoice_rows(doctype: str, company: str, from_date, to_date) -> list:
	"""One dict per submitted Sales/Purchase Invoice Item row in [from_date, to_date] for
	`company`, joined with its parent's classification flags and this app's Output/Input VAT
	Account item-wise amount parse. This is the one shared fetch every
	`utils/vat_return/sections/*.py` function filters/sums from — each section function is an
	independent, individually testable filter+sum over this row shape, deliberately not sharing a
	fetch across sections (five section functions issuing five similar queries during one return's
	generation is a fine trade against having each one be independently correct/testable, given
	the modest data volumes a periodic compliance return deals with).

	Every row carries: `item_code`, `vat_category`, `base_net_amount`, `is_return` (parent's, for
	the credit/debit-note adjustment split), `output_vat_amount`/`input_vat_amount` (this item's
	share of `item_wise_tax_detail` on whichever Taxes and Charges rows post to the company's
	configured Output/Input VAT Account), `is_fixed_asset` (Purchase Invoice Item only, core
	ERPNext field), and the doctype-specific parent flags in `_PARENT_FIELDS`.
	"""
	# frappe.get_all() below deliberately bypasses per-document permissions (that's what "all" means
	# here — it's the only way to sum across every invoice in the period) — which is exactly why the
	# one thing actually gated on the caller's own access, the Company itself, must be checked
	# explicitly. Without this, any user who can open a Script Report could pass an arbitrary
	# `company` filter and read that company's VAT totals regardless of their own User Permission
	# restrictions — the same class of gap fixed in item_tax_template.py's
	# get_vat_accounts_for_template().
	frappe.has_permission("Company", "read", doc=company, throw=True)

	invoices = frappe.get_all(
		doctype,
		filters={
			"company": company,
			"posting_date": ["between", [from_date, to_date]],
			"docstatus": 1,
		},
		fields=["name", "is_return", *_PARENT_FIELDS[doctype]],
	)
	if not invoices:
		return []

	invoices_by_name = {invoice.name: invoice for invoice in invoices}

	item_fields = ["parent", "item_code", "vat_category", "base_net_amount"]
	if doctype == "Purchase Invoice":
		item_fields.append("is_fixed_asset")

	items = frappe.get_all(
		f"{doctype} Item",
		filters={
			"parent": ["in", list(invoices_by_name)],
			"vat_category": ["in", REPORTABLE_VAT_CATEGORIES],
		},
		fields=item_fields,
	)
	if not items:
		return []

	tax_doctype = "Sales Taxes and Charges" if doctype == "Sales Invoice" else "Purchase Taxes and Charges"
	tax_rows_by_parent: dict[str, list] = {}
	for tax in frappe.get_all(
		tax_doctype,
		filters={"parent": ["in", list(invoices_by_name)]},
		fields=["parent", "account_head", "item_wise_tax_detail"],
	):
		tax_rows_by_parent.setdefault(tax.parent, []).append(tax)

	output_vat_by_parent = {
		parent: get_item_wise_vat_amounts(rows, company, is_output_vat_account)
		for parent, rows in tax_rows_by_parent.items()
	}
	input_vat_by_parent = {
		parent: get_item_wise_vat_amounts(rows, company, is_input_vat_account)
		for parent, rows in tax_rows_by_parent.items()
	}

	# item_wise_tax_detail is keyed by item_code, not row (the same limitation
	# overrides/sales_invoice.py::_get_item_wise_tax_rates already documents) — when an invoice has
	# two rows sharing an item_code, that one JSON entry is the combined amount across BOTH rows,
	# not either row's own share. Assigning the whole figure to every matching row would double (or
	# N-times) count it once summed, so it's allocated across those rows by each row's share of the
	# item_code's total base_net_amount instead — exact when there's only one row per item_code
	# (the common case, share = 1), proportional otherwise.
	net_amount_by_parent_and_item: dict[tuple[str, str], float] = {}
	for item in items:
		key = (item.parent, item.item_code)
		net_amount_by_parent_and_item[key] = net_amount_by_parent_and_item.get(key, 0) + (
			item.base_net_amount or 0
		)

	rows = []
	for item in items:
		invoice = invoices_by_name[item.parent]
		total_net_amount = net_amount_by_parent_and_item[(item.parent, item.item_code)]
		share = (item.base_net_amount or 0) / total_net_amount if total_net_amount else 0

		row = frappe._dict(item)
		row.is_return = bool(invoice.is_return)
		row.output_vat_amount = output_vat_by_parent.get(item.parent, {}).get(item.item_code, 0) * share
		row.input_vat_amount = input_vat_by_parent.get(item.parent, {}).get(item.item_code, 0) * share
		for field in _PARENT_FIELDS[doctype]:
			row[field] = bool(invoice.get(field))
		rows.append(row)

	return rows


def summarize_box(rows: list, vat_amount_field: str = "output_vat_amount") -> dict:
	"""Sums a filtered list of `get_invoice_rows()` rows into the box shape every section
	function returns: non-return rows land in `taxable_amount`/`vat_amount`, `is_return=1` rows
	(credit/debit notes) land in `adjustment_taxable_amount`/`adjustment_vat_amount` instead —
	kept separate rather than netted in, matching the legacy app's auditability approach. ERPNext
	stores a return's amounts as negative, so both figures are `abs()`'d back to a positive
	adjustment magnitude; `utils/vat_return/totals.py` is what actually nets it against the main
	figure for the return's real box 5/7 totals."""
	box = {
		"taxable_amount": 0.0,
		"vat_amount": 0.0,
		"adjustment_taxable_amount": 0.0,
		"adjustment_vat_amount": 0.0,
	}

	for row in rows:
		taxable = abs(row.base_net_amount or 0)
		vat = abs(row.get(vat_amount_field) or 0)

		if row.is_return:
			box["adjustment_taxable_amount"] += taxable
			box["adjustment_vat_amount"] += vat
		else:
			box["taxable_amount"] += taxable
			box["vat_amount"] += vat

	return box
