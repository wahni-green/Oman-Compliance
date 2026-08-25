from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.vat_return.sections.imports_of_goods import get_imports_of_goods
from oman_compliance.tests import (
	create_submitted_purchase_invoice,
	get_oman_test_company,
	get_oman_test_vat_accounts,
	get_unique_test_date,
	set_vat_accounts,
)


class TestGetImportsOfGoods(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, self.input_account = get_oman_test_vat_accounts(self.company)
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)
		self.test_date = get_unique_test_date()

	def _get_imports_of_goods(self):
		return get_imports_of_goods(self.company, self.test_date, self.test_date)

	def test_postponed_import_counts_in_both_4a_and_4b(self):
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

		boxes = self._get_imports_of_goods()

		self.assertEqual(boxes["postponed"]["taxable_amount"], 500)
		self.assertEqual(boxes["postponed"]["vat_amount"], 25)
		self.assertEqual(boxes["total"]["taxable_amount"], 500)
		self.assertEqual(boxes["total"]["vat_amount"], 25)

	def test_non_postponed_import_counts_only_in_4b(self):
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			dispatch_country="United Arab Emirates",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=500,
			posting_date=self.test_date,
		)

		boxes = self._get_imports_of_goods()

		self.assertEqual(boxes["postponed"]["taxable_amount"], 0)
		self.assertEqual(boxes["total"]["taxable_amount"], 500)

	def test_domestic_purchase_is_excluded(self):
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=500,
			posting_date=self.test_date,
		)

		boxes = self._get_imports_of_goods()

		self.assertEqual(boxes["postponed"]["taxable_amount"], 0)
		self.assertEqual(boxes["total"]["taxable_amount"], 0)
