import json

import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.overrides.sales_invoice import (
	set_export_flag,
	set_simplified_tax_invoice_flag,
	validate,
	validate_no_mixed_vat_category_per_item_code,
	validate_vat_category_tax_consistency,
)
from oman_compliance.tests import (
	get_non_oman_test_company,
	get_oman_test_company,
	get_or_create_test_customer,
	get_test_tax_account,
	set_simplified_tax_invoice_threshold,
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


class TestSetSimplifiedTaxInvoiceFlag(FrappeTestCase):
	def setUp(self):
		self.oman_company = get_oman_test_company()
		set_simplified_tax_invoice_threshold(500)
		self.non_taxable_customer = get_or_create_test_customer(self.oman_company)
		self.taxable_customer = get_or_create_test_customer(self.oman_company)
		frappe.db.set_value("Customer", self.taxable_customer, "oman_trn", "OM1234567890")

	def test_below_threshold_and_non_taxable_customer_is_simplified(self):
		doc = frappe._dict(
			company=self.oman_company,
			customer=self.non_taxable_customer,
			base_net_total=100,
			is_simplified_tax_invoice=0,
		)

		set_simplified_tax_invoice_flag(doc)

		self.assertTrue(doc.is_simplified_tax_invoice)

	def test_below_threshold_but_taxable_customer_is_not_simplified(self):
		# A registered (TRN-bearing) customer is a B2B supply, not the non-taxable-consumer case
		# OTA's Simplified Tax Invoice allowance is for, regardless of amount.
		doc = frappe._dict(
			company=self.oman_company,
			customer=self.taxable_customer,
			base_net_total=100,
			is_simplified_tax_invoice=0,
		)

		set_simplified_tax_invoice_flag(doc)

		self.assertFalse(doc.is_simplified_tax_invoice)

	def test_at_or_above_threshold_is_not_simplified(self):
		doc = frappe._dict(
			company=self.oman_company,
			customer=self.non_taxable_customer,
			base_net_total=500,
			is_simplified_tax_invoice=0,
		)

		set_simplified_tax_invoice_flag(doc)

		self.assertFalse(doc.is_simplified_tax_invoice)

	def test_blank_customer_is_not_simplified(self):
		doc = frappe._dict(
			company=self.oman_company, customer=None, base_net_total=100, is_simplified_tax_invoice=0
		)

		set_simplified_tax_invoice_flag(doc)

		self.assertFalse(doc.is_simplified_tax_invoice)

	def test_threshold_is_read_from_settings_not_hardcoded(self):
		set_simplified_tax_invoice_threshold(50)
		doc = frappe._dict(
			company=self.oman_company,
			customer=self.non_taxable_customer,
			base_net_total=100,
			is_simplified_tax_invoice=0,
		)

		set_simplified_tax_invoice_flag(doc)

		self.assertFalse(doc.is_simplified_tax_invoice)

	def test_changing_to_simplified_notifies_the_user(self):
		doc = frappe._dict(
			company=self.oman_company,
			customer=self.non_taxable_customer,
			base_net_total=100,
			is_simplified_tax_invoice=0,
		)

		frappe.message_log.clear()
		set_simplified_tax_invoice_flag(doc)

		self.assertTrue(doc.is_simplified_tax_invoice)
		self.assertTrue(frappe.get_message_log())

	def test_unchanged_value_does_not_notify(self):
		doc = frappe._dict(
			company=self.oman_company,
			customer=self.taxable_customer,
			base_net_total=100,
			is_simplified_tax_invoice=0,
		)

		frappe.message_log.clear()
		set_simplified_tax_invoice_flag(doc)

		self.assertFalse(doc.is_simplified_tax_invoice)
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

	def test_duplicate_item_code_with_mixed_categories_does_not_falsely_trip_the_rate_check(self):
		# item_wise_tax_detail is keyed by item_code, not row, so ERPNext can't tell these two
		# rows for the same item apart here — validate_vat_category_tax_consistency's own
		# rate-based check must not misfire against one of a legitimately mixed set (that's a
		# separate concern from whether the mismatch itself is allowed at all — see
		# validate_no_mixed_vat_category_per_item_code below, which is what actually blocks it).
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

		validate_vat_category_tax_consistency(doc)  # should not raise

	def test_duplicate_item_code_with_mixed_categories_is_rejected(self):
		# item_wise_tax_detail is keyed by item_code, not row: once merged, there is no way to
		# recover which row a combined VAT amount actually belongs to (ERPNext's own
		# taxes_and_totals.py only preserves the last-processed row's rate) — blocked outright
		# rather than risking a wrong figure in a later VAT return/register.
		doc = frappe._dict(
			items=[
				frappe._dict(idx=1, item_code="_Test Item", vat_category="Standard Rated"),
				frappe._dict(idx=2, item_code="_Test Item", vat_category="Zero Rated"),
			],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_no_mixed_vat_category_per_item_code(doc)

	def test_duplicate_item_code_with_the_same_category_is_accepted(self):
		doc = frappe._dict(
			items=[
				frappe._dict(idx=1, item_code="_Test Item", vat_category="Standard Rated"),
				frappe._dict(idx=2, item_code="_Test Item", vat_category="Standard Rated"),
			],
		)

		validate_no_mixed_vat_category_per_item_code(doc)  # should not raise

	def test_duplicate_item_code_with_same_category_but_different_template_is_rejected(self):
		# Category alone isn't a strong enough signal that two rows were actually taxed
		# identically — two "Standard Rated" rows could use different Item Tax Templates
		# configured with different rates, which a category-only check would miss entirely.
		doc = frappe._dict(
			items=[
				frappe._dict(
					idx=1,
					item_code="_Test Item",
					vat_category="Standard Rated",
					item_tax_template="Template A",
				),
				frappe._dict(
					idx=2,
					item_code="_Test Item",
					vat_category="Standard Rated",
					item_tax_template="Template B",
				),
			],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_no_mixed_vat_category_per_item_code(doc)

	def test_duplicate_item_code_with_the_same_category_and_template_is_accepted(self):
		doc = frappe._dict(
			items=[
				frappe._dict(
					idx=1,
					item_code="_Test Item",
					vat_category="Standard Rated",
					item_tax_template="Template A",
				),
				frappe._dict(
					idx=2,
					item_code="_Test Item",
					vat_category="Standard Rated",
					item_tax_template="Template A",
				),
			],
		)

		validate_no_mixed_vat_category_per_item_code(doc)  # should not raise

	def test_full_validate_rejects_a_mixed_category_duplicate_item_code(self):
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

		with self.assertRaises(frappe.ValidationError):
			validate(doc)

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
