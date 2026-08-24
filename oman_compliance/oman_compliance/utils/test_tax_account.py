import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.tax_account import (
	get_input_vat_account,
	get_output_vat_account,
	is_input_vat_account,
	is_output_vat_account,
)
from oman_compliance.tests import get_oman_test_company, get_test_tax_account, set_vat_accounts


class TestOutputVatAccount(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.account, _ = get_test_tax_account()
		set_vat_accounts(self.company, output_account=self.account)

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


class TestInputVatAccount(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, template_company = get_test_tax_account()
		self.input_account = frappe.db.get_value(
			"Account", {"name": ["!=", self.output_account], "is_group": 0, "company": template_company}
		)
		if not self.input_account:
			self.skipTest("No second account available on this bench for this test.")

		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)

	def test_get_input_vat_account_returns_configured_account(self):
		self.assertEqual(get_input_vat_account(self.company), self.input_account)

	def test_get_input_vat_account_returns_none_when_unconfigured(self):
		set_vat_accounts(self.company, output_account=self.output_account)  # input left unset

		self.assertIsNone(get_input_vat_account(self.company))

	def test_get_input_vat_account_returns_none_for_blank_company(self):
		self.assertIsNone(get_input_vat_account(None))

	def test_is_input_vat_account_matches_configured_account(self):
		self.assertTrue(is_input_vat_account(self.input_account, self.company))

	def test_is_input_vat_account_rejects_the_output_account(self):
		# The two must be independently checked — configuring one doesn't imply the other.
		self.assertFalse(is_input_vat_account(self.output_account, self.company))

	def test_is_input_vat_account_rejects_blank_account_head(self):
		self.assertFalse(is_input_vat_account(None, self.company))
