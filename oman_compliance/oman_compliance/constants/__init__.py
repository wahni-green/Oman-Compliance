import re

# Provisional TRN format only — the Oman Tax Authority (OTA) has not published an official TRN
# specification (see OMAN_COMPLIANCE_ARCHITECTURE.md §3, open question 1). Assumed shape: "OM"
# followed by 10 digits, matching the placeholder already used by the test company fixture in
# tests/__init__.py. Update this pattern once OTA's Fawtara integration guide confirms the real
# format (and add the checksum check alongside it, if one exists).
TRN_PATTERN = re.compile(r"^OM\d{10}$")
