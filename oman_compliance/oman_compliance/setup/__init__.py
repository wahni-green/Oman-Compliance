import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create_custom_fields

from oman_compliance.oman_compliance.constants.custom_fields import CUSTOM_FIELDS
from oman_compliance.oman_compliance.constants.designated_zones import DESIGNATED_ZONES


def create_custom_fields() -> None:
	_create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)


def create_designated_zones() -> None:
	# Insert-only: there's no way here to tell a still-default record from one an admin has
	# deliberately edited (e.g. corrected wording after checking with OTA), so this never
	# overwrites an existing row. A future correction to DESIGNATED_ZONES itself needs an
	# explicit dated patch (patches/vN/...) that updates the specific field(s), not a blanket
	# resync here.
	for zone in DESIGNATED_ZONES:
		if frappe.db.exists("Designated Zone", zone["zone_name"]):
			continue

		frappe.get_doc({"doctype": "Designated Zone", **zone}).insert(ignore_permissions=True)


def set_default_settings_currency() -> None:
	# A Single doctype's field-level `default` only applies to a document that's never been
	# persisted — a site where Oman VAT Settings already existed before settings_currency was
	# added would otherwise read back None for it forever, since nothing re-saves the singleton.
	if not frappe.db.get_single_value("Oman VAT Settings", "settings_currency"):
		frappe.db.set_single_value("Oman VAT Settings", "settings_currency", "OMR")
