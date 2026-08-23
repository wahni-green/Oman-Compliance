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


def get_test_tax_account() -> tuple[str, str]:
	"""Return (account_name, company) for any existing account usable as an Item Tax Template row
	— for tests that need a throwaway Item Tax Template fixture without depending on this app's
	own TEST_COMPANY existing (it may not, on a shared bench; see before_tests() above)."""
	account = frappe.db.get_value(
		"Account",
		{
			"account_type": ["in", ["Tax", "Chargeable", "Income Account", "Expense Account"]],
			"is_group": 0,
		},
		["name", "company"],
	)
	if not account:
		frappe.throw("No usable Tax/Chargeable/Income/Expense account found for test fixtures.")

	return account


def get_oman_test_company() -> str:
	"""Return the name of a Company registered in Oman, creating a minimal one if none exists yet
	on this bench — needed by any test exercising Oman-company-gated behavior (see
	utils/company.py::is_oman_company()). Created uncommitted, inside the calling test's own DB
	transaction, so FrappeTestCase's per-test rollback cleans it up automatically; no explicit
	deletion needed."""
	existing = frappe.db.get_value("Company", {"country": "Oman"})
	if existing:
		return existing

	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": "_Test Oman Gating Company",
			"abbr": "TOGC",
			"default_currency": "OMR",
			"country": "Oman",
		}
	).insert(ignore_permissions=True)

	return company.name
