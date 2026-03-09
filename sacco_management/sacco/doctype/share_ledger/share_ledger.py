# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class ShareLedger(Document):
    def validate(self):
        self.calculate_quantities()
        
    def calculate_quantities(self):
        """Calculate quantities before and after transaction"""
        # Get quantity before from previous ledger entry
        previous_entry = frappe.db.sql("""
            SELECT quantity_after
            FROM `tabShare Ledger`
            WHERE member = %s AND share_type = %s AND docstatus = 1
            ORDER BY transaction_date DESC, creation DESC
            LIMIT 1
        """, (self.member, self.share_type), as_dict=True)
        
        if previous_entry:
            self.quantity_before = flt(previous_entry[0].quantity_after)
        else:
            self.quantity_before = 0
        
        # Calculate quantity after
        self.quantity_after = flt(self.quantity_before) + flt(self.quantity_change)
        
        # Validate no negative shares
        if self.quantity_after < 0:
            frappe.throw(_("Share balance cannot be negative"))
    
    def on_submit(self):
        """Update member shares on submit"""
        self.update_member_shares()
    
    def on_cancel(self):
        """Reverse quantity change on cancel"""
        self.update_member_shares(cancel=True)
    
    def update_member_shares(self, cancel=False):
        """Update member's total shares"""
        member = frappe.get_doc("SACCO Member", self.member)
        
        multiplier = -1 if cancel else 1
        member.total_shares = flt(member.total_shares) + (flt(self.quantity_change) * multiplier)
        
        member.save(ignore_permissions=True)
