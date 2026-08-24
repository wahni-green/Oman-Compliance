import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.overrides.purchase_invoice import (
	set_import_of_goods_flag,
	validate,
	validate_reverse_charge,
)
from oman_compliance.tests import (
	get_non_oman_test_company,
	get_oman_test_company,
	get_test_tax_account,
	set_output_vat_account,
)


class TestPurchaseInvoiceReverseCharge(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()

	def test_reverse_charge_without_output_vat_account_configured_is_rejected(self):
		doc = frappe._dict(
			company=self.company, is_reverse_charge=1, taxes=[], items=[frappe._dict(vat_category=None)]
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_output_vat_account_row_is_accepted(self):
		tax_account, _ = get_test_tax_account()
		set_output_vat_account(self.company, tax_account)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=tax_account, rate=5)],
			items=[frappe._dict(vat_category=None)],
		)

		validate_reverse_charge(doc)  # should not raise

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")

	def test_reverse_charge_with_only_unrelated_tax_row_is_rejected(self):
		# Configured, but the invoice's tax row posts somewhere else entirely — a nonempty Taxes
		# and Charges table isn't proof of anything by itself.
		tax_account, _ = get_test_tax_account()
		set_output_vat_account(self.company, tax_account)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=None, rate=5)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_a_different_companys_output_vat_account_is_rejected(self):
		# The account posted to is *someone else's* configured Output VAT Account, not this
		# company's own one — must not be accepted just because it's an Output VAT Account for
		# some company.
		tax_account, other_company = get_test_tax_account()
		set_output_vat_account(other_company, tax_account)

		this_companys_account = frappe.db.get_value("Account", {"name": ["!=", tax_account], "is_group": 0})
		if not this_companys_account:
			self.skipTest("No second account available on this bench for this test.")
		set_output_vat_account(self.company, this_companys_account)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=tax_account, rate=5)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_zero_rate_vat_row_is_rejected(self):
		tax_account, _ = get_test_tax_account()
		set_output_vat_account(self.company, tax_account)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=tax_account, rate=0, tax_amount=0)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_non_reverse_charge_purchase_is_unaffected_by_missing_tax_rows(self):
		doc = frappe._dict(
			company=self.company, is_reverse_charge=0, taxes=[], items=[frappe._dict(vat_category=None)]
		)

		validate_reverse_charge(doc)  # should not raise

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")

	def test_existing_category_is_not_overwritten(self):
		doc = frappe._dict(
			company=self.company, is_reverse_charge=0, taxes=[], items=[frappe._dict(vat_category="Exempt")]
		)

		validate_reverse_charge(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Exempt")

	def test_item_tax_template_category_is_used_over_standard_rated_default(self):
		tax_account, template_company = get_test_tax_account()
		template = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test Template Exempt PI",
				"company": template_company,
				"taxes": [{"tax_type": tax_account, "tax_rate": 0}],
				"vat_category": "Exempt",
			}
		).insert()
		self.addCleanup(template.delete)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=0,
			taxes=[],
			items=[frappe._dict(vat_category=None, item_tax_template=template.name)],
		)

		validate_reverse_charge(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Exempt")


class TestPurchaseInvoiceValidateGating(FrappeTestCase):
	def setUp(self):
		self.oman_company = get_oman_test_company()

	def test_non_oman_company_is_left_completely_untouched(self):
		# Reverse Charge would otherwise reject this (checked, but no Output VAT Account
		# configured) — must not fire at all for an unrelated company on a shared bench.
		doc = frappe._dict(
			company=get_non_oman_test_company(),
			is_reverse_charge=1,
			taxes=[],
			items=[frappe._dict(vat_category=None)],
		)

		validate(doc)  # should not raise

		self.assertIsNone(doc.get("items")[0].vat_category)

	def test_oman_company_runs_both_reverse_charge_and_import_checks(self):
		doc = frappe._dict(
			company=self.oman_company,
			is_reverse_charge=0,
			taxes=[],
			items=[frappe._dict(vat_category=None)],
			dispatch_address=None,
		)

		validate(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")
		self.assertFalse(doc.is_import_of_goods)


class TestSetImportOfGoodsFlag(FrappeTestCase):
	def setUp(self):
		self.oman_company = get_oman_test_company()

	def test_blank_dispatch_address_is_not_an_import(self):
		doc = frappe._dict(company=self.oman_company, dispatch_address=None, is_import_of_goods=0)

		set_import_of_goods_flag(doc)

		self.assertFalse(doc.is_import_of_goods)

	def test_foreign_dispatch_address_is_an_import(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Foreign Dispatch Address",
				"address_type": "Shipping",
				"address_line1": "Somewhere Abroad",
				"city": "Dubai",
				"country": "United Arab Emirates",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(company=self.oman_company, dispatch_address=address.name, is_import_of_goods=0)

		set_import_of_goods_flag(doc)

		self.assertTrue(doc.is_import_of_goods)

	def test_domestic_dispatch_address_is_not_an_import(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Domestic Dispatch Address",
				"address_type": "Shipping",
				"address_line1": "Muscat",
				"city": "Muscat",
				"country": "Oman",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(company=self.oman_company, dispatch_address=address.name, is_import_of_goods=0)

		set_import_of_goods_flag(doc)

		self.assertFalse(doc.is_import_of_goods)

	def test_changing_to_import_notifies_the_user(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Foreign Dispatch Address Notify",
				"address_type": "Shipping",
				"address_line1": "Somewhere Abroad",
				"city": "Dubai",
				"country": "United Arab Emirates",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(company=self.oman_company, dispatch_address=address.name, is_import_of_goods=0)

		frappe.message_log.clear()
		set_import_of_goods_flag(doc)

		self.assertTrue(doc.is_import_of_goods)
		self.assertTrue(frappe.get_message_log())

	def test_unchanged_value_does_not_notify(self):
		doc = frappe._dict(company=self.oman_company, dispatch_address=None, is_import_of_goods=0)

		frappe.message_log.clear()
		set_import_of_goods_flag(doc)

		self.assertFalse(doc.is_import_of_goods)
		self.assertFalse(frappe.get_message_log())
