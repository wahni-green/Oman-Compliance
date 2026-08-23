import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.constants import VAT_BEARING_ACCOUNT_TYPES
from oman_compliance.oman_compliance.overrides.purchase_invoice import (
	set_import_of_goods_flag,
	validate,
	validate_reverse_charge,
)
from oman_compliance.tests import get_non_oman_test_company, get_oman_test_company, get_test_tax_account


class TestPurchaseInvoiceReverseCharge(FrappeTestCase):
	def test_reverse_charge_without_tax_rows_is_rejected(self):
		doc = frappe._dict(is_reverse_charge=1, taxes=[], items=[frappe._dict(vat_category=None)])

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_add_and_deduct_rows_is_accepted(self):
		tax_account, _ = get_test_tax_account()
		doc = frappe._dict(
			is_reverse_charge=1,
			taxes=[
				frappe._dict(account_head=tax_account, rate=5, add_deduct_tax="Add"),
				frappe._dict(account_head=tax_account, rate=5, add_deduct_tax="Deduct"),
			],
			items=[frappe._dict(vat_category=None)],
		)

		validate_reverse_charge(doc)  # should not raise

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")

	def test_reverse_charge_with_only_an_add_row_is_rejected(self):
		# A single "Add" VAT row is exactly what an ordinary domestic purchase's plain input VAT
		# looks like — not proof that reverse charge was actually self-accounted (both an output
		# liability "Add" row and an offsetting input-credit "Deduct" row are required).
		tax_account, _ = get_test_tax_account()
		doc = frappe._dict(
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=tax_account, rate=5, add_deduct_tax="Add")],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_only_a_deduct_row_is_rejected(self):
		tax_account, _ = get_test_tax_account()
		doc = frappe._dict(
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=tax_account, rate=5, add_deduct_tax="Deduct")],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_only_unrelated_tax_row_is_rejected(self):
		# A nonempty Taxes and Charges table isn't proof of anything by itself — a row with no
		# account_head at all (or one that isn't VAT-bearing) must still be rejected.
		doc = frappe._dict(
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=None, rate=5)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_only_a_non_vat_charge_row_is_rejected(self):
		# Distinct from the "no account_head at all" case above: this is a real charge row
		# (freight, discount, withholding, ...) posted to a genuine account that just isn't a
		# VAT-bearing type — must still be rejected as not satisfying self-accounting.
		_, template_company = get_test_tax_account()
		non_vat_account = frappe.db.get_value(
			"Account",
			{
				"company": template_company,
				"is_group": 0,
				"account_type": ["not in", list(VAT_BEARING_ACCOUNT_TYPES)],
			},
		)
		if not non_vat_account:
			self.skipTest("No non-VAT-bearing account available on this bench for this test.")

		doc = frappe._dict(
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=non_vat_account, rate=5)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_zero_rate_vat_row_is_rejected(self):
		tax_account, _ = get_test_tax_account()
		doc = frappe._dict(
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=tax_account, rate=0, tax_amount=0)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_non_reverse_charge_purchase_is_unaffected_by_missing_tax_rows(self):
		doc = frappe._dict(is_reverse_charge=0, taxes=[], items=[frappe._dict(vat_category=None)])

		validate_reverse_charge(doc)  # should not raise

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")

	def test_existing_category_is_not_overwritten(self):
		doc = frappe._dict(is_reverse_charge=0, taxes=[], items=[frappe._dict(vat_category="Exempt")])

		validate_reverse_charge(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Exempt")

	def test_item_tax_template_category_is_used_over_standard_rated_default(self):
		tax_account, company = get_test_tax_account()
		template = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test Template Exempt PI",
				"company": company,
				"taxes": [{"tax_type": tax_account, "tax_rate": 0}],
				"vat_category": "Exempt",
			}
		).insert()
		self.addCleanup(template.delete)

		doc = frappe._dict(
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
		# Reverse Charge would otherwise reject this (checked, but no tax rows) — must not fire
		# at all for an unrelated company on a shared bench.
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
