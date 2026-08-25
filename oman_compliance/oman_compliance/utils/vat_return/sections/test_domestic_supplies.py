from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.vat_return.sections.domestic_supplies import get_domestic_supplies
from oman_compliance.tests import (
	create_submitted_sales_invoice,
	get_oman_test_company,
	get_oman_test_vat_accounts,
	get_unique_test_date,
	set_vat_accounts,
)


class TestGetDomesticSupplies(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, self.input_account = get_oman_test_vat_accounts(self.company)
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)
		self.test_date = get_unique_test_date()

	def _get_domestic_supplies(self):
		return get_domestic_supplies(self.company, self.test_date, self.test_date)

	def test_standard_rated_domestic_sale_lands_in_1a(self):
		create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			posting_date=self.test_date,
		)

		boxes = self._get_domestic_supplies()

		self.assertEqual(boxes["standard_rated"]["taxable_amount"], 200)
		self.assertEqual(boxes["standard_rated"]["vat_amount"], 10)
		self.assertEqual(boxes["zero_rated"]["taxable_amount"], 0)
		self.assertEqual(boxes["exempt"]["taxable_amount"], 0)

	def test_zero_rated_domestic_sale_lands_in_1b(self):
		create_submitted_sales_invoice(
			self.company, vat_category="Zero Rated", net_amount=300, posting_date=self.test_date
		)

		boxes = self._get_domestic_supplies()

		self.assertEqual(boxes["zero_rated"]["taxable_amount"], 300)
		self.assertEqual(boxes["zero_rated"]["vat_amount"], 0)

	def test_zero_rated_export_sale_is_excluded_from_1b(self):
		create_submitted_sales_invoice(
			self.company,
			vat_category="Zero Rated",
			shipping_country="United Arab Emirates",
			net_amount=300,
			posting_date=self.test_date,
		)

		boxes = self._get_domestic_supplies()

		self.assertEqual(boxes["zero_rated"]["taxable_amount"], 0)

	def test_exempt_domestic_sale_lands_in_1c(self):
		create_submitted_sales_invoice(
			self.company, vat_category="Exempt", net_amount=150, posting_date=self.test_date
		)

		boxes = self._get_domestic_supplies()

		self.assertEqual(boxes["exempt"]["taxable_amount"], 150)
		self.assertEqual(boxes["exempt"]["vat_amount"], 0)

	def test_out_of_scope_sale_is_excluded_from_every_box(self):
		create_submitted_sales_invoice(
			self.company, vat_category="Out of Scope", net_amount=999, posting_date=self.test_date
		)

		boxes = self._get_domestic_supplies()

		self.assertEqual(boxes["standard_rated"]["taxable_amount"], 0)
		self.assertEqual(boxes["zero_rated"]["taxable_amount"], 0)
		self.assertEqual(boxes["exempt"]["taxable_amount"], 0)

	def test_sales_credit_note_is_kept_as_a_separate_adjustment(self):
		original = create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			posting_date=self.test_date,
		)
		create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			is_return=True,
			return_against=original.name,
			posting_date=self.test_date,
		)

		boxes = self._get_domestic_supplies()

		self.assertEqual(boxes["standard_rated"]["taxable_amount"], 200)
		self.assertEqual(boxes["standard_rated"]["vat_amount"], 10)
		self.assertEqual(boxes["standard_rated"]["adjustment_taxable_amount"], 200)
		self.assertEqual(boxes["standard_rated"]["adjustment_vat_amount"], 10)
