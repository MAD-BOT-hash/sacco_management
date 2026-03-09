import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months


class LoanApplication(Document):
    def validate(self):
        self.validate_member_status()
        self.validate_loan_type()
        self.validate_amount()
        self.validate_tenure()
        self.validate_guarantors()
        self.validate_collateral()
        self.calculate_loan_details()
        self.calculate_totals()
        
    def validate_member_status(self):
        """Ensure member is active"""
        status = frappe.db.get_value("SACCO Member", self.member, "status")
        if status != "Active":
            frappe.throw(_("Cannot create loan for {0} member").format(status))
            
    def validate_loan_type(self):
        """Validate loan type is active"""
        is_active = frappe.db.get_value("Loan Type", self.loan_type, "is_active")
        if not is_active:
            frappe.throw(_("Loan Type {0} is not active").format(self.loan_type))
            
    def validate_amount(self):
        """Validate loan amount against type limits"""
        loan_type = frappe.get_doc("Loan Type", self.loan_type)
        
        amount = flt(self.approved_amount) or flt(self.requested_amount)
        
        if amount < flt(loan_type.min_amount):
            frappe.throw(_("Minimum loan amount for {0} is {1}").format(
                self.loan_type, loan_type.min_amount
            ))
            
        if amount > flt(loan_type.max_amount):
            frappe.throw(_("Maximum loan amount for {0} is {1}").format(
                self.loan_type, loan_type.max_amount
            ))
            
        # Check against member savings multiplier
        member = frappe.get_doc("SACCO Member", self.member)
        member.update_contribution_balance()
        max_by_savings = flt(member.total_savings) * flt(loan_type.max_loan_multiplier)
        
        if amount > max_by_savings:
            frappe.throw(
                _("Maximum loan amount based on your savings ({0} x {1}) is {2}").format(
                    member.total_savings, loan_type.max_loan_multiplier, max_by_savings
                )
            )
            
    def validate_tenure(self):
        """Validate tenure against type limits"""
        loan_type = frappe.get_doc("Loan Type", self.loan_type)
        
        if self.tenure_months < loan_type.min_tenure_months:
            frappe.throw(_("Minimum tenure for {0} is {1} months").format(
                self.loan_type, loan_type.min_tenure_months
            ))
            
        if self.tenure_months > loan_type.max_tenure_months:
            frappe.throw(_("Maximum tenure for {0} is {1} months").format(
                self.loan_type, loan_type.max_tenure_months
            ))
            
    def validate_guarantors(self):
        """Validate guarantors"""
        loan_type = frappe.get_doc("Loan Type", self.loan_type)
        
        if loan_type.requires_guarantors:
            if len(self.guarantors) < loan_type.min_guarantors:
                frappe.throw(_("Minimum {0} guarantors required for {1}").format(
                    loan_type.min_guarantors, self.loan_type
                ))
                
            # Validate each guarantor
            for g in self.guarantors:
                # Check guarantor is not the applicant
                if g.guarantor_member == self.member:
                    frappe.throw(_("Applicant cannot be their own guarantor"))
                    
                # Check guarantor status
                status = frappe.db.get_value("SACCO Member", g.guarantor_member, "status")
                if status != "Active":
                    frappe.throw(_("Guarantor {0} is not an active member").format(
                        g.guarantor_name
                    ))
                    
                # Check guarantor's capacity
                guarantor_doc = frappe.get_doc("SACCO Member", g.guarantor_member)
                guarantor_doc.update_contribution_balance()
                max_guarantee = flt(guarantor_doc.total_savings) * flt(loan_type.max_guarantor_amount_percent) / 100
                
                if flt(g.guaranteed_amount) > max_guarantee:
                    frappe.throw(
                        _("Guarantor {0} can only guarantee up to {1} (based on their savings)").format(
                            g.guarantor_name, max_guarantee
                        )
                    )
                    
    def validate_collateral(self):
        """Validate collateral if required"""
        loan_type = frappe.get_doc("Loan Type", self.loan_type)
        
        if loan_type.requires_collateral:
            if not self.collateral:
                frappe.throw(_("Collateral is required for {0}").format(self.loan_type))
                
            amount = flt(self.approved_amount) or flt(self.requested_amount)
            min_collateral = amount * flt(loan_type.min_collateral_value_percent) / 100
            
            if flt(self.total_collateral_value) < min_collateral:
                frappe.throw(
                    _("Minimum collateral value required is {0} ({1}% of loan amount)").format(
                        min_collateral, loan_type.min_collateral_value_percent
                    )
                )
                
    def calculate_loan_details(self):
        """Calculate interest, fees, and installments"""
        loan_type = frappe.get_doc("Loan Type", self.loan_type)
        
        amount = flt(self.approved_amount) or flt(self.requested_amount)
        rate = flt(self.interest_rate) or flt(loan_type.interest_rate)
        tenure = self.tenure_months
        
        # Calculate interest
        if self.interest_method == "Flat Rate":
            self.total_interest = amount * (rate / 100) * (tenure / 12)
        else:  # Reducing Balance
            monthly_rate = rate / 100 / 12
            if monthly_rate > 0:
                self.total_interest = (
                    (amount * monthly_rate * pow(1 + monthly_rate, tenure)) /
                    (pow(1 + monthly_rate, tenure) - 1) * tenure
                ) - amount
            else:
                self.total_interest = 0
                
        self.total_payable = amount + flt(self.total_interest)
        self.monthly_installment = flt(self.total_payable) / tenure if tenure > 0 else 0
        
        # Calculate fees
        self.processing_fee = (
            (amount * flt(loan_type.processing_fee_percent) / 100) +
            flt(loan_type.processing_fee_fixed)
        )
        self.insurance_fee = amount * flt(loan_type.insurance_fee_percent) / 100
        
        self.net_disbursement = amount - flt(self.processing_fee) - flt(self.insurance_fee)
        
    def calculate_totals(self):
        """Calculate guarantor and collateral totals"""
        self.total_guaranteed_amount = sum(flt(g.guaranteed_amount) for g in self.guarantors)
        self.total_collateral_value = sum(flt(c.estimated_value) for c in self.collateral)
        
    def on_submit(self):
        """Handle loan submission"""
        self.db_set("status", "Pending Review")
        
    def on_cancel(self):
        """Handle loan cancellation"""
        if self.status in ["Disbursed", "Active"]:
            frappe.throw(_("Cannot cancel a disbursed or active loan"))
            
        # Reverse GL entries if any
        if self.gl_posted:
            from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
            reverse_gl_entry("Loan Application", self.name)
            self.db_set("gl_posted", 0)
            
    def on_update_after_submit(self):
        """Handle status changes after submit"""
        pass
        
    def generate_repayment_schedule(self):
        """Generate loan repayment schedule"""
        self.repayment_schedule = []
        
        amount = flt(self.disbursed_amount) or flt(self.approved_amount)
        rate = flt(self.interest_rate)
        tenure = self.tenure_months
        start_date = getdate(self.disbursement_date) or getdate(nowdate())
        
        if self.interest_method == "Flat Rate":
            # Flat rate: equal principal + declining interest
            monthly_principal = amount / tenure
            total_interest = amount * (rate / 100) * (tenure / 12)
            monthly_interest = total_interest / tenure
            
            balance = amount
            for i in range(tenure):
                due_date = add_months(start_date, i + 1)
                principal = monthly_principal
                interest = monthly_interest
                
                self.append("repayment_schedule", {
                    "due_date": due_date,
                    "principal_amount": principal,
                    "interest_amount": interest,
                    "total_due": principal + interest,
                    "balance_amount": balance - principal,
                    "status": "Pending"
                })
                balance -= principal
        else:
            # Reducing balance: EMI calculation
            monthly_rate = rate / 100 / 12
            if monthly_rate > 0:
                emi = (amount * monthly_rate * pow(1 + monthly_rate, tenure)) / \
                      (pow(1 + monthly_rate, tenure) - 1)
            else:
                emi = amount / tenure
                
            balance = amount
            for i in range(tenure):
                due_date = add_months(start_date, i + 1)
                interest = balance * monthly_rate
                principal = emi - interest
                
                self.append("repayment_schedule", {
                    "due_date": due_date,
                    "principal_amount": principal,
                    "interest_amount": interest,
                    "total_due": emi,
                    "balance_amount": balance - principal,
                    "status": "Pending"
                })
                balance -= principal
                
        self.save()
        
    def disburse_loan(self):
        """Process loan disbursement"""
        if self.status != "Approved":
            frappe.throw(_("Only approved loans can be disbursed"))
            
        if not self.disbursement_mode:
            frappe.throw(_("Please select disbursement mode"))
            
        self.disbursed_amount = self.approved_amount
        self.disbursement_date = nowdate()
        self.disbursed_by = frappe.session.user
        self.outstanding_amount = self.total_payable
        self.status = "Disbursed"
        
        # Generate repayment schedule
        self.generate_repayment_schedule()
        
        # Post to GL
        from sacco_management.sacco.utils.gl_utils import post_loan_disbursement_to_gl
        entries = post_loan_disbursement_to_gl(self)
        if entries:
            self.disbursement_journal_entry = entries[0].name
            self.gl_posted = 1
            
        # Update member loan balance
        member = frappe.get_doc("SACCO Member", self.member)
        member.update_loan_balance()
        member.db_update()
        
        self.save()
        
    def update_repayment_status(self):
        """Update outstanding amount and repayment status"""
        total_paid = frappe.db.sql("""
            SELECT 
                COALESCE(SUM(amount_paid), 0) as total,
                COALESCE(SUM(principal_paid), 0) as principal,
                COALESCE(SUM(interest_paid), 0) as interest,
                COALESCE(SUM(penalty_paid), 0) as penalty,
                MAX(payment_date) as last_date
            FROM `tabLoan Repayment`
            WHERE loan = %s AND docstatus = 1
        """, self.name, as_dict=True)[0]
        
        self.total_paid = flt(total_paid.total)
        self.total_principal_paid = flt(total_paid.principal)
        self.total_interest_paid = flt(total_paid.interest)
        self.total_penalty_paid = flt(total_paid.penalty)
        self.last_payment_date = total_paid.last_date
        
        self.outstanding_amount = flt(self.total_payable) - flt(self.total_paid)
        
        # Check if loan is fully paid
        if flt(self.outstanding_amount, 2) <= 0:
            self.status = "Closed"
            self.outstanding_amount = 0
        elif self.status == "Disbursed":
            self.status = "Active"
            
        self.db_update()


def on_submit(doc, method):
    """Hook called on submit"""
    pass


def on_cancel(doc, method):
    """Hook called on cancel"""
    pass


def on_update_after_submit(doc, method):
    """Hook called on update after submit"""
    pass


def get_permission_query_conditions(user):
    """Branch-based permission query"""
    if not user:
        user = frappe.session.user
        
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "SACCO Admin" in roles:
        return ""
        
    user_branch = frappe.db.get_value("User", user, "branch")
    if user_branch:
        return f"""(`tabLoan Application`.member IN 
            (SELECT name FROM `tabSACCO Member` WHERE branch = '{user_branch}'))"""
    
    return ""


def has_permission(doc, ptype, user):
    """Check branch-based permission"""
    if not user:
        user = frappe.session.user
        
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "SACCO Admin" in roles:
        return True
        
    member_branch = frappe.db.get_value("SACCO Member", doc.member, "branch")
    user_branch = frappe.db.get_value("User", user, "branch")
    
    if user_branch and member_branch == user_branch:
        return True
        
    return False


@frappe.whitelist()
def approve_loan(loan, approved_amount, remarks=None):
    """Approve a loan application"""
    doc = frappe.get_doc("Loan Application", loan)
    
    if doc.status not in ["Pending Review", "Under Review", "Pending Approval"]:
        frappe.throw(_("Loan is not pending approval"))
        
    doc.approved_amount = flt(approved_amount)
    doc.approved_by = frappe.session.user
    doc.approval_date = nowdate()
    doc.approval_remarks = remarks
    doc.status = "Approved"
    doc.calculate_loan_details()
    doc.save()
    
    return doc


@frappe.whitelist()
def reject_loan(loan, reason):
    """Reject a loan application"""
    doc = frappe.get_doc("Loan Application", loan)
    
    if doc.status not in ["Pending Review", "Under Review", "Pending Approval"]:
        frappe.throw(_("Loan is not pending approval"))
        
    doc.status = "Rejected"
    doc.rejection_reason = reason
    doc.save()
    
    return doc


@frappe.whitelist()
def disburse_loan(loan, disbursement_mode, reference=None):
    """Disburse an approved loan"""
    doc = frappe.get_doc("Loan Application", loan)
    doc.disbursement_mode = disbursement_mode
    doc.disbursement_reference = reference
    doc.disburse_loan()
    
    return doc
