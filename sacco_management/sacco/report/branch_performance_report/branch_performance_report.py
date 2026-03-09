# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    """Branch Performance Report - Comprehensive branch-wise analytics"""
    
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_branch_data(filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart


def get_columns():
    """Define report columns"""
    return [
        {"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 150},
        {"label": _("Total Members"), "fieldname": "total_members", "fieldtype": "Int", "width": 120},
        {"label": _("Active Members"), "fieldname": "active_members", "fieldtype": "Int", "width": 120},
        
        # Savings Section
        {"label": _("Total Savings"), "fieldname": "total_savings", "fieldtype": "Currency", "width": 130},
        {"label": _("Avg Savings/Member"), "fieldname": "avg_savings", "fieldtype": "Currency", "width": 130},
        
        # Shares Section
        {"label": _("Total Share Capital"), "fieldname": "total_share_capital", "fieldtype": "Currency", "width": 140},
        {"label": _("Shares Issued"), "fieldname": "shares_issued", "fieldtype": "Int", "width": 120},
        
        # Loans Section
        {"label": _("Total Loans Disbursed"), "fieldname": "total_loans_disbursed", "fieldtype": "Currency", "width": 150},
        {"label": _("Outstanding Loans"), "fieldname": "outstanding_loans", "fieldtype": "Currency", "width": 140},
        {"label": _("Loan Arrears"), "fieldname": "loan_arrears", "fieldtype": "Currency", "width": 130},
        {"label": _("PAR Ratio %"), "fieldname": "par_ratio", "fieldtype": "Percent", "width": 110},
        
        # Contributions Section
        {"label": _("Total Contributions"), "fieldname": "total_contributions", "fieldtype": "Currency", "width": 140},
        
        # Fines Section
        {"label": _("Fines Collected"), "fieldname": "fines_collected", "fieldtype": "Currency", "width": 130},
        
        # Dividends Section
        {"label": _("Dividends Paid"), "fieldname": "dividends_paid", "fieldtype": "Currency", "width": 130},
        
        # Financial Performance
        {"label": _("Interest Income"), "fieldname": "interest_income", "fieldtype": "Currency", "width": 130},
        {"label": _("Net Surplus"), "fieldname": "net_surplus", "fieldtype": "Currency", "width": 130},
    ]


def get_branch_data(filters):
    """Get comprehensive branch performance data"""
    from_date = filters.get("from_date") or "2020-01-01"
    to_date = filters.get("to_date") or nowdate()
    
    branches = frappe.get_all("Branch", 
                             filters={"disabled": 0},
                             fields=["name as branch"])
    
    data = []
    
    for branch in branches:
        branch_name = branch.branch
        
        # Member Statistics
        total_members = get_total_members(branch_name, to_date)
        active_members = get_active_members(branch_name, to_date)
        
        # Savings Statistics
        total_savings = get_total_savings(branch_name, from_date, to_date)
        avg_savings = total_savings / active_members if active_members > 0 else 0
        
        # Share Capital Statistics
        total_share_capital, shares_issued = get_share_capital_stats(branch_name, to_date)
        
        # Loan Statistics
        total_loans_disbursed, outstanding_loans, loan_arrears = get_loan_stats(branch_name, from_date, to_date)
        par_ratio = (loan_arrears / outstanding_loans * 100) if outstanding_loans > 0 else 0
        
        # Contribution Statistics
        total_contributions = get_total_contributions(branch_name, from_date, to_date)
        
        # Fine Statistics
        fines_collected = get_fines_collected(branch_name, from_date, to_date)
        
        # Dividend Statistics
        dividends_paid = get_dividends_paid(branch_name, from_date, to_date)
        
        # Financial Performance
        interest_income = get_interest_income(branch_name, from_date, to_date)
        net_surplus = calculate_net_surplus(branch_name, from_date, to_date)
        
        data.append({
            "branch": branch_name,
            "total_members": total_members,
            "active_members": active_members,
            "total_savings": flt(total_savings, 2),
            "avg_savings": flt(avg_savings, 2),
            "total_share_capital": flt(total_share_capital, 2),
            "shares_issued": shares_issued,
            "total_loans_disbursed": flt(total_loans_disbursed, 2),
            "outstanding_loans": flt(outstanding_loans, 2),
            "loan_arrears": flt(loan_arrears, 2),
            "par_ratio": flt(par_ratio / 100, 4),  # Convert to decimal for Percent field
            "total_contributions": flt(total_contributions, 2),
            "fines_collected": flt(fines_collected, 2),
            "dividends_paid": flt(dividends_paid, 2),
            "interest_income": flt(interest_income, 2),
            "net_surplus": flt(net_surplus, 2),
        })
    
    return data


def get_total_members(branch, to_date):
    """Get total members in branch"""
    result = frappe.db.sql("""
        SELECT COUNT(*) 
        FROM `tabSACCO Member` 
        WHERE branch = %s 
        AND docstatus = 1
        AND joining_date <= %s
    """, (branch, to_date))[0][0]
    
    return result or 0


def get_active_members(branch, to_date):
    """Get active members in branch"""
    result = frappe.db.sql("""
        SELECT COUNT(*) 
        FROM `tabSACCO Member` 
        WHERE branch = %s 
        AND docstatus = 1
        AND membership_status = 'Active'
        AND joining_date <= %s
    """, (branch, to_date))[0][0]
    
    return result or 0


def get_total_savings(branch, from_date, to_date):
    """Get total savings balance for branch"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(current_balance), 0)
        FROM `tabSavings Account` sa
        INNER JOIN `tabSACCO Member` m ON sa.member = m.name
        WHERE m.branch = %s
        AND sa.docstatus = 1
        AND sa.status = 'Active'
    """, (branch,))[0][0]
    
    return result or 0


def get_share_capital_stats(branch, to_date):
    """Get share capital statistics"""
    result = frappe.db.sql("""
        SELECT 
            COALESCE(SUM(sa.total_amount), 0),
            COALESCE(SUM(sa.quantity), 0)
        FROM `tabShare Allocation` sa
        INNER JOIN `tabSACCO Member` m ON sa.member = m.name
        WHERE m.branch = %s
        AND sa.docstatus = 1
        AND sa.status = 'Allocated'
        AND sa.allocation_date <= %s
    """, (branch, to_date))
    
    result = result[0] if result else (0, 0)
    return result[0] or 0, result[1] or 0


def get_loan_stats(branch, from_date, to_date):
    """Get loan statistics"""
    # Total disbursed
    total_disbursed = frappe.db.sql("""
        SELECT COALESCE(SUM(ld.amount), 0)
        FROM `tabLoan Disbursement` ld
        INNER JOIN `tabLoan Application` la ON ld.loan_application = la.name
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE m.branch = %s
        AND ld.docstatus = 1
        AND ld.disbursement_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0] or 0
    
    # Outstanding loans
    outstanding = frappe.db.sql("""
        SELECT COALESCE(SUM(la.outstanding_principal), 0)
        FROM `tabLoan Application` la
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE m.branch = %s
        AND la.docstatus = 1
        AND la.status IN ('Approved', 'Disbursed', 'Active')
    """, (branch,))[0][0] or 0
    
    # Loan arrears (overdue amount)
    arrears = frappe.db.sql("""
        SELECT COALESCE(SUM(lrs.overdue_amount), 0)
        FROM `tabLoan Repayment Schedule` lrs
        INNER JOIN `tabLoan Application` la ON lrs.parent = la.name
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE m.branch = %s
        AND lrs.payment_date < %s
        AND lrs.status IN ('Pending', 'Partial')
        AND lrs.overdue_amount > 0
    """, (branch, to_date))[0][0] or 0
    
    return total_disbursed, outstanding, arrears


def get_total_contributions(branch, from_date, to_date):
    """Get total contributions"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(mc.amount), 0)
        FROM `tabMember Contribution` mc
        INNER JOIN `tabSACCO Member` m ON mc.member = m.name
        WHERE m.branch = %s
        AND mc.docstatus = 1
        AND mc.posting_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0]
    
    return result or 0


def get_fines_collected(branch, from_date, to_date):
    """Get total fines collected"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(fp.fines_paid), 0)
        FROM `tabFine Payment` fp
        INNER JOIN `tabSACCO Member` m ON fp.member = m.name
        WHERE m.branch = %s
        AND fp.docstatus = 1
        AND fp.payment_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0]
    
    return result or 0


def get_dividends_paid(branch, from_date, to_date):
    """Get total dividends paid"""
    result = frappe.db.sql("""
        SELECT COALESCE(SUM(dl.dividend_paid), 0)
        FROM `tabDividend Ledger` dl
        INNER JOIN `tabSACCO Member` m ON dl.member = m.name
        WHERE m.branch = %s
        AND dl.docstatus = 1
        AND dl.payment_date BETWEEN %s AND %s
    """, (branch, from_date, to_date))[0][0]
    
    return result or 0


def get_interest_income(branch, from_date, to_date):
    """Get interest income for branch"""
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


def calculate_net_surplus(branch, from_date, to_date):
    """Calculate net surplus for branch (simplified)"""
    # Income: Interest + Fines
    interest_income = get_interest_income(branch, from_date, to_date)
    fines_income = get_fines_collected(branch, from_date, to_date)
    
    # Expenses: Dividends + Operating expenses (simplified)
    dividends_paid = get_dividends_paid(branch, from_date, to_date)
    
    # Net surplus
    net_surplus = (interest_income + fines_income) - dividends_paid
    
    return net_surplus


def get_chart_data(data):
    """Create chart visualization"""
    if not data:
        return None
    
    chart = {
        "data": {
            "labels": [d["branch"] for d in data],
            "datasets": [
                {
                    "name": "Total Savings",
                    "values": [d["total_savings"] for d in data],
                    "chartType": "bar"
                },
                {
                    "name": "Outstanding Loans",
                    "values": [d["outstanding_loans"] for d in data],
                    "chartType": "bar"
                },
                {
                    "name": "Share Capital",
                    "values": [d["total_share_capital"] for d in data],
                    "chartType": "line"
                }
            ]
        },
        "type": "bar",
        "colors": ["#4CAF50", "#2196F3", "#FF9800"],
        "tooltipOptions": {
            "formatTooltipY": lambda x: f"{x:,.2f}"
        }
    }
    
    return chart
