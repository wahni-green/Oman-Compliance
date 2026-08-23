import frappe
from frappe.tests.utils import FrappeTestCase


class TestTRN(FrappeTestCase):
	def test_valid_trn_is_normalized_and_timestamped(self):
		doc = frappe.get_doc({"doctype": "TRN", "trn": "om1234567890"}).insert()
		self.assertEqual(doc.trn, "OM1234567890")
		self.assertTrue(doc.last_validated_on)

	def test_invalid_trn_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc({"doctype": "TRN", "trn": "INVALID"}).insert()

	def test_rename_is_normalized(self):
		# Renaming (e.g. via the Desk rename dialog) bypasses before_naming entirely, so
		# before_rename() is TRN's only chance to validate/normalize a new name — test it
		# directly rather than through a real frappe.rename_doc() call, since that commits
		# mid-operation and breaks the per-test rollback isolation FrappeTestCase relies on.
		doc = frappe.get_doc({"doctype": "TRN", "trn": "OM1234567890"})

		self.assertEqual(doc.before_rename("OM1234567890", "om9876543210"), "OM9876543210")

	def test_rename_to_invalid_format_is_rejected(self):
		doc = frappe.get_doc({"doctype": "TRN", "trn": "OM1234567890"})

		with self.assertRaises(frappe.ValidationError):
			doc.before_rename("OM1234567890", "INVALID")
