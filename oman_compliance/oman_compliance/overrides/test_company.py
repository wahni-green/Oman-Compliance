import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.overrides.company import validate


class TestCompanyTRNValidation(FrappeTestCase):
	def test_valid_trn_is_normalized(self):
		doc = frappe._dict(oman_trn="om1234567890")

		validate(doc)

		self.assertEqual(doc.oman_trn, "OM1234567890")

	def test_invalid_trn_is_rejected(self):
		doc = frappe._dict(oman_trn="NOT-A-TRN")

		with self.assertRaises(frappe.ValidationError):
			validate(doc)

	def test_empty_trn_is_allowed(self):
		doc = frappe._dict(oman_trn=None)

		validate(doc)

		self.assertIsNone(doc.oman_trn)
