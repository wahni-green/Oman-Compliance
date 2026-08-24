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
	set_vat_accounts,
)


class TestPurchaseInvoiceReverseCharge(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, template_company = get_test_tax_account()
		self.input_account = frappe.db.get_value(
			"Account", {"name": ["!=", self.output_account], "is_group": 0, "company": template_company}
		)
		if not self.input_account:
			self.skipTest("No second account available on this bench for this test.")

	def test_reverse_charge_without_any_vat_accounts_configured_is_rejected(self):
		doc = frappe._dict(
			company=self.company, is_reverse_charge=1, taxes=[], items=[frappe._dict(vat_category=None)]
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_only_output_account_configured_is_rejected(self):
		set_vat_accounts(self.company, output_account=self.output_account)  # input left unset

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=self.output_account, rate=5)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_output_and_input_rows_is_accepted(self):
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[
				frappe._dict(account_head=self.output_account, rate=5),
				frappe._dict(account_head=self.input_account, rate=5),
			],
			items=[frappe._dict(vat_category=None)],
		)

		validate_reverse_charge(doc)  # should not raise

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")

	def test_reverse_charge_with_only_output_row_is_rejected(self):
		# Both accounts configured, but the invoice itself is missing the offsetting input VAT
		# credit row — only recording the output liability isn't complete self-accounting.
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=self.output_account, rate=5)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_only_input_row_is_rejected(self):
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=self.input_account, rate=5)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_only_unrelated_tax_rows_is_rejected(self):
		# Configured, but the invoice's tax rows post somewhere else entirely — a nonempty Taxes
		# and Charges table isn't proof of anything by itself.
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[frappe._dict(account_head=None, rate=5)],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_a_different_companys_vat_accounts_is_rejected(self):
		# The accounts posted to are *someone else's* configured VAT Accounts, not this invoice's
		# own company's ones — must not be accepted just because they're valid VAT Accounts for
		# some company.
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)

		other_company = get_non_oman_test_company()
		other_accounts = frappe.get_all(
			"Account",
			filters={"name": ["not in", [self.output_account, self.input_account]], "is_group": 0},
			pluck="name",
			limit=2,
		)
		if len(other_accounts) < 2:
			self.skipTest("Not enough distinct accounts available on this bench for this test.")
		set_vat_accounts(other_company, output_account=other_accounts[0], input_account=other_accounts[1])

		# Invoice belongs to other_company, but its tax rows post to self.company's accounts.
		doc = frappe._dict(
			company=other_company,
			is_reverse_charge=1,
			taxes=[
				frappe._dict(account_head=self.output_account, rate=5),
				frappe._dict(account_head=self.input_account, rate=5),
			],
			items=[frappe._dict(vat_category=None)],
		)

		with self.assertRaises(frappe.ValidationError):
			validate_reverse_charge(doc)

	def test_reverse_charge_with_zero_rate_vat_rows_is_rejected(self):
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)

		doc = frappe._dict(
			company=self.company,
			is_reverse_charge=1,
			taxes=[
				frappe._dict(account_head=self.output_account, rate=0, tax_amount=0),
				frappe._dict(account_head=self.input_account, rate=0, tax_amount=0),
			],
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
