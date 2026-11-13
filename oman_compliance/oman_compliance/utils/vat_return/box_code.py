def get_box_code(doctype: str, row) -> str:
	"""The one Oman VAT return box a `get_invoice_rows()` row is primarily reported under, for
	transaction-level listings. Mirrors the section functions' own predicates (so a listing's
	per-box totals tie back to the registers) but picks a single box per row:
	Sales: 1(a) standard rated, 1(b) zero rated domestic, 1(c) exempt, 3(a) zero-rated export.
	Purchases: 2(a)/2(b) reverse charge (GCC / non-GCC), 4(a)/4(b) import of goods (postponed /
	other), otherwise 6 (input VAT credit). Box 6 is also where an import row's input VAT is
	credited — the registers show that under their own box 6 rows; a listing keeps one box per row."""
	if doctype == "Sales Invoice":
		if row.vat_category == "Exempt":
			return "1(c)"
		if row.vat_category == "Zero Rated":
			return "3(a)" if row.is_export else "1(b)"
		return "1(a)"

	if row.is_reverse_charge:
		return "2(a)" if row.is_gcc_supplier else "2(b)"
	if row.is_import_of_goods:
		return "4(a)" if row.is_postponed_import_vat else "4(b)"
	return "6"
