import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.overrides.item_tax_template import (
	get_vat_accounts_for_template,
	validate,
)
from oman_compliance.tests import get_oman_test_company, get_test_tax_account, set_vat_accounts


class TestItemTaxTemplateVatCategoryValidation(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, template_company = get_test_tax_account()
		self.input_account = frappe.db.get_value(
			"Account", {"name": ["!=", self.output_account], "is_group": 0, "company": template_company}
		)
		if not self.input_account:
			self.skipTest("No second account available on this bench for this test.")

		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)

	def test_zero_rated_template_charging_output_vat_is_rejected(self):
		doc = frappe._dict(
			company=self.company,
			vat_category="Zero Rated",
			taxes=[frappe._dict(idx=1, tax_type=self.output_account, tax_rate=5)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate(doc)

	def test_zero_rated_template_charging_input_vat_is_rejected(self):
		doc = frappe._dict(
			company=self.company,
			vat_category="Zero Rated",
			taxes=[frappe._dict(idx=1, tax_type=self.input_account, tax_rate=5)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate(doc)

	def test_zero_rated_template_with_zero_rate_is_accepted(self):
		doc = frappe._dict(
			company=self.company,
			vat_category="Zero Rated",
			taxes=[frappe._dict(idx=1, tax_type=self.output_account, tax_rate=0)],
		)

		validate(doc)  # should not raise

	def test_standard_rated_template_charging_output_vat_is_accepted(self):
		doc = frappe._dict(
			company=self.company,
			vat_category="Standard Rated",
			taxes=[frappe._dict(idx=1, tax_type=self.output_account, tax_rate=5)],
		)

		validate(doc)  # should not raise

	def test_unrelated_account_is_never_flagged(self):
		non_vat_account = frappe.db.get_value(
			"Account",
			{"name": ["not in", [self.output_account, self.input_account]], "is_group": 0},
		)
		if not non_vat_account:
			self.skipTest("No third account available on this bench for this test.")

		doc = frappe._dict(
			company=self.company,
			vat_category="Zero Rated",
			taxes=[frappe._dict(idx=1, tax_type=non_vat_account, tax_rate=5)],
		)

		validate(doc)  # should not raise: not one of this company's configured VAT accounts

	def test_blank_company_is_never_flagged(self):
		doc = frappe._dict(
			company=None,
			vat_category="Zero Rated",
			taxes=[frappe._dict(idx=1, tax_type=self.output_account, tax_rate=5)],
		)

		validate(doc)  # should not raise: no company to check configured accounts against


class TestGetVatAccountsForTemplate(FrappeTestCase):
	def test_returns_configured_accounts(self):
		company = get_oman_test_company()
		output_account, template_company = get_test_tax_account()
		input_account = frappe.db.get_value(
			"Account", {"name": ["!=", output_account], "is_group": 0, "company": template_company}
		)
		if not input_account:
			self.skipTest("No second account available on this bench for this test.")

		set_vat_accounts(company, output_account=output_account, input_account=input_account)

		self.assertEqual(set(get_vat_accounts_for_template(company)), {output_account, input_account})

	def test_returns_empty_list_when_unconfigured(self):
		other_company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": "_Test Unconfigured Template Company",
				"abbr": "TUTC",
				"default_currency": "OMR",
				"country": "Oman",
			}
		).insert(ignore_permissions=True)

		self.assertEqual(get_vat_accounts_for_template(other_company.name), [])
