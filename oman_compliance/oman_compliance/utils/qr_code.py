import frappe
import pyqrcode
from frappe.utils import fmt_money

from oman_compliance.oman_compliance.utils.tax_account import get_output_vat_amount


def get_tax_invoice_qr_code(doc) -> str | None:
	"""Base64 PNG data URI for the Tax Invoice print formats' QR code, via `jinja.methods`.

	Provisional payload only: OTA hasn't published a Fawtara/PINT-OM QR spec yet (architecture doc
	§3), so this is plain labelled text, not a signed/TLV structure like ZATCA's. Once Phase 5's
	`e-Invoice Log` exists, this should read the OTA-issued QR payload from it instead of
	constructing one locally, per the architecture doc's §1.7 plan. Returns None (no QR rendered)
	for a company with no TRN configured yet, since a QR with no TRN in it wouldn't be useful."""
	company = doc.get("company")
	if not company:
		return None

	company_trn = frappe.get_cached_value("Company", company, "oman_trn")
	if not company_trn:
		return None

	currency = doc.get("currency")
	payload = "\n".join(
		[
			f"Seller: {company}",
			f"TRN: {company_trn}",
			f"Invoice: {doc.get('name') or ''}",
			f"Date: {doc.get('posting_date') or ''}",
			f"Total: {doc.get('grand_total') or 0} {currency or ''}",
			# Not doc.get("total_taxes_and_charges"): that sums every Taxes and Charges row
			# (freight, discount, withholding, ...), not just VAT — get_output_vat_amount() only
			# sums rows posted to the company's configured Output VAT Account. fmt_money (not a
			# fixed round()) since OMR is a 3-decimal currency (baisa), not 2 like most — the
			# correct precision depends on which currency this actually is.
			f"VAT: {fmt_money(get_output_vat_amount(doc), currency=currency)}",
		]
	)

	# encoding="utf-8" is required, not optional: pyqrcode's mode auto-detection falls back to
	# Latin-1 for a non-numeric/non-alphanumeric payload, and a Company name containing Arabic
	# text (a real possibility in Oman, not just company_name_in_arabic) raises UnicodeEncodeError
	# without it — confirmed by direct reproduction, not a theoretical concern.
	qr_code = pyqrcode.create(payload, encoding="utf-8")
	return "data:image/png;base64," + qr_code.png_as_base64_str(scale=4)
