"""
Loan Utilities for SACCO Management System

This module provides utility functions for loan calculations including:
- Interest calculations (flat rate and reducing balance)
- Amortization schedule generation
- Penalty calculations
- Loan eligibility checks
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months, date_diff
import math


def calculate_flat_rate_interest(principal, annual_rate, tenure_months):
    """
    Calculate interest using flat rate method
    
    Formula: Interest = Principal × Rate × Time
    
    Args:
        principal: Loan amount
        annual_rate: Annual interest rate (percentage)
        tenure_months: Loan tenure in months
        
    Returns:
        Total interest amount
    """
    rate = flt(annual_rate) / 100
    time_years = flt(tenure_months) / 12
    return flt(principal) * rate * time_years


def calculate_reducing_balance_interest(principal, annual_rate, tenure_months):
    """
    Calculate total interest using reducing balance method
    
    Uses EMI formula to calculate total payments, then subtracts principal
    
    Args:
        principal: Loan amount
        annual_rate: Annual interest rate (percentage)
        tenure_months: Loan tenure in months
        
    Returns:
        Total interest amount
    """
    if flt(annual_rate) == 0 or flt(tenure_months) == 0:
        return 0
        
    monthly_rate = flt(annual_rate) / 100 / 12
    n = int(tenure_months)
    
    # EMI = P × r × (1+r)^n / ((1+r)^n - 1)
    emi = (flt(principal) * monthly_rate * pow(1 + monthly_rate, n)) / (pow(1 + monthly_rate, n) - 1)
    
    total_payment = emi * n
    return total_payment - flt(principal)


def calculate_emi(principal, annual_rate, tenure_months, interest_method="Reducing Balance"):
    """
    Calculate Equated Monthly Installment
    
    Args:
        principal: Loan amount
        annual_rate: Annual interest rate (percentage)
        tenure_months: Loan tenure in months
        interest_method: "Flat Rate" or "Reducing Balance"
        
    Returns:
        Monthly installment amount
    """
    if flt(tenure_months) == 0:
        return 0
        
    if interest_method == "Flat Rate":
        total_interest = calculate_flat_rate_interest(principal, annual_rate, tenure_months)
        return (flt(principal) + total_interest) / flt(tenure_months)
    else:
        if flt(annual_rate) == 0:
            return flt(principal) / flt(tenure_months)
            
        monthly_rate = flt(annual_rate) / 100 / 12
        n = int(tenure_months)
        
        return (flt(principal) * monthly_rate * pow(1 + monthly_rate, n)) / (pow(1 + monthly_rate, n) - 1)


def generate_amortization_schedule(
    principal,
    annual_rate,
    tenure_months,
    start_date,
    interest_method="Reducing Balance"
):
    """
    Generate loan amortization schedule
    
    Args:
        principal: Loan amount
        annual_rate: Annual interest rate (percentage)
        tenure_months: Loan tenure in months
        start_date: Disbursement date
        interest_method: "Flat Rate" or "Reducing Balance"
        
    Returns:
        List of schedule entries with due_date, principal, interest, total_due, balance
    """
    schedule = []
    balance = flt(principal)
    start = getdate(start_date)
    
    if interest_method == "Flat Rate":
        monthly_principal = balance / int(tenure_months)
        total_interest = calculate_flat_rate_interest(principal, annual_rate, tenure_months)
        monthly_interest = total_interest / int(tenure_months)
        
        for i in range(int(tenure_months)):
            due_date = add_months(start, i + 1)
            schedule.append({
                "installment_no": i + 1,
                "due_date": due_date,
                "principal_amount": monthly_principal,
                "interest_amount": monthly_interest,
                "total_due": monthly_principal + monthly_interest,
                "balance_amount": balance - monthly_principal,
                "status": "Pending"
            })
            balance -= monthly_principal
    else:
        # Reducing Balance
        monthly_rate = flt(annual_rate) / 100 / 12 if flt(annual_rate) > 0 else 0
        emi = calculate_emi(principal, annual_rate, tenure_months, "Reducing Balance")
        
        for i in range(int(tenure_months)):
            due_date = add_months(start, i + 1)
            interest = balance * monthly_rate
            principal_portion = emi - interest
            
            # Adjust last installment for rounding
            if i == int(tenure_months) - 1:
                principal_portion = balance
                
            schedule.append({
                "installment_no": i + 1,
                "due_date": due_date,
                "principal_amount": principal_portion,
                "interest_amount": interest,
                "total_due": principal_portion + interest,
                "balance_amount": max(0, balance - principal_portion),
                "status": "Pending"
            })
            balance = max(0, balance - principal_portion)
            
    return schedule


def calculate_penalty(overdue_amount, penalty_rate, days_overdue, grace_period=0):
    """
    Calculate penalty on overdue amount
    
    Args:
        overdue_amount: Amount that is overdue
        penalty_rate: Annual penalty rate (percentage)
        days_overdue: Number of days overdue
        grace_period: Grace period in days before penalty applies
        
    Returns:
        Penalty amount
    """
    if days_overdue <= grace_period:
        return 0
        
    effective_days = days_overdue - grace_period
    daily_rate = flt(penalty_rate) / 100 / 365
    
    return flt(overdue_amount) * daily_rate * effective_days


def check_loan_eligibility(member, loan_type):
    """
    Check if a member is eligible for a loan
    
    Args:
        member: Member docname
        loan_type: Loan Type docname
        
    Returns:
        dict with eligibility status, max amount, and reasons
    """
    member_doc = frappe.get_doc("SACCO Member", member)
    loan_type_doc = frappe.get_doc("Loan Type", loan_type)
    
    eligibility = {
        "eligible": True,
        "max_amount": 0,
        "reasons": [],
        "warnings": []
    }
    
    # Check member status
    if member_doc.status != "Active":
        eligibility["eligible"] = False
        eligibility["reasons"].append(_("Member status is {0}, must be Active").format(member_doc.status))
        
    # Check contribution months
    member_doc.update_contribution_balance()
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
        
    # Check for existing active loans of same type
    existing_loans = frappe.db.count("Loan Application", {
        "member": member,
        "loan_type": loan_type,
        "status": ["in", ["Disbursed", "Active"]],
        "docstatus": 1
    })
    
    if existing_loans > 0:
        eligibility["warnings"].append(
            _("Member already has {0} active loan(s) of this type").format(existing_loans)
        )
        
    # Calculate maximum loan amount
    max_by_savings = flt(member_doc.total_savings) * flt(loan_type_doc.max_loan_multiplier)
    max_by_type = flt(loan_type_doc.max_amount)
    
    eligibility["max_amount"] = min(max_by_savings, max_by_type)
    
    if eligibility["max_amount"] < flt(loan_type_doc.min_amount):
        eligibility["eligible"] = False
        eligibility["reasons"].append(
            _("Maximum eligible amount ({0}) is less than minimum loan amount ({1})").format(
                eligibility["max_amount"], loan_type_doc.min_amount
            )
        )
        
    # Check guarantor capacity (if required)
    if loan_type_doc.requires_guarantors:
        eligibility["requires_guarantors"] = True
        eligibility["min_guarantors"] = loan_type_doc.min_guarantors
        
    # Check collateral requirement
    if loan_type_doc.requires_collateral:
        eligibility["requires_collateral"] = True
        eligibility["min_collateral_percent"] = loan_type_doc.min_collateral_value_percent
        
    return eligibility


def get_loan_summary(member):
    """
    Get comprehensive loan summary for a member
    
    Args:
        member: Member docname
        
    Returns:
        dict with loan statistics
    """
    summary = {
        "total_loans": 0,
        "active_loans": 0,
        "total_borrowed": 0,
        "total_repaid": 0,
        "outstanding_balance": 0,
        "overdue_amount": 0,
        "loans_by_type": [],
        "recent_payments": []
    }
    
    # Get loan statistics
    loans = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_loans,
            SUM(CASE WHEN status IN ('Disbursed', 'Active') THEN 1 ELSE 0 END) as active_loans,
            SUM(disbursed_amount) as total_borrowed,
            SUM(total_paid) as total_repaid,
            SUM(outstanding_amount) as outstanding_balance
        FROM `tabLoan Application`
        WHERE member = %s AND docstatus = 1
    """, member, as_dict=True)[0]
    
    summary.update({
        "total_loans": loans.total_loans or 0,
        "active_loans": loans.active_loans or 0,
        "total_borrowed": flt(loans.total_borrowed),
        "total_repaid": flt(loans.total_repaid),
        "outstanding_balance": flt(loans.outstanding_balance)
    })
    
    # Get overdue amount
    overdue = frappe.db.sql("""
        SELECT COALESCE(SUM(lrs.total_due - lrs.paid_amount), 0) as overdue
        FROM `tabLoan Repayment Schedule` lrs
        INNER JOIN `tabLoan Application` la ON lrs.parent = la.name
        WHERE la.member = %s AND la.docstatus = 1 AND lrs.status = 'Overdue'
    """, member)[0][0]
    summary["overdue_amount"] = flt(overdue)
    
    # Get loans by type
    loans_by_type = frappe.db.sql("""
        SELECT 
            loan_type,
            COUNT(*) as count,
            SUM(disbursed_amount) as total_amount
        FROM `tabLoan Application`
        WHERE member = %s AND docstatus = 1
        GROUP BY loan_type
    """, member, as_dict=True)
    summary["loans_by_type"] = loans_by_type
    
    # Get recent payments
    recent_payments = frappe.db.sql("""
        SELECT 
            name,
            payment_date,
            amount_paid,
            loan
        FROM `tabLoan Repayment`
        WHERE member = %s AND docstatus = 1
        ORDER BY payment_date DESC
        LIMIT 5
    """, member, as_dict=True)
    summary["recent_payments"] = recent_payments
    
    return summary


def update_overdue_status():
    """
    Update overdue status for all active loan schedules
    Called by scheduler daily
    """
    today = nowdate()
    
    # Get all pending schedules that are past due date
    overdue_schedules = frappe.db.sql("""
        SELECT lrs.name, lrs.parent
        FROM `tabLoan Repayment Schedule` lrs
        INNER JOIN `tabLoan Application` la ON lrs.parent = la.name
        WHERE la.docstatus = 1 
        AND la.status IN ('Disbursed', 'Active')
        AND lrs.status IN ('Pending', 'Partial')
        AND lrs.due_date < %s
    """, today, as_dict=True)
    
    for schedule in overdue_schedules:
        frappe.db.set_value(
            "Loan Repayment Schedule", 
            schedule.name, 
            "status", 
            "Overdue",
            update_modified=False
        )
        
    frappe.db.commit()
    
    return len(overdue_schedules)


@frappe.whitelist()
def get_loan_statement(loan, from_date=None, to_date=None):
    """
    Get loan statement with all transactions
    
    Args:
        loan: Loan Application name
        from_date: Start date filter
        to_date: End date filter
        
    Returns:
        dict with loan details and transaction history
    """
    loan_doc = frappe.get_doc("Loan Application", loan)
    
    statement = {
        "loan": loan,
        "member": loan_doc.member,
        "member_name": loan_doc.member_name,
        "loan_type": loan_doc.loan_type,
        "disbursed_amount": loan_doc.disbursed_amount,
        "total_payable": loan_doc.total_payable,
        "outstanding_amount": loan_doc.outstanding_amount,
        "status": loan_doc.status,
        "schedule": [],
        "payments": []
    }
    
    # Get repayment schedule
    for row in loan_doc.repayment_schedule:
        statement["schedule"].append({
            "due_date": row.due_date,
            "principal": row.principal_amount,
            "interest": row.interest_amount,
            "total_due": row.total_due,
            "paid_amount": row.paid_amount,
            "status": row.status
        })
        
    # Get payment history
    conditions = "loan = %(loan)s AND docstatus = 1"
    values = {"loan": loan}
    
    if from_date:
        conditions += " AND payment_date >= %(from_date)s"
        values["from_date"] = from_date
        
    if to_date:
        conditions += " AND payment_date <= %(to_date)s"
        values["to_date"] = to_date
        
    payments = frappe.db.sql(f"""
        SELECT 
            name,
            payment_date,
            amount_paid,
            principal_paid,
            interest_paid,
            penalty_paid,
            payment_mode,
            reference_number
        FROM `tabLoan Repayment`
        WHERE {conditions}
        ORDER BY payment_date
    """, values, as_dict=True)
    
    statement["payments"] = payments
    
    return statement
