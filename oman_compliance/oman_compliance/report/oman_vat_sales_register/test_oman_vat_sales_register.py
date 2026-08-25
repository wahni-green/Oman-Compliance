import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.report.oman_vat_sales_register.oman_vat_sales_register import execute
from oman_compliance.tests import (
	create_submitted_sales_invoice,
	get_oman_test_company,
	get_oman_test_vat_accounts,
	get_unique_test_date,
	set_vat_accounts,
)


class TestOmanVatSalesRegister(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, self.input_account = get_oman_test_vat_accounts(self.company)
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)
		self.test_date = get_unique_test_date()

	def test_missing_company_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"from_date": self.test_date, "to_date": self.test_date})

	def test_missing_dates_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"company": self.company})

	def test_report_rows_match_the_underlying_section_totals(self):
		create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			posting_date=self.test_date,
		)
		create_submitted_sales_invoice(
			self.company,
			vat_category="Zero Rated",
			shipping_country="United Arab Emirates",
			net_amount=300,
			posting_date=self.test_date,
		)

		columns, data = execute(
			{"company": self.company, "from_date": self.test_date, "to_date": self.test_date}
		)

		self.assertTrue(columns)
		by_code = {row["box_code"]: row for row in data}
		self.assertEqual(by_code["1(a)"]["taxable_amount"], 200)
		self.assertEqual(by_code["1(a)"]["vat_amount"], 10)
		self.assertEqual(by_code["3(a)"]["taxable_amount"], 300)
		self.assertEqual(by_code["1(b)"]["taxable_amount"], 0)
