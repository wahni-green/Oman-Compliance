import frappe


def get_output_vat_account(company: str | None) -> str | None:
	"""The given company's configured Output VAT account (Oman VAT Settings' per-company
	`vat_accounts` table). Used to identify a Sales Taxes and Charges / Purchase Taxes and Charges
	row as genuinely VAT — explicitly configured rather than guessed from account type, since
	ERPNext's generic account types (Chargeable, Expense Account, ...) are shared with unrelated
	charges (freight, discount, withholding, ...) and can't reliably tell them apart. Matches how
	India Compliance's GST Settings names its GST accounts explicitly, per company
	(`gst_accounts`), instead of inferring them from account type."""
	if not company:
		return None

	settings = frappe.get_cached_doc("Oman VAT Settings")
	for row in settings.vat_accounts:
		if row.company == company:
			return row.output_vat_account

	return None


def is_output_vat_account(account_head: str | None, company: str | None) -> bool:
	"""Whether a Taxes and Charges row's account is the given company's configured Output VAT
	account."""
	if not account_head:
		return False

	return account_head == get_output_vat_account(company)


# TODO (not yet implemented — tracked in OMAN_COMPLIANCE_PLAN.md Phase 2):
# 1. Validate, on Item Tax Template itself, that its `taxes` rows actually reference the
#    company's configured Output VAT Account — mirroring India Compliance's
#    gst_india/overrides/item_tax_template.py::validate_tax_rates(), which checks the template's
#    tax rows against the company's configured GST accounts (via get_valid_accounts()) and throws
#    on a mismatch, rather than silently allowing a VAT-category-tagged template with the wrong
#    account wired in.
# 2. A "Fetch Account" button on Item Tax Template (client script + a new
#    @frappe.whitelist() method here, e.g. get_output_vat_account_for_template(company)) that
#    auto-adds the missing `taxes` row for the company's configured Output VAT Account —
#    mirroring India Compliance's gst_india/client_scripts/item_tax_template.js
#    (fetch_and_update_missing_gst_accounts(), bound to a `fetch_gst_accounts` button field) and
#    its server-side gst_india/overrides/item_tax_template.py::get_valid_gst_accounts().
