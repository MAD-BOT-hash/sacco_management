# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class LoanAppraisal(Document):
    def validate(self):
        self.validate_loan_application()
        self.calculate_financial_ratios()
        self.calculate_credit_score()
        self.determine_risk_rating()
        
    def validate_loan_application(self):
        """Validate loan application exists and is in correct status"""
        if not self.loan_application:
            frappe.throw(_("Loan Application is required"))
        
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        if loan_app.status not in ["Draft", "Pending Review"]:
            frappe.throw(_("Cannot create appraisal for {0} loan application").format(loan_app.status))
    
    def calculate_financial_ratios(self):
        """Calculate key financial ratios"""
        # Debt-to-Income Ratio
        if flt(self.monthly_income) > 0:
            total_obligations = flt(self.existing_loan_obligations)
            self.debt_to_income_ratio = (total_obligations / flt(self.monthly_income)) * 100
        
        # Disposable Income
        self.disposable_income = flt(self.monthly_income) - flt(self.monthly_expenses) - flt(self.existing_loan_obligations)
        
        # Savings Ratio
        member_savings = self.get_member_savings()
        if flt(self.monthly_income) > 0:
            self.savings_ratio = (flt(member_savings) / (flt(self.monthly_income) * 12)) * 100  # Annual savings ratio
    
    def calculate_credit_score(self):
        """Calculate credit score based on multiple factors"""
        score = 0
        
        # Payment History (40 points max)
        payment_history_score = self.evaluate_payment_history()
        score += min(40, payment_history_score)
        
        # Credit Utilization (20 points max)
        utilization_score = self.evaluate_credit_utilization()
        score += min(20, utilization_score)
        
        # Length of Credit History (15 points max)
        history_length_score = self.evaluate_credit_history_length()
        score += min(15, history_length_score)
        
        # Employment Stability (15 points max)
        employment_score = flt(self.employment_stability_score) * 0.15
        score += min(15, employment_score)
        
        # Guarantor & Collateral (10 points max)
        security_score = (flt(self.guarantor_strength) + flt(self.collateral_coverage)) / 20
        score += min(10, security_score)
        
        self.credit_score = int(min(100, score))
    
    def evaluate_payment_history(self):
        """Evaluate member's past payment history (0-40 points)"""
        member = self.member
        if not member:
            return 0
        
        # Check past defaults
        defaults = frappe.db.count("Member Fine", {
            "member": member,
            "fine_type": ["like", "%Late%"],
            "docstatus": 1
        })
        
        if defaults == 0:
            return 40  # Perfect
        elif defaults <= 2:
            return 30  # Good
        elif defaults <= 5:
            return 20  # Fair
        else:
            return 10  # Poor
    
    def evaluate_credit_utilization(self):
        """Evaluate current credit utilization (0-20 points)"""
        member = self.member
        if not member:
            return 0
        
        # Get total outstanding loans
        outstanding = frappe.db.sql("""
            SELECT COALESCE(SUM(outstanding_amount), 0)
            FROM `tabLoan Application`
            WHERE member = %s AND docstatus = 1 AND status IN ('Disbursed', 'Active')
        """, (member,))[0][0] or 0
        
        # Get member's total savings + shares
        savings = self.get_member_savings()
        shares = self.get_member_shares()
        total_assets = flt(savings) + flt(shares)
        
        if total_assets == 0:
            return 10  # No assets to compare
        
        utilization_ratio = flt(outstanding) / total_assets
        
        if utilization_ratio < 1:
            return 20  # Excellent - low utilization
        elif utilization_ratio < 2:
            return 15  # Good
        elif utilization_ratio < 3:
            return 10  # Fair
        else:
            return 5   # Poor - high utilization
    
    def evaluate_credit_history_length(self):
        """Evaluate length of credit history (0-15 points)"""
        member = self.member
        if not member:
            return 0
        
        # Get first loan date
        first_loan = frappe.db.sql("""
            SELECT MIN(application_date)
            FROM `tabLoan Application`
            WHERE member = %s AND docstatus = 1
        """, (member,))[0][0]
        
        if not first_loan:
            return 8  # No history but not penalized heavily
        
        years_of_history = (getdate(nowdate()) - getdate(first_loan)).days / 365
        
        if years_of_history >= 5:
            return 15  # Excellent
        elif years_of_history >= 3:
            return 12  # Good
        elif years_of_history >= 1:
            return 9   # Fair
        else:
            return 6   # New but acceptable
    
    def determine_risk_rating(self):
        """Determine overall risk rating based on score and factors"""
        score = flt(self.credit_score)
        
        # Adjust based on DTI
        dti_penalty = 0
        if flt(self.debt_to_income_ratio) > 50:
            dti_penalty = 15
        elif flt(self.debt_to_income_ratio) > 40:
            dti_penalty = 10
        elif flt(self.debt_to_income_ratio) > 30:
            dti_penalty = 5
        
        # Adjust based on past defaults
        default_penalty = flt(self.past_defaults) * 5
        
        adjusted_score = score - dti_penalty - default_penalty
        
        if adjusted_score >= 80:
            self.overall_risk_rating = "Very Low"
        elif adjusted_score >= 65:
            self.overall_risk_rating = "Low"
        elif adjusted_score >= 50:
            self.overall_risk_rating = "Medium"
        elif adjusted_score >= 35:
            self.overall_risk_rating = "High"
        else:
            self.overall_risk_rating = "Very High"
    
    def get_member_savings(self):
        """Get member's total savings"""
        if not self.member:
            return 0
        
        return frappe.db.sql("""
            SELECT COALESCE(SUM(balance), 0)
            FROM `tabSavings Account`
            WHERE member = %s AND status = 'Active'
        """, (self.member,))[0][0] or 0
    
    def get_member_shares(self):
        """Get member's total share value"""
        if not self.member:
            return 0
        
        member = frappe.get_doc("SACCO Member", self.member)
        return flt(member.share_value)
    
    def generate_recommendation(self):
        """Generate loan recommendation based on analysis"""
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        
        # Calculate recommended amount based on income
        annual_income = flt(self.monthly_income) * 12
        max_recommended = annual_income * 3  # 3x annual income as max
        
        # Adjust based on risk rating
        risk_multipliers = {
            "Very Low": 1.0,
            "Low": 0.9,
            "Medium": 0.75,
            "High": 0.5,
            "Very High": 0.3
        }
        
        multiplier = risk_multipliers.get(self.overall_risk_rating, 0.5)
        self.recommended_amount = min(flt(max_recommended * multiplier), flt(loan_app.requested_amount))
        
        # Recommend tenure based on amount and income
        if flt(self.recommended_amount) > 0:
            monthly_capacity = flt(self.disposable_income) * 0.4  # 40% of disposable income
            if monthly_capacity > 0:
                self.recommended_tenure = int(flt(self.recommended_amount) / monthly_capacity)
                self.recommended_tenure = max(12, min(60, self.recommended_tenure))  # Between 1-5 years
        
        # Recommend interest rate based on risk
        base_rate = flt(loan_app.interest_rate) or 12
        rate_adjustments = {
            "Very Low": -1.0,
            "Low": -0.5,
            "Medium": 0,
            "High": 1.5,
            "Very High": 3.0
        }
        self.recommended_interest_rate = base_rate + rate_adjustments.get(self.overall_risk_rating, 0)
        
        # Determine approval recommendation
        if self.overall_risk_rating in ["Very Low", "Low"]:
            self.approval_recommendation = "Recommend Approval"
        elif self.overall_risk_rating == "Medium":
            self.approval_recommendation = "Recommend with Conditions"
            self.conditions_if_any = "Additional guarantor required; Reduce loan amount to recommended level"
        elif self.overall_risk_rating == "High":
            self.approval_recommendation = "Need More Information"
            self.conditions_if_any = "Require explanation for past defaults; Additional collateral needed"
        else:
            self.approval_recommendation = "Recommend Rejection"
            self.conditions_if_any = "High risk profile; Excessive debt-to-income ratio"
    
    def on_submit(self):
        """Update loan application status on submission"""
        loan_app = frappe.get_doc("Loan Application", self.loan_application)
        loan_app.status = "Under Review"
        loan_app.save(ignore_permissions=True)
        
        frappe.msgprint(_("Loan Appraisal submitted successfully"), alert=True)


@frappe.whitelist()
def create_appraisal(loan_application):
    """Create a new loan appraisal"""
    appraisal = frappe.new_doc("Loan Appraisal")
    appraisal.loan_application = loan_application
    
    # Auto-populate from loan application
    loan_app = frappe.get_doc("Loan Application", loan_application)
    appraisal.member = loan_app.member
    appraisal.member_name = loan_app.member_name
    
    # Populate member financial data
    member = frappe.get_doc("SACCO Member", loan_app.member)
    
    # Estimate monthly income (you may want to add income field to member)
    appraisal.monthly_income = flt(member.total_savings) / 12  # Rough estimate
    
    appraisal.insert(ignore_permissions=True)
    return appraisal.as_dict()


@frappe.whitelist()
def complete_appraisal(appraisal_name):
    """Complete the appraisal and generate recommendation"""
    appraisal = frappe.get_doc("Loan Appraisal", appraisal_name)
    appraisal.generate_recommendation()
    appraisal.status = "Completed"
    appraisal.save(ignore_permissions=True)
    
    return appraisal.as_dict()
