def get_total_vat_due(domestic_supplies: dict, reverse_charge_purchases: dict) -> float:
	"""Box 5 — total VAT due, summed over every *output*-VAT-bearing box: standard-rated domestic
	sales (1(a)) and reverse-charge purchases, both GCC and non-GCC (2(a)/2(b), the self-accounted
	output liability). Zero-rated/exempt/export boxes contribute 0 VAT by definition and are
	omitted here for clarity, not because they're excluded from the return.

	Nets each box's `adjustment_vat_amount` OUT of the total: a credit/debit note genuinely
	reduces what's owed to OTA, even though it's kept in its own column (not merged into
	`vat_amount`) for audit traceability in the per-box detail table. Netting it into the box-level
	*display* would defeat that traceability; not netting it into the *total* would overstate what's
	actually owed — this function has to do the second without undoing the first."""
	boxes = (
		domestic_supplies["standard_rated"],
		reverse_charge_purchases["gcc"],
		reverse_charge_purchases["non_gcc"],
	)

	return sum(box["vat_amount"] for box in boxes) - sum(box["adjustment_vat_amount"] for box in boxes)


def get_input_vat_credit_total(input_vat_credit: dict) -> float:
	"""Box 6 total — recoverable input VAT across "ordinary"/"imports"/"fixed_assets" (each
	already `is_return`-exclusive, so their own `adjustment_vat_amount` is always 0), minus the
	"adjustments" bucket's credit/debit-note figure (which, per `input_vat_credit.py`, lives in
	*its* `adjustment_vat_amount`, not `vat_amount`) — a purchase credit note reduces recoverable
	input credit the same way a sales credit note reduces output VAT due above."""
	main = sum(input_vat_credit[key]["vat_amount"] for key in ("ordinary", "imports", "fixed_assets"))

	return main - input_vat_credit["adjustments"]["adjustment_vat_amount"]


def get_net_tax_liability(total_vat_due: float, input_vat_credit_total: float) -> float:
	"""Box 7 = box 5 - box 6."""
	return total_vat_due - input_vat_credit_total
