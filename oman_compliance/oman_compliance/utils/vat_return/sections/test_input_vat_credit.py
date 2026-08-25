from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.vat_return.sections.input_vat_credit import get_input_vat_credit
from oman_compliance.tests import (
	create_submitted_purchase_invoice,
	get_oman_test_company,
	get_oman_test_vat_accounts,
	get_unique_test_date,
	set_vat_accounts,
)


class TestGetInputVatCredit(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, self.input_account = get_oman_test_vat_accounts(self.company)
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)
		self.test_date = get_unique_test_date()

	def _get_input_vat_credit(self):
		return get_input_vat_credit(self.company, self.test_date, self.test_date)

	def test_ordinary_purchase_lands_in_ordinary_only(self):
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=100,
			posting_date=self.test_date,
		)

		boxes = self._get_input_vat_credit()

		self.assertEqual(boxes["ordinary"]["taxable_amount"], 100)
		self.assertEqual(boxes["ordinary"]["vat_amount"], 5)
		self.assertEqual(boxes["imports"]["taxable_amount"], 0)
		self.assertEqual(boxes["fixed_assets"]["taxable_amount"], 0)
		self.assertEqual(boxes["adjustments"]["adjustment_taxable_amount"], 0)

	def test_import_of_goods_lands_in_imports_only(self):
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			dispatch_country="United Arab Emirates",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=500,
			posting_date=self.test_date,
		)

		boxes = self._get_input_vat_credit()

		self.assertEqual(boxes["imports"]["taxable_amount"], 500)
		self.assertEqual(boxes["imports"]["vat_amount"], 25)
		self.assertEqual(boxes["ordinary"]["taxable_amount"], 0)
		self.assertEqual(boxes["fixed_assets"]["taxable_amount"], 0)

	def test_fixed_asset_purchase_lands_in_fixed_assets_only(self):
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=1000,
			is_fixed_asset=1,
			posting_date=self.test_date,
		)

		boxes = self._get_input_vat_credit()

		self.assertEqual(boxes["fixed_assets"]["taxable_amount"], 1000)
		self.assertEqual(boxes["fixed_assets"]["vat_amount"], 50)
		self.assertEqual(boxes["ordinary"]["taxable_amount"], 0)
		self.assertEqual(boxes["imports"]["taxable_amount"], 0)

	def test_fixed_asset_import_lands_only_in_fixed_assets_not_imports(self):
		# A row that is both an import and a fixed asset must not be double-counted between the
		# two buckets — fixed_assets takes priority per input_vat_credit.py's own documented rule.
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			dispatch_country="United Arab Emirates",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=1000,
			is_fixed_asset=1,
			posting_date=self.test_date,
		)

		boxes = self._get_input_vat_credit()

		self.assertEqual(boxes["fixed_assets"]["taxable_amount"], 1000)
		self.assertEqual(boxes["imports"]["taxable_amount"], 0)
		self.assertEqual(boxes["ordinary"]["taxable_amount"], 0)

	def test_purchase_credit_note_lands_only_in_adjustments(self):
		original = create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=100,
			posting_date=self.test_date,
		)
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=100,
			is_return=True,
			return_against=original.name,
			posting_date=self.test_date,
		)

		boxes = self._get_input_vat_credit()

		# The original invoice's own figure stays intact in "ordinary" — never reduced there...
		self.assertEqual(boxes["ordinary"]["taxable_amount"], 100)
		self.assertEqual(boxes["ordinary"]["vat_amount"], 5)
		self.assertEqual(boxes["ordinary"]["adjustment_taxable_amount"], 0)
		# ...the credit note's own figure is reported separately, in "adjustments" only.
		self.assertEqual(boxes["adjustments"]["adjustment_taxable_amount"], 100)
		self.assertEqual(boxes["adjustments"]["adjustment_vat_amount"], 5)
		self.assertEqual(boxes["adjustments"]["taxable_amount"], 0)
