from oman_compliance.oman_compliance.utils.vat_return import get_invoice_rows, summarize_box


def get_reverse_charge_purchases(company: str, from_date, to_date) -> dict:
	"""Oman VAT return boxes 2(a)/2(b): reverse-charge purchases (`is_reverse_charge=1`), split by
	`is_gcc_supplier` into 2(a) intra-GCC and 2(b) non-GCC. Box 2(a) is computed and returned even
	though the OTA hasn't activated the intra-GCC mechanism yet (per the plan doc's Phase 3
	alignment note) — the doctype layer is responsible for surfacing it as a zero/not-yet-active
	row rather than omitting the box. The VAT amount reported is the self-accounted Output VAT
	liability (the row purchase_invoice.py's `validate_reverse_charge` requires on the company's
	Output VAT Account) — `summarize_box`'s default `vat_amount_field="output_vat_amount"` is
	exactly right here, so it isn't passed explicitly."""
	rows = [
		row
		for row in get_invoice_rows("Purchase Invoice", company, from_date, to_date)
		if row.is_reverse_charge
	]

	return {
		"gcc": summarize_box([row for row in rows if row.is_gcc_supplier]),
		"non_gcc": summarize_box([row for row in rows if not row.is_gcc_supplier]),
	}
