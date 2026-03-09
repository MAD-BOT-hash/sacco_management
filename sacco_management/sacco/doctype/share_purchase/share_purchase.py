# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class SharePurchase(Document):
    def validate(self):
        self.validate_member()
        self.validate_share_type()
        self.calculate_totals()
        
    def validate_member(self):
        """Validate member is active"""
        member_status = frappe.db.get_value("SACCO Member", self.member, "status")
        if member_status != "Active":
            frappe.throw(_("Cannot purchase shares for {0} member").format(member_status))
    
    def validate_share_type(self):
        """Validate share type is active"""
        share_active = frappe.db.get_value("Share Type", self.share_type, "is_active")
        if not share_active:
            frappe.throw(_("Share Type {0} is not active").format(self.share_type))
    
    def calculate_totals(self):
        """Calculate total amount and update share counts"""
        if self.quantity and self.price_per_share:
            self.total_amount = flt(self.quantity) * flt(self.price_per_share)
        
        # Get previous shares
        previous_shares = frappe.db.sql("""
            SELECT COALESCE(SUM(quantity), 0)
            FROM `tabShare Allocation`
            WHERE member = %s AND share_type = %s AND docstatus = 1 AND status = 'Allocated'
        """, (self.member, self.share_type))[0][0] or 0
        
        self.previous_shares = previous_shares
        self.new_total_shares = previous_shares + self.quantity
    
    def on_submit(self):
        """Create share allocation and GL entries on submission"""
        self.create_share_allocation()
        self.create_gl_entries()
        self.update_member_shares()
    
    def on_cancel(self):
        """Reverse allocation and GL entries on cancellation"""
        self.cancel_share_allocation()
        self.reverse_gl_entries()
        self.update_member_shares(cancel=True)
    
    def create_share_allocation(self):
        """Create share allocation document"""
        allocation = frappe.get_doc({
            "doctype": "Share Allocation",
            "member": self.member,
            "share_type": self.share_type,
            "quantity": self.quantity,
            "allocation_date": self.purchase_date,
            "payment_mode": self.payment_mode,
            "reference_number": self.payment_reference,
            "remarks": f"Purchased via Share Purchase {self.name}"
        })
        
        allocation.insert(ignore_permissions=True)
        allocation.submit()
        
        frappe.db.set_value("Share Purchase", self.name, "journal_entry", allocation.journal_entry)
        frappe.db.set_value("Share Purchase", self.name, "gl_posted", 1)
    
    def cancel_share_allocation(self):
        """Cancel linked share allocation"""
        allocation_name = frappe.db.get_value("Share Allocation", {
            "member": self.member,
            "share_type": self.share_type,
            "remarks": ("like", f"%{self.name}%")
        })
        
        if allocation_name:
            allocation = frappe.get_doc("Share Allocation", allocation_name)
            allocation.cancel()
    
    def create_gl_entries(self):
        """Create GL entries for share purchase"""
        from sacco_management.sacco.utils.gl_utils import make_gl_entry
        
        posting_date = self.purchase_date or nowdate()
        
        # Get accounts
        share_capital_account = frappe.db.get_single_value("SACCO Settings", "share_capital_account")
        bank_account = self.bank_account or frappe.db.get_single_value("SACCO Settings", "default_bank_account")
        
        if not share_capital_account or not bank_account:
            frappe.throw(_("Please configure Share Capital Account and Bank Account in SACCO Settings"))
        
        # Debit Bank Account
        make_gl_entry(
            voucher_type="Share Purchase",
            voucher_no=self.name,
            posting_date=posting_date,
            account=bank_account,
            debit=self.total_amount,
            credit=0,
            remarks=f"Share purchase - {self.name}"
        )
        
        # Credit Share Capital Account
        make_gl_entry(
            voucher_type="Share Purchase",
            voucher_no=self.name,
            posting_date=posting_date,
            account=share_capital_account,
            debit=0,
            credit=self.total_amount,
            remarks=f"Share capital issued - {self.name}"
        )
    
    def reverse_gl_entries(self):
        """Reverse GL entries"""
        gl_entries = frappe.get_all("SACCO Journal Entry Account",
                                   filters={
                                       "reference_type": "Share Purchase",
                                       "reference_name": self.name
                                   })
        
        for gl in gl_entries:
            frappe.db.set_value("SACCO Journal Entry Account", gl.name, "is_cancelled", 1)
        
        frappe.db.set_value("Share Purchase", self.name, "gl_posted", 0)
    
    def update_member_shares(self, cancel=False):
        """Update member's total shares"""
        member = frappe.get_doc("SACCO Member", self.member)
        
        if cancel:
            member.total_shares = flt(member.total_shares) - self.quantity
        else:
            member.total_shares = flt(member.total_shares) + self.quantity
        
        member.save(ignore_permissions=True)
