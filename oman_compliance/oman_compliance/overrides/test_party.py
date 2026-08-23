import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.overrides.party import validate_trn


class TestPartyTRNValidation(FrappeTestCase):
	def test_valid_trn_is_normalized_for_customer(self):
		doc = frappe._dict(doctype="Customer", oman_trn="om1234567890")

		validate_trn(doc)

		self.assertEqual(doc.oman_trn, "OM1234567890")

	def test_invalid_trn_is_rejected_for_supplier(self):
		doc = frappe._dict(doctype="Supplier", oman_trn="123")

		with self.assertRaises(frappe.ValidationError):
			validate_trn(doc)

	def test_empty_trn_is_allowed(self):
		doc = frappe._dict(doctype="Customer", oman_trn=None)

		validate_trn(doc)

		self.assertIsNone(doc.oman_trn)
