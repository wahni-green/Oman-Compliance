import frappe
from frappe import _

from oman_compliance.oman_compliance.utils.vat_return.sections.domestic_supplies import get_domestic_supplies
from oman_compliance.oman_compliance.utils.vat_return.sections.exports import get_exports


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	return get_columns(), get_data(filters)


def validate_filters(filters) -> None:
	if not filters.get("company"):
		frappe.throw(_("Company is mandatory"))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are mandatory"))


def get_columns() -> list[dict]:
	return [
		{"label": _("Box"), "fieldname": "box_code", "fieldtype": "Data", "width": 70},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 260},
		{
			"label": _("Taxable Amount"),
			"fieldname": "taxable_amount",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 140,
		},
		{
			"label": _("VAT Amount"),
			"fieldname": "vat_amount",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 120,
		},
		{
			"label": _("Adjustment Taxable Amount"),
			"fieldname": "adjustment_taxable_amount",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 190,
		},
		{
			"label": _("Adjustment VAT Amount"),
			"fieldname": "adjustment_vat_amount",
			"fieldtype": "Currency",
			"options": "Company:company:default_currency",
			"width": 170,
		},
	]


def get_data(filters) -> list[dict]:
	"""Thin wrapper over the same `utils/vat_return/sections` functions the `Oman VAT Return`
	doctype uses — never re-derives a VAT figure itself, per this app's architecture doc's
	instruction not to duplicate aggregation logic between a report and the return doctype.

	This is a box-level summary register (one row per return box) rather than an invoice-level
	detail listing — a deliberate scope choice for this phase, since the underlying section
	functions currently return summed totals, not per-invoice rows. A drill-down-to-invoice
	variant is a natural follow-up once a section module also exposes a row-level query alongside
	its summing one, not a gap in this report's own logic."""
	domestic_supplies = get_domestic_supplies(filters.company, filters.from_date, filters.to_date)
	exports = get_exports(filters.company, filters.from_date, filters.to_date)

	rows = [
		("1(a)", _("Standard-rated domestic supplies"), domestic_supplies["standard_rated"]),
		("1(b)", _("Zero-rated domestic supplies"), domestic_supplies["zero_rated"]),
		("1(c)", _("Exempt domestic supplies"), domestic_supplies["exempt"]),
		("3(a)", _("Exports"), exports),
	]

	return [
		{
			"box_code": box_code,
			"description": description,
			"taxable_amount": box["taxable_amount"],
			"vat_amount": box["vat_amount"],
			"adjustment_taxable_amount": box["adjustment_taxable_amount"],
			"adjustment_vat_amount": box["adjustment_vat_amount"],
		}
		for box_code, description, box in rows
	]
