import frappe
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
from frappe.utils import getdate

TEST_COMPANY = "_Test Oman VAT Company"


def before_tests() -> None:
	frappe.clear_cache()

	# Matches India Compliance's before_tests(): only bootstraps if no Company
	# exists at all, since setup_complete() is a one-time site setup step. On a
	# site that already has a Company (e.g. a shared bench running other apps'
	# tests), TEST_COMPANY is never created here — run this app's tests on a
	# dedicated site if that matters.
	if not frappe.db.a_row_exists("Company"):
		year = getdate().year

		setup_complete(
			{
				"currency": "OMR",
				"full_name": "Test User",
				"company_name": TEST_COMPANY,
				"timezone": "Asia/Muscat",
				"company_abbr": "TOVC",
				"industry": "Manufacturing",
				"country": "Oman",
				"fy_start_date": f"{year}-01-01",
				"fy_end_date": f"{year}-12-31",
				"language": "English",
				"company_tagline": "Testing",
				"email": "test@example.com",
				"password": "test",
				"chart_of_accounts": "Standard",
			}
		)

		frappe.db.set_value("Company", TEST_COMPANY, "tax_id", "OM1234567890")

	if frappe.db.exists("Company", TEST_COMPANY):
		set_default_company_for_tests()

	frappe.db.commit()  # nosemgrep

	frappe.flags.country = "Oman"


def set_default_company_for_tests() -> None:
	global_defaults = frappe.get_single("Global Defaults")
	global_defaults.default_company = TEST_COMPANY
	global_defaults.save()
