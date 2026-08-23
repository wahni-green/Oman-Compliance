import frappe
from frappe.tests.utils import FrappeTestCase


class TestOmanVATSettings(FrappeTestCase):
	def test_default_thresholds(self):
		settings = frappe.get_single("Oman VAT Settings")
		self.assertEqual(settings.simplified_tax_invoice_threshold, 500)
		self.assertEqual(settings.mandatory_registration_threshold, 38500)
		self.assertEqual(settings.voluntary_registration_threshold, 19250)
		self.assertEqual(settings.settings_currency, "OMR")
