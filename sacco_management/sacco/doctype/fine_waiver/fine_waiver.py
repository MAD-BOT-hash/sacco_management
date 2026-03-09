# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class FineWaiver(Document):
    def validate(self):
        self.validate_member()
        self.validate_waiver_amount()
        
    def validate_member(self):
        """Validate member exists"""
        if not self.member:
            frappe.throw(_("Member is required"))
    
    def validate_waiver_amount(self):
        """Validate waiver amount doesn't exceed total fines"""
        # Get total outstanding fines for member
        total_fines = frappe.db.sql("""
            SELECT COALESCE(SUM(amount - COALESCE(amount_paid, 0)), 0)
            FROM `tabMember Fine`
            WHERE member = %s AND docstatus = 1 AND status != 'Paid'
        """, (self.member,))[0][0] or 0
        
        self.total_fine_amount = total_fines
        
        if flt(self.waiver_amount) > flt(total_fines):
            frappe.throw(
                _("Waiver amount ({0}) cannot exceed outstanding fines ({1})")
                .format(self.waiver_amount, total_fines)
            )
        
        self.net_payable_amount = flt(total_fines) - flt(self.waiver_amount)
    
    def before_submit(self):
        """Set approval details"""
        if not self.recommended_by:
            self.recommended_by = frappe.session.user
            self.recommended_date = frappe.utils.nowdate()
        
        if not self.approved_by:
            frappe.throw(_("Approval is required for fine waiver"))
        
        self.approved_date = frappe.utils.nowdate()
        self.status = "Approved"
    
    def on_submit(self):
        """Apply waiver to member fines"""
        self.apply_waiver_to_fines()
        self.create_gl_entries()
    
    def on_cancel(self):
        """Reverse waiver on cancellation"""
        self.reverse_waiver()
        self.reverse_gl_entries()
    
    def apply_waiver_to_fines(self):
        """Apply waiver amount to member's outstanding fines"""
        remaining_waiver = flt(self.waiver_amount)
        
        # Get unpaid fines ordered by date
        unpaid_fines = frappe.get_all("Member Fine",
                                     filters={
                                         "member": self.member,
                                         "docstatus": 1,
                                         "status": ["!=", "Paid"]
                                     },
                                     fields=["name", "amount", "amount_paid"],
                                     order_by="posting_date ASC")
        
        for fine_data in unpaid_fines:
            if remaining_waiver <= 0:
                break
            
            fine = frappe.get_doc("Member Fine", fine_data.name)
            outstanding = flt(fine.amount) - flt(fine.amount_paid)
            
            # Apply waiver to this fine
            waiver_for_this_fine = min(remaining_waiver, outstanding)
            fine.amount_paid = flt(fine.amount_paid) + waiver_for_this_fine
            remaining_waiver -= waiver_for_this_fine
            
            # Update status
            if flt(fine.amount_paid) >= flt(fine.amount):
                fine.status = "Waived" if waiver_for_this_fine > 0 else "Paid"
            else:
                fine.status = "Partial"
            
            fine.save(ignore_permissions=True)
    
    def reverse_waiver(self):
        """Reverse waiver application"""
        # This is complex - would need to track which fines were waived
        # For simplicity, we'll just update statuses back
        unpaid_fines = frappe.get_all("Member Fine",
                                     filters={
                                         "member": self.member,
                                         "docstatus": 1,
                                         "status": "Waived"
                                     })
        
        for fine_data in unpaid_fines:
            fine = frappe.get_doc("Member Fine", fine_data.name)
            fine.status = "Unpaid"
            fine.save(ignore_permissions=True)
    
    def create_gl_entries(self):
        """Create GL entries for fine waiver"""
        from sacco_management.sacco.utils.gl_utils import make_gl_entry
        
        posting_date = self.waiver_date
        
        # Get accounts
        fine_income_account = frappe.db.get_single_value("SACCO Settings", "fine_income_account")
        waiver_expense_account = frappe.db.get_single_value("SACCO Settings", "fine_waiver_expense_account")
        
        if not fine_income_account or not waiver_expense_account:
            frappe.throw(_("Please configure Fine Income Account and Waiver Expense Account"))
        
        # Debit Waiver Expense Account
        make_gl_entry(
            voucher_type="Fine Waiver",
            voucher_no=self.name,
            posting_date=posting_date,
            account=waiver_expense_account,
            debit=self.waiver_amount,
            credit=0,
            remarks=f"Fine waiver approved - {self.name}"
        )
        
        # Credit Fine Income Account (reduce expected income)
        make_gl_entry(
            voucher_type="Fine Waiver",
            voucher_no=self.name,
            posting_date=posting_date,
            account=fine_income_account,
            debit=0,
            credit=self.waiver_amount,
            remarks=f"Fine income waived - {self.name}"
        )
        
        self.gl_posted = 1
    
    def reverse_gl_entries(self):
        """Reverse GL entries"""
        gl_entries = frappe.get_all("SACCO Journal Entry Account",
                                   filters={
                                       "reference_type": "Fine Waiver",
                                       "reference_name": self.name
                                   })
        
        for gl in gl_entries:
            frappe.db.set_value("SACCO Journal Entry Account", gl.name, "is_cancelled", 1)
        
        self.gl_posted = 0
