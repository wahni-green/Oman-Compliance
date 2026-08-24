import frappe
from frappe import _

from oman_compliance.oman_compliance.constants import NO_TAX_VAT_CATEGORIES
from oman_compliance.oman_compliance.utils.tax_account import is_input_vat_account, is_output_vat_account


def validate(doc, method=None):
	validate_vat_category_tax_consistency(doc)


def validate_vat_category_tax_consistency(doc):
	"""The same class of check `sales_invoice.py` runs at invoice time, done here at template-
	definition time instead — catching a Zero Rated/Exempt/Out of Scope template that still posts
	a nonzero rate to the company's configured Output/Input VAT Account before it's ever used on a
	real transaction, rather than only discovering the mistake later on an invoice."""
	if doc.vat_category not in NO_TAX_VAT_CATEGORIES or not doc.company:
		return

	for row in doc.get("taxes") or []:
		if not row.tax_rate:
			continue

		if is_output_vat_account(row.tax_type, doc.company) or is_input_vat_account(
			row.tax_type, doc.company
		):
			frappe.throw(
				_(
					"Row #{0}: this template is marked {1} but posts a {2}% rate to {3}, one of this"
					" Company's configured VAT Accounts."
				).format(row.idx, doc.vat_category, row.tax_rate, frappe.bold(row.tax_type)),
				title=_("VAT Category Mismatch"),
			)
