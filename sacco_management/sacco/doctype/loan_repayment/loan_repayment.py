import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class LoanRepayment(Document):
    def validate(self):
        self.validate_loan_status()
        self.validate_amount()
        self.allocate_payment()
        self.calculate_outstanding()
        
    def validate_loan_status(self):
        """Ensure loan is active"""
        loan_status = frappe.db.get_value("Loan Application", self.loan, "status")
        if loan_status not in ["Disbursed", "Active"]:
            frappe.throw(_("Cannot make repayment for {0} loan").format(loan_status))
            
    def validate_amount(self):
        """Validate repayment amount"""
        if flt(self.amount_paid) <= 0:
            frappe.throw(_("Amount must be greater than zero"))
            
        loan = frappe.get_doc("Loan Application", self.loan)
        if flt(self.amount_paid) > flt(loan.outstanding_amount):
            frappe.msgprint(
                _("Payment amount ({0}) exceeds outstanding balance ({1}). Excess will be recorded.").format(
                    self.amount_paid, loan.outstanding_amount
                )
            )
            
    def allocate_payment(self):
        """Allocate payment to penalty, interest, then principal"""
        loan = frappe.get_doc("Loan Application", self.loan)
        remaining = flt(self.amount_paid)
        
        # First, pay any penalties
        penalty_due = self.calculate_penalty_due()
        self.penalty_paid = min(remaining, penalty_due)
        remaining -= flt(self.penalty_paid)
        
        # Second, pay interest due
        interest_due = self.calculate_interest_due()
        self.interest_paid = min(remaining, interest_due)
        remaining -= flt(self.interest_paid)
        
        # Remaining goes to principal
        self.principal_paid = remaining
        
    def calculate_penalty_due(self):
        """Calculate total penalty due"""
        loan = frappe.get_doc("Loan Application", self.loan)
        loan_type = frappe.get_doc("Loan Type", loan.loan_type)
        
        penalty = 0
        for schedule in loan.repayment_schedule:
            if schedule.status == "Overdue":
                days_overdue = (getdate(nowdate()) - getdate(schedule.due_date)).days
                if days_overdue > flt(loan_type.grace_period_days):
                    penalty += flt(schedule.total_due) * flt(loan_type.penalty_rate) / 100
                    
        # Subtract already paid penalties
        paid_penalties = frappe.db.sql("""
            SELECT COALESCE(SUM(penalty_paid), 0)
            FROM `tabLoan Repayment`
            WHERE loan = %s AND docstatus = 1 AND name != %s
        """, (self.loan, self.name or ""))[0][0]
        
        return max(0, penalty - flt(paid_penalties))
        
    def calculate_interest_due(self):
        """Calculate total interest due"""
        loan = frappe.get_doc("Loan Application", self.loan)
        
        interest_due = 0
        for schedule in loan.repayment_schedule:
            if schedule.status in ["Pending", "Overdue", "Partial"]:
                interest_due += flt(schedule.interest_amount)
                
        # Subtract already paid interest
        paid_interest = frappe.db.sql("""
            SELECT COALESCE(SUM(interest_paid), 0)
            FROM `tabLoan Repayment`
            WHERE loan = %s AND docstatus = 1 AND name != %s
        """, (self.loan, self.name or ""))[0][0]
        
        return max(0, interest_due - flt(paid_interest))
        
    def calculate_outstanding(self):
        """Calculate outstanding balance before and after payment"""
        loan = frappe.get_doc("Loan Application", self.loan)
        
        self.outstanding_before = flt(loan.outstanding_amount)
        self.outstanding_after = max(0, flt(self.outstanding_before) - flt(self.amount_paid))
        
    def on_submit(self):
        """Post to GL and update loan"""
        self.post_to_gl()
        self.update_loan_schedule()
        self.update_loan_status()
        self.update_member_balance()
        
    def on_cancel(self):
        """Reverse GL and update loan"""
        self.reverse_gl_entry()
        self.update_loan_status()
        self.update_member_balance()
        
    def post_to_gl(self):
        """Post repayment to General Ledger"""
        from sacco_management.sacco.utils.gl_utils import post_loan_repayment_to_gl
        
        je = post_loan_repayment_to_gl(self)
        self.db_set("journal_entry", je.name)
        self.db_set("gl_posted", 1)
        
    def reverse_gl_entry(self):
        """Reverse GL entry on cancellation"""
        from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
        
        if self.journal_entry:
            reverse_gl_entry("Loan Repayment", self.name)
            self.db_set("gl_posted", 0)
            
    def update_loan_schedule(self):
        """Update repayment schedule based on payment"""
        loan = frappe.get_doc("Loan Application", self.loan)
        remaining = flt(self.principal_paid) + flt(self.interest_paid)
        
        for schedule in loan.repayment_schedule:
            if schedule.status in ["Pending", "Overdue", "Partial"] and remaining > 0:
                schedule_balance = flt(schedule.total_due) - flt(schedule.paid_amount)
                
                if remaining >= schedule_balance:
                    schedule.paid_amount = schedule.total_due
                    schedule.status = "Paid"
                    schedule.payment_date = self.payment_date
                    remaining -= schedule_balance
                else:
                    schedule.paid_amount = flt(schedule.paid_amount) + remaining
                    schedule.status = "Partial"
                    remaining = 0
                    
        loan.save()
        
    def update_loan_status(self):
        """Update loan outstanding and status"""
        loan = frappe.get_doc("Loan Application", self.loan)
        loan.update_repayment_status()
        
    def update_member_balance(self):
        """Update member's loan balance"""
        member = frappe.get_doc("SACCO Member", self.member)
        member.update_loan_balance()
        member.db_update()


def on_submit(doc, method):
    """Hook called on submit"""
    pass


def on_cancel(doc, method):
    """Hook called on cancel"""
    pass


@frappe.whitelist()
def get_repayment_details(loan):
    """Get loan details for repayment"""
    loan_doc = frappe.get_doc("Loan Application", loan)
    
    return {
        "member": loan_doc.member,
        "member_name": loan_doc.member_name,
        "loan_type": loan_doc.loan_type,
        "outstanding_amount": loan_doc.outstanding_amount,
        "monthly_installment": loan_doc.monthly_installment,
        "next_due_date": get_next_due_date(loan),
        "overdue_amount": get_overdue_amount(loan)
    }


def get_next_due_date(loan):
    """Get next due date from schedule"""
    result = frappe.db.sql("""
        SELECT MIN(due_date)
        FROM `tabLoan Repayment Schedule`
        WHERE parent = %s AND status IN ('Pending', 'Partial', 'Overdue')
    """, loan)
    return result[0][0] if result else None


def get_overdue_amount(loan):
    """Get total overdue amount"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(total_due - paid_amount), 0)
        FROM `tabLoan Repayment Schedule`
        WHERE parent = %s AND status = 'Overdue'
    """, loan)
    return flt(result[0][0]) if result else 0
