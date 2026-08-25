from oman_compliance.oman_compliance.utils.vat_return import get_invoice_rows, summarize_box


def get_imports_of_goods(company: str, from_date, to_date) -> dict:
	"""Oman VAT return boxes 4(a)/4(b): imports of goods (`is_import_of_goods=1`, distinct from
	Reverse Charge, which covers imported services). 4(b) "total value of goods imported" covers
	every such row; 4(a) "import of goods with postponed/deferred payment" is the
	`is_postponed_import_vat=1` subset of the same rows — a subset, not a disjoint category, so
	"postponed" is always <= "total" here. VAT amount is read from the Input VAT Account (import
	VAT paid/self-assessed and recorded as a recoverable input credit), not the Output VAT
	Account — that's what `input_vat_amount` is for."""
	rows = [
		row
		for row in get_invoice_rows("Purchase Invoice", company, from_date, to_date)
		if row.is_import_of_goods
	]

	return {
		"postponed": summarize_box(
			[row for row in rows if row.is_postponed_import_vat], vat_amount_field="input_vat_amount"
		),
		"total": summarize_box(rows, vat_amount_field="input_vat_amount"),
	}
