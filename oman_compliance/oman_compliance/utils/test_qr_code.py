import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.qr_code import get_tax_invoice_qr_code
from oman_compliance.tests import get_oman_test_company


class TestGetTaxInvoiceQrCode(FrappeTestCase):
	def test_returns_a_png_data_uri_when_company_trn_is_set(self):
		company = get_oman_test_company()
		frappe.db.set_value("Company", company, "oman_trn", "OM1234567890")

		doc = frappe._dict(
			company=company,
			name="_Test SINV-0001",
			posting_date="2026-01-01",
			grand_total=105,
			total_taxes_and_charges=5,
			currency="OMR",
		)

		qr_code = get_tax_invoice_qr_code(doc)

		self.assertIsNotNone(qr_code)
		self.assertTrue(qr_code.startswith("data:image/png;base64,"))

	def test_returns_none_when_company_has_no_trn(self):
		company = get_oman_test_company()
		frappe.db.set_value("Company", company, "oman_trn", None)

		doc = frappe._dict(company=company, name="_Test SINV-0002")

		self.assertIsNone(get_tax_invoice_qr_code(doc))

	def test_returns_none_when_company_is_blank(self):
		doc = frappe._dict(company=None, name="_Test SINV-0003")

		self.assertIsNone(get_tax_invoice_qr_code(doc))
