# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, date_diff


def execute(filters=None):
    """Portfolio at Risk (PAR) Report - Critical loan quality metric"""
    
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_par_data(filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart


def get_columns():
    """Define PAR report columns"""
    return [
        {"label": _("Loan Application"), "fieldname": "loan_application", "fieldtype": "Link", "options": "Loan Application", "width": 150},
        {"label": _("Member"), "fieldname": "member", "fieldtype": "Link", "options": "SACCO Member", "width": 150},
        {"label": _("Member Name"), "fieldname": "member_name", "fieldtype": "Data", "width": 200},
        {"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 120},
        
        # Loan Details
        {"label": _("Loan Amount"), "fieldname": "loan_amount", "fieldtype": "Currency", "width": 130},
        {"label": _("Outstanding Principal"), "fieldname": "outstanding_principal", "fieldtype": "Currency", "width": 150},
        {"label": _("Overdue Amount"), "fieldname": "overdue_amount", "fieldtype": "Currency", "width": 130},
        
        # Days Buckets
        {"label": _("Days Past Due"), "fieldname": "days_past_due", "fieldtype": "Int", "width": 120},
        {"label": _("PAR 1-30 Days"), "fieldname": "par_1_30", "fieldtype": "Currency", "width": 130},
        {"label": _("PAR 31-60 Days"), "fieldname": "par_31_60", "fieldtype": "Currency", "width": 130},
        {"label": _("PAR 61-90 Days"), "fieldname": "par_61_90", "fieldtype": "Currency", "width": 130},
        {"label": _("PAR >90 Days"), "fieldname": "par_above_90", "fieldtype": "Currency", "width": 130},
        
        # Risk Indicators
        {"label": _("Risk Category"), "fieldname": "risk_category", "fieldtype": "Data", "width": 120},
        {"label": _("Provision Required"), "fieldname": "provision_required", "fieldtype": "Currency", "width": 140},
    ]


def get_par_data(filters):
    """Get Portfolio at Risk data"""
    from_date = filters.get("from_date") or add_months(nowdate(), -12)
    to_date = filters.get("to_date") or nowdate()
    branch = filters.get("branch")
    min_days_overdue = filters.get("min_days_overdue") or 1
    
    conditions = "WHERE la.docstatus = 1 AND la.status IN ('Approved', 'Disbursed', 'Active')"
    
    if branch:
        conditions += f" AND m.branch = '{branch}'"
    
    loans = frappe.db.sql(f"""
        SELECT 
            la.name as loan_application,
            la.member,
            la.member_name,
            m.branch,
            la.amount_requested as loan_amount,
            la.outstanding_principal,
            la.interest_rate,
            la.repayment_period
        FROM `tabLoan Application` la
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        {conditions}
        ORDER BY la.outstanding_principal DESC
    """, as_dict=True)
    
    data = []
    
    for loan in loans:
        # Calculate overdue amount and days
        overdue_info = calculate_overdue_details(loan.loan_application, to_date)
        
        if overdue_info['days_past_due'] >= min_days_overdue:
            # Categorize into PAR buckets
            par_buckets = categorize_par_buckets(overdue_info['overdue_amount'], overdue_info['days_past_due'])
            
            # Determine risk category
            risk_category = determine_risk_category(overdue_info['days_past_due'])
            
            # Calculate provision required
            provision_required = calculate_provision(loan.outstanding_principal, risk_category)
            
            data.append({
                "loan_application": loan.loan_application,
                "member": loan.member,
                "member_name": loan.member_name,
                "branch": loan.branch,
                "loan_amount": flt(loan.loan_amount, 2),
                "outstanding_principal": flt(loan.outstanding_principal, 2),
                "overdue_amount": flt(overdue_info['overdue_amount'], 2),
                "days_past_due": overdue_info['days_past_due'],
                "par_1_30": flt(par_buckets['par_1_30'], 2),
                "par_31_60": flt(par_buckets['par_31_60'], 2),
                "par_61_90": flt(par_buckets['par_61_90'], 2),
                "par_above_90": flt(par_buckets['par_above_90'], 2),
                "risk_category": risk_category,
                "provision_required": flt(provision_required, 2),
            })
    
    return data


def calculate_overdue_details(loan_name, as_of_date):
    """Calculate overdue amount and days past due"""
    # Get all overdue repayment schedules
    overdue_schedules = frappe.db.sql("""
        SELECT 
            lrs.name,
            lrs.payment_date,
            lrs.principal_amount,
            lrs.interest_amount,
            lrs.paid_amount,
            lrs.overdue_amount
        FROM `tabLoan Repayment Schedule` lrs
        WHERE lrs.parent = %s
        AND lrs.payment_date < %s
        AND lrs.status IN ('Pending', 'Partial')
        AND lrs.overdue_amount > 0
        ORDER BY lrs.payment_date ASC
    """, (loan_name, as_of_date), as_dict=True)
    
    total_overdue = 0
    max_days_past_due = 0
    
    for schedule in overdue_schedules:
        total_overdue += flt(schedule.overdue_amount)
        
        # Calculate days past due for this installment
        days_past_due = date_diff(as_of_date, schedule.payment_date)
        max_days_past_due = max(max_days_past_due, days_past_due)
    
    return {
        'overdue_amount': total_overdue,
        'days_past_due': max_days_past_due
    }


def categorize_par_buckets(overdue_amount, days_past_due):
    """Categorize overdue amount into PAR buckets"""
    buckets = {
        'par_1_30': 0,
        'par_31_60': 0,
        'par_61_90': 0,
        'par_above_90': 0
    }
    
    if days_past_due <= 0:
        return buckets
    
    # Allocate entire overdue amount to appropriate bucket
    if 1 <= days_past_due <= 30:
        buckets['par_1_30'] = overdue_amount
    elif 31 <= days_past_due <= 60:
        buckets['par_31_60'] = overdue_amount
    elif 61 <= days_past_due <= 90:
        buckets['par_61_90'] = overdue_amount
    else:
        buckets['par_above_90'] = overdue_amount
    
    return buckets


def determine_risk_category(days_past_due):
    """Determine loan risk category based on days past due"""
    if days_past_due <= 30:
        return "Special Mention"
    elif days_past_due <= 60:
        return "Substandard"
    elif days_past_due <= 90:
        return "Doubtful"
    else:
        return "Loss"


def calculate_provision(outstanding_principal, risk_category):
    """Calculate provision required based on risk category"""
    provision_rates = {
        "Special Mention": 0.01,  # 1%
        "Substandard": 0.05,      # 5%
        "Doubtful": 0.25,         # 25%
        "Loss": 1.0               # 100%
    }
    
    rate = provision_rates.get(risk_category, 0)
    return flt(outstanding_principal) * rate


def get_chart_data(data):
    """Create PAR analysis chart"""
    if not data:
        return None
    
    # Aggregate by PAR bucket
    par_1_30 = sum([d['par_1_30'] for d in data])
    par_31_60 = sum([d['par_31_60'] for d in data])
    par_61_90 = sum([d['par_61_90'] for d in data])
    par_above_90 = sum([d['par_above_90'] for d in data])
    
    chart = {
        "data": {
            "labels": ["PAR 1-30 Days", "PAR 31-60 Days", "PAR 61-90 Days", "PAR >90 Days"],
            "datasets": [
                {
                    "name": "Portfolio at Risk",
                    "values": [par_1_30, par_31_60, par_61_90, par_above_90],
                    "chartType": "bar"
                }
            ]
        },
        "type": "bar",
        "colors": ["#4CAF50", "#FF9800", "#F44336", "#9C27B0"],
        "tooltipOptions": {
            "formatTooltipY": lambda x: f"{x:,.2f}"
        }
    }
    
    return chart


def add_months(date, months):
    """Add/subtract months from date"""
    from dateutil.relativedelta import relativedelta
    return getdate(date) + relativedelta(months=months)
