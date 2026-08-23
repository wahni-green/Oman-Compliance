import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.constants import VAT_BEARING_ACCOUNT_TYPES
from oman_compliance.oman_compliance.utils.tax_account import is_vat_bearing_account
from oman_compliance.tests import get_test_tax_account


class TestIsVatBearingAccount(FrappeTestCase):
	def test_vat_bearing_account_returns_true(self):
		tax_account, _ = get_test_tax_account()

		self.assertTrue(is_vat_bearing_account(tax_account))

	def test_non_vat_bearing_account_returns_false(self):
		_, company = get_test_tax_account()
		non_vat_account = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"is_group": 0,
				"account_type": ["not in", list(VAT_BEARING_ACCOUNT_TYPES)],
			},
		)
		if not non_vat_account:
			self.skipTest("No non-VAT-bearing account available on this bench for this test.")

		self.assertFalse(is_vat_bearing_account(non_vat_account))

	def test_blank_account_head_returns_false(self):
		self.assertFalse(is_vat_bearing_account(None))
