import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields as _create_custom_fields

from oman_compliance.oman_compliance.constants.custom_fields import CUSTOM_FIELDS
from oman_compliance.oman_compliance.constants.designated_zones import DESIGNATED_ZONES


def create_custom_fields() -> None:
	_create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)


def create_designated_zones() -> None:
	for zone in DESIGNATED_ZONES:
		if frappe.db.exists("Designated Zone", zone["zone_name"]):
			continue

		frappe.get_doc({"doctype": "Designated Zone", **zone}).insert(ignore_permissions=True)
