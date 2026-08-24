import frappe

from oman_compliance.oman_compliance.constants import DEFAULT_VAT_CATEGORY, ZONE_DEFAULT_VAT_CATEGORY
from oman_compliance.oman_compliance.utils.company import is_oman_company
from oman_compliance.oman_compliance.utils.vat_category import get_item_tax_template_category


def set_vat_category_defaults(doc, method=None):
	"""Shared across Sales Order/Quotation/Delivery Note/Sales Invoice. Only fills a blank
	category, never overwrites one already set; a row's own Item Tax Template wins over the zone
	guess below when it declares one."""
	if not is_oman_company(doc.get("company")):
		return

	zone_default = ZONE_DEFAULT_VAT_CATEGORY if _is_designated_zone_transaction(doc) else DEFAULT_VAT_CATEGORY

	for row in doc.get("items", []):
		if row.get("vat_category"):
			continue

		row.vat_category = get_item_tax_template_category(row.get("item_tax_template")) or zone_default


def _is_designated_zone_transaction(doc) -> bool:
	# Checks every relevant address independently (not "billing, falling back to shipping only if
	# blank") — a zone address on any one of them must still be caught even when the others are
	# non-zone. `dispatch_address_name` (Sales Order/Delivery Note/Sales Invoice — not Quotation,
	# which has no dispatch concept) covers "supply out of a zone": the company's own warehouse
	# address for this specific transaction, when it's the zone-linked one rather than the
	# customer's.
	for address_name in (
		doc.get("customer_address"),
		doc.get("shipping_address_name"),
		doc.get("dispatch_address_name"),
	):
		if address_name and _address_is_in_active_designated_zone(address_name):
			return True

	return False


def _address_is_in_active_designated_zone(address_name: str) -> bool:
	zone = frappe.db.get_value("Address", address_name, "designated_zone")
	if not zone:
		return False

	# A deactivated zone (is_active=0) no longer gets the automatic default — existing records
	# still pointing at it are left alone, but new documents fall back to Standard Rated.
	return bool(frappe.db.get_value("Designated Zone", zone, "is_active"))
