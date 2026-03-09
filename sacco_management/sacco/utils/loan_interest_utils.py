"""
Loan Interest Calculation Utilities for SACCO Management System

This module provides advanced utility functions for loan interest calculations,
penalty computations, and amortization schedule generation.

Functions:
- calculate_loan_interest: Calculate interest for a loan
- generate_amortization_schedule: Create complete repayment schedule
- calculate_penalty: Calculate late payment penalties
- accrue_daily_interest: Daily interest accrual for accounting
- calculate_outstanding_balance: Calculate current outstanding balance
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months, date_diff


def calculate_loan_interest(principal, annual_rate, tenure_months, method="Reducing Balance"):
    """
    Calculate loan interest based on method
    
    Args:
        principal: Loan principal amount
        annual_rate: Annual interest rate (%)
        tenure_months: Loan tenure in months
        method: Interest calculation method (Flat Rate or Reducing Balance)
    
    Returns:
        dict with interest details
    """
    if method == "Flat Rate":
        return calculate_flat_rate_interest(principal, annual_rate, tenure_months)
    else:  # Reducing Balance
        return calculate_reducing_balance_interest(principal, annual_rate, tenure_months)


def calculate_flat_rate_interest(principal, annual_rate, tenure_months):
    """
    Calculate flat rate interest
    Total Interest = Principal × Rate × Time (in years)
    
    Args:
        principal: Principal amount
        annual_rate: Annual interest rate (%)
        tenure_months: Tenure in months
    
    Returns:
        dict with calculation results
    """
    total_interest = flt(principal) * (flt(annual_rate) / 100) * (flt(tenure_months) / 12)
    total_payable = flt(principal) + flt(total_interest)
    monthly_installment = flt(total_payable) / flt(tenure_months) if tenure_months > 0 else 0
    
    return {
        "total_interest": flt(total_interest),
        "total_payable": flt(total_payable),
        "monthly_installment": flt(monthly_installment),
        "principal_component": flt(principal) / flt(tenure_months) if tenure_months > 0 else 0,
        "interest_component": flt(total_interest) / flt(tenure_months) if tenure_months > 0 else 0
    }


def calculate_reducing_balance_interest(principal, annual_rate, tenure_months):
    """
    Calculate reducing balance interest using EMI formula
    
    EMI = [P x R x (1+R)^N]/[(1+R)^N-1]
    Where:
    P = Principal
    R = Monthly interest rate
    N = Tenure in months
    
    Args:
        principal: Principal amount
        annual_rate: Annual interest rate (%)
        tenure_months: Tenure in months
    
    Returns:
        dict with calculation results
    """
    if flt(annual_rate) == 0:
        # Zero interest loan
        monthly_installment = flt(principal) / flt(tenure_months) if tenure_months > 0 else 0
        return {
            "total_interest": 0,
            "total_payable": flt(principal),
            "monthly_installment": flt(monthly_installment),
            "method": "Zero Interest"
        }
    
    monthly_rate = flt(annual_rate) / 100 / 12
    n = flt(tenure_months)
    
    # EMI calculation
    if monthly_rate > 0:
        emi = (flt(principal) * monthly_rate * pow(1 + monthly_rate, n)) / \
              (pow(1 + monthly_rate, n) - 1)
    else:
        emi = flt(principal) / n
    
    total_payable = flt(emi) * n
    total_interest = flt(total_payable) - flt(principal)
    
    return {
        "total_interest": flt(total_interest),
        "total_payable": flt(total_payable),
        "monthly_installment": flt(emi),
        "method": "Reducing Balance"
    }


def generate_amortization_schedule(loan_name, principal, annual_rate, tenure_months, 
                                   method="Reducing Balance", start_date=None):
    """
    Generate complete amortization schedule for a loan
    
    Args:
        loan_name: Loan Application name
        principal: Principal amount
        annual_rate: Annual interest rate (%)
        tenure_months: Tenure in months
        method: Interest method
        start_date: First payment due date
    
    Returns:
        List of schedule entries
    """
    start_date = getdate(start_date) or getdate(nowdate())
    
    # Calculate loan details
    calc_result = calculate_loan_interest(principal, annual_rate, tenure_months, method)
    
    schedule = []
    outstanding_balance = flt(principal)
    
    if method == "Flat Rate":
        # Flat rate: equal principal + fixed interest
        monthly_principal = flt(principal) / tenure_months
        monthly_interest = flt(calc_result["total_interest"]) / tenure_months
        
        for i in range(int(tenure_months)):
            due_date = add_months(start_date, i + 1)
            interest_amount = monthly_interest
            principal_amount = monthly_principal
            total_due = principal_amount + interest_amount
            outstanding_balance -= principal_amount
            
            schedule.append({
                "payment_no": i + 1,
                "due_date": due_date,
                "principal_amount": flt(principal_amount),
                "interest_amount": flt(interest_amount),
                "total_due": flt(total_due),
                "outstanding_balance": flt(max(0, outstanding_balance)),
                "status": "Pending"
            })
    
    else:  # Reducing Balance
        monthly_rate = flt(annual_rate) / 100 / 12
        emi = calc_result["monthly_installment"]
        
        for i in range(int(tenure_months)):
            due_date = add_months(start_date, i + 1)
            
            # Calculate interest for the month
            interest_amount = flt(outstanding_balance) * monthly_rate
            
            # Principal component
            principal_amount = flt(emi) - flt(interest_amount)
            
            # Handle last installment rounding
            if i == int(tenure_months) - 1:
                principal_amount = flt(outstanding_balance)
                total_due = principal_amount + interest_amount
            else:
                total_due = flt(emi)
            
            outstanding_balance -= principal_amount
            
            schedule.append({
                "payment_no": i + 1,
                "due_date": due_date,
                "principal_amount": flt(principal_amount),
                "interest_amount": flt(interest_amount),
                "total_due": flt(total_due),
                "outstanding_balance": flt(max(0, outstanding_balance)),
                "status": "Pending"
            })
    
    return {
        "schedule": schedule,
        "summary": {
            "total_principal": flt(principal),
            "total_interest": flt(calc_result["total_interest"]),
            "total_payable": flt(calc_result["total_payable"]),
            "monthly_installment": flt(calc_result["monthly_installment"]),
            "tenure_months": int(tenure_months),
            "interest_rate": flt(annual_rate),
            "method": method
        }
    }


def calculate_penalty(overdue_amount, days_overdue, penalty_type="Percentage", 
                      penalty_rate=5, grace_period_days=7, max_penalty_cap=None):
    """
    Calculate penalty for overdue payment
    
    Args:
        overdue_amount: Overdue payment amount
        days_overdue: Number of days overdue
        penalty_type: Percentage or Fixed Amount
        penalty_rate: Penalty rate (%) or fixed amount
        grace_period_days: Grace period before penalty applies
        max_penalty_cap: Maximum penalty amount cap
    
    Returns:
        dict with penalty details
    """
    # Check grace period
    if days_overdue <= grace_period_days:
        return {
            "penalty_amount": 0,
            "days_penalized": 0,
            "reason": f"Within grace period of {grace_period_days} days"
        }
    
    actual_days_overdue = days_overdue - grace_period_days
    
    if penalty_type == "Percentage":
        # Calculate percentage penalty
        penalty_amount = flt(overdue_amount) * (flt(penalty_rate) / 100)
    else:  # Fixed Amount
        penalty_amount = flt(penalty_rate)
    
    # Apply time-based multiplier if needed (e.g., per month)
    months_overdue = actual_days_overdue / 30
    if months_overdue > 1:
        penalty_amount = penalty_amount * months_overdue
    
    # Apply cap if specified
    if max_penalty_cap and flt(penalty_amount) > flt(max_penalty_cap):
        penalty_amount = flt(max_penalty_cap)
    
    return {
        "penalty_amount": flt(penalty_amount),
        "days_penalized": actual_days_overdue,
        "calculation_basis": penalty_type,
        "rate_applied": flt(penalty_rate)
    }


def calculate_outstanding_balance(loan_name, as_of_date=None):
    """
    Calculate outstanding balance for a loan as of specific date
    
    Args:
        loan_name: Loan Application name
        as_of_date: Date to calculate balance as of
    
    Returns:
        dict with outstanding balance details
    """
    as_of_date = getdate(as_of_date) or nowdate()
    
    loan = frappe.get_doc("Loan Application", loan_name)
    
    # Get original principal
    principal = flt(loan.disbursed_amount) or flt(loan.approved_amount)
    
    # Get total repayments made
    repayments = frappe.db.sql("""
        SELECT 
            COALESCE(SUM(principal_paid), 0) as total_principal,
            COALESCE(SUM(interest_paid), 0) as total_interest,
            COALESCE(SUM(penalty_paid), 0) as total_penalty,
            COUNT(*) as payment_count,
            MAX(payment_date) as last_payment_date
        FROM `tabLoan Repayment`
        WHERE loan = %s AND docstatus = 1 AND payment_date <= %s
    """, (loan_name, as_of_date), as_dict=True)[0]
    
    total_principal_paid = flt(repayments.total_principal)
    outstanding_principal = principal - total_principal_paid
    
    # Calculate accrued interest up to as_of_date
    accrued_interest = calculate_accrued_interest(
        loan_name, 
        outstanding_principal, 
        as_of_date
    )
    
    # Get unpaid penalties
    unpaid_penalties = get_unpaid_penalties(loan_name, as_of_date)
    
    return {
        "original_principal": principal,
        "principal_repaid": total_principal_paid,
        "outstanding_principal": flt(outstanding_principal),
        "accrued_interest": flt(accrued_interest),
        "unpaid_penalties": flt(unpaid_penalties),
        "total_outstanding": flt(outstanding_principal) + flt(accrued_interest) + flt(unpaid_penalties),
        "total_payments_made": repayments.payment_count,
        "last_payment_date": repayments.last_payment_date
    }


def calculate_accrued_interest(loan_name, outstanding_principal, as_of_date=None):
    """
    Calculate accrued but not yet due interest
    
    Args:
        loan_name: Loan Application name
        outstanding_principal: Current outstanding principal
        as_of_date: Accrual date
    
    Returns:
        Accrued interest amount
    """
    loan = frappe.get_doc("Loan Application", loan_name)
    
    # Get last payment date or disbursement date
    last_payment = frappe.db.sql("""
        SELECT MAX(payment_date)
        FROM `tabLoan Repayment`
        WHERE loan = %s AND docstatus = 1
    """, (loan_name,))[0][0]
    
    from_date = getdate(last_payment) or getdate(loan.disbursement_date)
    to_date = getdate(as_of_date) or nowdate()
    
    days_accrued = date_diff(to_date, from_date)
    
    if days_accrued <= 0:
        return 0
    
    # Daily interest calculation
    annual_rate = flt(loan.interest_rate)
    daily_rate = annual_rate / 100 / 365
    
    accrued_interest = flt(outstanding_principal) * daily_rate * days_accrued
    
    return flt(accrued_interest)


def get_unpaid_penalties(loan_name, as_of_date=None):
    """
    Get total unpaid penalties for a loan
    
    Args:
        loan_name: Loan Application name
        as_of_date: Date to check
    
    Returns:
        Total unpaid penalties
    """
    as_of_date = getdate(as_of_date) or nowdate()
    
    # Get penalties from Member Fine table linked to this loan
    unpaid_fines = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0)
        FROM `tabMember Fine`
        WHERE member = (SELECT member FROM `tabLoan Application` WHERE name = %s)
        AND fine_type LIKE '%Late%'
        AND docstatus = 1
        AND (paid_amount IS NULL OR paid_amount < amount)
    """, (loan_name,))[0][0]
    
    return flt(unpaid_fines) or 0


@frappe.whitelist()
def recalculate_loan_schedule(loan_name):
    """
    Recalculate loan schedule based on current outstanding balance
    
    Useful when partial prepayments have been made
    """
    loan = frappe.get_doc("Loan Application", loan_name)
    
    # Get current outstanding balance
    outstanding_info = calculate_outstanding_balance(loan_name)
    outstanding_principal = outstanding_info["outstanding_principal"]
    
    # Get remaining tenure
    remaining_schedule = frappe.db.sql("""
        SELECT COUNT(*) 
        FROM `tabLoan Repayment Schedule`
        WHERE parent = %s AND status = 'Pending'
    """, (loan_name,))[0][0]
    
    if remaining_schedule == 0:
        return {"error": "No remaining schedule to recalculate"}
    
    # Generate new schedule for remaining balance and tenure
    new_schedule = generate_amortization_schedule(
        loan_name,
        outstanding_principal,
        loan.interest_rate,
        remaining_schedule,
        loan.interest_method,
        add_months(getdate(nowdate()), 1)
    )
    
    return new_schedule


@frappe.whitelist()
def calculate_loan_payoff_amount(loan_name, payoff_date=None):
    """
    Calculate early payoff amount for a loan
    
    Includes outstanding principal + accrued interest + penalties
    """
    payoff_date = getdate(payoff_date) or nowdate()
    
    outstanding_info = calculate_outstanding_balance(loan_name, payoff_date)
    
    # Check for prepayment penalty
    loan = frappe.get_doc("Loan Application", loan_name)
    loan_type = frappe.get_doc("Loan Type", loan.loan_type)
    
    prepayment_penalty = 0
    if hasattr(loan_type, 'prepayment_penalty_percent'):
        prepayment_penalty = flt(outstanding_info["outstanding_principal"]) * \
                           (flt(loan_type.prepayment_penalty_percent) / 100)
    
    return {
        "payoff_principal": outstanding_info["outstanding_principal"],
        "accrued_interest": outstanding_info["accrued_interest"],
        "unpaid_penalties": outstanding_info["unpaid_penalties"],
        "prepayment_penalty": prepayment_penalty,
        "total_payoff_amount": flt(outstanding_info["outstanding_principal"]) + 
                              flt(outstanding_info["accrued_interest"]) + 
                              flt(outstanding_info["unpaid_penalties"]) + 
                              prepayment_penalty,
        "as_of_date": payoff_date
    }
