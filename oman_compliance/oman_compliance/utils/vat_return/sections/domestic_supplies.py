from oman_compliance.oman_compliance.utils.vat_return import get_invoice_rows, summarize_box


def get_domestic_supplies(company: str, from_date, to_date) -> dict:
	"""Oman VAT return boxes 1(a)/1(b)/1(c): standard-rated, zero-rated, and exempt DOMESTIC
	sales. A Zero Rated sale where the parent invoice's `is_export` is set belongs to box 3(a)
	instead (see `exports.py`) — excluded here so the two boxes never double-count the same row.
	Standard Rated/Exempt rows are never split by `is_export`: box 3(a) is specifically defined as
	a Zero Rated export (OTA's guide: "zero rating for exportation applies"), so a non-zero-rated
	row stays domestic regardless of where it ships."""
	rows = get_invoice_rows("Sales Invoice", company, from_date, to_date)

	return {
		"standard_rated": summarize_box([row for row in rows if row.vat_category == "Standard Rated"]),
		"zero_rated": summarize_box(
			[row for row in rows if row.vat_category == "Zero Rated" and not row.is_export]
		),
		"exempt": summarize_box([row for row in rows if row.vat_category == "Exempt"]),
	}
