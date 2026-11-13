frappe.query_reports["Oman VAT Transaction Summary"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_end(),
			reqd: 1,
		},
		{
			fieldname: "transaction_type",
			label: __("Purchase / Sales"),
			fieldtype: "Select",
			options: "\nPurchase\nSales",
		},
		{
			fieldname: "box_code",
			label: __("Box"),
			fieldtype: "Select",
			options: "\n1(a)\n1(b)\n1(c)\n2(a)\n2(b)\n3(a)\n4(a)\n4(b)\n6",
		},
		{
			fieldname: "party",
			label: __("Customer / Supplier"),
			fieldtype: "Data",
		},
	],
};
