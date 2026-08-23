import frappe
from frappe import _
from frappe.model.document import Document


class OmanVATSettings(Document):
	def validate(self):
		self.validate_unique_vat_account_per_company()

	def validate_unique_vat_account_per_company(self):
		seen = set()
		for row in self.vat_accounts:
			if row.company in seen:
				frappe.throw(
					_("Company {0} has more than one row in VAT Accounts — only one is allowed.").format(
						frappe.bold(row.company)
					),
					title=_("Duplicate VAT Account"),
				)

			seen.add(row.company)
