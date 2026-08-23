import frappe
from frappe import _
from frappe.utils import formatdate


def get_exchange_rate_disclosure(doc) -> str | None:
	"""Human-readable exchange-rate disclosure for a foreign-currency Sales/Purchase Invoice.
	Oman VAT invoices in a foreign currency must state the rate used to arrive at the OMR figures
	(findings §30/88) — exposed via `jinja.methods` for the tax invoice print formats (Phase 4).
	Returns None for a company-currency document, where no disclosure is needed."""
	if not doc.get("currency") or not doc.get("company"):
		return None

	company_currency = frappe.get_cached_value("Company", doc.company, "default_currency")
	if doc.currency == company_currency:
		return None

	return _("Exchange rate: 1 {0} = {1} {2} (as on {3})").format(
		doc.currency, doc.conversion_rate, company_currency, formatdate(doc.get("posting_date"))
	)
