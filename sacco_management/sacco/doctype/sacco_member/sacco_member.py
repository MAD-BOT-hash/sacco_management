import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import getdate, nowdate, date_diff, flt


class SaccoMember(Document):
    def validate(self):
        self.validate_id_number()
        self.validate_age()
        self.validate_nominees()
        self.validate_phone()
        self.set_full_name()
        
    def validate_id_number(self):
        """Ensure ID number is unique"""
        if self.id_number:
            self.id_number = self.id_number.strip().upper()
            existing = frappe.db.exists(
                "SACCO Member", 
                {"id_number": self.id_number, "name": ("!=", self.name)}
            )
            if existing:
                frappe.throw(_("A member with ID Number {0} already exists: {1}").format(
                    self.id_number, existing
                ))
                
    def validate_age(self):
        """Ensure member is at least 18 years old"""
        if self.date_of_birth:
            age = date_diff(nowdate(), self.date_of_birth) / 365
            if age < 18:
                frappe.throw(_("Member must be at least 18 years old. Current age: {0:.1f} years").format(age))
                
    def validate_nominees(self):
        """Validate nominee share percentages"""
        if self.nominees:
            total_percentage = sum(flt(n.share_percentage) for n in self.nominees)
            if total_percentage > 100:
                frappe.throw(_("Total nominee share percentage cannot exceed 100%. Current: {0}%").format(total_percentage))
                
    def validate_phone(self):
        """Clean and validate phone number"""
        if self.phone:
            self.phone = self.phone.strip().replace(" ", "")
            
    def set_full_name(self):
        """Ensure member name is properly formatted"""
        if self.member_name:
            self.member_name = " ".join(self.member_name.strip().split())
            
    def on_update(self):
        self.update_balances()
        
    def update_balances(self):
        """Update all member balances"""
        self.update_contribution_balance()
        self.update_share_balance()
        self.update_loan_balance()
        self.update_fine_balance()
        
    def update_contribution_balance(self):
        """Calculate total contributions"""
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM `tabMember Contribution`
            WHERE member = %s AND docstatus = 1
        """, self.name)[0][0]
        self.total_contributions = flt(result)
        
        # Calculate savings (contributions with interest applicable)
        savings = frappe.db.sql("""
            SELECT COALESCE(SUM(mc.amount), 0) as total
            FROM `tabMember Contribution` mc
            INNER JOIN `tabContribution Type` ct ON mc.contribution_type = ct.name
            WHERE mc.member = %s AND mc.docstatus = 1 AND ct.interest_applicable = 1
        """, self.name)[0][0]
        self.total_savings = flt(savings)
        
    def update_share_balance(self):
        """Calculate total shares and value"""
        result = frappe.db.sql("""
            SELECT 
                COALESCE(SUM(quantity), 0) as total_shares,
                COALESCE(SUM(total_amount), 0) as share_value
            FROM `tabShare Allocation`
            WHERE member = %s AND docstatus = 1 AND status = 'Allocated'
        """, self.name, as_dict=True)[0]
        self.total_shares = result.total_shares or 0
        self.share_value = flt(result.share_value)
        
    def update_loan_balance(self):
        """Calculate loan balances"""
        # Total loans taken
        total_loans = frappe.db.sql("""
            SELECT COALESCE(SUM(disbursed_amount), 0)
            FROM `tabLoan Application`
            WHERE member = %s AND docstatus = 1 AND status IN ('Disbursed', 'Active', 'Closed')
        """, self.name)[0][0]
        self.total_loans_taken = flt(total_loans)
        
        # Outstanding balance
        outstanding = frappe.db.sql("""
            SELECT COALESCE(SUM(outstanding_amount), 0)
            FROM `tabLoan Application`
            WHERE member = %s AND docstatus = 1 AND status IN ('Disbursed', 'Active')
        """, self.name)[0][0]
        self.outstanding_loan_balance = flt(outstanding)
        
    def update_fine_balance(self):
        """Calculate fine balances"""
        # Total fines
        total_fines = frappe.db.sql("""
            SELECT COALESCE(SUM(amount), 0)
            FROM `tabMember Fine`
            WHERE member = %s AND docstatus = 1
        """, self.name)[0][0]
        self.total_fines = flt(total_fines)
        
        # Unpaid fines
        unpaid = frappe.db.sql("""
            SELECT COALESCE(SUM(amount - COALESCE(paid_amount, 0)), 0)
            FROM `tabMember Fine`
            WHERE member = %s AND docstatus = 1 AND status != 'Paid'
        """, self.name)[0][0]
        self.unpaid_fines = flt(unpaid)
        
    def get_contribution_months(self):
        """Get number of months member has contributed"""
        result = frappe.db.sql("""
            SELECT COUNT(DISTINCT DATE_FORMAT(contribution_date, '%%Y-%%m')) as months
            FROM `tabMember Contribution`
            WHERE member = %s AND docstatus = 1
        """, self.name)[0][0]
        return result or 0
        
    def has_loan_arrears(self):
        """Check if member has any loan arrears"""
        arrears = frappe.db.sql("""
            SELECT COUNT(*)
            FROM `tabLoan Application` la
            INNER JOIN `tabLoan Repayment Schedule` lrs ON lrs.parent = la.name
            WHERE la.member = %s 
            AND la.docstatus = 1 
            AND la.status IN ('Disbursed', 'Active')
            AND lrs.status = 'Overdue'
        """, self.name)[0][0]
        return arrears > 0
        
    def get_guarantor_exposure(self):
        """Get total amount member is guaranteeing for others"""
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(lg.guaranteed_amount), 0)
            FROM `tabLoan Guarantor` lg
            INNER JOIN `tabLoan Application` la ON lg.parent = la.name
            WHERE lg.guarantor_member = %s 
            AND la.docstatus = 1 
            AND la.status IN ('Disbursed', 'Active')
        """, self.name)[0][0]
        return flt(result)


def get_permission_query_conditions(user):
    """Branch-based permission query"""
    if not user:
        user = frappe.session.user
        
    if "System Manager" in frappe.get_roles(user) or "SACCO Admin" in frappe.get_roles(user):
        return ""
        
    # Get user's branch
    user_branch = frappe.db.get_value("User", user, "branch")
    if user_branch:
        return f"(`tabSACCO Member`.branch = '{user_branch}')"
    
    return ""


def has_permission(doc, ptype, user):
    """Check branch-based permission"""
    if not user:
        user = frappe.session.user
        
    roles = frappe.get_roles(user)
    if "System Manager" in roles or "SACCO Admin" in roles:
        return True
        
    user_branch = frappe.db.get_value("User", user, "branch")
    if user_branch and doc.branch == user_branch:
        return True
        
    return False


@frappe.whitelist()
def get_member_summary(member):
    """Get comprehensive member summary"""
    doc = frappe.get_doc("SACCO Member", member)
    doc.update_balances()
    doc.db_update()
    
    return {
        "member_name": doc.member_name,
        "status": doc.status,
        "branch": doc.branch,
        "join_date": doc.join_date,
        "total_contributions": doc.total_contributions,
        "total_savings": doc.total_savings,
        "total_shares": doc.total_shares,
        "share_value": doc.share_value,
        "total_loans_taken": doc.total_loans_taken,
        "outstanding_loan_balance": doc.outstanding_loan_balance,
        "total_fines": doc.total_fines,
        "unpaid_fines": doc.unpaid_fines,
        "contribution_months": doc.get_contribution_months(),
        "has_arrears": doc.has_loan_arrears(),
        "guarantor_exposure": doc.get_guarantor_exposure()
    }


@frappe.whitelist()
def check_loan_eligibility(member, loan_type):
    """Check if member is eligible for a loan"""
    member_doc = frappe.get_doc("SACCO Member", member)
    loan_type_doc = frappe.get_doc("Loan Type", loan_type)
    
    eligibility = {
        "eligible": True,
        "reasons": [],
        "max_amount": 0
    }
    
    # Check contribution months
    contribution_months = member_doc.get_contribution_months()
    if contribution_months < loan_type_doc.min_contribution_months:
        eligibility["eligible"] = False
        eligibility["reasons"].append(
            _("Minimum {0} contribution months required. Current: {1}").format(
                loan_type_doc.min_contribution_months, contribution_months
            )
        )
    
    # Check for existing loan arrears
    if member_doc.has_loan_arrears():
        eligibility["eligible"] = False
        eligibility["reasons"].append(_("Member has existing loan arrears"))
    
    # Check member status
    if member_doc.status != "Active":
        eligibility["eligible"] = False
        eligibility["reasons"].append(_("Member status is not Active"))
    
    # Calculate max loan amount based on savings multiplier
    member_doc.update_contribution_balance()
    max_by_savings = flt(member_doc.total_savings) * flt(loan_type_doc.max_loan_multiplier)
    max_by_type = flt(loan_type_doc.max_amount)
    
    eligibility["max_amount"] = min(max_by_savings, max_by_type)
    
    if eligibility["max_amount"] <= 0:
        eligibility["eligible"] = False
        eligibility["reasons"].append(_("No savings to qualify for loan"))
    
    return eligibility
