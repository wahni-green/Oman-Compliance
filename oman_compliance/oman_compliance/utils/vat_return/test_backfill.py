from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.vat_return.backfill import backfill_classification_flags
from oman_compliance.tests import (
	create_submitted_purchase_invoice,
	create_submitted_sales_invoice,
	get_non_oman_test_company,
	get_oman_test_company,
	get_unique_test_date,
)


class TestBackfillClassificationFlags(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.test_date = get_unique_test_date()

	def test_backfills_is_export_for_a_pre_existing_export_invoice(self):
		invoice = create_submitted_sales_invoice(
			self.company,
			vat_category="Zero Rated",
			shipping_country="United Arab Emirates",
			net_amount=300,
			posting_date=self.test_date,
		)
		# Simulate an invoice submitted before this field existed: correctly computed at the time
		# (above), then forced back to unset to represent what a pre-Phase-3 invoice would show.
		invoice.db_set("is_export", 0)

		result = backfill_classification_flags(company=self.company)

		invoice.reload()
		self.assertTrue(invoice.is_export)
		self.assertEqual(result["sales_invoice"], 1)

	def test_backfills_is_gcc_supplier_and_is_import_of_goods_for_a_pre_existing_purchase_invoice(self):
		invoice = create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			supplier_country="United Arab Emirates",
			dispatch_country="United Arab Emirates",
			net_amount=500,
			posting_date=self.test_date,
		)
		invoice.db_set("is_gcc_supplier", 0)
		invoice.db_set("is_import_of_goods", 0)

		result = backfill_classification_flags(company=self.company)

		invoice.reload()
		self.assertTrue(invoice.is_gcc_supplier)
		self.assertTrue(invoice.is_import_of_goods)
		self.assertEqual(result["purchase_invoice"], 1)

	def test_domestic_invoices_are_left_unset(self):
		invoice = create_submitted_sales_invoice(
			self.company, vat_category="Standard Rated", net_amount=200, posting_date=self.test_date
		)
		invoice.db_set("is_export", 0)

		result = backfill_classification_flags(company=self.company)

		invoice.reload()
		self.assertFalse(invoice.is_export)
		self.assertEqual(result["sales_invoice"], 0)

	def test_is_idempotent(self):
		invoice = create_submitted_sales_invoice(
			self.company,
			vat_category="Zero Rated",
			shipping_country="United Arab Emirates",
			net_amount=300,
			posting_date=self.test_date,
		)
		invoice.db_set("is_export", 0)

		backfill_classification_flags(company=self.company)
		second_run = backfill_classification_flags(company=self.company)

		self.assertEqual(second_run["sales_invoice"], 0)

	def test_company_filter_excludes_other_companies(self):
		unrelated_company = get_non_oman_test_company()
		invoice = create_submitted_sales_invoice(
			self.company,
			vat_category="Zero Rated",
			shipping_country="United Arab Emirates",
			net_amount=300,
			posting_date=self.test_date,
		)
		invoice.db_set("is_export", 0)

		unrelated_result = backfill_classification_flags(company=unrelated_company)

		self.assertEqual(unrelated_result["sales_invoice"], 0)
		invoice.reload()
		self.assertFalse(invoice.is_export)

		result = backfill_classification_flags(company=self.company)
		self.assertEqual(result["sales_invoice"], 1)
