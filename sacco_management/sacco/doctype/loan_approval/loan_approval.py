# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class LoanApproval(Document):
    def validate(self):
        self.validate_loan_application()
        self.update_approval_history()
        
    def validate_loan_application(self):
        """Validate loan application exists"""
        if not self.loan_application:
            frappe.throw(_("Loan Application is required"))
    
    def update_approval_history(self):
        """Add current approval to history"""
        self.append("approval_history", {
            "approval_level": self.approval_level,
            "approved_by": self.approved_by,
            "approver_designation": self.approver_designation,
            "approval_date": self.approval_date,
            "approval_action": self.approval_action,
            "status": self.status,
            "approved_amount": self.approved_amount,
            "approved_interest_rate": self.approved_interest_rate,
            "remarks": self.remarks,
            "special_conditions": self.special_conditions
        })
    
    def on_submit(self):
        """Process approval based on action"""
        if self.approval_action == "Approve":
            self.process_approval()
        elif self.approval_action == "Reject":
            self.process_rejection()
        elif self.approval_action == "Recommend":
            self.process_recommendation()
    
    def process_approval(self):
        """Process loan approval"""
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        
        # Update loan application with approved terms
        if flt(self.approved_amount) > 0:
            loan_app.approved_amount = flt(self.approved_amount)
        
        if flt(self.approved_interest_rate) > 0:
            loan_app.interest_rate = flt(self.approved_interest_rate)
        
        if flt(self.approved_tenure) > 0:
            loan_app.tenure_months = flt(self.approved_tenure)
        
        # Add special conditions
        if self.special_conditions:
            existing_remarks = loan_app.remarks or ""
            loan_app.remarks = f"{existing_remarks}\n\nApproved with conditions:\n{self.special_conditions}"
        
        # Determine next step
        if self.is_final_approval or self.all_approvals_complete:
            loan_app.status = "Approved"
            loan_app.approved_by = self.approved_by
            loan_app.approval_date = self.approval_date
            frappe.msgprint(_("Loan fully approved and ready for disbursement"), alert=True)
        else:
            loan_app.status = "Pending Approval"
            frappe.msgprint(_("Approval recorded. Pending next level approval"), alert=True)
        
        loan_app.save(ignore_permissions=True)
        self.status = "Approved"
        self.save(ignore_permissions=True)
    
    def process_rejection(self):
        """Process loan rejection"""
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        loan_app.status = "Rejected"
        loan_app.rejection_reason = self.remarks
        loan_app.save(ignore_permissions=True)
        
        self.status = "Rejected"
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Loan application has been rejected"), alert=True)
    
    def process_recommendation(self):
        """Process recommendation for next level"""
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        loan_app.status = "Under Review"
        loan_app.save(ignore_permissions=True)
        
        self.status = "Recommended"
        
        # Set next approver
        if self.next_approver:
            self.next_approval_level = self.get_next_level()
        
        self.save(ignore_permissions=True)
        frappe.msgprint(_("Loan recommended for next approval level"), alert=True)
    
    def get_next_level(self):
        """Determine next approval level"""
        level_map = {
            "Level 1": "Level 2",
            "Level 2": "Level 3",
            "Level 3": "Final Approval"
        }
        return level_map.get(self.approval_level, "None")


@frappe.whitelist()
def create_approval(loan_application, approval_level="Level 1"):
    """Create a new loan approval document"""
    approval = frappe.new_doc("Loan Approval")
    approval.loan_application = loan_application
    approval.approval_level = approval_level
    approval.approval_date = nowdate()
    
    # Auto-populate from loan application
    loan_app = frappe.get_doc("Loan Application", loan_application)
    approval.member = loan_app.member
    approval.member_name = loan_app.member_name
    approval.approved_amount = loan_app.requested_amount
    approval.approved_interest_rate = loan_app.interest_rate
    approval.approved_tenure = loan_app.tenure_months
    
    approval.insert(ignore_permissions=True)
    return approval.as_dict()


@frappe.whitelist()
def approve_loan(approval_name, approved_amount=None, interest_rate=None, tenure=None, remarks=None):
    """Quick approval function"""
    approval = frappe.get_doc("Loan Approval", approval_name)
    
    if approved_amount:
        approval.approved_amount = flt(approved_amount)
    if interest_rate:
        approval.approved_interest_rate = flt(interest_rate)
    if tenure:
        approval.approved_tenure = int(tenure)
    if remarks:
        approval.remarks = remarks
    
    approval.approval_action = "Approve"
    approval.insert(ignore_permissions=True)
    approval.submit()
    
    frappe.db.commit()
    return approval.as_dict()
