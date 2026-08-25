import itertools
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import frappe
from frappe.desk.page.setup_wizard.setup_wizard import setup_complete
from frappe.utils import add_days, getdate

TEST_COMPANY = "_Test Oman VAT Company"

_test_date_counter = itertools.count()


def get_unique_test_date():
	"""A fresh Date, never repeated within a test run — needed because
	`frappe.tests.utils.FrappeTestCase` only rolls back once per test *class*
	(`addClassCleanup(_rollback_db)`), not after each test method. Two sibling test methods that
	both created a Sales/Purchase Invoice dated `today()` (the natural default) would otherwise see
	each other's invoices too, since nothing rolls back between them — a real VAT return period
	query has no way to tell "this test's invoice" apart from "the previous test method's invoice"
	if both happen to fall on the same day. Callers should use this same date for both the fixture
	invoice's `posting_date` and the from_date/to_date passed to whatever section function reads it
	back, keeping each test's period fully isolated from its siblings.

	Offsets from the *current* Fiscal Year's start date, not a hardcoded calendar date — a
	submitted invoice dated outside every configured Fiscal Year fails ERPNext's own
	`validate_date_with_fiscal_year()` before it ever reaches this app's own validation. On a truly
	fresh site, `before_tests()`'s `setup_complete()` only creates the fiscal year covering
	*today*, so anchoring anywhere else (e.g. a fixed 2020-01-01) would only work by coincidence of
	whatever Fiscal Year records happen to already exist on a given bench."""
	from erpnext.accounts.utils import get_fiscal_year

	_, fiscal_year_start, _ = get_fiscal_year(getdate())
	return add_days(fiscal_year_start, next(_test_date_counter))


@contextmanager
def _without_broken_third_party_hooks():
	"""This shared bench has other apps installed (`galfar`, `erpnext`) whose doc_event hooks
	assume custom fields that were never actually installed here — a pre-existing environment gap
	unrelated to Oman Compliance, not something this app owns or should fix by patching shared
	Contact/Customer/Address schema. Every real Sales/Purchase Invoice submission runs into two
	of them regardless of what else is installed: ERPNext's own
	`accounts/party.py::get_default_contact()` (queries `Contact.is_billing_contact`) and
	`get_address_tax_category()` (queries `Address.tax_category` — both normally present on a
	fully migrated ERPNext install) via `set_missing_values`. The third,
	`galfar.overrides.sales_invoice.validate_overdue_customers` (queries `Customer.is_walkin`, a
	`galfar` custom field) via Sales Invoice's own `validate`, only applies when `galfar` is
	actually installed — this app's own `required_apps` (hooks.py) never lists it, so patching that
	target unconditionally would raise ModuleNotFoundError on any bench (e.g. CI) that doesn't
	happen to have `galfar` installed too."""
	patches = [
		patch("erpnext.accounts.party.get_default_contact", return_value=None),
		patch("erpnext.accounts.party.get_address_tax_category", return_value=""),
	]
	if "galfar" in frappe.get_installed_apps():
		patches.append(patch("galfar.overrides.sales_invoice.validate_overdue_customers", return_value=None))

	with ExitStack() as stack:
		for target in patches:
			stack.enter_context(target)
		yield


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


def get_non_oman_test_company() -> str:
	"""Return the name of a Company registered somewhere other than Oman, creating a minimal one
	if none exists yet. Used by tests confirming Oman-company-gated behavior leaves a non-Oman
	company's transactions untouched — deliberately not a hardcoded literal like "Dev Server",
	since that only happens to exist on this particular shared bench and wouldn't exercise
	anything real (or even exist) elsewhere; frappe.get_cached_value() needs a genuine Company
	record with a genuine non-Oman country to actually be exercised."""
	existing = frappe.db.get_value("Company", {"country": ["!=", "Oman"]})
	if existing:
		return existing

	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": "_Test Non-Oman Gating Company",
			"abbr": "TNOGC",
			"default_currency": "USD",
			"country": "United Arab Emirates",
		}
	).insert(ignore_permissions=True)

	return company.name


def set_vat_accounts(
	company: str, output_account: str | None = None, input_account: str | None = None
) -> None:
	"""Configure Oman VAT Settings' per-company `vat_accounts` table with the given company's
	Output/Input VAT Accounts (either may be omitted to leave that one unset), replacing any
	existing row for that company. Test-only: relies on FrappeTestCase's per-test rollback to undo
	it afterward, matching how other Single-doctype settings are exercised elsewhere in this test
	suite."""
	settings = frappe.get_single("Oman VAT Settings")
	settings.vat_accounts = [row for row in settings.vat_accounts if row.company != company]
	settings.append(
		"vat_accounts",
		{"company": company, "output_vat_account": output_account, "input_vat_account": input_account},
	)
	settings.save(ignore_permissions=True)


def get_oman_test_vat_accounts(company: str) -> tuple[str, str]:
	"""Two dedicated leaf Account records for `company`, for use as its Output/Input VAT Account
	when a test needs to build and submit a *real* Sales/Purchase Invoice — unlike
	get_test_tax_account() (which finds an account on *any* company, fine for a throwaway Item Tax
	Template that isn't tied to a specific transactional company), a real invoice's tax row account
	must belong to the exact same company as the invoice itself. Created idempotently by name, so
	calling this more than once for the same company within one test is safe."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	parent_account = frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Liability", "is_group": 1, "parent_account": ["is", "not set"]},
	)

	accounts = []
	for account_name in ("Test Output VAT", "Test Input VAT"):
		full_name = f"{account_name} - {abbr}"
		if not frappe.db.exists("Account", full_name):
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": account_name,
					"company": company,
					"parent_account": parent_account,
					"account_type": "Tax",
					"is_group": 0,
				}
			).insert(ignore_permissions=True)
		accounts.append(full_name)

	return accounts[0], accounts[1]


def get_or_create_test_item(
	is_stock_item: int = 0, is_fixed_asset: int = 0, company: str | None = None
) -> str:
	"""A throwaway Item, shared across VAT return tests that don't care about stock/valuation —
	only about the amounts/categories a Sales/Purchase Invoice Item row carries. A separate item
	code for `is_fixed_asset=1` since ERPNext resets a Purchase Invoice Item row's own
	`is_fixed_asset` flag from the Item master's flag during `set_missing_values` — setting it only
	on the invoice row (not the Item itself) silently gets overwritten back to 0. Created
	idempotently by name."""
	if is_fixed_asset:
		return _get_or_create_test_fixed_asset_item(company)

	item_code = "_Test VAT Return Item"
	if frappe.db.exists("Item", item_code):
		return item_code

	return (
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Services" if not is_stock_item else "Products",
				"is_stock_item": is_stock_item,
				"stock_uom": "Nos",
			}
		)
		.insert(ignore_permissions=True)
		.item_code
	)


def _get_or_create_test_fixed_asset_item(company: str) -> str:
	item_code = "_Test VAT Return Fixed Asset Item"
	if frappe.db.exists("Item", item_code):
		return item_code

	asset_category = "_Test VAT Return Asset Category"
	if not frappe.db.exists("Asset Category", asset_category):
		abbr = frappe.get_cached_value("Company", company, "abbr")
		fixed_asset_account = f"Test Fixed Asset - {abbr}"
		if not frappe.db.exists("Account", fixed_asset_account):
			parent_account = frappe.db.get_value(
				"Account", {"company": company, "account_name": "Fixed Assets"}
			)
			frappe.get_doc(
				{
					"doctype": "Account",
					"account_name": "Test Fixed Asset",
					"company": company,
					"parent_account": parent_account,
					"account_type": "Fixed Asset",
					"is_group": 0,
				}
			).insert(ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Asset Category",
				"asset_category_name": asset_category,
				"enable_cwip_accounting": 0,
				"accounts": [{"company_name": company, "fixed_asset_account": fixed_asset_account}],
				# Same unrelated-app workaround as get_or_create_test_supplier()'s cr_number: the
				# `galfar` app's generic "validate": galfar.utils.set_abbreviation hook (wired to
				# several doctypes, Asset Category included) reads doc.abbr unconditionally.
				"abbr": None,
			}
		).insert(ignore_permissions=True)

	return (
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": item_code,
				"item_group": "Products",
				"is_stock_item": 0,
				"is_fixed_asset": 1,
				"asset_category": asset_category,
				"stock_uom": "Nos",
			}
		)
		.insert(ignore_permissions=True)
		.item_code
	)


def create_test_address(
	country: str, address_type: str = "Billing", link_doctype: str | None = None, link_name: str | None = None
) -> str:
	"""A fresh Address in the given country — used to drive this app's country-comparison flags
	(is_export, is_gcc_supplier, is_import_of_goods) in tests that need a real submitted invoice,
	not a frappe._dict mock. Always creates a new record (Address names are auto-generated, so
	repeated calls never collide) since FrappeTestCase's per-test rollback cleans it up.

	`link_doctype`/`link_name` add a Dynamic Link row — required for `customer_address`/
	`shipping_address_name` on a Sales Invoice and `supplier_address` on a Purchase Invoice, since
	ERPNext's own `accounts_controller.py::validate_party_address` rejects an address that isn't
	linked to the invoice's own party. `dispatch_address` has no such check, so callers building one
	of those can leave this unset."""
	doc = {
		"doctype": "Address",
		"address_title": f"_Test VAT Return Address {frappe.generate_hash(length=8)}",
		"address_type": address_type,
		"address_line1": "Test Address Line",
		"city": "Test City",
		"country": country,
	}
	if link_doctype and link_name:
		doc["links"] = [{"link_doctype": link_doctype, "link_name": link_name}]

	return frappe.get_doc(doc).insert(ignore_permissions=True).name


def get_or_create_test_customer(company: str) -> str:
	"""A fresh Customer, every call — deliberately NOT idempotent-by-name like most other fixture
	helpers here. `frappe.tests.utils.FrappeTestCase` only rolls back once per test *class*
	(`addClassCleanup`), so a shared, reused Customer would accumulate linked Addresses (see
	create_test_address()'s `links`) across sibling test methods in the same class — and ERPNext's
	own `get_party_details()` auto-fills a blank `shipping_address_name`/`customer_address` from
	whatever's already linked to the customer, silently making a later "no address" test look like
	it has one. A brand-new Customer per invoice avoids that class of cross-test leakage entirely."""
	return (
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": f"_Test VAT Return Customer {frappe.generate_hash(length=8)}",
				"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}),
				"territory": frappe.db.get_value("Territory", {"is_group": 0}),
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def get_or_create_test_supplier() -> str:
	"""Purchase-side counterpart to get_or_create_test_customer() — see its docstring for why this
	is a fresh Supplier every call rather than idempotent-by-name."""
	return (
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": f"_Test VAT Return Supplier {frappe.generate_hash(length=8)}",
				"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}),
				# This bench also has the unrelated `galfar` app installed, whose Supplier `validate`
				# hook (galfar/crud_events/supplier.py::set_expiry_date) reads `doc.cr_number`
				# unconditionally — not a field this app defines or cares about, but omitting it here
				# raises an AttributeError on that hook before our own document even finishes
				# inserting. Passing it explicitly avoids depending on another app's fixture.
				"cr_number": None,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def create_submitted_sales_invoice(
	company: str,
	*,
	vat_category: str = "Standard Rated",
	output_vat_account: str | None = None,
	rate: float = 0,
	net_amount: float = 100,
	shipping_country: str | None = None,
	customer_country: str | None = None,
	is_return: bool = False,
	return_against: str | None = None,
	posting_date: str | None = None,
	extra_item_net_amounts: list[float] | None = None,
):
	"""Builds and submits a real, minimal Sales Invoice for `company` — one non-stock item row
	carrying `vat_category`, an optional Output VAT tax row, and — if `shipping_country`/
	`customer_country` is given — a fresh Address in that country, linked to the customer and set
	as `shipping_address_name`/`customer_address`, to drive this app's `is_export` computation.
	`utils/vat_return` section functions read genuinely computed `base_net_amount`/
	`item_wise_tax_detail` fields, so section-function tests need a real submitted document, not a
	frappe._dict mock (unlike the override-level tests elsewhere in this suite, which only exercise
	a single validate function against already-validated doc data). Pass `posting_date` (see
	get_unique_test_date()) rather than leaving it defaulted whenever the test also queries a
	specific period — FrappeTestCase's per-class (not per-test) rollback means sibling test
	methods' invoices would otherwise share today's date and pollute each other's query window.

	`extra_item_net_amounts` adds further rows sharing the *same* item_code and `vat_category` as
	the main row (net amount `net_amount`) — for testing get_invoice_rows()'s handling of
	`item_wise_tax_detail`, which is keyed by item_code, not row. All rows share one category since
	`validate_no_mixed_vat_category_per_item_code` blocks a mismatched one from ever submitting —
	a test needing that mismatched state has to force it in after the fact (e.g. `db_set` on one
	row), the same way a test simulates any other pre-existing/pre-this-check invoice."""
	item_code = get_or_create_test_item()
	# A return must share its original invoice's own customer (ERPNext's own
	# validate_return_against enforces this) — a fresh customer per call is right for an
	# independent invoice, but wrong here.
	customer = (
		frappe.db.get_value("Sales Invoice", return_against, "customer")
		if return_against
		else get_or_create_test_customer(company)
	)
	sign = -1 if is_return else 1

	shipping_address = (
		create_test_address(shipping_country, "Shipping", "Customer", customer) if shipping_country else None
	)
	customer_address = (
		create_test_address(customer_country, "Billing", "Customer", customer) if customer_country else None
	)

	doc = frappe.get_doc(
		{
			"doctype": "Sales Invoice",
			"company": company,
			"customer": customer,
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
			"conversion_rate": 1,
			"posting_date": posting_date,
			"set_posting_time": 1 if posting_date else 0,
			"is_return": 1 if is_return else 0,
			"return_against": return_against,
			"customer_address": customer_address,
			"shipping_address_name": shipping_address,
			"items": [
				{
					"item_code": item_code,
					"item_name": item_code,
					"qty": sign,
					"rate": amount,
					"vat_category": vat_category,
					"income_account": frappe.get_cached_value("Company", company, "default_income_account"),
					"cost_center": frappe.get_cached_value("Company", company, "cost_center"),
				}
				for amount in (net_amount, *(extra_item_net_amounts or []))
			],
			"taxes": (
				[
					{
						"charge_type": "On Net Total",
						"account_head": output_vat_account,
						"description": "VAT",
						"rate": rate,
					}
				]
				if output_vat_account
				else []
			),
		}
	)
	with _without_broken_third_party_hooks():
		doc.insert(ignore_permissions=True)
		doc.submit()
	return doc


def create_submitted_purchase_invoice(
	company: str,
	*,
	vat_category: str = "Standard Rated",
	output_vat_account: str | None = None,
	input_vat_account: str | None = None,
	output_rate: float = 0,
	input_rate: float = 0,
	net_amount: float = 100,
	is_reverse_charge: bool = False,
	is_fixed_asset: int = 0,
	dispatch_country: str | None = None,
	supplier_country: str | None = None,
	is_postponed_import_vat: bool = False,
	is_return: bool = False,
	return_against: str | None = None,
	posting_date: str | None = None,
):
	"""Purchase-side counterpart to create_submitted_sales_invoice — builds and submits a real,
	minimal Purchase Invoice, with separate Output/Input VAT tax rows since Reverse Charge
	self-accounting (and this app's box 2/4/6 reads) need both distinguished, not just one generic
	"VAT" row. `dispatch_country`/`supplier_country` each create a fresh Address in that country —
	dispatch needs no party link (ERPNext doesn't validate it against the supplier), but the
	supplier address does, so it's linked to the supplier."""
	item_code = get_or_create_test_item(is_fixed_asset=is_fixed_asset, company=company)
	# Same reasoning as create_submitted_sales_invoice: a return must share its original
	# invoice's own supplier.
	supplier = (
		frappe.db.get_value("Purchase Invoice", return_against, "supplier")
		if return_against
		else get_or_create_test_supplier()
	)
	sign = -1 if is_return else 1

	dispatch_address = create_test_address(dispatch_country, "Shipping") if dispatch_country else None
	supplier_address = (
		create_test_address(supplier_country, "Billing", "Supplier", supplier) if supplier_country else None
	)

	taxes = []
	if output_vat_account:
		taxes.append(
			{
				"charge_type": "On Net Total",
				"account_head": output_vat_account,
				"description": "Output VAT",
				"rate": output_rate,
			}
		)
	if input_vat_account:
		taxes.append(
			{
				"charge_type": "On Net Total",
				"account_head": input_vat_account,
				"description": "Input VAT",
				"rate": input_rate,
			}
		)

	doc = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": company,
			"supplier": supplier,
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
			"conversion_rate": 1,
			"posting_date": posting_date,
			"set_posting_time": 1 if posting_date else 0,
			"is_return": 1 if is_return else 0,
			"return_against": return_against,
			"is_reverse_charge": 1 if is_reverse_charge else 0,
			"is_postponed_import_vat": 1 if is_postponed_import_vat else 0,
			"dispatch_address": dispatch_address,
			"supplier_address": supplier_address,
			"items": [
				{
					"item_code": item_code,
					"item_name": item_code,
					"qty": sign,
					"rate": net_amount,
					"vat_category": vat_category,
					"is_fixed_asset": is_fixed_asset,
					"expense_account": frappe.get_cached_value("Company", company, "default_expense_account"),
					"cost_center": frappe.get_cached_value("Company", company, "cost_center"),
				}
			],
			"taxes": taxes,
		}
	)
	with _without_broken_third_party_hooks():
		doc.insert(ignore_permissions=True)
		doc.submit()
	return doc
