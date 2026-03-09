"""
Loan Interest Calculation Utilities for SACCO Management System

This module provides advanced interest calculation functions for loans:
- Reducing balance interest calculations
- Daily accrual calculations
- Penalty calculations for late payments
- Amortization schedule generation
- Prepayment calculations

"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, date_diff, add_months, add_days
from datetime import timedelta


def calculate_reducing_balance_interest(principal, annual_rate, days_in_period):
    """
    Calculate interest using reducing balance method
    
    Args:
        principal: Outstanding principal amount
        annual_rate: Annual interest rate (percentage)
        days_in_period: Number of days for interest calculation
    
    Returns:
        float: Interest amount
    """
    if flt(principal) <= 0 or flt(annual_rate) <= 0:
        return 0.0
    
    # Daily interest rate
    daily_rate = flt(annual_rate) / 365 / 100
    
    # Interest for the period
    interest = flt(principal) * daily_rate * flt(days_in_period)
    
    return flt(interest, 2)


def calculate_daily_accrual(loan_name, from_date=None, to_date=None):
    """
    Calculate daily interest accrual for a loan
    
    Args:
        loan_name: Loan Application name
        from_date: Start date (default: last accrual date)
        to_date: End date (default: today)
    
    Returns:
        dict with accrual details
    """
    loan = frappe.get_doc("Loan Application", loan_name)
    
    if not from_date:
        # Get last accrual date from loan ledger
        last_accrual = frappe.db.sql("""
            SELECT MAX(accrual_date) as last_date 
            FROM `tabLoan Ledger` 
            WHERE loan_application = %s AND accrual_date IS NOT NULL
        """, (loan_name,), as_dict=True)
        
        from_date = last_accrual[0].last_date if last_accrual and last_accrual[0].last_date else loan.posting_date
    
    if not to_date:
        to_date = nowdate()
    
    days = date_diff(to_date, from_date)
    if days <= 0:
        return {"accrued_interest": 0, "days": 0}
    
    # Get outstanding principal
    outstanding_principal = get_outstanding_principal(loan_name)
    
    # Calculate daily accrual
    daily_rate = flt(loan.interest_rate) / 365 / 100
    accrued_interest = flt(outstanding_principal) * daily_rate * days
    
    return {
        "accrued_interest": flt(accrued_interest, 2),
        "days": days,
        "from_date": from_date,
        "to_date": to_date,
        "outstanding_principal": outstanding_principal
    }


def get_outstanding_principal(loan_name):
    """
    Get current outstanding principal for a loan
    
    Args:
        loan_name: Loan Application name
    
    Returns:
        float: Outstanding principal amount
    """
    loan = frappe.get_doc("Loan Application", loan_name)
    
    # Total disbursed
    total_disbursed = flt(loan.amount_requested)
    
    # Total principal repaid from loan repayments
    total_principal = frappe.db.sql("""
        SELECT COALESCE(SUM(principal_amount), 0) 
        FROM `tabLoan Repayment` 
        WHERE loan_application = %s AND docstatus = 1
    """, (loan_name,))[0][0]
    
    outstanding = flt(total_disbursed) - flt(total_principal)
    return flt(outstanding, 2)


def generate_amortization_schedule(loan_name):
    """
    Generate complete amortization schedule for a loan
    
    Args:
        loan_name: Loan Application name
    
    Returns:
        list: List of payment schedule details
    """
    loan = frappe.get_doc("Loan Application", loan_name)
    
    principal = flt(loan.amount_requested)
    annual_rate = flt(loan.interest_rate)
    months = flt(loan.repayment_period)
    
    if principal <= 0 or annual_rate <= 0 or months <= 0:
        return []
    
    # Monthly interest rate
    monthly_rate = annual_rate / 12 / 100
    
    # Calculate EMI using reducing balance formula
    if monthly_rate > 0:
        emi = principal * monthly_rate * (1 + monthly_rate)**months / ((1 + monthly_rate)**months - 1)
    else:
        emi = principal / months
    
    emi = flt(emi, 2)
    
    schedule = []
    outstanding = principal
    start_date = loan.expected_disbursement_date or nowdate()
    
    for month in range(1, int(months) + 1):
        # Interest component for this month
        interest = flt(outstanding * monthly_rate, 2)
        
        # Principal component
        principal_component = flt(emi - interest, 2)
        
        # Ensure last payment clears the balance
        if month == int(months):
            principal_component = outstanding
            emi = principal_component + interest
        
        # New outstanding balance
        outstanding = flt(outstanding - principal_component, 2)
        if outstanding < 0:
            outstanding = 0
        
        schedule.append({
            "payment_number": month,
            "payment_date": add_months(start_date, month),
            "emi_amount": emi,
            "principal_component": principal_component,
            "interest_component": interest,
            "outstanding_balance": outstanding
        })
    
    return schedule


def calculate_penalty(late_payment_amount, days_late, penalty_rate=2.0):
    """
    Calculate penalty for late loan payment
    
    Args:
        late_payment_amount: Amount that was paid late
        days_late: Number of days late
        penalty_rate: Annual penalty rate percentage (default: 2% per month = 24% per year)
    
    Returns:
        float: Penalty amount
    """
    if flt(late_payment_amount) <= 0 or days_late <= 0:
        return 0.0
    
    # Daily penalty rate
    daily_penalty_rate = flt(penalty_rate) / 365 / 100
    
    # Penalty amount
    penalty = flt(late_payment_amount) * daily_penalty_rate * days_late
    
    return flt(penalty, 2)


def calculate_prepayment_amount(loan_name, prepayment_date=None):
    """
    Calculate amount required to fully prepay a loan
    
    Args:
        loan_name: Loan Application name
        prepayment_date: Date of prepayment (default: today)
    
    Returns:
        dict with prepayment breakdown
    """
    if not prepayment_date:
        prepayment_date = nowdate()
    
    loan = frappe.get_doc("Loan Application", loan_name)
    
    # Outstanding principal
    outstanding_principal = get_outstanding_principal(loan_name)
    
    # Accrued interest to date
    accrual = calculate_daily_accrual(loan_name, to_date=prepayment_date)
    accrued_interest = accrual["accrued_interest"]
    
    # Any unpaid penalties
    unpaid_penalties = frappe.db.sql("""
        SELECT COALESCE(SUM(penalty_amount), 0) 
        FROM `tabLoan Repayment Schedule` 
        WHERE parent = %s AND penalty_amount > 0 AND paid_amount < penalty_amount
    """, (loan_name,))[0][0]
    
    # Total payoff amount
    total_payoff = flt(outstanding_principal) + flt(accrued_interest) + flt(unpaid_penalties)
    
    return {
        "outstanding_principal": outstanding_principal,
        "accrued_interest": accrued_interest,
        "unpaid_penalties": unpaid_penalties,
        "total_payoff_amount": flt(total_payoff, 2),
        "prepayment_date": prepayment_date
    }


def process_loan_interest_accrual(loan_name=None):
    """
    Process interest accrual for loans
    If loan_name is None, process all active loans
    
    Args:
        loan_name: Optional specific loan to process
    
    Returns:
        dict with processing statistics
    """
    filters = {"status": ["in", ["Disbursed", "Active"]]}
    if loan_name:
        filters["name"] = loan_name
    
    loans = frappe.get_all("Loan Application", filters=filters)
    
    stats = {
        "processed": 0,
        "total_accrued": 0,
        "errors": []
    }
    
    for loan_data in loans:
        try:
            loan = frappe.get_doc("Loan Application", loan_data.name)
            
            # Calculate accrual
            accrual = calculate_daily_accrual(loan_data.name)
            
            if accrual["accrued_interest"] > 0:
                # Create accrual entry in loan ledger
                create_interest_accrual_entry(loan, accrual)
                
                stats["total_accrued"] += accrual["accrued_interest"]
                stats["processed"] += 1
                
        except Exception as e:
            stats["errors"].append(f"{loan_data.name}: {str(e)}")
            frappe.log_error(
                message=f"Error accruing interest for {loan_data.name}: {str(e)}",
                title="Loan Interest Accrual Error"
            )
    
    return stats


def create_interest_accrual_entry(loan, accrual):
    """
    Create interest accrual entry in loan ledger
    
    Args:
        loan: Loan Application document
        accrual: Accrual calculation result dict
    """
    from sacco_management.sacco.utils.gl_utils import make_gl_entry
    
    ledger = frappe.get_doc({
        "doctype": "Loan Ledger",
        "loan_application": loan.name,
        "member": loan.member,
        "transaction_date": nowdate(),
        "accrual_date": accrual["to_date"],
        "principal_amount": 0,
        "interest_amount": accrual["accrued_interest"],
        "penalty_amount": 0,
        "outstanding_balance": accrual["outstanding_principal"],
        "remarks": f"Interest accrual from {accrual['from_date']} to {accrual['to_date']}"
    })
    
    ledger.insert(ignore_permissions=True)
    ledger.submit()
    
    # Create GL entries
    if loan.loan_account and loan.interest_income_account:
        make_gl_entry(
            voucher_type="Loan Application",
            voucher_no=loan.name,
            posting_date=nowdate(),
            account=loan.interest_income_account,
            debit=0,
            credit=accrual["accrued_interest"],
            remarks="Interest accrual on loan"
        )
        
        # Debit to accrued interest receivable
        accrued_interest_account = frappe.db.get_single_value("SACCO Settings", "accrued_interest_account")
        if accrued_interest_account:
            make_gl_entry(
                voucher_type="Loan Application",
                voucher_no=loan.name,
                posting_date=nowdate(),
                account=accrued_interest_account,
                debit=accrual["accrued_interest"],
                credit=0,
                remarks="Accrued interest receivable"
            )
