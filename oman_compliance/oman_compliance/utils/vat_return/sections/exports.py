from oman_compliance.oman_compliance.utils.vat_return import get_invoice_rows, summarize_box


def get_exports(company: str, from_date, to_date) -> dict:
	"""Oman VAT return box 3(a): "total value of supplies of goods and services exported on
	which zero rating for exportation applies" — a Zero Rated Sales Invoice Item row whose parent
	invoice's `is_export` is set (place of supply outside Oman). Named `exports.py`, not the plan
	doc's original `supplies_outside_oman.py` — the Phase 2/3 alignment note found that name
	described a different concept ("Out of Scope" supplies, which aren't reported on the return at
	all) than what box 3(a) actually is."""
	rows = get_invoice_rows("Sales Invoice", company, from_date, to_date)

	return summarize_box([row for row in rows if row.vat_category == "Zero Rated" and row.is_export])
