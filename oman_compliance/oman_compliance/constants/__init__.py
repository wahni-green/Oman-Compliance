import re

# Provisional TRN format only — the Oman Tax Authority (OTA) has not published an official TRN
# specification (see OMAN_COMPLIANCE_ARCHITECTURE.md §3, open question 1). Assumed shape: "OM"
# followed by 10 digits, matching the placeholder already used by the test company fixture in
# tests/__init__.py. Update this pattern once OTA's Fawtara integration guide confirms the real
# format (and add the checksum check alongside it, if one exists).
TRN_PATTERN = re.compile(r"^OM[0-9]{10}$")

# The four VAT categories the legacy app never modeled (findings §51/85) — "Out of Scope" in
# particular was entirely missing there.
VAT_CATEGORIES = ["Standard Rated", "Zero Rated", "Exempt", "Out of Scope"]
DEFAULT_VAT_CATEGORY = "Standard Rated"
ZONE_DEFAULT_VAT_CATEGORY = "Zero Rated"
NO_TAX_VAT_CATEGORIES = {"Zero Rated", "Exempt", "Out of Scope"}

# A leading blank option, not just "\n".join(VAT_CATEGORIES): Frappe auto-fills any Select field
# with no explicit `default` to its *first* option on every new document/child row
# (frappe.model.create_new.get_static_default_value), before our own validate() hooks ever run.
# Without the blank line, every new row would silently arrive at our defaulting logic already
# set to "Standard Rated", never actually blank — quietly defeating the zone/template-based
# defaulting entirely. This is the same leading-blank-option idiom Frappe/ERPNext's own optional
# Select fields use for exactly this reason.
VAT_CATEGORY_SELECT_OPTIONS = "\n" + "\n".join(VAT_CATEGORIES)
