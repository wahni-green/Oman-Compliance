from frappe.model.document import Document
from frappe.utils import now_datetime

from oman_compliance.oman_compliance.utils.trn import validate_trn


class TRN(Document):
	def before_naming(self):
		# Runs before the "field:trn" autoname rule copies `trn` into `name` — normalize/validate
		# here rather than in validate(), since Document._sync_autoname_field() re-derives `trn`
		# from `name` after every save, which would otherwise clobber any normalization done later.
		self.trn = validate_trn(self.trn, label="TRN")

	def validate(self):
		if self.is_new():
			self.last_validated_on = now_datetime()

	def before_rename(self, old, new, merge=False):
		# Renaming (e.g. via the Desk rename dialog) bypasses before_naming entirely, so this is
		# the only chance to validate/normalize the new value before it becomes the document name.
		return validate_trn(new, label="TRN")
