import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.company import is_oman_company
from oman_compliance.tests import get_non_oman_test_company, get_oman_test_company


class TestIsOmanCompany(FrappeTestCase):
	def test_oman_company_returns_true(self):
		self.assertTrue(is_oman_company(get_oman_test_company()))

	def test_non_oman_company_returns_false(self):
		self.assertFalse(is_oman_company(get_non_oman_test_company()))

	def test_blank_company_returns_false(self):
		self.assertFalse(is_oman_company(None))

	def test_nonexistent_company_returns_false(self):
		self.assertFalse(is_oman_company("_Test Company That Does Not Exist"))
