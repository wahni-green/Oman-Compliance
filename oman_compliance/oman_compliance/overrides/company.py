from oman_compliance.oman_compliance.utils.trn import validate_trn


def validate(doc, method=None):
	doc.oman_trn = validate_trn(doc.oman_trn, label="Company TRN")
