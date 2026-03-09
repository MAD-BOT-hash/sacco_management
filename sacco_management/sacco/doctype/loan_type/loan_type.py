from frappe.model.document import Document


class LoanType(Document):
    def validate(self):
        if self.code:
            self.code = self.code.upper().strip()
            
        # Validate tenure
        if self.min_tenure_months > self.max_tenure_months:
            from frappe import throw, _
            throw(_("Minimum tenure cannot be greater than maximum tenure"))
            
        # Validate amounts
        if self.min_amount > self.max_amount:
            from frappe import throw, _
            throw(_("Minimum amount cannot be greater than maximum amount"))
