# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class DividendLedger(Document):
    def validate(self):
        self.calculate_outstanding()
        
    def calculate_outstanding(self):
        """Calculate outstanding dividend"""
        self.outstanding_dividend = flt(self.net_dividend) - flt(self.dividend_paid)
    
    def on_submit(self):
        """Update member dividend balance"""
        self.update_member_dividend_balance()
    
    def on_cancel(self):
        """Reverse dividend entry"""
        self.update_member_dividend_balance(cancel=True)
    
    def update_member_dividend_balance(self, cancel=False):
        """Update member's total dividend received"""
        member = frappe.get_doc("SACCO Member", self.member)
        
        multiplier = -1 if cancel else 1
        
        # Update total dividend paid
        if hasattr(member, 'total_dividend_received'):
            member.total_dividend_received = flt(member.total_dividend_received) + (flt(self.dividend_paid) * multiplier)
            member.save(ignore_permissions=True)
