import frappe

from oman_compliance.oman_compliance.constants import VAT_BEARING_ACCOUNT_TYPES


def is_vat_bearing_account(account_head: str | None) -> bool:
	"""Whether a Taxes and Charges row's account is plausibly a VAT account, as opposed to an
	unrelated charge (freight, discount, withholding, ...) that happens to sit in the same child
	table and would otherwise be misread as VAT by rate/amount alone."""
	if not account_head:
		return False

	return frappe.get_cached_value("Account", account_head, "account_type") in VAT_BEARING_ACCOUNT_TYPES
