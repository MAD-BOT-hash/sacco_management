# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class LoanAgreement(Document):
    def validate(self):
        self.validate_loan_application()
        self.validate_signatures()
        self.set_emi_amount()
        
    def validate_loan_application(self):
        """Validate loan application exists and is approved"""
        if not self.loan_application:
            frappe.throw(_("Loan Application is required"))
        
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        if loan.status != "Approved":
            frappe.throw(_("Loan Application must be in Approved status"))
        
        # Check if agreement already exists
        existing_agreement = frappe.db.exists(
            "Loan Agreement",
            {"loan_application": self.loan_application, "docstatus": 1}
        )
        
        if existing_agreement:
            frappe.throw(_("Loan Agreement already exists for this loan"))
    
    def validate_signatures(self):
        """Validate all required signatures are present"""
        if self.docstatus == 1:  # On submit
            if not self.borrower_signature or not self.lender_signature:
                frappe.throw(_("Both Borrower and Lender signatures are required"))
            
            if not self.borrower_signature_date or not self.lender_signature_date:
                frappe.throw(_("Signature dates are required"))
    
    def set_emi_amount(self):
        """Calculate and set EMI amount if not provided"""
        if not self.emi_amount and self.loan_application:
            from sacco_management.sacco.utils.loan_utils import generate_amortization_schedule
            
            schedule = generate_amortization_schedule(self.loan_application)
            if schedule:
                self.emi_amount = schedule[0]["emi_amount"]
    
    def on_submit(self):
        """Update loan application status on agreement submission"""
        self.update_loan_status()
        self.create_loan_ledger_entry()
        
    def on_cancel(self):
        """Update loan application status on agreement cancellation"""
        self.update_loan_status(cancel=True)
    
    def update_loan_status(self, cancel=False):
        """Update loan application status"""
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        if cancel:
            loan.status = "Approved"
        else:
            loan.status = "Agreement Created"
        
        loan.db_set("status", loan.status)
    
    def create_loan_ledger_entry(self):
        """Create initial loan ledger entry"""
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        ledger = frappe.get_doc({
            "doctype": "Loan Ledger",
            "loan_application": self.loan_application,
            "member": self.member,
            "transaction_date": self.agreement_date,
            "principal_amount": self.loan_amount,
            "interest_amount": 0,
            "penalty_amount": 0,
            "outstanding_balance": self.loan_amount,
            "remarks": f"Loan agreement created - {self.name}"
        })
        
        ledger.insert(ignore_permissions=True)
        ledger.submit()
