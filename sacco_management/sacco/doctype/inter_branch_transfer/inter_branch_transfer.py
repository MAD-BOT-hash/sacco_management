# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class InterBranchTransfer(Document):
    def validate(self):
        self.validate_branches()
        self.validate_amount()
        
    def validate_branches(self):
        """Validate that from and to branches are different"""
        if self.from_branch == self.to_branch:
            frappe.throw(_("From Branch and To Branch cannot be the same"))
    
    def validate_amount(self):
        """Validate amount is positive"""
        if flt(self.amount) <= 0:
            frappe.throw(_("Amount must be greater than zero"))
    
    def before_submit(self):
        """Set user details"""
        if not self.requested_by:
            self.requested_by = frappe.session.user
        
        if not self.approved_by:
            frappe.throw(_("Approval is required for inter-branch transfer"))
        
        self.status = "Approved"
    
    def on_submit(self):
        """Process transfer and create GL entries"""
        self.process_transfer()
        self.create_gl_entries()
        self.update_status()
    
    def on_cancel(self):
        """Reverse transfer on cancellation"""
        self.reverse_gl_entries()
        self.update_status(cancel=True)
    
    def process_transfer(self):
        """Process the transfer based on type"""
        if self.transfer_type == "Member Transfer":
            self.transfer_member_records()
        elif self.transfer_type in ["Cash Transfer", "Bank Transfer"]:
            self.transfer_funds()
        elif self.transfer_type == "Account Reallocation":
            self.reallocate_account()
    
    def transfer_funds(self):
        """Transfer funds between branches"""
        # This would typically involve updating account balances
        # For now, we'll just log the transfer
        frappe.log_error(
            message=f"Funds transferred from {self.from_branch} to {self.to_branch}: {self.amount}",
            title="Inter-Branch Transfer"
        )
    
    def transfer_member_records(self):
        """Transfer member from one branch to another"""
        # This would update member's branch assignment
        pass
    
    def reallocate_account(self):
        """Reallocate account to different branch"""
        # Update account's branch assignment
        pass
    
    def create_gl_entries(self):
        """Create GL entries for inter-branch transfer"""
        from sacco_management.sacco.utils.gl_utils import make_gl_entry
        
        posting_date = self.transfer_date
        
        # Debit receiving branch account
        make_gl_entry(
            voucher_type="Inter Branch Transfer",
            voucher_no=self.name,
            posting_date=posting_date,
            account=self.account,
            debit=self.amount,
            credit=0,
            cost_center=self.get_branch_cost_center(self.to_branch),
            remarks=f"Inter-branch transfer from {self.from_branch} - {self.name}"
        )
        
        # Credit sending branch account
        make_gl_entry(
            voucher_type="Inter Branch Transfer",
            voucher_no=self.name,
            posting_date=posting_date,
            account=self.account,
            debit=0,
            credit=self.amount,
            cost_center=self.get_branch_cost_center(self.from_branch),
            remarks=f"Inter-branch transfer to {self.to_branch} - {self.name}"
        )
        
        self.gl_posted = 1
    
    def get_branch_cost_center(self, branch):
        """Get cost center for branch"""
        cost_center = frappe.db.get_value("Branch", branch, "cost_center")
        if not cost_center:
            # Create default cost center if not exists
            cost_center = f"{branch} - Cost Center"
        
        return cost_center
    
    def reverse_gl_entries(self):
        """Reverse GL entries"""
        gl_entries = frappe.get_all("SACCO Journal Entry Account",
                                   filters={
                                       "reference_type": "Inter Branch Transfer",
                                       "reference_name": self.name
                                   })
        
        for gl in gl_entries:
            frappe.db.set_value("SACCO Journal Entry Account", gl.name, "is_cancelled", 1)
        
        self.gl_posted = 0
    
    def update_status(self, cancel=False):
        """Update transfer status"""
        if cancel:
            self.status = "Cancelled"
        else:
            self.status = "Completed"
            self.processed_by = frappe.session.user
