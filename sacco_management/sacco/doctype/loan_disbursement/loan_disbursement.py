# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class LoanDisbursement(Document):
    def validate(self):
        self.validate_loan_application()
        self.validate_disbursement_amount()
        
    def validate_loan_application(self):
        """Validate loan is approved"""
        if not self.loan_application:
            frappe.throw(_("Loan Application is required"))
        
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        
        if loan_app.status != "Approved":
            frappe.throw(_("Only approved loans can be disbursed. Current status: {0}").format(
                loan_app.status))
        
        # Check if already disbursed
        existing_disbursement = frappe.db.exists("Loan Disbursement", {
            "loan_application": self.loan_application,
            "docstatus": 1
        })
        
        if existing_disbursement:
            frappe.throw(_("Loan already disbursed"))
    
    def validate_disbursement_amount(self):
        """Validate disbursement amount"""
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        
        if flt(self.disbursed_amount) > flt(loan_app.approved_amount):
            frappe.throw(_("Disbursement amount cannot exceed approved amount"))
    
    def on_submit(self):
        """Process loan disbursement"""
        self.process_disbursement()
    
    def on_cancel(self):
        """Reverse disbursement on cancel"""
        self.reverse_disbursement()
    
    def process_disbursement(self):
        """Process the loan disbursement"""
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        
        # Update loan application
        loan_app.disbursed_amount = self.disbursed_amount
        loan_app.disbursement_date = self.disbursement_date
        loan_app.disbursement_mode = self.payment_mode
        loan_app.status = "Disbursed"
        loan_app.save(ignore_permissions=True)
        
        # Generate repayment schedule
        loan_app.generate_repayment_schedule()
        
        # Post to GL
        self.post_to_gl(loan_app)
        
        self.status = "Disbursed"
        self.save(ignore_permissions=True)
        
        # Update member loan balance
        self.update_member_loan_balance(loan_app)
        
        frappe.msgprint(_("Loan disbursed successfully"), alert=True)
    
    def reverse_disbursement(self):
        """Reverse the disbursement"""
        if self.status != "Disbursed":
            frappe.throw(_("Can only reverse disbursed entries"))
        
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        
        # Reverse loan application
        loan_app.disbursed_amount = 0
        loan_app.disbursement_date = None
        loan_app.status = "Approved"
        loan_app.save(ignore_permissions=True)
        
        # Reverse GL entry
        if self.gl_posted and self.journal_entry:
            from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
            reverse_gl_entry("Loan Disbursement", self.name)
        
        self.status = "Cancelled"
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Loan disbursement reversed successfully"), alert=True)
    
    def post_to_gl(self, loan_app):
        """Post disbursement to General Ledger"""
        loan_type_account = frappe.db.get_value("Loan Type", loan_app.loan_type, "default_gl_account")
        payment_account = frappe.db.get_value("Payment Mode", self.payment_mode, "gl_account")
        
        if not loan_type_account:
            frappe.throw(_("Loan Type does not have GL Account configured"))
        
        if not payment_account:
            frappe.throw(_("Payment Mode does not have GL Account configured"))
        
        from sacco_management.sacco.utils.gl_utils import create_gl_entry
        
        accounts = [
            {
                "gl_account": loan_type_account,
                "debit": self.disbursed_amount,
                "credit": 0,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Loan disbursement to {self.member_name}"
            },
            {
                "gl_account": payment_account,
                "debit": 0,
                "credit": self.disbursed_amount,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Loan disbursement - {loan_app.loan_type}"
            }
        ]
        
        je = create_gl_entry(
            voucher_type="Payment Voucher",
            posting_date=self.disbursement_date,
            accounts=accounts,
            remarks=f"Loan Disbursement: {loan_app.loan_type} - {self.member_name}",
            reference_type="Loan Disbursement",
            reference_name=self.name,
            branch=self.branch
        )
        
        self.journal_entry = je.name
        self.gl_posted = 1
    
    def update_member_loan_balance(self, loan_app):
        """Update member's total loans taken"""
        member = frappe.get_doc("SACCO Member", self.member)
        
        # Get all active loans
        total_loans = frappe.db.sql("""
            SELECT COALESCE(SUM(outstanding_amount), 0)
            FROM `tabLoan Application`
            WHERE member = %s AND docstatus = 1 AND status IN ('Disbursed', 'Active')
        """, (self.member,))[0][0] or 0
        
        member.total_loans_taken = flt(total_loans) + flt(self.disbursed_amount)
        member.outstanding_loan_balance = flt(member.outstanding_loan_balance) + flt(self.disbursed_amount)
        member.db_update()


@frappe.whitelist()
def disburse_loan(loan_application, payment_mode, disbursed_amount=None, 
                  payment_reference=None, bank_account=None, cheque_number=None):
    """Create and submit loan disbursement"""
    loan_app = frappe.get_doc("Loan Application", loan_application)
    
    disbursement = frappe.new_doc("Loan Disbursement")
    disbursement.loan_application = loan_application
    disbursement.member = loan_app.member
    disbursement.member_name = loan_app.member_name
    disbursement.disbursed_amount = disbursed_amount or loan_app.approved_amount
    disbursement.payment_mode = payment_mode
    disbursement.payment_reference = payment_reference
    disbursement.bank_account = bank_account
    disbursement.cheque_number = cheque_number
    disbursement.disbursement_date = nowdate()
    
    disbursement.insert(ignore_permissions=True)
    disbursement.submit()
    
    frappe.db.commit()
    return disbursement.as_dict()
