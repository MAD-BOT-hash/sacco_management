# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class AttendanceFineType(Document):
    def validate(self):
        self.validate_amount()
        self.validate_waiver()
    
    def validate_amount(self):
        """Ensure amount is positive"""
        if self.amount and self.amount <= 0:
            frappe.throw(_("Amount must be greater than zero"))
    
    def validate_waiver(self):
        """Validate waiver percentage"""
        if self.waiver_allowed and self.max_waiver_percent:
            if self.max_waiver_percent < 0 or self.max_waiver_percent > 100:
                frappe.throw(_("Max Waiver % must be between 0 and 100"))
