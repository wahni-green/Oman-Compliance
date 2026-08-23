import frappe


class ServiceProviderError(frappe.ValidationError):
	pass


class ServiceProviderLimitExceededError(ServiceProviderError):
	pass


class GatewayTimeoutError(ServiceProviderError):
	pass


class NotApplicableError(frappe.ValidationError):
	pass


class AlreadySubmittedError(frappe.ValidationError):
	pass
