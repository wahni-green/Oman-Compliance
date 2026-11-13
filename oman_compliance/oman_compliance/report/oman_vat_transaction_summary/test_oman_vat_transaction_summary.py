import frappe
from frappe.tests.utils import FrappeTestCase

from oman_compliance.oman_compliance.report.oman_vat_purchase_register.oman_vat_purchase_register import (
	execute as purchase_register,
)
from oman_compliance.oman_compliance.report.oman_vat_sales_register.oman_vat_sales_register import (
	execute as sales_register,
)
from oman_compliance.oman_compliance.report.oman_vat_transaction_summary.oman_vat_transaction_summary import (
	execute,
)
from oman_compliance.tests import (
	create_submitted_purchase_invoice,
	create_submitted_sales_invoice,
	get_oman_test_company,
	get_oman_test_vat_accounts,
	get_unique_test_date,
	set_vat_accounts,
)


class TestOmanVatTransactionSummary(FrappeTestCase):
	def setUp(self):
		self.company = get_oman_test_company()
		self.output_account, self.input_account = get_oman_test_vat_accounts(self.company)
		set_vat_accounts(self.company, output_account=self.output_account, input_account=self.input_account)
		self.test_date = get_unique_test_date()
		self.filters = {"company": self.company, "from_date": self.test_date, "to_date": self.test_date}

	def test_missing_company_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"from_date": self.test_date, "to_date": self.test_date})

	def test_missing_dates_are_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			execute({"company": self.company})

	def test_currency_columns_are_bound_to_the_selected_companys_currency(self):
		columns, _data = execute(self.filters)

		currency_columns = [column for column in columns if column["fieldtype"] == "Currency"]
		self.assertTrue(currency_columns)
		for column in currency_columns:
			self.assertEqual(column["options"], "Company:company:default_currency")

	def test_sales_rows_are_tagged_with_their_box(self):
		standard = create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			posting_date=self.test_date,
		)
		exempt = create_submitted_sales_invoice(
			self.company, vat_category="Exempt", net_amount=300, posting_date=self.test_date
		)

		_columns, data = execute(self.filters)
		by_invoice = {row["invoice"]: row for row in data}

		self.assertEqual(by_invoice[standard.name]["box_code"], "1(a)")
		self.assertEqual(by_invoice[standard.name]["base_net_amount"], 200)
		self.assertEqual(by_invoice[standard.name]["output_vat_amount"], 10)
		self.assertEqual(by_invoice[standard.name]["transaction"], "Customer Invoice")
		self.assertEqual(by_invoice[exempt.name]["box_code"], "1(c)")

	def test_purchase_rows_are_tagged_with_their_box(self):
		ordinary = create_submitted_purchase_invoice(
			self.company,
			input_vat_account=self.input_account,
			input_rate=5,
			net_amount=400,
			posting_date=self.test_date,
		)
		reverse_charge = create_submitted_purchase_invoice(
			self.company,
			output_vat_account=self.output_account,
			input_vat_account=self.input_account,
			output_rate=5,
			input_rate=5,
			net_amount=100,
			is_reverse_charge=True,
			posting_date=self.test_date,
		)

		_columns, data = execute({**self.filters, "transaction_type": "Purchase"})
		by_invoice = {row["invoice"]: row for row in data}

		self.assertEqual(by_invoice[ordinary.name]["box_code"], "6")
		self.assertEqual(by_invoice[ordinary.name]["input_vat_amount"], 20)
		self.assertEqual(by_invoice[reverse_charge.name]["box_code"], "2(b)")

	def test_return_keeps_negative_amounts_and_credit_note_label(self):
		original = create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			posting_date=self.test_date,
		)
		credit_note = create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			is_return=True,
			return_against=original.name,
			posting_date=self.test_date,
		)

		_columns, data = execute(self.filters)
		row = next(row for row in data if row["invoice"] == credit_note.name)

		self.assertEqual(row["transaction"], "Credit Note")
		self.assertEqual(row["base_net_amount"], -200)

	def test_box_and_type_filters(self):
		create_submitted_sales_invoice(
			self.company, vat_category="Exempt", net_amount=300, posting_date=self.test_date
		)
		create_submitted_purchase_invoice(
			self.company, input_vat_account=self.input_account, input_rate=5, posting_date=self.test_date
		)

		_columns, data = execute({**self.filters, "box_code": "1(c)"})
		self.assertTrue(data)
		self.assertTrue(all(row["box_code"] == "1(c)" for row in data))

		_columns, data = execute({**self.filters, "transaction_type": "Purchase"})
		self.assertTrue(all(row["voucher_type"] == "Purchase Invoice" for row in data))

	def test_sales_box_totals_tie_back_to_the_sales_register(self):
		create_submitted_sales_invoice(
			self.company,
			vat_category="Standard Rated",
			output_vat_account=self.output_account,
			rate=5,
			net_amount=200,
			posting_date=self.test_date,
		)
		create_submitted_sales_invoice(
			self.company, vat_category="Exempt", net_amount=300, posting_date=self.test_date
		)

		_columns, data = execute({**self.filters, "transaction_type": "Sales"})
		_columns, register = sales_register(self.filters)

		for box in ("1(a)", "1(c)"):
			listed = sum(row["base_net_amount"] for row in data if row["box_code"] == box)
			summarized = sum(
				row["taxable_amount"] - row["adjustment_taxable_amount"]
				for row in register
				if row["box_code"] == box
			)
			self.assertEqual(listed, summarized, box)

	def test_purchase_reverse_charge_total_ties_back_to_the_purchase_register(self):
		create_submitted_purchase_invoice(
			self.company,
			output_vat_account=self.output_account,
			input_vat_account=self.input_account,
			output_rate=5,
			input_rate=5,
			net_amount=100,
			is_reverse_charge=True,
			posting_date=self.test_date,
		)

		_columns, data = execute({**self.filters, "transaction_type": "Purchase"})
		_columns, register = purchase_register(self.filters)

		listed = sum(row["base_net_amount"] for row in data if row["box_code"] == "2(b)")
		summarized = next(row["taxable_amount"] for row in register if row["box_code"] == "2(b)")
		self.assertEqual(listed, summarized)
