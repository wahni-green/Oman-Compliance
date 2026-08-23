import json

import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.constants import VAT_BEARING_ACCOUNT_TYPES
from oman_compliance.oman_compliance.overrides.sales_invoice import validate
from oman_compliance.tests import get_non_oman_test_company, get_oman_test_company, get_test_tax_account


class TestSalesInvoiceVatCategoryValidation(FrappeTestCase):
	def setUp(self):
		self.oman_company = get_oman_test_company()
		self.tax_account, _ = get_test_tax_account()

	def test_zero_rated_item_with_tax_charged_is_rejected(self):
		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[frappe._dict(idx=1, item_code="_Test Item", vat_category="Zero Rated")],
			taxes=[
				frappe._dict(
					account_head=self.tax_account,
					item_wise_tax_detail=json.dumps({"_Test Item": [5.0, 2.5]}),
				)
			],
		)

		with self.assertRaises(frappe.ValidationError):
			validate(doc)

	def test_zero_rated_item_with_non_vat_charge_is_not_rejected(self):
		# A Sales Taxes and Charges row can just as easily be an unrelated charge (freight,
		# discount, withholding, ...) that happens to have its own nonzero item-wise rate — that
		# must never be misread as VAT actually applied to a Zero Rated item.
		non_vat_account = frappe.db.get_value(
			"Account",
			{
				"company": get_test_tax_account()[1],
				"is_group": 0,
				"account_type": ["not in", list(VAT_BEARING_ACCOUNT_TYPES)],
			},
		)
		if not non_vat_account:
			self.skipTest("No non-VAT-bearing account available on this bench for this test.")

		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[frappe._dict(idx=1, item_code="_Test Item", vat_category="Zero Rated")],
			taxes=[
				frappe._dict(
					account_head=non_vat_account,
					item_wise_tax_detail=json.dumps({"_Test Item": [5.0, 2.5]}),
				)
			],
		)

		validate(doc)  # should not raise

	def test_zero_rated_item_with_no_tax_charged_is_accepted(self):
		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[frappe._dict(idx=1, item_code="_Test Item", vat_category="Zero Rated")],
			taxes=[
				frappe._dict(
					account_head=self.tax_account,
					item_wise_tax_detail=json.dumps({"_Test Item": [0.0, 0.0]}),
				)
			],
		)

		validate(doc)  # should not raise

		self.assertEqual(doc.get("items")[0].vat_category, "Zero Rated")

	def test_standard_rated_item_with_tax_charged_is_accepted(self):
		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[frappe._dict(idx=1, item_code="_Test Item", vat_category="Standard Rated")],
			taxes=[
				frappe._dict(
					account_head=self.tax_account,
					item_wise_tax_detail=json.dumps({"_Test Item": [5.0, 2.5]}),
				)
			],
		)

		validate(doc)  # should not raise

	def test_blank_category_is_defaulted_before_validation(self):
		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[frappe._dict(idx=1, item_code="_Test Item", vat_category=None)],
			taxes=[],
		)

		validate(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")

	def test_duplicate_item_code_with_mixed_categories_is_not_falsely_rejected(self):
		# item_wise_tax_detail is keyed by item_code, not row, so ERPNext can't tell these two
		# rows for the same item apart here — the merged rate must not block the invoice.
		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[
				frappe._dict(idx=1, item_code="_Test Item", vat_category="Standard Rated"),
				frappe._dict(idx=2, item_code="_Test Item", vat_category="Zero Rated"),
			],
			taxes=[
				frappe._dict(
					account_head=self.tax_account,
					item_wise_tax_detail=json.dumps({"_Test Item": [5.0, 2.5]}),
				)
			],
		)

		validate(doc)  # should not raise

	def test_unrelated_item_tax_does_not_affect_other_rows(self):
		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[frappe._dict(idx=1, item_code="_Test Zero Rated Item", vat_category="Zero Rated")],
			taxes=[
				frappe._dict(
					account_head=self.tax_account,
					item_wise_tax_detail=json.dumps({"_Test Other Item": [5.0, 2.5]}),
				)
			],
		)

		validate(doc)  # should not raise: the charged rate belongs to a different item

	def test_row_category_contradicting_its_item_tax_template_is_rejected(self):
		tax_account, template_company = get_test_tax_account()
		template = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test Template Exempt SI",
				"company": template_company,
				"taxes": [{"tax_type": tax_account, "tax_rate": 0}],
				"vat_category": "Exempt",
			}
		).insert()
		self.addCleanup(template.delete)

		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[
				frappe._dict(
					idx=1,
					item_code="_Test Item",
					vat_category="Standard Rated",
					item_tax_template=template.name,
				)
			],
			taxes=[],
		)

		with self.assertRaises(frappe.ValidationError):
			validate(doc)

	def test_row_category_matching_its_item_tax_template_is_accepted(self):
		tax_account, template_company = get_test_tax_account()
		template = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test Template Exempt SI Match",
				"company": template_company,
				"taxes": [{"tax_type": tax_account, "tax_rate": 0}],
				"vat_category": "Exempt",
			}
		).insert()
		self.addCleanup(template.delete)

		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[
				frappe._dict(
					idx=1, item_code="_Test Item", vat_category="Exempt", item_tax_template=template.name
				)
			],
			taxes=[],
		)

		validate(doc)  # should not raise

	def test_non_oman_company_is_not_validated_at_all(self):
		# This app must never block an unrelated company's invoice on a shared bench, even one
		# that would otherwise be a clear VAT Category/tax mismatch.
		doc = frappe._dict(
			company=get_non_oman_test_company(),
			customer_address=None,
			items=[frappe._dict(idx=1, item_code="_Test Item", vat_category="Zero Rated")],
			taxes=[
				frappe._dict(
					account_head=self.tax_account,
					item_wise_tax_detail=json.dumps({"_Test Item": [5.0, 2.5]}),
				)
			],
		)

		validate(doc)  # should not raise
