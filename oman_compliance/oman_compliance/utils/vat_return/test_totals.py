from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.utils.vat_return.totals import (
	get_input_vat_credit_total,
	get_net_tax_liability,
	get_total_vat_due,
)

_EMPTY_BOX = {
	"taxable_amount": 0,
	"vat_amount": 0,
	"adjustment_taxable_amount": 0,
	"adjustment_vat_amount": 0,
}


def _box(vat_amount=0, adjustment_vat_amount=0):
	return {**_EMPTY_BOX, "vat_amount": vat_amount, "adjustment_vat_amount": adjustment_vat_amount}


class TestGetTotalVatDue(FrappeTestCase):
	def test_sums_standard_rated_and_reverse_charge_boxes(self):
		domestic_supplies = {"standard_rated": _box(vat_amount=10), "zero_rated": _box(), "exempt": _box()}
		reverse_charge_purchases = {"gcc": _box(vat_amount=3), "non_gcc": _box(vat_amount=7)}

		total = get_total_vat_due(domestic_supplies, reverse_charge_purchases)

		self.assertEqual(total, 20)

	def test_nets_out_adjustment_vat_amount(self):
		domestic_supplies = {
			"standard_rated": _box(vat_amount=10, adjustment_vat_amount=4),
			"zero_rated": _box(),
			"exempt": _box(),
		}
		reverse_charge_purchases = {"gcc": _box(), "non_gcc": _box()}

		total = get_total_vat_due(domestic_supplies, reverse_charge_purchases)

		self.assertEqual(total, 6)


class TestGetInputVatCreditTotal(FrappeTestCase):
	def test_sums_ordinary_imports_and_fixed_assets(self):
		input_vat_credit = {
			"ordinary": _box(vat_amount=5),
			"imports": _box(vat_amount=3),
			"fixed_assets": _box(vat_amount=2),
			"adjustments": _box(),
		}

		total = get_input_vat_credit_total(input_vat_credit)

		self.assertEqual(total, 10)

	def test_nets_out_adjustments_bucket(self):
		input_vat_credit = {
			"ordinary": _box(vat_amount=5),
			"imports": _box(),
			"fixed_assets": _box(),
			"adjustments": _box(adjustment_vat_amount=2),
		}

		total = get_input_vat_credit_total(input_vat_credit)

		self.assertEqual(total, 3)


class TestGetNetTaxLiability(FrappeTestCase):
	def test_box_seven_is_box_five_minus_box_six(self):
		self.assertEqual(get_net_tax_liability(20, 8), 12)

	def test_negative_net_liability_is_allowed(self):
		# A period with more recoverable input credit than output VAT due is a real, valid outcome
		# (a refund position) — not something to clamp to zero.
		self.assertEqual(get_net_tax_liability(5, 20), -15)
