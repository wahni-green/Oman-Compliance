frappe.ui.form.on("Item Tax Template", {
	refresh: show_missing_vat_accounts_banner,
	fetch_vat_accounts: fetch_and_add_missing_vat_accounts,
});

async function show_missing_vat_accounts_banner(frm) {
	if (frm.doc.__islocal) return;

	const missing_accounts = await get_missing_vat_accounts(frm);
	if (!missing_accounts || !missing_accounts.length) return;

	frm.dashboard.add_comment(
		__("<strong>Missing VAT Accounts:</strong> {0}", [missing_accounts.join(", ")]),
		"orange",
		true
	);
}

async function fetch_and_add_missing_vat_accounts(frm) {
	// Guards against a second click landing while the first fetch is still awaiting its server
	// round-trip: both would otherwise read frm.doc.taxes before either had added a row, see the
	// same "missing" accounts, and each add_child() a duplicate row for the same account.
	if (frm._fetching_vat_accounts) return;
	frm._fetching_vat_accounts = true;

	try {
		const missing_accounts = await get_missing_vat_accounts(frm);
		if (!missing_accounts || !missing_accounts.length) return;

		missing_accounts.forEach((account) => {
			frm.add_child("taxes", { tax_type: account, tax_rate: 0 });
		});

		frm.refresh_field("taxes");
	} finally {
		frm._fetching_vat_accounts = false;
	}
}

async function get_missing_vat_accounts(frm) {
	const vat_accounts = await get_vat_accounts(frm);
	if (!vat_accounts || !vat_accounts.length) return;

	const template_accounts = (frm.doc.taxes || []).map((row) => row.tax_type);
	const missing_accounts = vat_accounts.filter(
		(account) => account && !template_accounts.includes(account)
	);

	if (missing_accounts.length) return missing_accounts;
}

async function get_vat_accounts(frm) {
	const company = frm.doc.company;
	if (!company) return;

	frm._oman_vat_accounts = frm._oman_vat_accounts || {};
	if (!frm._oman_vat_accounts[company]) {
		const { message } = await frappe.call({
			method: "oman_compliance.oman_compliance.overrides.item_tax_template.get_vat_accounts_for_template",
			args: { company: company },
		});

		frm._oman_vat_accounts[company] = message;
	}

	return frm._oman_vat_accounts[company];
}
