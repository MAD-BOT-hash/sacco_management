"""
Savings Utilities for SACCO Management System

This module provides utility functions for savings account management,
interest calculations, and automated processing.

Functions:
- calculate_savings_interest: Calculate interest for a single account
- process_monthly_interest: Batch process interest for all accounts
- get_account_statement: Generate account statements
- accrue_daily_interest: Daily interest accrual calculations
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months, date_diff
from datetime import timedelta


def calculate_savings_interest(account_name, from_date=None, to_date=None):
    """
    Calculate interest for a savings account
    
    Args:
        account_name: Savings Account name
        from_date: Start date (default: last calculation date)
        to_date: End date (default: today)
    
    Returns:
        dict with interest details
    """
    account = frappe.get_doc("Savings Account", account_name)
    
    if not account.interest_rate or account.interest_rate <= 0:
        return {
            "interest": 0,
            "principal": 0,
            "rate": 0,
            "days": 0,
            "method": "N/A"
        }
    
    # Get dates
    from_date = getdate(from_date) or getdate(account.last_interest_calculation_date) or getdate(account.opening_date)
    to_date = getdate(to_date) or nowdate()
    days_in_period = (to_date - from_date).days or 1
    
    # Get product
    product = frappe.get_doc("Savings Product", account.product)
    
    # Check minimum balance for interest
    if flt(product.min_balance_for_interest) > 0 and flt(account.balance) < flt(product.min_balance_for_interest):
        return {
            "interest": 0,
            "principal": flt(account.balance),
            "rate": 0,
            "days": days_in_period,
            "method": account.interest_calculation_method,
            "reason": f"Balance below minimum {product.min_balance_for_interest}"
        }
    
    # Calculate principal based on method
    method = account.interest_calculation_method or "Daily Balance"
    
    if method == "Daily Balance":
        principal = get_daily_average_balance(account_name, from_date, to_date)
    elif method == "Monthly Balance":
        principal = flt(account.balance)
    elif method == "Average Balance":
        principal = get_daily_average_balance(account_name, from_date, to_date)
    elif method == "Minimum Balance":
        principal = get_minimum_balance_in_period(account_name, from_date, to_date)
    else:
        principal = flt(account.balance)
    
    # Check for applicable interest rules
    applicable_rules = get_applicable_interest_rules(account_name)
    total_interest = 0
    applied_rates = []
    
    if applicable_rules:
        # Use rule-based calculation
        for rule in applicable_rules:
            rule_doc = frappe.get_doc("Savings Interest Rule", rule['name'])
            interest = rule_doc.calculate_interest(account, from_date, to_date)
            if interest > 0:
                total_interest += interest
                applied_rates.append(f"{rule['rule_name']}: {interest:.2f}")
    else:
        # Default calculation
        days_in_year = 365
        total_interest = (principal * flt(account.interest_rate) * days_in_period) / (100 * days_in_year)
    
    return {
        "interest": flt(total_interest),
        "principal": flt(principal),
        "rate": flt(account.interest_rate),
        "days": days_in_period,
        "method": method,
        "from_date": from_date,
        "to_date": to_date,
        "applied_rules": ", ".join(applied_rates) if applied_rates else "Default"
    }


def get_daily_average_balance(account_name, from_date, to_date):
    """
    Calculate daily average balance for a period
    
    Args:
        account_name: Savings Account name
        from_date: Start date
        to_date: End date
    
    Returns:
        Average daily balance
    """
    transactions = frappe.db.sql("""
        SELECT 
            DATE(transaction_date) as trans_date,
            SUM(CASE WHEN transaction_type IN ('Deposit', 'Interest Credit', 'Transfer In') THEN amount ELSE 0 END) as inflows,
            SUM(CASE WHEN transaction_type IN ('Withdrawal', 'Penalty Debit', 'Transfer Out') THEN amount ELSE 0 END) as outflows
        FROM `tabSavings Transaction`
        WHERE account = %s 
        AND DATE(transaction_date) BETWEEN %s AND %s
        GROUP BY DATE(transaction_date)
        ORDER BY trans_date
    """, (account_name, from_date, to_date), as_dict=True)
    
    if not transactions:
        account = frappe.get_doc("Savings Account", account_name)
        return flt(account.balance)
    
    account = frappe.get_doc("Savings Account", account_name)
    total_balance_days = 0
    running_balance = flt(account.balance)
    
    for row in transactions:
        balance = running_balance - flt(row.inflows) + flt(row.outflows)
        total_balance_days += abs(balance)
        running_balance = balance
    
    days_in_period = (to_date - from_date).days or 1
    return total_balance_days / days_in_period


def get_minimum_balance_in_period(account_name, from_date, to_date):
    """
    Get minimum balance during a period
    
    Args:
        account_name: Savings Account name
        from_date: Start date
        to_date: End date
    
    Returns:
        Minimum balance
    """
    min_balance = frappe.db.sql("""
        SELECT MIN(balance_after_transaction)
        FROM `tabSavings Transaction`
        WHERE account = %s 
        AND DATE(transaction_date) BETWEEN %s AND %s
    """, (account_name, from_date, to_date))[0][0]
    
    return flt(min_balance) if min_balance else 0


def get_applicable_interest_rules(account_name):
    """
    Get all applicable interest rules for an account
    
    Args:
        account_name: Savings Account name
    
    Returns:
        List of applicable rules
    """
    account = frappe.get_doc("Savings Account", account_name)
    
    rules = frappe.db.sql("""
        SELECT name, rule_name, priority, special_interest_rate
        FROM `tabSavings Interest Rule`
        WHERE product = %s AND is_active = 1
        ORDER BY priority ASC
    """, (account.product,), as_dict=True)
    
    applicable_rules = []
    for rule_data in rules:
        rule = frappe.get_doc("Savings Interest Rule", rule_data.name)
        if rule.is_applicable(account):
            applicable_rules.append({
                "name": rule_data.name,
                "rule_name": rule_data.rule_name,
                "priority": rule_data.priority,
                "special_interest_rate": flt(rule_data.special_interest_rate)
            })
    
    return applicable_rules


def process_monthly_interest(posting_date=None):
    """
    Process monthly interest for all eligible savings accounts
    
    Args:
        posting_date: Posting date (default: today)
    
    Returns:
        dict with processing statistics
    """
    posting_date = getdate(posting_date) or nowdate()
    
    # Get all active savings accounts due for interest posting
    accounts = frappe.db.sql("""
        SELECT sa.name, sa.member, sa.product, sa.balance, 
               sa.last_interest_calculation_date, sa.next_interest_posting_date,
               p.interest_posting_frequency
        FROM `tabSavings Account` sa
        INNER JOIN `tabSavings Product` p ON sa.product = p.name
        WHERE sa.status = 'Active'
        AND sa.interest_rate > 0
        AND (sa.next_interest_posting_date IS NULL OR sa.next_interest_posting_date <= %s)
    """, (posting_date,), as_dict=True)
    
    stats = {
        "total_accounts": len(accounts),
        "processed": 0,
        "failed": 0,
        "total_interest_posted": 0,
        "errors": []
    }
    
    for acc_data in accounts:
        try:
            # Determine period start date
            period_start = getdate(acc_data.last_interest_calculation_date) or getdate(acc_data.opening_date)
            period_end = posting_date
            
            # Create interest posting document
            interest_doc = frappe.new_doc("Savings Interest Posting")
            interest_doc.account = acc_data.name
            interest_doc.period_start_date = period_start
            interest_doc.period_end_date = period_end
            interest_doc.posting_date = posting_date
            
            # Calculate and post interest
            interest_doc.calculate_interest()
            interest_doc.insert(ignore_permissions=True)
            interest_doc.submit()
            
            stats["processed"] += 1
            stats["total_interest_posted"] += flt(interest_doc.total_interest)
            
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append(f"{acc_data.name}: {str(e)}")
            frappe.log_error(
                title=f"Interest Processing Failed for {acc_data.name}",
                message=str(e)
            )
    
    return stats


def accrue_daily_interest(accrual_date=None):
    """
    Calculate daily accrued interest for all accounts (for accounting purposes)
    
    This function calculates but does not post interest. Used for day-end accruals.
    
    Args:
        accrual_date: Date for accrual (default: today)
    
    Returns:
        dict with accrual statistics
    """
    accrual_date = getdate(accrual_date) or nowdate()
    
    # Get all interest-bearing active accounts
    accounts = frappe.db.sql("""
        SELECT sa.name, sa.member, sa.product, sa.balance, sa.interest_rate,
               sa.accrued_interest, p.interest_calculation_method
        FROM `tabSavings Account` sa
        INNER JOIN `tabSavings Product` p ON sa.product = p.name
        WHERE sa.status = 'Active'
        AND sa.interest_rate > 0
        AND p.interest_applicable = 1
    """, as_dict=True)
    
    stats = {
        "total_accounts": len(accounts),
        "total_accrued": 0,
        "accounts_updated": 0
    }
    
    for acc_data in accounts:
        try:
            # Calculate one day interest
            from_date = accrual_date
            to_date = accrual_date
            
            interest_info = calculate_savings_interest(acc_data.name, from_date, to_date)
            daily_interest = flt(interest_info.get("interest", 0))
            
            # Update account accrued interest
            if daily_interest > 0:
                account = frappe.get_doc("Savings Account", acc_data.name)
                account.accrued_interest = flt(account.accrued_interest) + daily_interest
                account.save(ignore_permissions=True)
                
                stats["accounts_updated"] += 1
                stats["total_accrued"] += daily_interest
                
        except Exception as e:
            frappe.log_error(
                title=f"Daily Accrual Failed for {acc_data.name}",
                message=str(e)
            )
    
    return stats


def get_account_statement(account_name, from_date=None, to_date=None, include_projections=False):
    """
    Generate comprehensive account statement
    
    Args:
        account_name: Savings Account name
        from_date: Start date
        to_date: End date
        include_projections: Include future interest projections
    
    Returns:
        dict with statement data
    """
    account = frappe.get_doc("Savings Account", account_name)
    product = frappe.get_doc("Savings Product", account.product)
    
    from_date = getdate(from_date) or getdate(account.opening_date)
    to_date = getdate(to_date) or nowdate()
    
    # Get transactions
    transactions = frappe.db.sql("""
        SELECT 
            transaction_date,
            transaction_type,
            amount,
            balance_after_transaction,
            remarks,
            payment_mode,
            reference_number
        FROM `tabSavings Transaction`
        WHERE account = %s 
        AND DATE(transaction_date) BETWEEN %s AND %s
        ORDER BY transaction_date, creation
    """, (account_name, from_date, to_date), as_dict=True)
    
    # Calculate summary
    total_deposits = sum(flt(t.amount) for t in transactions if t.transaction_type in ["Deposit", "Interest Credit", "Transfer In"])
    total_withdrawals = sum(flt(t.amount) for t in transactions if t.transaction_type in ["Withdrawal", "Penalty Debit", "Transfer Out"])
    net_change = total_deposits - total_withdrawals
    
    statement = {
        "account_info": {
            "account_name": account.account_name,
            "member": account.member_name,
            "member_id": account.member,
            "product": product.product_name,
            "branch": account.branch
        },
        "period": {
            "from_date": from_date,
            "to_date": to_date
        },
        "summary": {
            "opening_balance": flt(account.balance) - net_change,
            "closing_balance": flt(account.balance),
            "total_deposits": total_deposits,
            "total_withdrawals": total_withdrawals,
            "net_change": net_change,
            "total_interest_earned": account.total_interest_earned
        },
        "transactions": transactions,
        "product_details": {
            "interest_rate": product.interest_rate if product.interest_applicable else 0,
            "min_balance": product.min_balance,
            "max_balance": product.max_balance
        }
    }
    
    # Include projections if requested
    if include_projections and product.interest_applicable:
        # Project interest for next year
        projected_annual_interest = (flt(account.balance) * flt(product.interest_rate)) / 100
        statement["projections"] = {
            "projected_annual_interest": projected_annual_interest,
            "projected_balance_after_year": flt(account.balance) + projected_annual_interest
        }
    
    return statement


@frappe.whitelist()
def generate_member_statement(member, include_all_accounts=True):
    """
    Generate consolidated statement for a member
    
    Args:
        member: Member ID
        include_all_accounts: Include all member's accounts
    
    Returns:
        Consolidated statement
    """
    accounts = frappe.get_all("Savings Account",
        filters={"member": member, "status": "Active"},
        fields=["name", "account_name", "product", "balance"])
    
    statements = []
    total_balance = 0
    
    for acc_data in accounts:
        statement = get_account_statement(acc_data.name)
        statements.append(statement)
        total_balance += flt(statement["summary"]["closing_balance"])
    
    return {
        "member": member,
        "total_accounts": len(statements),
        "total_balance": total_balance,
        "account_statements": statements
    }
