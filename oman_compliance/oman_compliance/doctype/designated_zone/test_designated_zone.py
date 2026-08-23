import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.constants.designated_zones import DESIGNATED_ZONES
from oman_compliance.oman_compliance.setup import create_designated_zones


class TestDesignatedZone(FrappeTestCase):
	def test_seed_creates_expected_zones(self):
		create_designated_zones()

		for zone in DESIGNATED_ZONES:
			self.assertTrue(frappe.db.exists("Designated Zone", zone["zone_name"]))

	def test_seed_is_idempotent(self):
		create_designated_zones()
		count_before = frappe.db.count("Designated Zone")

		create_designated_zones()

		self.assertEqual(frappe.db.count("Designated Zone"), count_before)

	def test_rerun_never_overwrites_a_local_edit(self):
		# create_designated_zones() is insert-only: it can't tell a still-default record from one
		# an admin has deliberately edited, so a local customization must survive a re-run.
		create_designated_zones()
		zone_name = DESIGNATED_ZONES[0]["zone_name"]
		frappe.db.set_value("Designated Zone", zone_name, "authority", "Locally Corrected Authority")

		create_designated_zones()

		self.assertEqual(
			frappe.db.get_value("Designated Zone", zone_name, "authority"), "Locally Corrected Authority"
		)
