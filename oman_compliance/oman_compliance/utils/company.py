import frappe


def is_oman_company(company: str | None) -> bool:
	"""Whether the given Company is registered in Oman. Every transaction-level override in this
	app must gate on this before applying any Oman VAT defaulting/validation — this app is
	routinely installed on a bench shared with unrelated companies' own apps (see
	OMAN_COMPLIANCE_PLAN.md's Phase 1 status log for the tax_id/property-setter incident that
	first showed this kind of cross-company leakage is a real risk here, not a hypothetical one),
	so a non-Oman company's transactions must be left completely untouched."""
	if not company:
		return False

	return frappe.get_cached_value("Company", company, "country") == "Oman"
