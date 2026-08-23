MODULE = "Oman Compliance"

CUSTOM_FIELDS = {
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
}
