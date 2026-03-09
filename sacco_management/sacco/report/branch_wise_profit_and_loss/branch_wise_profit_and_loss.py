# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    """Branch-wise Profit & Loss Report"""
    
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart


def get_columns():
    """Define P&L columns"""
    return [
        {"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 150},
        
        # INCOME SECTION
        {"label": _("Interest Income"), "fieldname": "interest_income", "fieldtype": "Currency", "width": 130},
        {"label": _("Fines Income"), "fieldname": "fines_income", "fieldtype": "Currency", "width": 130},
        {"label": _("Other Income"), "fieldname": "other_income", "fieldtype": "Currency", "width": 130},
        {"label": _("Total Income"), "fieldname": "total_income", "fieldtype": "Currency", "width": 130},
        
        # EXPENSES SECTION
        {"label": _("Dividends Paid"), "fieldname": "dividends_paid", "fieldtype": "Currency", "width": 130},
        {"label": _("Interest Expense"), "fieldname": "interest_expense", "fieldtype": "Currency", "width": 130},
        {"label": _("Operating Expenses"), "fieldname": "operating_expenses", "fieldtype": "Currency", "width": 140},
        {"label": _("Provision for Bad Debt"), "fieldname": "bad_debt_provision", "fieldtype": "Currency", "width": 150},
        {"label": _("Total Expenses"), "fieldname": "total_expenses", "fieldtype": "Currency", "width": 130},
        
        # NET RESULT
        {"label": _("Net Surplus/(Deficit)"), "fieldname": "net_surplus", "fieldtype": "Currency", "width": 150},
        {"label": _("Surplus Margin %"), "fieldname": "surplus_margin", "fieldtype": "Percent", "width": 120},
    ]


def get_data(filters):
    """Get P&L data by branch"""
    from_date = filters.get("from_date") or "2020-01-01"
    to_date = filters.get("to_date") or nowdate()
    
    branches = frappe.get_all("Branch", 
                             filters={"disabled": 0},
                             fields=["name as branch"])
    
    data = []
    
    for branch in branches:
        branch_name = branch.branch
        
        # Calculate income components
        interest_income = calculate_interest_income(branch_name, from_date, to_date)
        fines_income = calculate_fines_income(branch_name, from_date, to_date)
        other_income = calculate_other_income(branch_name, from_date, to_date)
        total_income = interest_income + fines_income + other_income
        
        # Calculate expense components
        dividends_paid = calculate_dividends_paid(branch_name, from_date, to_date)
        interest_expense = calculate_interest_expense(branch_name, from_date, to_date)
        operating_expenses = calculate_operating_expenses(branch_name, from_date, to_date)
        bad_debt_provision = calculate_bad_debt_provision(branch_name, from_date, to_date)
        total_expenses = dividends_paid + interest_expense + operating_expenses + bad_debt_provision
        
        # Calculate net surplus
        net_surplus = total_income - total_expenses
        surplus_margin = (net_surplus / total_income * 100) if total_income > 0 else 0
        
        data.append({
            "branch": branch_name,
            "interest_income": flt(interest_income, 2),
            "fines_income": flt(fines_income, 2),
            "other_income": flt(other_income, 2),
            "total_income": flt(total_income, 2),
            
            "dividends_paid": flt(dividends_paid, 2),
            "interest_expense": flt(interest_expense, 2),
            "operating_expenses": flt(operating_expenses, 2),
            "bad_debt_provision": flt(bad_debt_provision, 2),
            "total_expenses": flt(total_expenses, 2),
            
            "net_surplus": flt(net_surplus, 2),
            "surplus_margin": flt(surplus_margin / 100, 4),  # Convert to decimal for Percent field
        })
    
    return data


def calculate_interest_income(branch, from_date, to_date):
    """Calculate interest income for branch"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(lr.interest_amount), 0)
        FROM `tabLoan Repayment` lr
        INNER JOIN `tabLoan Application` la ON lr.loan_application = la.name
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE m.branch = %s
        AND lr.docstatus = 1
        AND lr.payment_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0]
    
    return result or 0


def calculate_fines_income(branch, from_date, to_date):
    """Calculate fines income for branch"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(fp.fines_paid), 0)
        FROM `tabFine Payment` fp
        INNER JOIN `tabSACCO Member` m ON fp.member = m.name
        WHERE m.branch = %s
        AND fp.docstatus = 1
        AND fp.payment_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0]
    
    return result or 0


def calculate_other_income(branch, from_date, to_date):
    """Calculate other income (fees, penalties, etc.)"""
    # Loan processing fees
    processing_fees = frappe.db.sql("""
        SELECT COALESCE(SUM(la.processing_fee), 0)
        FROM `tabLoan Application` la
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE m.branch = %s
        AND la.docstatus = 1
        AND la.application_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0] or 0
    
    # Penalties
    penalties = frappe.db.sql("""
        SELECT COALESCE(SUM(lr.penalty_amount), 0)
        FROM `tabLoan Repayment` lr
        INNER JOIN `tabLoan Application` la ON lr.loan_application = la.name
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE m.branch = %s
        AND lr.docstatus = 1
        AND lr.payment_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0] or 0
    
    return processing_fees + penalties


def calculate_dividends_paid(branch, from_date, to_date):
    """Calculate dividends paid for branch"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(dl.dividend_paid), 0)
        FROM `tabDividend Ledger` dl
        INNER JOIN `tabSACCO Member` m ON dl.member = m.name
        WHERE m.branch = %s
        AND dl.docstatus = 1
        AND dl.payment_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0]
    
    return result or 0


def calculate_interest_expense(branch, from_date, to_date):
    """Calculate interest expense on savings"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(sip.interest_amount), 0)
        FROM `tabSavings Interest Posting` sip
        INNER JOIN `tabSavings Account` sa ON sip.savings_account = sa.name
        INNER JOIN `tabSACCO Member` m ON sa.member = m.name
        WHERE m.branch = %s
        AND sip.docstatus = 1
        AND sip.posting_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0]
    
    return result or 0


def calculate_operating_expenses(branch, from_date, to_date):
    """Calculate operating expenses allocated to branch"""
    # Get journal entries for expenses
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(jea.debit), 0)
        FROM `tabSACCO Journal Entry Account` jea
        INNER JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name
        WHERE je.branch = %s
        AND je.docstatus = 1
        AND je.posting_date BETWEEN %s AND %s
        AND jea.account LIKE '%Expense%'
    """, (branch, from_date, to_date))
    
    return result[0][0] or 0 if result else 0


def calculate_bad_debt_provision(branch, from_date, to_date):
    """Calculate provision for bad debts"""
    # This would typically come from loan write-offs or provisions
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(lwo.amount_written_off), 0)
        FROM `tabLoan Write Off` lwo
        INNER JOIN `tabLoan Application` la ON lwo.loan_application = la.name
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE m.branch = %s
        AND lwo.docstatus = 1
        AND lwo.write_off_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0]
    
    return result or 0


def get_chart_data(data):
    """Create chart visualization"""
    if not data:
        return None
    
    chart = {
        "data": {
            "labels": [d["branch"] for d in data],
            "datasets": [
                {
                    "name": "Total Income",
                    "values": [d["total_income"] for d in data],
                    "chartType": "bar"
                },
                {
                    "name": "Total Expenses",
                    "values": [d["total_expenses"] for d in data],
                    "chartType": "bar"
                },
                {
                    "name": "Net Surplus",
                    "values": [d["net_surplus"] for d in data],
                    "chartType": "line"
                }
            ]
        },
        "type": "bar",
        "colors": ["#4CAF50", "#F44336", "#2196F3"],
        "tooltipOptions": {
            "formatTooltipY": lambda x: f"{x:,.2f}"
        }
    }
    
    return chart
