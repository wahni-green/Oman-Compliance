from oman_compliance.oman_compliance.constants import VAT_CATEGORY_SELECT_OPTIONS

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
		{
			"fieldname": "designated_zone",
			"label": "Designated Zone",
			"fieldtype": "Link",
			"options": "Designated Zone",
			"insert_after": "country",
			"translatable": 0,
			"description": "Set if this address is inside an Oman VAT designated/free zone (Duqm,"
			" Salalah, Sohar, Al Mazunah). Used to default line items on transactions to Zero Rated"
			" per Article 54 — confirm actual eligibility before relying on the default.",
			"module": MODULE,
		},
	],
	(
		"Sales Order Item",
		"Quotation Item",
		"Delivery Note Item",
		"Sales Invoice Item",
		"Purchase Invoice Item",
	): [
		{
			"fieldname": "vat_category",
			"label": "VAT Category",
			"fieldtype": "Select",
			"options": VAT_CATEGORY_SELECT_OPTIONS,
			"insert_after": "item_tax_template",
			"in_list_view": 1,
			"translatable": 0,
			"description": "Standard-rated, zero-rated, exempt, or out-of-scope for Oman VAT purposes"
			" (findings §51/85). Left blank, this is defaulted automatically on save.",
			"module": MODULE,
		},
	],
	"Item Tax Template": [
		{
			"fieldname": "vat_category",
			"label": "VAT Category",
			"fieldtype": "Select",
			"options": VAT_CATEGORY_SELECT_OPTIONS,
			"insert_after": "disabled",
			"translatable": 0,
			"description": "Set this so transactions using this template can default and validate their"
			" own VAT Category from it, rather than relying on a designated-zone guess or a bare tax rate"
			" that can't tell Zero Rated apart from Exempt or Out of Scope (all commonly 0%).",
			"module": MODULE,
		},
		{
			"fieldname": "fetch_vat_accounts",
			"label": "Fetch VAT Accounts",
			"fieldtype": "Button",
			"insert_after": "section_break_5",
			"description": "Adds a row below for each of this Company's configured Output/Input VAT"
			" Accounts (Oman VAT Settings) not already present here.",
			"module": MODULE,
		},
	],
	"Purchase Invoice": [
		{
			"fieldname": "is_reverse_charge",
			"label": "Reverse Charge Applicable",
			"fieldtype": "Check",
			"insert_after": "tax_category",
			"translatable": 0,
			"description": "Check for imported services and other reverse-charge supplies where this"
			" company must self-account for output VAT as the recipient (Oman VAT return box 2,"
			" findings §56/86). Requires VAT rows on this invoice for the self-accounting entries.",
			"module": MODULE,
		},
		{
			"fieldname": "is_import_of_goods",
			"label": "Import of Goods",
			"fieldtype": "Check",
			"insert_after": "is_reverse_charge",
			"read_only": 1,
			"translatable": 0,
			"description": "Automatically set from the Dispatch Address's country (Oman VAT return"
			" box 4 — distinct from Reverse Charge above, which covers imported services, not goods)."
			" A blank Dispatch Address is treated as not an import.",
			"module": MODULE,
		},
	],
}
