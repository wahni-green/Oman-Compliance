import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.tax_account import get_output_vat_account, is_output_vat_account
from oman_compliance.tests import get_oman_test_company, get_test_tax_account, set_output_vat_account


class TestOutputVatAccount(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.account, _ = get_test_tax_account()
		set_output_vat_account(self.company, self.account)

	def test_get_output_vat_account_returns_configured_account(self):
		self.assertEqual(get_output_vat_account(self.company), self.account)

	def test_get_output_vat_account_returns_none_for_unconfigured_company(self):
		other_company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test Unconfigured VAT Company",
				"abbr": "TUVC",
				"default_currency": "OMR",
				"country": "Oman",
			}
		).insert(ignore_permissions=True)

		self.assertIsNone(get_output_vat_account(other_company.name))

	def test_get_output_vat_account_returns_none_for_blank_company(self):
		self.assertIsNone(get_output_vat_account(None))

	def test_is_output_vat_account_matches_configured_account(self):
		self.assertTrue(is_output_vat_account(self.account, self.company))

	def test_is_output_vat_account_rejects_a_different_account(self):
		self.assertFalse(is_output_vat_account("_Test Some Other Account", self.company))

	def test_is_output_vat_account_rejects_blank_account_head(self):
		self.assertFalse(is_output_vat_account(None, self.company))
