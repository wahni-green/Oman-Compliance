import frappe
from frappe import _

from oman_compliance.oman_compliance.constants import TRN_PATTERN


def validate_trn(trn: str | None, label: str = "TRN") -> str | None:
	"""Validate TRN format. Returns the normalized (upper-cased, stripped) TRN, or the falsy
	input unchanged if no TRN was given — TRN is optional on Company/Customer/Supplier."""
	if not trn:
		return trn

	trn = trn.strip().upper()

	if not TRN_PATTERN.match(trn):
		frappe.throw(
			_("{0} {1} is invalid. Expected format: OM followed by 10 digits (e.g. OM1234567890).").format(
				label, frappe.bold(trn)
			),
			title=_("Invalid {0}").format(label),
		)

	return trn
