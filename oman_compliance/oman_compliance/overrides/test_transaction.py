import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.overrides.transaction import set_vat_category_defaults
from oman_compliance.tests import get_non_oman_test_company, get_oman_test_company, get_test_tax_account


class TestSetVatCategoryDefaults(FrappeTestCase):
	def setUp(self):
		self.oman_company = get_oman_test_company()

	def test_blank_category_defaults_to_standard_rated(self):
		doc = frappe._dict(
			company=self.oman_company, customer_address=None, items=[frappe._dict(vat_category=None)]
		)

		set_vat_category_defaults(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")

	def test_existing_category_is_not_overwritten(self):
		doc = frappe._dict(
			company=self.oman_company, customer_address=None, items=[frappe._dict(vat_category="Exempt")]
		)

		set_vat_category_defaults(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Exempt")

	def test_non_oman_company_is_left_untouched(self):
		# This app must never touch an unrelated company's transactions on a shared bench.
		doc = frappe._dict(
			company=get_non_oman_test_company(),
			customer_address=None,
			items=[frappe._dict(vat_category=None)],
		)

		set_vat_category_defaults(doc)

		self.assertIsNone(doc.get("items")[0].vat_category)

	def test_blank_company_is_left_untouched(self):
		doc = frappe._dict(company=None, customer_address=None, items=[frappe._dict(vat_category=None)])

		set_vat_category_defaults(doc)

		self.assertIsNone(doc.get("items")[0].vat_category)

	def test_designated_zone_address_defaults_to_zero_rated(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Duqm Address",
				"address_type": "Shipping",
				"address_line1": "Duqm SEZAD",
				"city": "Duqm",
				"country": "Oman",
				"designated_zone": "Duqm",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(
			company=self.oman_company,
			customer_address=address.name,
			items=[frappe._dict(vat_category=None)],
		)

		set_vat_category_defaults(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Zero Rated")

	def test_zone_shipping_address_is_caught_even_with_a_non_zone_billing_address(self):
		billing_address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Muscat Billing Address",
				"address_type": "Billing",
				"address_line1": "Muscat",
				"city": "Muscat",
				"country": "Oman",
			}
		).insert()
		self.addCleanup(billing_address.delete)

		shipping_address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Duqm Shipping Address",
				"address_type": "Shipping",
				"address_line1": "Duqm SEZAD",
				"city": "Duqm",
				"country": "Oman",
				"designated_zone": "Duqm",
			}
		).insert()
		self.addCleanup(shipping_address.delete)

		doc = frappe._dict(
			company=self.oman_company,
			customer_address=billing_address.name,
			shipping_address_name=shipping_address.name,
			items=[frappe._dict(vat_category=None)],
		)

		set_vat_category_defaults(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Zero Rated")

	def test_zone_dispatch_address_is_caught_with_non_zone_customer_addresses(self):
		# "Supply out of a zone": the company's own warehouse/dispatch address for this
		# transaction is the zone-linked one, not the customer's billing/shipping address.
		customer_address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Muscat Customer Address",
				"address_type": "Billing",
				"address_line1": "Muscat",
				"city": "Muscat",
				"country": "Oman",
			}
		).insert()
		self.addCleanup(customer_address.delete)

		dispatch_address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Duqm Dispatch Address",
				"address_type": "Shipping",
				"address_line1": "Duqm SEZAD Warehouse",
				"city": "Duqm",
				"country": "Oman",
				"designated_zone": "Duqm",
			}
		).insert()
		self.addCleanup(dispatch_address.delete)

		doc = frappe._dict(
			company=self.oman_company,
			customer_address=customer_address.name,
			shipping_address_name=customer_address.name,
			dispatch_address_name=dispatch_address.name,
			items=[frappe._dict(vat_category=None)],
		)

		set_vat_category_defaults(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Zero Rated")

	def test_deactivated_zone_no_longer_defaults_to_zero_rated(self):
		frappe.db.set_value("Designated Zone", "Duqm", "is_active", 0)
		self.addCleanup(frappe.db.set_value, "Designated Zone", "Duqm", "is_active", 1)

		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Deactivated Zone Address",
				"address_type": "Shipping",
				"address_line1": "Duqm SEZAD",
				"city": "Duqm",
				"country": "Oman",
				"designated_zone": "Duqm",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(
			company=self.oman_company,
			customer_address=address.name,
			items=[frappe._dict(vat_category=None)],
		)

		set_vat_category_defaults(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")

	def test_non_zone_address_defaults_to_standard_rated(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Muscat Address",
				"address_type": "Shipping",
				"address_line1": "Muscat",
				"city": "Muscat",
				"country": "Oman",
			}
		).insert()
		self.addCleanup(address.delete)

		doc = frappe._dict(
			company=self.oman_company,
			customer_address=address.name,
			items=[frappe._dict(vat_category=None)],
		)

		set_vat_category_defaults(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Standard Rated")

	def test_item_tax_template_category_wins_over_zone_default(self):
		# The zone signal on the address would normally suggest Zero Rated, but an explicit
		# category on the row's own Item Tax Template is a stronger signal and takes priority.
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Duqm Address For Template Priority",
				"address_type": "Shipping",
				"address_line1": "Duqm SEZAD",
				"city": "Duqm",
				"country": "Oman",
				"designated_zone": "Duqm",
			}
		).insert()
		self.addCleanup(address.delete)

		tax_account, template_company = get_test_tax_account()
		template = frappe.get_doc(
			{
				"doctype": "Item Tax Template",
				"title": "_Test Template Exempt Priority",
				"company": template_company,
				"taxes": [{"tax_type": tax_account, "tax_rate": 0}],
				"vat_category": "Exempt",
			}
		).insert()
		self.addCleanup(template.delete)

		doc = frappe._dict(
			company=self.oman_company,
			customer_address=address.name,
			items=[frappe._dict(vat_category=None, item_tax_template=template.name)],
		)

		set_vat_category_defaults(doc)

		self.assertEqual(doc.get("items")[0].vat_category, "Exempt")
