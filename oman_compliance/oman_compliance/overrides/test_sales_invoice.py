import json

import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.overrides.sales_invoice import set_export_flag, validate
from oman_compliance.tests import (
	get_non_oman_test_company,
	get_oman_test_company,
	get_test_tax_account,
	set_vat_accounts,
)


class TestSetExportFlag(FrappeTestCase):
	def setUp(self):
		self.oman_company = get_oman_test_company()

	def test_blank_addresses_are_not_an_export(self):
		doc = frappe._dict(
			company=self.oman_company, shipping_address_name=None, customer_address=None, is_export=0
		)

		set_export_flag(doc)

		self.assertFalse(doc.is_export)

	def test_foreign_shipping_address_is_an_export(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Foreign Shipping Address",
				"address_type": "Shipping",
				"address_line1": "Somewhere Abroad",
				"city": "Dubai",
				"country": "United Arab Emirates",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(
			company=self.oman_company,
			shipping_address_name=address.name,
			customer_address=None,
			is_export=0,
		)

		set_export_flag(doc)

		self.assertTrue(doc.is_export)

	def test_domestic_shipping_address_is_not_an_export(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Domestic Shipping Address",
				"address_type": "Shipping",
				"address_line1": "Muscat",
				"city": "Muscat",
				"country": "Oman",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(
			company=self.oman_company,
			shipping_address_name=address.name,
			customer_address=None,
			is_export=0,
		)

		set_export_flag(doc)

		self.assertFalse(doc.is_export)

	def test_customer_address_is_the_fallback_when_shipping_is_blank(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Foreign Customer Address",
				"address_type": "Billing",
				"address_line1": "Somewhere Abroad",
				"city": "Dubai",
				"country": "United Arab Emirates",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(
			company=self.oman_company, shipping_address_name=None, customer_address=address.name, is_export=0
		)

		set_export_flag(doc)

		self.assertTrue(doc.is_export)

	def test_shipping_address_takes_priority_over_customer_address(self):
		domestic_shipping = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Priority Domestic Shipping Address",
				"address_type": "Shipping",
				"address_line1": "Muscat",
				"city": "Muscat",
				"country": "Oman",
			}
		).insert()
		self.addCleanup(domestic_shipping.delete)
		foreign_customer = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Priority Foreign Customer Address",
				"address_type": "Billing",
				"address_line1": "Somewhere Abroad",
				"city": "Dubai",
				"country": "United Arab Emirates",
			}
		).insert()
		self.addCleanup(foreign_customer.delete)

		doc = frappe._dict(
			company=self.oman_company,
			shipping_address_name=domestic_shipping.name,
			customer_address=foreign_customer.name,
			is_export=0,
		)

		set_export_flag(doc)

		self.assertFalse(doc.is_export)

	def test_changing_to_export_notifies_the_user(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Foreign Shipping Address Notify",
				"address_type": "Shipping",
				"address_line1": "Somewhere Abroad",
				"city": "Dubai",
				"country": "United Arab Emirates",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(
			company=self.oman_company,
			shipping_address_name=address.name,
			customer_address=None,
			is_export=0,
		)

		frappe.message_log.clear()
		set_export_flag(doc)

		self.assertTrue(doc.is_export)
		self.assertTrue(frappe.get_message_log())

	def test_unchanged_value_does_not_notify(self):
		doc = frappe._dict(
			company=self.oman_company, shipping_address_name=None, customer_address=None, is_export=0
		)

		frappe.message_log.clear()
		set_export_flag(doc)

		self.assertFalse(doc.is_export)
		self.assertFalse(frappe.get_message_log())


class TestSalesInvoiceVatCategoryValidation(FrappeTestCase):
	def setUp(self):
		self.oman_company = get_oman_test_company()
		self.tax_account, _ = get_test_tax_account()
		set_vat_accounts(self.oman_company, output_account=self.tax_account)

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
		# discount, withholding, ...) posted to some other account entirely, with its own nonzero
		# item-wise rate — that must never be misread as VAT actually applied to a Zero Rated item.
		non_vat_account = frappe.db.get_value("Account", {"name": ["!=", self.tax_account], "is_group": 0})
		if not non_vat_account:
			self.skipTest("No second account available on this bench for this test.")

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

	def test_zero_rated_item_is_not_rejected_when_output_vat_account_is_unconfigured(self):
		# Without a configured Output VAT Account, nothing can be identified as VAT at all — the
		# mismatch check must not fire (rather than falling back to a guess).
		other_company = get_non_oman_test_company()  # guaranteed to have no vat_accounts row
		doc = frappe._dict(
			company=self.oman_company,
			customer_address=None,
			items=[frappe._dict(idx=1, item_code="_Test Item", vat_category="Zero Rated")],
			taxes=[
				frappe._dict(
					account_head=other_company,  # not a real account; irrelevant, never matched
					item_wise_tax_detail=json.dumps({"_Test Item": [5.0, 2.5]}),
				)
			],
		)

		# Reset this company's configuration for this test only.
		settings = frappe.get_single("Oman VAT Settings")
		settings.vat_accounts = [row for row in settings.vat_accounts if row.company != self.oman_company]
		settings.save(ignore_permissions=True)

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
		self.assertIsNone(doc.get("is_export"))
