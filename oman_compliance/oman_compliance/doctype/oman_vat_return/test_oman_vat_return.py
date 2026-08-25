from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.tests import get_oman_test_company, get_unique_test_date

_MODULE = "oman_compliance.oman_compliance.doctype.oman_vat_return.oman_vat_return"

_EMPTY_BOX = {
	"taxable_amount": 0,
	"vat_amount": 0,
	"adjustment_taxable_amount": 0,
	"adjustment_vat_amount": 0,
}


def _box(**overrides):
	return {**_EMPTY_BOX, **overrides}


class TestOmanVATReturn(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		test_date = get_unique_test_date()
		self.doc = frappe.get_doc(
			{
				"doctype": "Oman VAT Return",
				"company": self.company,
				"from_date": test_date,
				"to_date": test_date,
				"period_type": "Monthly",
			}
		).insert()

	def _generate_with(
		self,
		domestic_supplies=None,
		exports=None,
		reverse_charge_purchases=None,
		imports_of_goods=None,
		input_vat_credit=None,
	):
		domestic_supplies = domestic_supplies or {
			"standard_rated": _box(taxable_amount=200, vat_amount=10),
			"zero_rated": _box(taxable_amount=50),
			"exempt": _box(taxable_amount=30),
		}
		exports = exports if exports is not None else _box(taxable_amount=100)
		reverse_charge_purchases = reverse_charge_purchases or {
			"gcc": _box(),
			"non_gcc": _box(taxable_amount=80, vat_amount=4),
		}
		imports_of_goods = imports_of_goods or {"postponed": _box(), "total": _box(taxable_amount=60)}
		input_vat_credit = input_vat_credit or {
			"ordinary": _box(taxable_amount=90, vat_amount=4.5),
			"imports": _box(),
			"fixed_assets": _box(),
			"adjustments": _box(),
		}

		with (
			patch(f"{_MODULE}.get_domestic_supplies", return_value=domestic_supplies),
			patch(f"{_MODULE}.get_exports", return_value=exports),
			patch(f"{_MODULE}.get_reverse_charge_purchases", return_value=reverse_charge_purchases),
			patch(f"{_MODULE}.get_imports_of_goods", return_value=imports_of_goods),
			patch(f"{_MODULE}.get_input_vat_credit", return_value=input_vat_credit),
		):
			self.doc.generate_return()

	def test_generate_return_populates_boxes_in_official_order(self):
		self._generate_with()

		box_codes = [row.box_code for row in self.doc.boxes]
		self.assertEqual(
			box_codes,
			[
				"1(a)",
				"1(b)",
				"1(c)",
				"1(d)",
				"1(e)",
				"1(f)",
				"2(a)",
				"2(b)",
				"3(a)",
				"4(a)",
				"4(b)",
				"6",
				"6",
				"6",
				"6",
			],
		)

	def test_generate_return_carries_box_amounts_through(self):
		self._generate_with()

		by_code = {row.box_code: row for row in self.doc.boxes}
		self.assertEqual(by_code["1(a)"].taxable_amount, 200)
		self.assertEqual(by_code["1(a)"].vat_amount, 10)
		self.assertEqual(by_code["3(a)"].taxable_amount, 100)
		self.assertEqual(by_code["2(b)"].taxable_amount, 80)

	def test_unbuilt_boxes_are_present_but_zero(self):
		self._generate_with()

		by_code = {row.box_code: row for row in self.doc.boxes}
		for box_code in ("1(d)", "1(e)", "1(f)"):
			self.assertEqual(by_code[box_code].taxable_amount, 0)
			self.assertEqual(by_code[box_code].vat_amount, 0)

	def test_generate_return_computes_totals(self):
		self._generate_with()

		# box 5 = 1(a).vat + 2(a).vat + 2(b).vat = 10 + 0 + 4
		self.assertEqual(self.doc.total_vat_due, 14)
		# box 6 = ordinary.vat + imports.vat + fixed_assets.vat = 4.5 + 0 + 0
		self.assertEqual(self.doc.input_vat_credit_total, 4.5)
		self.assertEqual(self.doc.net_tax_liability, 14 - 4.5)

	def test_regenerating_a_draft_return_replaces_rows_not_appends(self):
		self._generate_with()
		first_count = len(self.doc.boxes)

		self._generate_with(
			domestic_supplies={
				"standard_rated": _box(taxable_amount=999, vat_amount=50),
				"zero_rated": _box(),
				"exempt": _box(),
			}
		)

		self.assertEqual(len(self.doc.boxes), first_count)
		by_code = {row.box_code: row for row in self.doc.boxes}
		self.assertEqual(by_code["1(a)"].taxable_amount, 999)

	def test_regenerating_a_filed_return_is_rejected(self):
		self._generate_with()
		self.doc.status = "Filed"
		self.doc.save()

		with self.assertRaises(frappe.ValidationError):
			self.doc.generate_return()

	def test_from_date_after_to_date_is_rejected(self):
		self.doc.from_date = get_unique_test_date()
		self.doc.to_date = frappe.utils.add_days(self.doc.from_date, -1)

		with self.assertRaises(frappe.ValidationError):
			self.doc.save()

	def test_editing_a_filed_return_is_rejected(self):
		self._generate_with()
		self.doc.status = "Filed"
		self.doc.save()

		self.doc.period_type = "Quarterly"
		with self.assertRaises(frappe.ValidationError):
			self.doc.save()

	def test_reverting_a_filed_return_to_draft_is_rejected(self):
		self._generate_with()
		self.doc.status = "Filed"
		self.doc.save()

		self.doc.status = "Draft"
		with self.assertRaises(frappe.ValidationError):
			self.doc.save()

	def test_deleting_a_filed_return_is_rejected(self):
		self._generate_with()
		self.doc.status = "Filed"
		self.doc.save()

		with self.assertRaises(frappe.ValidationError):
			self.doc.delete()

	def test_deleting_a_draft_return_is_allowed(self):
		self._generate_with()

		self.doc.delete()  # should not raise

	def test_deleting_via_a_stale_draft_instance_of_a_now_filed_return_is_rejected(self):
		# on_trash() must read the persisted status, not self.status: a doc instance loaded before
		# another request filed this same return would otherwise still say "Draft" in memory and
		# sail through the check, deleting a return that's actually Filed in the database.
		self._generate_with()
		stale_doc = frappe.get_doc("Oman VAT Return", self.doc.name)
		self.assertEqual(stale_doc.status, "Draft")

		self.doc.status = "Filed"
		self.doc.save()

		with self.assertRaises(frappe.ValidationError):
			stale_doc.delete()
