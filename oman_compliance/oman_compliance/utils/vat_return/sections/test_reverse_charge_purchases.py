from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.vat_return.sections.reverse_charge_purchases import (
	get_reverse_charge_purchases,
)
from oman_compliance.tests import (
	create_submitted_purchase_invoice,
	get_oman_test_company,
	get_oman_test_vat_accounts,
	get_unique_test_date,
	set_vat_accounts,
)


class TestGetReverseChargePurchases(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, self.input_account = get_oman_test_vat_accounts(self.company)
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)
		self.test_date = get_unique_test_date()

	def _get_reverse_charge_purchases(self):
		return get_reverse_charge_purchases(self.company, self.test_date, self.test_date)

	def test_gcc_reverse_charge_purchase_lands_in_2a(self):
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			input_vat_account=self.input_account,
			output_rate=5,
			input_rate=5,
			net_amount=400,
			is_reverse_charge=True,
			supplier_country="United Arab Emirates",
			posting_date=self.test_date,
		)

		boxes = self._get_reverse_charge_purchases()

		self.assertEqual(boxes["gcc"]["taxable_amount"], 400)
		self.assertEqual(boxes["gcc"]["vat_amount"], 20)
		self.assertEqual(boxes["non_gcc"]["taxable_amount"], 0)

	def test_non_gcc_reverse_charge_purchase_lands_in_2b(self):
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

		boxes = self._get_reverse_charge_purchases()

		self.assertEqual(boxes["non_gcc"]["taxable_amount"], 400)
		self.assertEqual(boxes["non_gcc"]["vat_amount"], 20)
		self.assertEqual(boxes["gcc"]["taxable_amount"], 0)

	def test_non_reverse_charge_purchase_is_excluded(self):
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=400,
			posting_date=self.test_date,
		)

		boxes = self._get_reverse_charge_purchases()

		self.assertEqual(boxes["gcc"]["taxable_amount"], 0)
		self.assertEqual(boxes["non_gcc"]["taxable_amount"], 0)

	def test_reverse_charge_credit_note_is_kept_as_a_separate_adjustment(self):
		original = create_submitted_purchase_invoice(
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
			output_vat_account=self.output_account,
			input_vat_account=self.input_account,
			output_rate=5,
			input_rate=5,
			net_amount=400,
			is_reverse_charge=True,
			supplier_country="India",
			is_return=True,
			return_against=original.name,
			posting_date=self.test_date,
		)

		boxes = self._get_reverse_charge_purchases()

		self.assertEqual(boxes["non_gcc"]["taxable_amount"], 400)
		self.assertEqual(boxes["non_gcc"]["adjustment_taxable_amount"], 400)
