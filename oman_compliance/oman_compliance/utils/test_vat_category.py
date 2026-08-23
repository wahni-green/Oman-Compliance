import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.vat_category import get_item_tax_template_category
from oman_compliance.tests import get_test_tax_account


class TestGetItemTaxTemplateCategory(FrappeTestCase):
	def setUp(self):
		self.tax_account, self.company = get_test_tax_account()

	def test_blank_template_returns_none(self):
		self.assertIsNone(get_item_tax_template_category(None))

	def test_template_without_category_returns_none(self):
		template = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test Template No Category",
				"company": self.company,
				"taxes": [{"tax_type": self.tax_account, "tax_rate": 5}],
			}
		).insert()
		self.addCleanup(template.delete)

		self.assertIsNone(get_item_tax_template_category(template.name))

	def test_template_with_category_returns_it(self):
		template = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test Template Exempt",
				"company": self.company,
				"taxes": [{"tax_type": self.tax_account, "tax_rate": 0}],
				"vat_category": "Exempt",
			}
		).insert()
		self.addCleanup(template.delete)

		self.assertEqual(get_item_tax_template_category(template.name), "Exempt")
