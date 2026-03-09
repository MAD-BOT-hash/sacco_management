# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class FinePayment(Document):
    def validate(self):
        self.validate_member()
        self.calculate_totals()
        self.validate_allocations()
        
    def validate_member(self):
        """Validate member exists"""
        if not self.member:
            frappe.throw(_("Member is required"))
    
    def calculate_totals(self):
        """Calculate total fines and outstanding"""
        if self.fines_paid:
            self.total_fines = self.get_total_fines_payable()
            self.outstanding_fines = flt(self.total_fines) - flt(self.fines_paid)
    
    def get_total_fines_payable(self):
        """Get total fines payable by member"""
        total = frappe.db.sql("""
            SELECT COALESCE(SUM(amount), 0)
            FROM `tabMember Fine`
            WHERE member = %s AND docstatus = 1
        """, (self.member,))[0][0] or 0
        
        paid = frappe.db.sql("""
            SELECT COALESCE(SUM(fines_paid), 0)
            FROM `tabFine Payment`
            WHERE member = %s AND docstatus = 1
        """, (self.member,))[0][0] or 0
        
        return flt(total) - flt(paid)
    
    def validate_allocations(self):
        """Validate fine allocations"""
        if not self.fine_allocations:
            return
        
        total_allocated = sum([flt(alloc.amount_paid) for alloc in self.fine_allocations])
        
        if abs(total_allocated - flt(self.fines_paid)) > 0.01:
            frappe.throw(
                _("Total allocation ({0}) must equal amount paid ({1})")
                .format(total_allocated, self.fines_paid)
            )
    
    def on_submit(self):
        """Update fine status and create GL entries"""
        self.update_fine_status()
        self.create_gl_entries()
    
    def on_cancel(self):
        """Reverse payment on cancellation"""
        self.reverse_fine_status()
        self.reverse_gl_entries()
    
    def update_fine_status(self):
        """Update fine payment status"""
        for alloc in self.fine_allocations:
            if alloc.fine_reference:
                fine = frappe.get_doc("Member Fine", alloc.fine_reference)
                
                # Update paid amount
                new_paid = flt(fine.amount_paid) + flt(alloc.amount_paid)
                fine.amount_paid = new_paid
                
                # Update status
                if flt(fine.amount) <= flt(new_paid):
                    fine.status = "Paid"
                else:
                    fine.status = "Partial"
                
                fine.save(ignore_permissions=True)
    
    def reverse_fine_status(self):
        """Reverse fine payment status on cancellation"""
        for alloc in self.fine_allocations:
            if alloc.fine_reference:
                fine = frappe.get_doc("Member Fine", alloc.fine_reference)
                
                # Reduce paid amount
                fine.amount_paid = flt(fine.amount_paid) - flt(alloc.amount_paid)
                
                # Update status
                if flt(fine.amount_paid) <= 0:
                    fine.status = "Unpaid"
                elif flt(fine.amount_paid) < flt(fine.amount):
                    fine.status = "Partial"
                else:
                    fine.status = "Paid"
                
                fine.save(ignore_permissions=True)
    
    def create_gl_entries(self):
        """Create GL entries for fine payment"""
        from sacco_management.sacco.utils.gl_utils import make_gl_entry
        
        posting_date = self.payment_date
        
        # Get accounts
        bank_account = self.bank_account or frappe.db.get_single_value("SACCO Settings", "default_bank_account")
        fine_income_account = frappe.db.get_single_value("SACCO Settings", "fine_income_account")
        
        if not bank_account or not fine_income_account:
            frappe.throw(_("Please configure Bank Account and Fine Income Account"))
        
        # Debit Bank Account
        make_gl_entry(
            voucher_type="Fine Payment",
            voucher_no=self.name,
            posting_date=posting_date,
            account=bank_account,
            debit=self.fines_paid,
            credit=0,
            remarks=f"Fine payment received - {self.name}"
        )
        
        # Credit Fine Income Account
        make_gl_entry(
            voucher_type="Fine Payment",
            voucher_no=self.name,
            posting_date=posting_date,
            account=fine_income_account,
            debit=0,
            credit=self.fines_paid,
            remarks=f"Fine income - {self.name}"
        )
        
        self.gl_posted = 1
    
    def reverse_gl_entries(self):
        """Reverse GL entries"""
        gl_entries = frappe.get_all("SACCO Journal Entry Account",
                                   filters={
                                       "reference_type": "Fine Payment",
                                       "reference_name": self.name
                                   })
        
        for gl in gl_entries:
            frappe.db.set_value("SACCO Journal Entry Account", gl.name, "is_cancelled", 1)
        
        self.gl_posted = 0
