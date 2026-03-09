from frappe.model.document import Document


class ShareType(Document):
    def validate(self):
        if self.code:
            self.code = self.code.upper().strip()
