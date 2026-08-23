from oman_compliance.oman_vat.setup import create_custom_fields


def after_install() -> None:
	create_custom_fields()
