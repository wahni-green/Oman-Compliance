import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.tax_account import (
	get_input_vat_account,
	get_output_vat_account,
	get_output_vat_amount,
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


class TestGetOutputVatAmount(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.vat_account, _ = get_test_tax_account()
		set_vat_accounts(self.company, output_account=self.vat_account)

	def test_sums_only_rows_on_the_output_vat_account(self):
		# The bug this guards: total_taxes_and_charges would sum every row below (VAT + freight),
		# mislabelling the freight charge as VAT.
		doc = frappe._dict(
			company=self.company,
			taxes=[
				frappe._dict(account_head=self.vat_account, tax_amount=5),
				frappe._dict(account_head="_Test Freight Account", tax_amount=20),
			],
		)

		self.assertEqual(get_output_vat_amount(doc), 5)

	def test_returns_zero_when_no_taxes(self):
		doc = frappe._dict(company=self.company, taxes=[])

		self.assertEqual(get_output_vat_amount(doc), 0)

	def test_returns_zero_when_output_vat_account_is_unconfigured(self):
		other_company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test Unconfigured Output VAT Amount Company",
				"abbr": "TUOVAC",
				"default_currency": "OMR",
				"country": "Oman",
			}
		).insert(ignore_permissions=True)

		doc = frappe._dict(
			company=other_company.name,
			taxes=[frappe._dict(account_head=self.vat_account, tax_amount=5)],
		)

		self.assertEqual(get_output_vat_amount(doc), 0)


class TestInputVatAccount(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, self.template_company = get_test_tax_account()

	def _configure_distinct_input_account(self) -> str:
		"""Only called by tests that need a genuine second, distinct account configured — skipping
		the whole class in setUp() whenever a second account isn't available would also skip tests
		that never touch one at all (blank-input and unconfigured-input cases included)."""
		input_account = frappe.db.get_value(
			"Account",
			{"name": ["!=", self.output_account], "is_group": 0, "company": self.template_company},
		)
		if not input_account:
			self.skipTest("No second account available on this bench for this test.")

		set_vat_accounts(self.company, output_account=self.output_account, input_account=input_account)
		return input_account

	def test_get_input_vat_account_returns_configured_account(self):
		input_account = self._configure_distinct_input_account()

		self.assertEqual(get_input_vat_account(self.company), input_account)

	def test_get_input_vat_account_returns_none_when_unconfigured(self):
		set_vat_accounts(self.company, output_account=self.output_account)  # input left unset

		self.assertIsNone(get_input_vat_account(self.company))

	def test_get_input_vat_account_returns_none_for_blank_company(self):
		self.assertIsNone(get_input_vat_account(None))

	def test_is_input_vat_account_matches_configured_account(self):
		input_account = self._configure_distinct_input_account()

		self.assertTrue(is_input_vat_account(input_account, self.company))

	def test_is_input_vat_account_rejects_the_output_account(self):
		# The two must be independently checked — configuring one doesn't imply the other.
		self._configure_distinct_input_account()

		self.assertFalse(is_input_vat_account(self.output_account, self.company))

	def test_is_input_vat_account_rejects_blank_account_head(self):
		self.assertFalse(is_input_vat_account(None, self.company))
