from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.vat_return.sections.exports import get_exports
from oman_compliance.tests import create_submitted_sales_invoice, get_oman_test_company, get_unique_test_date


class TestGetExports(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.test_date = get_unique_test_date()

	def test_zero_rated_export_lands_in_3a(self):
		create_submitted_sales_invoice(
			self.company,
			vat_category="Zero Rated",
			shipping_country="United Arab Emirates",
			net_amount=300,
			posting_date=self.test_date,
		)

		box = get_exports(self.company, self.test_date, self.test_date)

		self.assertEqual(box["taxable_amount"], 300)
		self.assertEqual(box["vat_amount"], 0)

	def test_zero_rated_domestic_sale_is_excluded_from_3a(self):
		create_submitted_sales_invoice(
			self.company, vat_category="Zero Rated", net_amount=300, posting_date=self.test_date
		)

		box = get_exports(self.company, self.test_date, self.test_date)

		self.assertEqual(box["taxable_amount"], 0)

	def test_standard_rated_export_is_excluded_from_3a(self):
		# Box 3(a) is specifically a Zero Rated export per OTA's guide — a Standard Rated sale
		# shipped abroad (an unusual combination) still belongs to box 1(a), not here.
		create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			shipping_country="United Arab Emirates",
			net_amount=300,
			posting_date=self.test_date,
		)

		box = get_exports(self.company, self.test_date, self.test_date)

		self.assertEqual(box["taxable_amount"], 0)

	def test_export_credit_note_is_kept_as_a_separate_adjustment(self):
		original = create_submitted_sales_invoice(
			self.company,
			vat_category="Zero Rated",
			shipping_country="United Arab Emirates",
			net_amount=300,
			posting_date=self.test_date,
		)
		create_submitted_sales_invoice(
			self.company,
			vat_category="Zero Rated",
			shipping_country="United Arab Emirates",
			net_amount=300,
			is_return=True,
			return_against=original.name,
			posting_date=self.test_date,
		)

		box = get_exports(self.company, self.test_date, self.test_date)

		self.assertEqual(box["taxable_amount"], 300)
		self.assertEqual(box["adjustment_taxable_amount"], 300)
