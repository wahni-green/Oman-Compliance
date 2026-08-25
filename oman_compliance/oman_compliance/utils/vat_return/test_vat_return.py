import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days

from oman_compliance.oman_compliance.utils.vat_return import get_invoice_rows, summarize_box
from oman_compliance.tests import (
	create_submitted_purchase_invoice,
	create_submitted_sales_invoice,
	get_non_oman_test_company,
	get_oman_test_company,
	get_oman_test_vat_accounts,
	get_unique_test_date,
	set_vat_accounts,
)


class TestGetInvoiceRows(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, self.input_account = get_oman_test_vat_accounts(self.company)
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)
		self.test_date = get_unique_test_date()

	def test_sales_invoice_row_reads_base_net_amount_and_output_vat_amount(self):
		create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			posting_date=self.test_date,
		)

		rows = get_invoice_rows("Sales Invoice", self.company, self.test_date, self.test_date)

		self.assertEqual(len(rows), 1)
		row = rows[0]
		self.assertEqual(row.base_net_amount, 200)
		self.assertEqual(row.output_vat_amount, 10)  # 200 * 5%
		self.assertEqual(row.input_vat_amount, 0)
		self.assertFalse(row.is_return)
		self.assertFalse(row.is_export)

	def test_purchase_invoice_row_reads_both_output_and_input_vat_amounts(self):
		create_submitted_purchase_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			input_vat_account=self.input_account,
			output_rate=5,
			input_rate=5,
			net_amount=400,
			is_reverse_charge=True,
			posting_date=self.test_date,
		)

		rows = get_invoice_rows("Purchase Invoice", self.company, self.test_date, self.test_date)

		self.assertEqual(len(rows), 1)
		row = rows[0]
		self.assertEqual(row.base_net_amount, 400)
		self.assertEqual(row.output_vat_amount, 20)
		self.assertEqual(row.input_vat_amount, 20)
		self.assertTrue(row.is_reverse_charge)

	def test_out_of_scope_rows_are_excluded(self):
		create_submitted_sales_invoice(
			self.company, vat_category="Out of Scope", net_amount=500, posting_date=self.test_date
		)

		rows = get_invoice_rows("Sales Invoice", self.company, self.test_date, self.test_date)

		self.assertEqual(rows, [])

	def test_return_row_is_flagged_and_amount_is_negative(self):
		original = create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			posting_date=self.test_date,
		)
		create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			is_return=True,
			return_against=original.name,
			posting_date=self.test_date,
		)

		rows = get_invoice_rows("Sales Invoice", self.company, self.test_date, self.test_date)

		self.assertEqual(len(rows), 2)
		return_rows = [row for row in rows if row.is_return]
		self.assertEqual(len(return_rows), 1)
		self.assertEqual(return_rows[0].base_net_amount, -200)

	def test_out_of_period_invoice_is_excluded(self):
		create_submitted_sales_invoice(
			self.company, vat_category="Standard Rated", net_amount=100, posting_date=self.test_date
		)

		rows = get_invoice_rows(
			"Sales Invoice", self.company, add_days(self.test_date, 10), add_days(self.test_date, 20)
		)

		self.assertEqual(rows, [])

	def test_no_invoices_returns_empty_list(self):
		rows = get_invoice_rows("Sales Invoice", self.company, self.test_date, self.test_date)

		self.assertEqual(rows, [])

	def test_duplicate_item_code_rows_are_not_double_counted(self):
		# item_wise_tax_detail is keyed by item_code, not row — a naive read would assign the full
		# combined VAT amount to each row sharing that item_code, doubling it once summed.
		create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=100,
			extra_item_net_amounts=[300],
			posting_date=self.test_date,
		)

		rows = get_invoice_rows("Sales Invoice", self.company, self.test_date, self.test_date)

		self.assertEqual(len(rows), 2)
		self.assertEqual(sum(row.base_net_amount for row in rows), 400)
		# Total VAT across both rows must equal the real invoice-level VAT (400 * 5% = 20), not
		# 20 counted once per row (40).
		self.assertEqual(sum(row.output_vat_amount for row in rows), 20)
		# Allocated proportionally to each row's own share of the combined net amount.
		by_net_amount = {row.base_net_amount: row.output_vat_amount for row in rows}
		self.assertEqual(by_net_amount[100], 5)
		self.assertEqual(by_net_amount[300], 15)

	def test_duplicate_item_code_rows_with_different_vat_categories_are_rejected(self):
		# item_wise_tax_detail only preserves the combined VAT amount across rows sharing an item
		# code, not each row's own share, once they carry different VAT Categories (confirmed
		# against ERPNext's own taxes_and_totals.py — the stored `rate` is just whichever row was
		# processed last, not an average). Proportionally splitting by net amount alone would
		# silently misattribute real VAT between return boxes.
		#
		# Submission-time validation (overrides/sales_invoice.py::
		# validate_no_mixed_vat_category_per_item_code) blocks a *new* invoice from ever reaching
		# this state, so this test has to force it in afterward — via db_set, bypassing controller
		# validation entirely — to simulate an invoice that predates that check. Even then, a
		# silently incomplete return is worse than one that refuses to generate at all.
		invoice = create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=100,
			extra_item_net_amounts=[100],
			posting_date=self.test_date,
		)
		frappe.db.set_value("Sales Invoice Item", invoice.items[1].name, "vat_category", "Zero Rated")

		with self.assertRaises(frappe.ValidationError):
			get_invoice_rows("Sales Invoice", self.company, self.test_date, self.test_date)

	def test_duplicate_item_code_rows_with_same_category_but_different_template_are_rejected(self):
		# VAT Category alone isn't a strong enough signal: two "Standard Rated" rows can use
		# different Item Tax Templates configured with different rates, which a category-only
		# ambiguity check would miss and then still misallocate VAT via the net-amount-proportional
		# split. Same submission-time/legacy-data reasoning as the category-mismatch test above.
		invoice = create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=100,
			extra_item_net_amounts=[100],
			posting_date=self.test_date,
		)
		frappe.db.set_value(
			"Sales Invoice Item", invoice.items[0].name, "item_tax_template", "_Test Template A"
		)
		frappe.db.set_value(
			"Sales Invoice Item", invoice.items[1].name, "item_tax_template", "_Test Template B"
		)

		with self.assertRaises(frappe.ValidationError):
			get_invoice_rows("Sales Invoice", self.company, self.test_date, self.test_date)

	def test_company_permission_is_enforced(self):
		other_company = get_non_oman_test_company()

		test_user_email = "_test_vat_return_permission@example.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": test_user_email,
				"first_name": "Test VAT Return Permission",
				"send_welcome_email": 0,
				"roles": [{"role": "Accounts User"}],
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{"doctype": "User Permission", "user": user.name, "allow": "Company", "for_value": other_company}
		).insert(ignore_permissions=True)

		frappe.set_user(user.name)
		self.addCleanup(frappe.set_user, "Administrator")

		with self.assertRaises(frappe.PermissionError):
			get_invoice_rows("Sales Invoice", self.company, self.test_date, self.test_date)


class TestSummarizeBox(FrappeTestCase):
	def test_non_return_rows_land_in_main_columns(self):
		rows = [frappe._dict(base_net_amount=100, output_vat_amount=5, is_return=False)]

		box = summarize_box(rows)

		self.assertEqual(box["taxable_amount"], 100)
		self.assertEqual(box["vat_amount"], 5)
		self.assertEqual(box["adjustment_taxable_amount"], 0)
		self.assertEqual(box["adjustment_vat_amount"], 0)

	def test_return_rows_land_in_adjustment_columns_as_positive_magnitudes(self):
		rows = [frappe._dict(base_net_amount=-100, output_vat_amount=-5, is_return=True)]

		box = summarize_box(rows)

		self.assertEqual(box["taxable_amount"], 0)
		self.assertEqual(box["vat_amount"], 0)
		self.assertEqual(box["adjustment_taxable_amount"], 100)
		self.assertEqual(box["adjustment_vat_amount"], 5)

	def test_mixed_rows_are_split_correctly(self):
		rows = [
			frappe._dict(base_net_amount=100, output_vat_amount=5, is_return=False),
			frappe._dict(base_net_amount=-40, output_vat_amount=-2, is_return=True),
		]

		box = summarize_box(rows)

		self.assertEqual(box["taxable_amount"], 100)
		self.assertEqual(box["vat_amount"], 5)
		self.assertEqual(box["adjustment_taxable_amount"], 40)
		self.assertEqual(box["adjustment_vat_amount"], 2)

	def test_alternate_vat_amount_field_is_used_when_given(self):
		rows = [frappe._dict(base_net_amount=100, input_vat_amount=7, is_return=False)]

		box = summarize_box(rows, vat_amount_field="input_vat_amount")

		self.assertEqual(box["vat_amount"], 7)

	def test_empty_rows_produce_a_zeroed_box(self):
		box = summarize_box([])

		self.assertEqual(
			box,
			{
				"taxable_amount": 0.0,
				"vat_amount": 0.0,
				"adjustment_taxable_amount": 0.0,
				"adjustment_vat_amount": 0.0,
			},
		)
