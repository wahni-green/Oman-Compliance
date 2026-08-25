import frappe

from oman_compliance.oman_compliance.overrides.purchase_invoice import (
	is_gcc_supplier_candidate,
	is_import_of_goods_candidate,
)
from oman_compliance.oman_compliance.overrides.sales_invoice import is_export_candidate


@frappe.whitelist()
def backfill_classification_flags(company: str | None = None) -> dict:
	"""One-time, explicitly-invoked recomputation of `is_export` (Sales Invoice) and
	`is_gcc_supplier`/`is_import_of_goods` (Purchase Invoice) for already-submitted invoices whose
	value is still unset. These are read-only, computed-on-validate fields
	(`overrides/sales_invoice.py::set_export_flag`, `overrides/purchase_invoice.py::
	set_gcc_supplier_flag`/`set_import_of_goods_flag`) — a submitted invoice's `validate()` never
	runs again on its own, so any invoice submitted before these fields existed is left with an
	unset (falsy) value even if it genuinely was an export/GCC purchase/import, which
	`generate_return()` would then silently read as "no" for a historical period.

	Deliberately NOT wired into `patches.txt` as an automatic `bench migrate` step: this app has
	no live deployment yet with real historical invoice data to correct, and silently recomputing
	a classification flag across every submitted invoice on every affected site's next migrate is a
	materially bigger, more surprising action than this app's other patches (which only ever touch
	reference/settings data — Designated Zones, custom field definitions — never bulk-edit
	transactional documents). An admin adopting this phase on a site with pre-existing invoice
	history should run this once, deliberately, e.g. via `bench execute
	oman_compliance.oman_compliance.utils.vat_return.backfill.backfill_classification_flags`, not
	have it happen invisibly on every site's next migrate.

	`is_postponed_import_vat` is intentionally not backfilled — it's a manual customs election with
	no derivable data, so there's nothing to compute for a historical invoice; an admin must set it
	by hand for any historical import where postponed payment was actually elected.

	Uses `db_set`, not a full `doc.save()`, per invoice: these are already-submitted documents, and
	re-running their whole validate()/before_save() chain is neither necessary nor safe for a bulk
	historical correction — only the specific classification field(s) are touched. Returns a count
	of how many rows were changed, for the caller to sanity-check. Deliberately does not call
	`frappe.db.commit()` itself — both real invocation paths (`bench execute`, and a whitelisted
	API call through the normal web request cycle) already commit once this returns; committing
	here too would force-commit mid-transaction for any other caller (a test, or code composing
	this into a larger unit of work), permanently baking in whatever that caller had done earlier
	in the same transaction.

	Restricted to System Manager: this bypasses ordinary document permissions entirely (`db_set`
	writes straight to the database) and can touch every submitted invoice on the site, which is
	well beyond what any lesser role should be able to trigger."""
	frappe.only_for("System Manager")

	filters = {"docstatus": 1, "is_export": 0}
	if company:
		filters["company"] = company

	updated = {"sales_invoice": 0, "purchase_invoice": 0}

	for invoice in frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=["name", "company", "shipping_address_name", "customer_address"],
	):
		if is_export_candidate(invoice):
			frappe.db.set_value("Sales Invoice", invoice.name, "is_export", 1)
			updated["sales_invoice"] += 1

	purchase_filters = {"docstatus": 1}
	if company:
		purchase_filters["company"] = company

	for invoice in frappe.get_all(
		"Purchase Invoice",
		filters=purchase_filters,
		fields=[
			"name",
			"company",
			"supplier_address",
			"dispatch_address",
			"is_gcc_supplier",
			"is_import_of_goods",
		],
	):
		changes = {}
		if not invoice.is_gcc_supplier and is_gcc_supplier_candidate(invoice):
			changes["is_gcc_supplier"] = 1
		if not invoice.is_import_of_goods and is_import_of_goods_candidate(invoice):
			changes["is_import_of_goods"] = 1

		if changes:
			frappe.db.set_value("Purchase Invoice", invoice.name, changes)
			updated["purchase_invoice"] += 1

	return updated
