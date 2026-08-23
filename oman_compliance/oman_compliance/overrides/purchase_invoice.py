import frappe
from frappe import _
from frappe.utils import flt

from oman_compliance.oman_compliance.constants import DEFAULT_VAT_CATEGORY
from oman_compliance.oman_compliance.utils.company import is_oman_company
from oman_compliance.oman_compliance.utils.tax_account import is_vat_bearing_account
from oman_compliance.oman_compliance.utils.vat_category import get_item_tax_template_category


def validate(doc, method=None):
	if not is_oman_company(doc.get("company")):
		return

	validate_reverse_charge(doc)
	set_import_of_goods_flag(doc)


def validate_reverse_charge(doc, method=None):
	_set_default_vat_category(doc)

	if doc.get("is_reverse_charge") and not _has_recipient_output_vat_row(doc):
		frappe.throw(
			_(
				"Reverse Charge Applicable is checked but this Purchase Invoice has no VAT row recording"
				" the self-accounted output VAT. Self-accounting for reverse charge requires recording the"
				" output VAT (as recipient) here, not just flagging the invoice."
			),
			title=_("Reverse Charge Requires VAT Rows"),
		)


def _has_recipient_output_vat_row(doc) -> bool:
	"""A nonempty Taxes and Charges table isn't proof of anything — it could just as easily hold
	an unrelated charge (freight, discount, withholding, ...) with no real VAT row at all. Requires
	at least one row that both posts to a VAT-bearing account and actually carries a nonzero
	rate/amount."""
	for tax in doc.get("taxes") or []:
		if not is_vat_bearing_account(tax.get("account_head")):
			continue

		if flt(tax.get("rate")) or flt(tax.get("tax_amount")):
			return True

	return False


def _set_default_vat_category(doc):
	for row in doc.get("items", []):
		if row.get("vat_category"):
			continue

		row.vat_category = (
			get_item_tax_template_category(row.get("item_tax_template")) or DEFAULT_VAT_CATEGORY
		)


def set_import_of_goods_flag(doc, method=None):
	"""VAT return box 4 (imports of goods) is distinct from box 2 (reverse charge, which covers
	imported *services*) — this is a computed flag, not a manual one like Reverse Charge
	Applicable, since it's fully derivable from where the goods are actually dispatched from.
	Always recomputed on save so a later edit to the Dispatch Address keeps it correct; the user
	is notified whenever this changes the stored value, since the field itself is read-only."""
	previous_value = bool(doc.get("is_import_of_goods"))
	new_value = _is_import_of_goods(doc)

	doc.is_import_of_goods = new_value

	if previous_value != new_value:
		frappe.msgprint(
			_("Import of Goods set to {0}, based on the Dispatch Address's country.").format(
				_("Yes") if new_value else _("No")
			),
			indicator="blue",
			alert=True,
		)


def _is_import_of_goods(doc) -> bool:
	dispatch_address = doc.get("dispatch_address")
	if not dispatch_address:
		return False

	dispatch_country = frappe.db.get_value("Address", dispatch_address, "country")
	if not dispatch_country:
		return False

	company_country = frappe.get_cached_value("Company", doc.company, "country")
	if not company_country:
		return False

	return dispatch_country != company_country
