# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class FineRule(Document):
    def validate(self):
        self.validate_dates()
        self.validate_fine_amounts()
        self.validate_priority()
        
    def validate_dates(self):
        """Validate date configuration"""
        if self.applicable_from and getdate(self.applicable_from) > getdate(nowdate()):
            frappe.msgprint(
                _("Warning: Rule is applicable from a future date"),
                indicator='orange'
            )
    
    def validate_fine_amounts(self):
        """Validate fine amount configuration"""
        if self.fine_calculation_method == "Fixed Amount" and not self.fine_amount:
            frappe.throw(_("Fixed Fine Amount is required for Fixed Amount method"))
        
        if self.fine_calculation_method == "Percentage" and not self.percentage_of_amount:
            frappe.throw(_("Percentage is required for Percentage calculation method"))
        
        if self.minimum_fine and self.maximum_fine:
            if flt(self.minimum_fine) > flt(self.maximum_fine):
                frappe.throw(_("Minimum Fine cannot be greater than Maximum Fine"))
    
    def validate_priority(self):
        """Check for duplicate priorities with same trigger event"""
        existing = frappe.db.exists(
            "Fine Rule",
            {
                "trigger_event": self.trigger_event,
                "priority": self.priority,
                "name": ["!=", self.name or ""],
                "status": "Active"
            }
        )
        
        if existing:
            frappe.throw(
                _("Another active rule with same priority {0} exists for trigger event {1}")
                .format(self.priority, self.trigger_event)
            )
    
    def calculate_fine(self, context_data=None):
        """
        Calculate fine amount based on rule configuration
        
        Args:
            context_data: dict with contextual information 
                         (e.g., days_overdue, amount_due, etc.)
        
        Returns:
            float: Calculated fine amount
        """
        fine_amount = 0.0
        
        if self.fine_calculation_method == "Fixed Amount":
            fine_amount = flt(self.fine_amount)
            
        elif self.fine_calculation_method == "Percentage":
            if context_data and 'amount' in context_data:
                fine_amount = flt(context_data['amount']) * flt(self.percentage_of_amount) / 100
                
        elif self.fine_calculation_method == "Per Day":
            if context_data and 'days' in context_data:
                fine_amount = flt(self.fine_amount) * flt(context_data['days'])
                
        elif self.fine_calculation_method == "Progressive":
            # Progressive fine increases with each occurrence
            if context_data and 'occurrences' in context_data:
                occurrences = flt(context_data['occurrences'])
                fine_amount = flt(self.fine_amount) * (occurrences ** 0.5)  # Square root progression
        
        # Apply minimum/maximum limits
        if self.minimum_fine and fine_amount < flt(self.minimum_fine):
            fine_amount = flt(self.minimum_fine)
        
        if self.maximum_fine and fine_amount > flt(self.maximum_fine):
            fine_amount = flt(self.maximum_fine)
        
        return flt(fine_amount, 2)
