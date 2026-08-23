import re

import frappe
from frappe import _

MINIMUM_FRAPPE_VERSION = 15


def execute() -> None:
	match = re.match(r"\d+", frappe.__version__)
	if not match:
		return

	if int(match.group()) < MINIMUM_FRAPPE_VERSION:
		frappe.throw(
			_("Oman Compliance requires Frappe version {0} or above.").format(MINIMUM_FRAPPE_VERSION),
			title=_("Version Incompatible"),
		)
