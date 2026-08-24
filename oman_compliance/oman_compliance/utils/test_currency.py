import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.currency import get_exchange_rate_disclosure


class TestExchangeRateDisclosure(FrappeTestCase):
	def setUp(self):
		# Avoid hardcoding a company name: this app's tests may run on a shared bench where the
		# bootstrap test company was skipped (see tests/__init__.py) in favour of whatever
		# Company already exists there.
		self.company = frappe.get_all("Company", limit=1, pluck="name")[0]
		self.company_currency = frappe.get_cached_value("Company", self.company, "default_currency")

	def test_company_currency_document_has_no_disclosure(self):
		doc = frappe._dict(
			currency=self.company_currency,
			company=self.company,
			conversion_rate=1,
			posting_date="2026-01-01",
		)

		self.assertIsNone(get_exchange_rate_disclosure(doc))

	def test_foreign_currency_document_discloses_rate(self):
		foreign_currency = "USD" if self.company_currency != "USD" else "EUR"
		doc = frappe._dict(
			currency=foreign_currency,
			company=self.company,
			conversion_rate=0.385,
			posting_date="2026-01-01",
		)

		disclosure = get_exchange_rate_disclosure(doc)

		self.assertIn(foreign_currency, disclosure)
		self.assertIn(self.company_currency, disclosure)
		self.assertIn("0.385", disclosure)
