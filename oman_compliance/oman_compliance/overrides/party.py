from oman_compliance.oman_compliance.utils.trn import validate_trn as validate_trn_format


def validate_trn(doc, method=None):
	doc.oman_trn = validate_trn_format(doc.oman_trn, label=f"{doc.doctype} TRN")
