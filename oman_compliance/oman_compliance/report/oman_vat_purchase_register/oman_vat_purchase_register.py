import frappe
from frappe import _

from oman_compliance.oman_compliance.utils.vat_return.sections.imports_of_goods import get_imports_of_goods
from oman_compliance.oman_compliance.utils.vat_return.sections.input_vat_credit import get_input_vat_credit
from oman_compliance.oman_compliance.utils.vat_return.sections.reverse_charge_purchases import (
	get_reverse_charge_purchases,
)


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
		{"label": _("Taxable Amount"), "fieldname": "taxable_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("VAT Amount"), "fieldname": "vat_amount", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Adjustment Taxable Amount"),
			"fieldname": "adjustment_taxable_amount",
			"fieldtype": "Currency",
			"width": 190,
		},
		{
			"label": _("Adjustment VAT Amount"),
			"fieldname": "adjustment_vat_amount",
			"fieldtype": "Currency",
			"width": 170,
		},
	]


def get_data(filters) -> list[dict]:
	"""Purchase-side counterpart to oman_vat_sales_register.py — see its docstring for why this is
	a box-level summary register, thinly wrapping the same `utils/vat_return/sections` functions
	the `Oman VAT Return` doctype uses rather than re-deriving any figure itself. Box 2(a) (intra-
	GCC reverse charge) is shown even though the OTA hasn't activated that mechanism yet, matching
	the doctype's own "computed but not-yet-active" treatment — see reverse_charge_purchases.py."""
	reverse_charge_purchases = get_reverse_charge_purchases(
		filters.company, filters.from_date, filters.to_date
	)
	imports_of_goods = get_imports_of_goods(filters.company, filters.from_date, filters.to_date)
	input_vat_credit = get_input_vat_credit(filters.company, filters.from_date, filters.to_date)

	rows = [
		(
			"2(a)",
			_("Intra-GCC reverse-charge purchases (not yet activated by the OTA)"),
			reverse_charge_purchases["gcc"],
		),
		("2(b)", _("Non-GCC reverse-charge purchases"), reverse_charge_purchases["non_gcc"]),
		("4(a)", _("Imports of goods with postponed payment"), imports_of_goods["postponed"]),
		("4(b)", _("Total goods imported"), imports_of_goods["total"]),
		("6", _("Input VAT credit — ordinary purchases"), input_vat_credit["ordinary"]),
		("6", _("Input VAT credit — imports"), input_vat_credit["imports"]),
		("6", _("Input VAT credit — fixed assets"), input_vat_credit["fixed_assets"]),
		("6", _("Input VAT credit — adjustments"), input_vat_credit["adjustments"]),
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
