import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create_custom_fields

from oman_compliance.oman_compliance.constants.custom_fields import CUSTOM_FIELDS
from oman_compliance.oman_compliance.constants.designated_zones import DESIGNATED_ZONES


def create_custom_fields() -> None:
	_create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)


def create_designated_zones() -> None:
	for zone in DESIGNATED_ZONES:
		if frappe.db.exists("Designated Zone", zone["zone_name"]):
			# Keep authority/conditions in sync with DESIGNATED_ZONES on re-run (e.g. after a
			# wording correction), without touching is_active — that's a user-controlled toggle,
			# not part of the seed data.
			frappe.db.set_value("Designated Zone", zone["zone_name"], zone)
			continue

		frappe.get_doc({"doctype": "Designated Zone", **zone}).insert(ignore_permissions=True)
