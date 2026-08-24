import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.tests import get_oman_test_company, get_test_tax_account


class TestOmanVATSettings(FrappeTestCase):
	def test_default_thresholds(self):
		settings = frappe.get_single("Oman VAT Settings")
		self.assertEqual(settings.simplified_tax_invoice_threshold, 500)
		self.assertEqual(settings.mandatory_registration_threshold, 38500)
		self.assertEqual(settings.voluntary_registration_threshold, 19250)
		self.assertEqual(settings.settings_currency, "OMR")

	def test_duplicate_company_in_vat_accounts_is_rejected(self):
		company = get_oman_test_company()
		account, _ = get_test_tax_account()

		settings = frappe.get_single("Oman VAT Settings")
		settings.vat_accounts = [row for row in settings.vat_accounts if row.company != company]
		settings.append("vat_accounts", {"company": company, "output_vat_account": account})
		settings.append("vat_accounts", {"company": company, "output_vat_account": account})

		with self.assertRaises(frappe.ValidationError):
			settings.save(ignore_permissions=True)

	def test_one_row_per_company_is_accepted(self):
		company = get_oman_test_company()
		account, _ = get_test_tax_account()

		settings = frappe.get_single("Oman VAT Settings")
		settings.vat_accounts = [row for row in settings.vat_accounts if row.company != company]
		settings.append("vat_accounts", {"company": company, "output_vat_account": account})

		settings.save(ignore_permissions=True)  # should not raise
