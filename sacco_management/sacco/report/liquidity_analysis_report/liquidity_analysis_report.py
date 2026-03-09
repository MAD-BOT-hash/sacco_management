# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    """Liquidity Analysis Report - Financial liquidity metrics"""
    
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_liquidity_data(filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart


def get_columns():
    """Define liquidity report columns"""
    return [
        {"label": _("Metric"), "fieldname": "metric", "fieldtype": "Data", "width": 200},
        {"label": _("Current Period"), "fieldname": "current_period", "fieldtype": "Currency", "width": 150},
        {"label": _("Previous Period"), "fieldname": "previous_period", "fieldtype": "Currency", "width": 150},
        {"label": _("Change %"), "fieldname": "change_percent", "fieldtype": "Percent", "width": 120},
        {"label": _("Target"), "fieldname": "target", "fieldtype": "Currency", "width": 130},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
    ]


def get_liquidity_data(filters):
    """Get comprehensive liquidity analysis"""
    as_of_date = filters.get("as_of_date") or nowdate()
    
    # Calculate liquid assets
    liquid_assets_current = calculate_liquid_assets(as_of_date)
    liquid_assets_previous = calculate_liquid_assets(add_months(as_of_date, -1))
    
    # Calculate current liabilities
    current_liabilities_current = calculate_current_liabilities(as_of_date)
    current_liabilities_previous = calculate_current_liabilities(add_months(as_of_date, -1))
    
    # Calculate quick assets (cash + cash equivalents)
    quick_assets_current = calculate_quick_assets(as_of_date)
    quick_assets_previous = calculate_quick_assets(add_months(as_of_date, -1))
    
    # Calculate savings deposits (potential withdrawal liability)
    savings_deposits_current = calculate_savings_deposits(as_of_date)
    savings_deposits_previous = calculate_savings_deposits(add_months(as_of_date, -1))
    
    data = []
    
    # Current Ratio = Current Assets / Current Liabilities
    current_ratio = liquid_assets_current / current_liabilities_current if current_liabilities_current > 0 else 0
    previous_current_ratio = liquid_assets_previous / current_liabilities_previous if current_liabilities_previous > 0 else 0
    
    data.append({
        "metric": "Current Ratio",
        "current_period": flt(current_ratio, 2),
        "previous_period": flt(previous_current_ratio, 2),
        "change_percent": flt((current_ratio - previous_current_ratio) / previous_current_ratio * 100 if previous_current_ratio > 0 else 0, 2),
        "target": 1.5,
        "status": get_status(current_ratio, 1.5, 1.0)
    })
    
    # Quick Ratio = Quick Assets / Current Liabilities
    quick_ratio = quick_assets_current / current_liabilities_current if current_liabilities_current > 0 else 0
    previous_quick_ratio = quick_assets_previous / current_liabilities_previous if current_liabilities_previous > 0 else 0
    
    data.append({
        "metric": "Quick Ratio",
        "current_period": flt(quick_ratio, 2),
        "previous_period": flt(previous_quick_ratio, 2),
        "change_percent": flt((quick_ratio - previous_quick_ratio) / previous_quick_ratio * 100 if previous_quick_ratio > 0 else 0, 2),
        "target": 1.0,
        "status": get_status(quick_ratio, 1.0, 0.8)
    })
    
    # Liquid Assets to Savings Deposits
    liquid_to_savings = liquid_assets_current / savings_deposits_current if savings_deposits_current > 0 else 0
    previous_liquid_to_savings = liquid_assets_previous / savings_deposits_previous if savings_deposits_previous > 0 else 0
    
    data.append({
        "metric": "Liquid Assets to Savings Deposits",
        "current_period": flt(liquid_assets_current, 2),
        "previous_period": flt(liquid_assets_previous, 2),
        "change_percent": flt((liquid_assets_current - liquid_assets_previous) / liquid_assets_previous * 100 if liquid_assets_previous > 0 else 0, 2),
        "target": flt(savings_deposits_current * 0.2, 2),  # Target: 20% of savings
        "status": get_status(liquid_to_savings, 0.2, 0.15)
    })
    
    # Cash Reserve Ratio
    cash_reserve = calculate_cash_reserves(as_of_date)
    total_assets = calculate_total_assets(as_of_date)
    cash_reserve_ratio = cash_reserve / total_assets if total_assets > 0 else 0
    
    previous_cash_reserve = calculate_cash_reserves(add_months(as_of_date, -1))
    previous_total_assets = calculate_total_assets(add_months(as_of_date, -1))
    previous_cash_reserve_ratio = previous_cash_reserve / previous_total_assets if previous_total_assets > 0 else 0
    
    data.append({
        "metric": "Cash Reserve Ratio",
        "current_period": flt(cash_reserve_ratio * 100, 2),  # Show as percentage
        "previous_period": flt(previous_cash_reserve_ratio * 100, 2),
        "change_percent": flt((cash_reserve_ratio - previous_cash_reserve_ratio) / previous_cash_reserve_ratio * 100 if previous_cash_reserve_ratio > 0 else 0, 2),
        "target": 10.0,  # Target: 10% cash reserves
        "status": get_status(cash_reserve_ratio * 100, 10, 8)
    })
    
    # Loan to Deposit Ratio
    total_loans = calculate_total_loans(as_of_date)
    total_deposits = calculate_total_deposits(as_of_date)
    loan_to_deposit = total_loans / total_deposits if total_deposits > 0 else 0
    
    previous_loans = calculate_total_loans(add_months(as_of_date, -1))
    previous_deposits = calculate_total_deposits(add_months(as_of_date, -1))
    previous_loan_to_deposit = previous_loans / previous_deposits if previous_deposits > 0 else 0
    
    data.append({
        "metric": "Loan to Deposit Ratio",
        "current_period": flt(loan_to_deposit * 100, 2),  # Show as percentage
        "previous_period": flt(previous_loan_to_deposit * 100, 2),
        "change_percent": flt((loan_to_deposit - previous_loan_to_deposit) / previous_loan_to_deposit * 100 if previous_loan_to_deposit > 0 else 0, 2),
        "target": 80.0,  # Target: 80% (not lending more than 80% of deposits)
        "status": get_status(loan_to_deposit * 100, 80, 90, reverse=True)  # Lower is better
    })
    
    return data


def calculate_liquid_assets(date):
    """Calculate total liquid assets"""
    # Cash in hand + Bank balances + Short-term investments
    liquid_accounts = frappe.db.sql("""
        SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
        FROM `tabSACCO Journal Entry Account` gle
        INNER JOIN `tabSACCO Journal Entry` je ON gle.parent = je.name
        WHERE je.docstatus = 1
        AND je.posting_date <= %s
        AND gle.account IN ('Cash', 'Cash in Hand', 'Petty Cash', 'Bank', 'Bank Accounts', 'Short Term Investments')
    """, (date,))[0][0] or 0
    
    return liquid_accounts


def calculate_quick_assets(date):
    """Calculate quick assets (cash + cash equivalents)"""
    quick_accounts = frappe.db.sql("""
        SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
        FROM `tabSACCO Journal Entry Account` gle
        INNER JOIN `tabSACCO Journal Entry` je ON gle.parent = je.name
        WHERE je.docstatus = 1
        AND je.posting_date <= %s
        AND gle.account IN ('Cash', 'Cash in Hand', 'Bank')
    """, (date,))[0][0] or 0
    
    return quick_accounts


def calculate_current_liabilities(date):
    """Calculate current liabilities"""
    # Savings deposits + Short-term borrowings + Accounts payable
    liability_accounts = frappe.db.sql("""
        SELECT COALESCE(SUM(gle.credit - gle.debit), 0)
        FROM `tabSACCO Journal Entry Account` gle
        INNER JOIN `tabSACCO Journal Entry` je ON gle.parent = je.name
        WHERE je.docstatus = 1
        AND je.posting_date <= %s
        AND gle.account LIKE '%Deposit%' OR gle.account LIKE '%Payable%'
    """, (date,))[0][0] or 0
    
    return liability_accounts


def calculate_savings_deposits(date):
    """Calculate total savings deposits"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(current_balance), 0)
        FROM `tabSavings Account`
        WHERE docstatus = 1
        AND status = 'Active'
    """, ())[0][0] or 0
    
    return result


def calculate_cash_reserves(date):
    """Calculate cash reserves"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
        FROM `tabSACCO Journal Entry Account` gle
        INNER JOIN `tabSACCO Journal Entry` je ON gle.parent = je.name
        WHERE je.docstatus = 1
        AND je.posting_date <= %s
        AND gle.account IN ('Cash', 'Cash in Hand', 'Bank')
    """, (date,))[0][0] or 0
    
    return result


def calculate_total_assets(date):
    """Calculate total assets"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(gle.debit - gle.credit), 0)
        FROM `tabSACCO Journal Entry Account` gle
        INNER JOIN `tabSACCO Journal Entry` je ON gle.parent = je.name
        WHERE je.docstatus = 1
        AND je.posting_date <= %s
        AND gle.account LIKE '%Asset%'
    """, (date,))[0][0] or 0
    
    return result


def calculate_total_loans(date):
    """Calculate total loans outstanding"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(outstanding_principal), 0)
        FROM `tabLoan Application`
        WHERE docstatus = 1
        AND status IN ('Approved', 'Disbursed', 'Active')
    """, ())[0][0] or 0
    
    return result


def calculate_total_deposits(date):
    """Calculate total deposits"""
    return calculate_savings_deposits(date)


def get_status(actual, target, warning_threshold, reverse=False):
    """Get status indicator"""
    if reverse:
        # For ratios where lower is better (e.g., Loan to Deposit)
        if actual <= target:
            return "Good"
        elif actual <= warning_threshold:
            return "Warning"
        else:
            return "Critical"
    else:
        # For ratios where higher is better
        if actual >= target:
            return "Good"
        elif actual >= warning_threshold:
            return "Warning"
        else:
            return "Critical"


def add_months(date, months):
    """Add/subtract months from date"""
    from dateutil.relativedelta import relativedelta
    return getdate(date) + relativedelta(months=months)


def get_chart_data(data):
    """Create liquidity trend chart"""
    if not data:
        return None
    
    chart = {
        "data": {
            "labels": [d["metric"] for d in data],
            "datasets": [
                {
                    "name": "Current Period",
                    "values": [flt(d["current_period"]) for d in data],
                    "chartType": "bar"
                },
                {
                    "name": "Previous Period",
                    "values": [flt(d["previous_period"]) for d in data],
                    "chartType": "bar"
                }
            ]
        },
        "type": "bar",
        "colors": ["#4CAF50", "#FF9800"],
        "tooltipOptions": {
            "formatTooltipY": lambda x: f"{x:,.2f}"
        }
    }
    
    return chart
