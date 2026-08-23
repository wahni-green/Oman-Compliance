from oman_compliance.oman_compliance.setup import (
	create_custom_fields,
	create_designated_zones,
	set_default_settings_currency,
)


def after_install() -> None:
	create_custom_fields()
	create_designated_zones()
	set_default_settings_currency()
