import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.tests import (
	create_submitted_sales_invoice,
	get_oman_test_company,
	get_oman_test_vat_accounts,
	set_simplified_tax_invoice_threshold,
	set_vat_accounts,
)


class TestTaxInvoicePrintFormats(FrappeTestCase):
	"""Rendering smoke tests (Phase 4 checklist) — confirms both Jinja print formats actually
	render without error against a real submitted Sales Invoice, and that "Oman Tax Invoice"
	auto-switches its heading/layout based on the threshold-switch flag computed in
	overrides/sales_invoice.py::set_simplified_tax_invoice_flag, while "Oman Simplified Tax
	Invoice" always renders the simplified layout regardless of that flag."""

	def setUp(self):
		self.company = get_oman_test_company()
		frappe.db.set_value("Company", self.company, "oman_trn", "OM1234567890")
		set_simplified_tax_invoice_threshold(500)

	def test_oman_tax_invoice_renders_full_layout_above_threshold(self):
		invoice = create_submitted_sales_invoice(self.company, net_amount=1000)
		self.assertFalse(invoice.is_simplified_tax_invoice)

		html = frappe.get_print("Sales Invoice", invoice.name, print_format="Oman Tax Invoice")

		self.assertIn("<h1>Tax Invoice</h1>", html)
		self.assertNotIn("<h1>Simplified Tax Invoice</h1>", html)

	def test_oman_tax_invoice_auto_switches_to_simplified_layout_below_threshold(self):
		invoice = create_submitted_sales_invoice(self.company, net_amount=100)
		self.assertTrue(invoice.is_simplified_tax_invoice)

		html = frappe.get_print("Sales Invoice", invoice.name, print_format="Oman Tax Invoice")

		self.assertIn("<h1>Simplified Tax Invoice</h1>", html)

	def test_oman_simplified_tax_invoice_always_renders_simplified_layout(self):
		# net_amount is well above the threshold, so the auto-switching flag would be False — this
		# standalone format must still always render the simplified layout regardless.
		invoice = create_submitted_sales_invoice(self.company, net_amount=1000)
		self.assertFalse(invoice.is_simplified_tax_invoice)

		html = frappe.get_print("Sales Invoice", invoice.name, print_format="Oman Simplified Tax Invoice")

		self.assertIn("<h1>Simplified Tax Invoice</h1>", html)

	def test_missing_supplier_address_shows_a_visible_warning(self):
		# The fixture never sets a company_address, matching a real Company with no default
		# address configured yet — the OTA requires a supplier address on every Tax Invoice, so
		# this must be an unmissable warning rather than a silently blank line (CodeRabbit review).
		invoice = create_submitted_sales_invoice(self.company, net_amount=1000)

		html = frappe.get_print("Sales Invoice", invoice.name, print_format="Oman Tax Invoice")

		self.assertIn("Supplier address missing", html)

	def test_missing_customer_address_shows_a_visible_warning_on_full_layout(self):
		invoice = create_submitted_sales_invoice(self.company, net_amount=1000)
		self.assertFalse(invoice.is_simplified_tax_invoice)

		html = frappe.get_print("Sales Invoice", invoice.name, print_format="Oman Tax Invoice")

		self.assertIn("Customer address missing", html)

	def test_item_vat_rate_is_rendered(self):
		output_account, _ = get_oman_test_vat_accounts(self.company)
		set_vat_accounts(self.company, output_account=output_account)
		invoice = create_submitted_sales_invoice(
			self.company, net_amount=1000, output_vat_account=output_account, rate=5
		)

		html = frappe.get_print("Sales Invoice", invoice.name, print_format="Oman Tax Invoice")

		self.assertIn("5%", html)
