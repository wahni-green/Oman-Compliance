import frappe


def get_item_tax_template_category(item_tax_template: str | None) -> str | None:
	"""VAT Category declared on an Item Tax Template itself (e.g. "Oman VAT 0% - Exempt"), if any.
	This is the most reliable defaulting/validation signal available: a template's own tax rate
	alone can't distinguish Zero Rated from Exempt from Out of Scope, which are all commonly 0%
	but have different VAT return treatment."""
	if not item_tax_template:
		return None

	# Normalize "" (an unset Select field) to None, so the return contract genuinely means
	# "no category declared" rather than leaking the Select field's blank-string representation.
	return frappe.get_cached_value("Item Tax Template", item_tax_template, "vat_category") or None
