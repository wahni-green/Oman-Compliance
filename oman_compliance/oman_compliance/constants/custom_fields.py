MODULE = "Oman Compliance"

CUSTOM_FIELDS = {
	"Company": [
		{
			"fieldname": "company_name_in_arabic",
			"label": "Company Name in Arabic",
			"fieldtype": "Data",
			"insert_after": "company_name",
			"translatable": 0,
			"module": MODULE,
		},
	],
	("Company", "Customer", "Supplier"): [
		{
			"fieldname": "oman_trn",
			"label": "TRN",
			"fieldtype": "Data",
			"insert_after": "tax_id",
			"translatable": 0,
			"description": "Oman Tax Registration Number. Kept separate from the generic Tax ID field since"
			" other compliance apps on this site may use Tax ID for their own country's format.",
			"module": MODULE,
		},
	],
	"Customer": [
		{
			"fieldname": "customer_name_in_arabic",
			"label": "Customer Name in Arabic",
			"fieldtype": "Data",
			"insert_after": "customer_name",
			"translatable": 0,
			"module": MODULE,
		},
	],
	"Supplier": [
		{
			"fieldname": "supplier_name_in_arabic",
			"label": "Supplier Name in Arabic",
			"fieldtype": "Data",
			"insert_after": "supplier_name",
			"translatable": 0,
			"module": MODULE,
		},
	],
	"Address": [
		{
			"fieldname": "address_in_arabic",
			"label": "Address in Arabic",
			"fieldtype": "Small Text",
			"insert_after": "address_line2",
			"translatable": 0,
			"module": MODULE,
		},
	],
}
