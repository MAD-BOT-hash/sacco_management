# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class LoanWriteOff(Document):
    def validate(self):
        self.validate_loan_application()
        self.calculate_amounts()
        self.validate_approval()
        
    def validate_loan_application(self):
        """Validate loan application exists"""
        if not self.loan_application:
            frappe.throw(_("Loan Application is required"))
        
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        # Check if already written off
        existing_write_off = frappe.db.exists(
            "Loan Write Off",
            {"loan_application": self.loan_application, "docstatus": 1}
        )
        
        if existing_write_off:
            frappe.throw(_("Loan already written off"))
    
    def calculate_amounts(self):
        """Calculate write off amounts"""
        from sacco_management.sacco.utils.loan_utils import get_outstanding_principal
        
        # Get outstanding principal
        self.total_outstanding_principal = get_outstanding_principal(self.loan_application)
        
        # Get due interest and penalties
        dues = frappe.db.sql("""
            SELECT 
                COALESCE(SUM(CASE WHEN paid_amount < interest_amount THEN interest_amount - paid_amount ELSE 0 END), 0) as interest_due,
                COALESCE(SUM(CASE WHEN paid_amount < penalty_amount THEN penalty_amount - paid_amount ELSE 0 END), 0) as penalty_due,
                DATEDIFF(CURDATE(), MIN(CASE WHEN status != 'Paid' THEN payment_date END)) as days_overdue
            FROM `tabLoan Repayment Schedule`
            WHERE parent = %s
        """, (self.loan_application,), as_dict=True)
        
        if dues:
            self.total_interest_due = flt(dues[0].interest_due)
            self.total_penalty_due = flt(dues[0].penalty_due)
            self.days_overdue = flt(dues[0].days_overdue) if dues[0].days_overdue else 0
        
        # Calculate total write off amount
        self.total_write_off_amount = flt(self.total_outstanding_principal) + \
                                     flt(self.total_interest_due) + \
                                     flt(self.total_penalty_due)
        
        # Calculate net loss
        self.net_loss_amount = flt(self.total_write_off_amount) - flt(self.recovery_amount) - flt(self.provision_made)
    
    def validate_approval(self):
        """Validate approval requirements"""
        if self.docstatus == 1:  # On submit
            if not self.approved_by or not self.board_resolution_number:
                frappe.throw(_("Board approval and resolution number are required for write off"))
    
    def before_submit(self):
        """Set recommendation and approval details"""
        if not self.recommended_by:
            self.recommended_by = frappe.session.user
            self.recommended_date = nowdate()
        
        if not self.approved_by:
            frappe.throw(_("Approval is required"))
        
        self.approved_date = nowdate()
        self.status = "Approved"
    
    def on_submit(self):
        """Post GL entries and update loan status"""
        self.update_loan_status()
        self.create_gl_entries()
        self.create_loan_ledger_entry()
    
    def on_cancel(self):
        """Reverse GL entries on cancellation"""
        self.update_loan_status(cancel=True)
        self.reverse_gl_entries()
    
    def update_loan_status(self, cancel=False):
        """Update loan application status"""
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        if cancel:
            loan.status = "Active"
        else:
            loan.status = "Written Off"
        
        loan.db_set("status", loan.status)
    
    def create_gl_entries(self):
        """Create GL entries for write off"""
        from sacco_management.sacco.utils.gl_utils import make_gl_entry
        
        posting_date = nowdate()
        
        # Get provision account
        provision_account = frappe.db.get_single_value("SACCO Settings", "loan_provision_account")
        loan_account = frappe.db.get_value("Loan Application", self.loan_application, "loan_account")
        
        if not provision_account or not loan_account:
            frappe.throw(_("Please configure Loan Provision Account and Loan Account in SACCO Settings"))
        
        # Credit the Loan Account (reverse the asset)
        make_gl_entry(
            voucher_type="Loan Write Off",
            voucher_no=self.name,
            posting_date=posting_date,
            account=loan_account,
            debit=0,
            credit=self.total_outstanding_principal,
            remarks=f"Loan write off - {self.name}"
        )
        
        # Debit Provision Account (if provision exists)
        if flt(self.provision_made) > 0:
            make_gl_entry(
                voucher_type="Loan Write Off",
                voucher_no=self.name,
                posting_date=posting_date,
                account=provision_account,
                debit=self.provision_made,
                credit=0,
                remarks=f"Utilize loan loss provision"
            )
        
        # Debit Bad Debt Expense (for the net loss)
        bad_debt_account = frappe.db.get_single_value("SACCO Settings", "bad_debt_expense_account")
        if bad_debt_account and flt(self.net_loss_amount) > 0:
            make_gl_entry(
                voucher_type="Loan Write Off",
                voucher_no=self.name,
                posting_date=posting_date,
                account=bad_debt_account,
                debit=self.net_loss_amount,
                credit=0,
                remarks=f"Bad debt expense on loan write off"
            )
        
        self.gl_entry_posted = 1
    
    def reverse_gl_entries(self):
        """Reverse GL entries"""
        # Cancel all GL entries linked to this write off
        gl_entries = frappe.get_all("SACCO Journal Entry Account",
                                   filters={
                                       "reference_type": "Loan Write Off",
                                       "reference_name": self.name
                                   })
        
        for gl in gl_entries:
            frappe.db.set_value("SACCO Journal Entry Account", gl.name, "is_cancelled", 1)
        
        self.gl_entry_posted = 0
    
    def create_loan_ledger_entry(self):
        """Create final loan ledger entry"""
        ledger = frappe.get_doc({
            "doctype": "Loan Ledger",
            "loan_application": self.loan_application,
            "member": self.member,
            "transaction_date": nowdate(),
            "principal_amount": -self.total_outstanding_principal,
            "interest_amount": -self.total_interest_due,
            "penalty_amount": -self.total_penalty_due,
            "outstanding_balance": 0,
            "remarks": f"Loan written off - {self.name}"
        })
        
        ledger.insert(ignore_permissions=True)
        ledger.submit()
