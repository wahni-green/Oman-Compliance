import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.report.oman_vat_purchase_register.oman_vat_purchase_register import (
	execute,
)
from oman_compliance.tests import (
	create_submitted_purchase_invoice,
	get_oman_test_company,
	get_oman_test_vat_accounts,
	get_unique_test_date,
	set_vat_accounts,
)


class TestOmanVatPurchaseRegister(FrappeTestCase):
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
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			input_vat_account=self.input_account,
			output_rate=5,
			input_rate=5,
			net_amount=400,
			is_reverse_charge=True,
			supplier_country="India",
			posting_date=self.test_date,
		)
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			dispatch_country="United Arab Emirates",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=500,
			is_postponed_import_vat=True,
			posting_date=self.test_date,
		)

		columns, data = execute(
			{"company": self.company, "from_date": self.test_date, "to_date": self.test_date}
		)

		self.assertTrue(columns)
		by_code = {}
		for row in data:
			by_code.setdefault(row["box_code"], []).append(row)

		self.assertEqual(by_code["2(b)"][0]["taxable_amount"], 400)
		self.assertEqual(by_code["2(b)"][0]["vat_amount"], 20)
		self.assertEqual(by_code["2(a)"][0]["taxable_amount"], 0)
		self.assertEqual(by_code["4(a)"][0]["taxable_amount"], 500)
		self.assertEqual(by_code["4(b)"][0]["taxable_amount"], 500)
		# box 6 has four rows sharing the same box_code "6" (ordinary/imports/fixed_assets/adjustments)
		self.assertEqual(len(by_code["6"]), 4)
