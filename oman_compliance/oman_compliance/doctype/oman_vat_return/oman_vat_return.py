import frappe
from frappe import _
from frappe.model.document import Document

from oman_compliance.oman_compliance.utils.vat_return.sections.domestic_supplies import get_domestic_supplies
from oman_compliance.oman_compliance.utils.vat_return.sections.exports import get_exports
from oman_compliance.oman_compliance.utils.vat_return.sections.imports_of_goods import get_imports_of_goods
from oman_compliance.oman_compliance.utils.vat_return.sections.input_vat_credit import get_input_vat_credit
from oman_compliance.oman_compliance.utils.vat_return.sections.reverse_charge_purchases import (
	get_reverse_charge_purchases,
)
from oman_compliance.oman_compliance.utils.vat_return.totals import (
	get_input_vat_credit_total,
	get_net_tax_liability,
	get_total_vat_due,
)

_EMPTY_BOX = {
	"taxable_amount": 0.0,
	"vat_amount": 0.0,
	"adjustment_taxable_amount": 0.0,
	"adjustment_vat_amount": 0.0,
}


class OmanVATReturn(Document):
	def validate(self):
		if self.from_date and self.to_date and self.from_date > self.to_date:
			frappe.throw(_("From Date cannot be after To Date"))

	@frappe.whitelist()
	def generate_return(self):
		"""Recomputes every box from the current transaction data and replaces `boxes` wholesale —
		safe to call repeatedly while still Draft, since it's meant to be re-run as invoices for the
		period get corrected. Locked once Filed, matching how a filed government return shouldn't
		silently change under a user's feet."""
		if self.status == "Filed":
			frappe.throw(_("Cannot regenerate a Filed return."))

		if not (self.company and self.from_date and self.to_date):
			frappe.throw(_("Company, From Date and To Date are required before generating a return."))

		domestic_supplies = get_domestic_supplies(self.company, self.from_date, self.to_date)
		exports = get_exports(self.company, self.from_date, self.to_date)
		reverse_charge_purchases = get_reverse_charge_purchases(self.company, self.from_date, self.to_date)
		imports_of_goods = get_imports_of_goods(self.company, self.from_date, self.to_date)
		input_vat_credit = get_input_vat_credit(self.company, self.from_date, self.to_date)

		self.boxes = []
		for box_code, description, box in _build_box_rows(
			domestic_supplies, exports, reverse_charge_purchases, imports_of_goods, input_vat_credit
		):
			self.append(
				"boxes",
				{
					"box_code": box_code,
					"description": description,
					"taxable_amount": box["taxable_amount"],
					"vat_amount": box["vat_amount"],
					"adjustment_taxable_amount": box["adjustment_taxable_amount"],
					"adjustment_vat_amount": box["adjustment_vat_amount"],
				},
			)

		self.total_vat_due = get_total_vat_due(domestic_supplies, reverse_charge_purchases)
		self.input_vat_credit_total = get_input_vat_credit_total(input_vat_credit)
		self.net_tax_liability = get_net_tax_liability(self.total_vat_due, self.input_vat_credit_total)

		self.save()


def _build_box_rows(domestic_supplies, exports, reverse_charge_purchases, imports_of_goods, input_vat_credit):
	"""Yields (box_code, description, box) tuples in official return order. 1(d)/1(e)/1(f) are
	always zero — no signal exists for profit-margin-scheme goods, and the intra-GCC supplies
	mechanism isn't activated by the OTA yet — but still appear as rows, not omitted, so the
	return's shape always mirrors the official 7-box form. Box 2(a) intra-GCC purchases *is*
	computed (`is_gcc_supplier` exists), unlike 1(d)/1(e)'s supply-side counterpart, but carries the
	same "not yet activated" caveat in its description, since the OTA hasn't turned the mechanism
	on for either side yet. Box 6 has no official sub-letters in the return form itself, but this
	app still reports its four required sub-splits (ordinary/imports/fixed assets/adjustments) as
	separate rows sharing box_code "6", since collapsing them would silently drop the very
	breakdown the box definition asks for."""
	yield "1(a)", _("Standard-rated domestic supplies"), domestic_supplies["standard_rated"]
	yield "1(b)", _("Zero-rated domestic supplies"), domestic_supplies["zero_rated"]
	yield "1(c)", _("Exempt domestic supplies"), domestic_supplies["exempt"]
	yield "1(d)", _("Intra-GCC supplies (not yet activated by the OTA)"), _EMPTY_BOX
	yield "1(e)", _("Intra-GCC supplies (not yet activated by the OTA)"), _EMPTY_BOX
	yield "1(f)", _("Profit-margin scheme goods (not yet supported by this app)"), _EMPTY_BOX
	yield (
		"2(a)",
		_("Intra-GCC reverse-charge purchases (not yet activated by the OTA)"),
		reverse_charge_purchases["gcc"],
	)
	yield "2(b)", _("Non-GCC reverse-charge purchases"), reverse_charge_purchases["non_gcc"]
	yield "3(a)", _("Exports"), exports
	yield "4(a)", _("Imports of goods with postponed payment"), imports_of_goods["postponed"]
	yield "4(b)", _("Total goods imported"), imports_of_goods["total"]
	yield "6", _("Input VAT credit — ordinary purchases"), input_vat_credit["ordinary"]
	yield "6", _("Input VAT credit — imports"), input_vat_credit["imports"]
	yield "6", _("Input VAT credit — fixed assets"), input_vat_credit["fixed_assets"]
	yield "6", _("Input VAT credit — adjustments"), input_vat_credit["adjustments"]
