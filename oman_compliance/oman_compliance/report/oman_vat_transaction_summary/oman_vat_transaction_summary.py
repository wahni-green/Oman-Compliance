import frappe
from frappe import _

from oman_compliance.oman_compliance.utils.vat_return import get_invoice_rows
from oman_compliance.oman_compliance.utils.vat_return.box_code import get_box_code

_CURRENCY = {"fieldtype": "Currency", "options": "Company:company:default_currency"}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	return get_columns(), get_data(filters)


def validate_filters(filters) -> None:
	if not filters.get("company"):
		frappe.throw(_("Company is mandatory"))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are mandatory"))


def get_columns() -> list[dict]:
	return [
		{"label": _("Purchase / Sales"), "fieldname": "transaction_type", "fieldtype": "Data", "width": 100},
		{"label": _("Box"), "fieldname": "box_code", "fieldtype": "Data", "width": 60},
		{"label": _("Transaction"), "fieldname": "transaction", "fieldtype": "Data", "width": 130},
		{
			"label": _("Document"),
			"fieldname": "invoice",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 160,
		},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "hidden": 1},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 100},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 200},
		{"label": _("Party TRN"), "fieldname": "party_trn", "fieldtype": "Data", "width": 120},
		{
			"label": _("Country"),
			"fieldname": "party_country",
			"fieldtype": "Link",
			"options": "Country",
			"width": 100,
		},
		{"label": _("Bill No"), "fieldname": "bill_no", "fieldtype": "Data", "width": 130},
		{"label": _("Bill Date"), "fieldname": "bill_date", "fieldtype": "Date", "width": 95},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 70,
		},
		{
			"label": _("Exch. Rate"),
			"fieldname": "conversion_rate",
			"fieldtype": "Float",
			"precision": 6,
			"width": 90,
		},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 120},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("VAT Category"), "fieldname": "vat_category", "fieldtype": "Data", "width": 110},
		{"label": _("Net Amount"), "fieldname": "base_net_amount", "width": 130, **_CURRENCY},
		{"label": _("Input VAT"), "fieldname": "input_vat_amount", "width": 110, **_CURRENCY},
		{"label": _("Output VAT"), "fieldname": "output_vat_amount", "width": 110, **_CURRENCY},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 200},
	]


def get_data(filters) -> list[dict]:
	"""Transaction-level counterpart to the Sales/Purchase registers: one row per invoice item
	from the same `get_invoice_rows()` fetch the Oman VAT Return uses (so Out of Scope exclusion,
	item-wise VAT parsing and the company permission check are shared, not re-derived), tagged
	with the box from `get_box_code()`. Credit/debit notes keep ERPNext's negative amounts so
	totals net correctly. Output VAT is the self-accounted liability on reverse-charge purchases."""
	doctypes = {"Sales": ["Sales Invoice"], "Purchase": ["Purchase Invoice"]}.get(
		filters.get("transaction_type"), ["Sales Invoice", "Purchase Invoice"]
	)

	rows = []
	for doctype in doctypes:
		rows += get_doctype_rows(doctype, filters)

	if filters.get("box_code"):
		rows = [row for row in rows if row["box_code"] == filters.box_code]
	if filters.get("party"):
		rows = [row for row in rows if row["party"] == filters.party]

	return sorted(
		rows,
		key=lambda r: (
			r["transaction_type"] != "Purchase",
			r["box_code"],
			str(r["posting_date"]),
			r["invoice"],
		),
	)


def get_doctype_rows(doctype: str, filters) -> list[dict]:
	is_sales = doctype == "Sales Invoice"
	invoice_rows = get_invoice_rows(doctype, filters.company, filters.from_date, filters.to_date)
	parties = {row.customer if is_sales else row.supplier for row in invoice_rows}
	party_info = get_party_info("Customer" if is_sales else "Supplier", parties)

	result = []
	for row in invoice_rows:
		party = row.customer if is_sales else row.supplier
		info = party_info.get(party, {})
		result.append(
			{
				"transaction_type": _("Sales") if is_sales else _("Purchase"),
				"box_code": get_box_code(doctype, row),
				"transaction": get_transaction_label(is_sales, row.is_return),
				"voucher_type": doctype,
				"invoice": row.invoice,
				"posting_date": row.posting_date,
				"party": party,
				"party_name": row.customer_name if is_sales else row.supplier_name,
				"party_trn": row.tax_id or info.get("trn"),
				"party_country": info.get("country"),
				"bill_no": row.invoice if is_sales else row.bill_no,
				"bill_date": row.posting_date if is_sales else row.bill_date,
				"currency": row.currency,
				"conversion_rate": row.conversion_rate,
				"item_code": row.item_code,
				"item_name": row.item_name,
				"vat_category": row.vat_category,
				"base_net_amount": row.base_net_amount,
				"input_vat_amount": row.input_vat_amount,
				"output_vat_amount": row.output_vat_amount,
				"remarks": row.remarks,
			}
		)

	return result


def get_transaction_label(is_sales: bool, is_return: bool) -> str:
	if is_sales:
		return _("Credit Note") if is_return else _("Customer Invoice")
	return _("Debit Note") if is_return else _("Supplier Invoice")


def get_party_info(party_type: str, parties: set) -> dict[str, dict]:
	"""TRN and (first linked address's) country per party."""
	if not parties:
		return {}

	info = {
		party.name: {"trn": party.oman_trn}
		for party in frappe.get_all(
			party_type, filters={"name": ["in", list(parties)]}, fields=["name", "oman_trn"]
		)
	}
	links = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": party_type, "link_name": ["in", list(parties)], "parenttype": "Address"},
		fields=["link_name", "parent"],
		order_by="creation",
	)
	countries = {
		address.name: address.country
		for address in frappe.get_all(
			"Address",
			filters={"name": ["in", [link.parent for link in links]]},
			fields=["name", "country"],
		)
	}
	for link in links:
		info.setdefault(link.link_name, {}).setdefault("country", countries.get(link.parent))

	return info
