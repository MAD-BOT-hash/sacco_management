# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class LoanSettlement(Document):
    def validate(self):
        self.validate_loan_application()
        self.calculate_settlement_amounts()
        self.validate_payment()
        
    def validate_loan_application(self):
        """Validate loan application exists"""
        if not self.loan_application:
            frappe.throw(_("Loan Application is required"))
        
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        # Check if already settled or written off
        if loan.status in ["Closed", "Written Off", "Settled"]:
            frappe.throw(_("Loan is already {0}").format(loan.status))
    
    def calculate_settlement_amounts(self):
        """Calculate settlement amounts"""
        from sacco_management.sacco.utils.loan_utils import (
            get_outstanding_principal, 
            calculate_daily_accrual,
            calculate_prepayment_amount
        )
        
        # Get outstanding principal
        self.total_outstanding_principal = get_outstanding_principal(self.loan_application)
        
        # Calculate accrued interest up to settlement date
        accrual = calculate_daily_accrual(self.loan_application, to_date=self.settlement_date)
        self.accrued_interest = accrual["accrued_interest"]
        
        # Get unpaid penalties
        penalties = frappe.db.sql("""
            SELECT COALESCE(SUM(CASE WHEN paid_amount < penalty_amount THEN penalty_amount - paid_amount ELSE 0 END), 0)
            FROM `tabLoan Repayment Schedule`
            WHERE parent = %s
        """, (self.loan_application,), as_dict=True)
        
        self.penalty_charges = flt(penalties[0].get('penalty_amount', 0)) if penalties else 0
        
        # Calculate total payable
        self.total_amount_payable = flt(self.total_outstanding_principal) + \
                                   flt(self.accrued_interest) + \
                                   flt(self.penalty_charges)
        
        # Apply discount if any
        self.final_settlement_amount = flt(self.total_amount_payable) - flt(self.settlement_discount)
    
    def validate_payment(self):
        """Validate payment details"""
        if self.docstatus == 1:
            if not self.payment_reference and self.payment_mode:
                frappe.msgprint(_("Warning: No payment reference provided"), indicator='orange')
            
            if getdate(self.payment_date) > getdate(nowdate()):
                frappe.throw(_("Payment date cannot be in the future"))
    
    def before_submit(self):
        """Set approval details"""
        if not self.approved_by:
            self.approved_by = frappe.session.user
        
        self.approval_date = nowdate()
        self.status = "Approved"
    
    def on_submit(self):
        """Process loan settlement"""
        self.create_gl_entries()
        self.update_loan_status()
        self.create_loan_ledger_entry()
    
    def on_cancel(self):
        """Reverse settlement on cancellation"""
        self.update_loan_status(cancel=True)
        self.reverse_gl_entries()
    
    def create_gl_entries(self):
        """Create GL entries for loan settlement"""
        from sacco_management.sacco.utils.gl_utils import make_gl_entry
        
        posting_date = self.payment_date or nowdate()
        
        # Get accounts
        loan = frappe.get_doc("Loan Application", self.loan_application)
        bank_account = self.bank_account or frappe.db.get_single_value("SACCO Settings", "default_bank_account")
        loan_account = loan.loan_account
        
        if not bank_account or not loan_account:
            frappe.throw(_("Please configure Bank Account and Loan Account"))
        
        # Debit Bank Account
        make_gl_entry(
            voucher_type="Loan Settlement",
            voucher_no=self.name,
            posting_date=posting_date,
            account=bank_account,
            debit=self.final_settlement_amount,
            credit=0,
            remarks=f"Loan settlement received - {self.name}"
        )
        
        # Credit Loan Account (principal)
        make_gl_entry(
            voucher_type="Loan Settlement",
            voucher_no=self.name,
            posting_date=posting_date,
            account=loan_account,
            debit=0,
            credit=self.total_outstanding_principal,
            remarks=f"Loan principal closed - {self.name}"
        )
        
        # Credit Interest Income Account
        if flt(self.accrued_interest) > 0:
            interest_account = loan.interest_income_account or frappe.db.get_single_value("SACCO Settings", "interest_income_account")
            if interest_account:
                make_gl_entry(
                    voucher_type="Loan Settlement",
                    voucher_no=self.name,
                    posting_date=posting_date,
                    account=interest_account,
                    debit=0,
                    credit=self.accrued_interest,
                    remarks=f"Interest income on loan settlement"
                )
        
        # Handle discount (if any)
        if flt(self.settlement_discount) > 0:
            discount_account = frappe.db.get_single_value("SACCO Settings", "settlement_discount_account")
            if discount_account:
                make_gl_entry(
                    voucher_type="Loan Settlement",
                    voucher_no=self.name,
                    posting_date=posting_date,
                    account=discount_account,
                    debit=self.settlement_discount,
                    credit=0,
                    remarks=f"Settlement discount allowed"
                )
        
        self.gl_posted = 1
    
    def reverse_gl_entries(self):
        """Reverse GL entries"""
        gl_entries = frappe.get_all("SACCO Journal Entry Account",
                                   filters={
                                       "reference_type": "Loan Settlement",
                                       "reference_name": self.name
                                   })
        
        for gl in gl_entries:
            frappe.db.set_value("SACCO Journal Entry Account", gl.name, "is_cancelled", 1)
        
        self.gl_posted = 0
    
    def update_loan_status(self, cancel=False):
        """Update loan application status"""
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        if cancel:
            loan.status = "Active"
        else:
            loan.status = "Settled"
        
        loan.db_set("status", loan.status)
    
    def create_loan_ledger_entry(self):
        """Create final loan ledger entry"""
        ledger = frappe.get_doc({
            "doctype": "Loan Ledger",
            "loan_application": self.loan_application,
            "member": self.member,
            "transaction_date": self.payment_date or nowdate(),
            "principal_amount": -self.total_outstanding_principal,
            "interest_amount": -self.accrued_interest,
            "penalty_amount": -self.penalty_charges,
            "outstanding_balance": 0,
            "remarks": f"Loan fully settled - {self.name}"
        })
        
        ledger.insert(ignore_permissions=True)
        ledger.submit()
