import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.trn import validate_trn


class TestValidateTrn(FrappeTestCase):
	def test_valid_trn_is_normalized(self):
		self.assertEqual(validate_trn("om1234567890"), "OM1234567890")

	def test_invalid_trn_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			validate_trn("INVALID")

	def test_blank_trn_is_allowed(self):
		self.assertIsNone(validate_trn(None))
		self.assertEqual(validate_trn(""), "")
