from oman_compliance.oman_compliance.utils.vat_return import get_invoice_rows, summarize_box


def get_input_vat_credit(company: str, from_date, to_date) -> dict:
	"""Oman VAT return box 6: recoverable input VAT credit, split into "ordinary purchases",
	"imports", "fixed assets", and "adjustments" (credit/debit notes), per the official box
	structure. The three non-adjustment buckets are built to be mutually exclusive — a row counts
	toward "fixed_assets" first (Purchase Invoice Item's core `is_fixed_asset` field, regardless of
	import status), then "imports" (`is_import_of_goods`, excluding anything already counted as a
	fixed asset), then "ordinary" (everything else) — so a row that happens to be both an import
	and a fixed asset is never double-counted between those two buckets. This deliberately
	recomputes the import predicate locally rather than reusing `imports_of_goods.get_imports_of_
	goods()`'s "total" figure directly: that box's own total is *not* fixed-asset-exclusive (box
	4 has no such split), so reusing it here would double-count against "fixed_assets".

	"adjustments" is built from every `is_return=1` row regardless of the other three buckets'
	classification — `summarize_box` on an all-`is_return` row list naturally puts the whole figure
	in `adjustment_taxable_amount`/`adjustment_vat_amount` and leaves `taxable_amount`/
	`vat_amount` at zero, which is exactly right: this bucket *is* the adjustment, so its value
	belongs in the adjustment columns, not a "main" figure of its own."""
	rows = get_invoice_rows("Purchase Invoice", company, from_date, to_date)

	non_return_rows = [row for row in rows if not row.is_return]
	return_rows = [row for row in rows if row.is_return]

	fixed_asset_rows = [row for row in non_return_rows if row.is_fixed_asset]
	import_rows = [row for row in non_return_rows if row.is_import_of_goods and not row.is_fixed_asset]
	ordinary_rows = [row for row in non_return_rows if not row.is_fixed_asset and not row.is_import_of_goods]

	return {
		"ordinary": summarize_box(ordinary_rows, vat_amount_field="input_vat_amount"),
		"imports": summarize_box(import_rows, vat_amount_field="input_vat_amount"),
		"fixed_assets": summarize_box(fixed_asset_rows, vat_amount_field="input_vat_amount"),
		"adjustments": summarize_box(return_rows, vat_amount_field="input_vat_amount"),
	}
