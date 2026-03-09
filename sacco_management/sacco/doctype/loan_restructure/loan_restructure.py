# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months


class LoanRestructure(Document):
    def validate(self):
        self.validate_loan_application()
        self.calculate_totals()
        self.validate_new_terms()
        
    def validate_loan_application(self):
        """Validate loan application exists and is active"""
        if not self.loan_application:
            frappe.throw(_("Loan Application is required"))
        
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        if loan.status not in ["Disbursed", "Active"]:
            frappe.throw(_("Loan must be in Disbursed or Active status"))
    
    def calculate_totals(self):
        """Calculate current outstanding amounts"""
        from sacco_management.sacco.utils.loan_utils import get_outstanding_principal
        
        # Get outstanding principal
        self.current_outstanding_principal = get_outstanding_principal(self.loan_application)
        
        # Get due interest and penalties from schedule
        dues = frappe.db.sql("""
            SELECT 
                COALESCE(SUM(CASE WHEN payment_date < CURDATE() AND paid_amount < interest_amount THEN interest_amount - paid_amount ELSE 0 END), 0) as interest_due,
                COALESCE(SUM(CASE WHEN payment_date < CURDATE() AND paid_amount < penalty_amount THEN penalty_amount - paid_amount ELSE 0 END), 0) as penalty_due,
                MAX(DATEDIFF(CURDATE(), payment_date)) as overdue_days
            FROM `tabLoan Repayment Schedule`
            WHERE parent = %s
        """, (self.loan_application,), as_dict=True)
        
        if dues:
            self.current_interest_due = flt(dues[0].interest_due)
            self.current_penalty_due = flt(dues[0].penalty_due)
            self.overdue_days = flt(dues[0].overdue_days) if dues[0].overdue_days else 0
        
        # Calculate total amount due
        self.total_amount_due = flt(self.current_outstanding_principal) + \
                               flt(self.current_interest_due) + \
                               flt(self.current_penalty_due)
        
        # Calculate total restructure charges
        self.total_restructure_charges = flt(self.restructure_fee) + \
                                        flt(self.legal_charges) + \
                                        flt(self.other_charges)
    
    def validate_new_terms(self):
        """Validate new loan terms"""
        if self.new_interest_rate and flt(self.new_interest_rate) < 0:
            frappe.throw(_("New interest rate cannot be negative"))
        
        if self.new_repayment_period and flt(self.new_repayment_period) <= 0:
            frappe.throw(_("New repayment period must be positive"))
        
        if self.grace_period_months and flt(self.grace_period_months) < 0:
            frappe.throw(_("Grace period cannot be negative"))
    
    def before_submit(self):
        """Set approval details and update loan"""
        if not self.approved_by:
            self.approved_by = frappe.session.user
        
        self.approval_date = nowdate()
        self.status = "Approved"
    
    def on_submit(self):
        """Update loan application with new terms"""
        self.update_loan_terms()
        self.create_restructure_ledger_entry()
        self.generate_new_schedule()
    
    def update_loan_terms(self):
        """Update loan application with restructured terms"""
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        if self.new_interest_rate:
            loan.interest_rate = self.new_interest_rate
        
        if self.new_repayment_period:
            loan.repayment_period = self.new_repayment_period
        
        if self.new_first_payment_date:
            loan.expected_first_payment_date = self.new_first_payment_date
        
        loan.status = "Restructured"
        loan.save(ignore_permissions=True)
    
    def create_restructure_ledger_entry(self):
        """Create loan ledger entry for restructure charges"""
        if flt(self.total_restructure_charges) > 0:
            ledger = frappe.get_doc({
                "doctype": "Loan Ledger",
                "loan_application": self.loan_application,
                "member": self.member,
                "transaction_date": nowdate(),
                "principal_amount": 0,
                "interest_amount": 0,
                "penalty_amount": self.total_restructure_charges,
                "outstanding_balance": self.total_amount_due + self.total_restructure_charges,
                "remarks": f"Restructure charges - {self.name}"
            })
            
            ledger.insert(ignore_permissions=True)
            ledger.submit()
    
    def generate_new_schedule(self):
        """Generate new repayment schedule based on restructured terms"""
        from sacco_management.sacco.utils.loan_utils import generate_amortization_schedule
        
        # Delete old unpaid schedule
        frappe.db.sql("""
            DELETE FROM `tabLoan Repayment Schedule`
            WHERE parent = %s AND payment_date >= CURDATE()
        """, (self.loan_application,))
        
        # Generate new schedule
        schedule_data = generate_amortization_schedule(self.loan_application)
        
        loan = frappe.get_doc("Loan Application", self.loan_application)
        
        for idx, row in enumerate(schedule_data):
            child = loan.append("repayment_schedule", {
                "payment_number": row["payment_number"],
                "payment_date": row["payment_date"],
                "emi_amount": row["emi_amount"],
                "principal_component": row["principal_component"],
                "interest_component": row["interest_component"],
                "outstanding_balance": row["outstanding_balance"]
            })
        
        loan.save(ignore_permissions=True)
