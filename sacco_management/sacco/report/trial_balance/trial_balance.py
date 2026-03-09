# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "fieldname": "account",
            "label": _("Account"),
            "fieldtype": "Link",
            "options": "SACCO GL Account",
            "width": 300
        },
        {
            "fieldname": "account_number",
            "label": _("Account Number"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "account_type",
            "label": _("Type"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "opening_debit",
            "label": _("Opening (Dr)"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "opening_credit",
            "label": _("Opening (Cr)"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "debit",
            "label": _("Debit"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "credit",
            "label": _("Credit"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "closing_debit",
            "label": _("Closing (Dr)"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "closing_credit",
            "label": _("Closing (Cr)"),
            "fieldtype": "Currency",
            "width": 130
        }
    ]


def get_data(filters):
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    data = []
    totals = {
        "opening_debit": 0,
        "opening_credit": 0,
        "debit": 0,
        "credit": 0,
        "closing_debit": 0,
        "closing_credit": 0
    }
    
    # Get all accounts (non-group accounts only)
    accounts = frappe.get_all("SACCO GL Account", 
        filters={"is_group": 0},
        fields=["name", "account_name", "account_number", "account_type"],
        order_by="account_number, account_name"
    )
    
    for account in accounts:
        opening_balance = get_opening_balance(account.name, from_date) if from_date else {"debit": 0, "credit": 0}
        period_balance = get_period_balance(account.name, from_date, to_date)
        
        opening_debit = flt(opening_balance.get("debit", 0))
        opening_credit = flt(opening_balance.get("credit", 0))
        debit = flt(period_balance.get("debit", 0))
        credit = flt(period_balance.get("credit", 0))
        
        # Calculate net opening
        net_opening = opening_debit - opening_credit
        if net_opening > 0:
            opening_debit = net_opening
            opening_credit = 0
        else:
            opening_debit = 0
            opening_credit = abs(net_opening)
        
        # Calculate closing balance
        closing = net_opening + debit - credit
        if closing > 0:
            closing_debit = closing
            closing_credit = 0
        else:
            closing_debit = 0
            closing_credit = abs(closing)
        
        # Skip accounts with no activity
        if opening_debit == 0 and opening_credit == 0 and debit == 0 and credit == 0:
            continue
        
        row = {
            "account": account.name,
            "account_number": account.account_number,
            "account_type": account.account_type,
            "opening_debit": opening_debit,
            "opening_credit": opening_credit,
            "debit": debit,
            "credit": credit,
            "closing_debit": closing_debit,
            "closing_credit": closing_credit
        }
        
        data.append(row)
        
        # Accumulate totals
        totals["opening_debit"] += opening_debit
        totals["opening_credit"] += opening_credit
        totals["debit"] += debit
        totals["credit"] += credit
        totals["closing_debit"] += closing_debit
        totals["closing_credit"] += closing_credit
    
    # Add totals row
    if data:
        data.append({
            "account": _("Total"),
            "account_number": "",
            "account_type": "",
            "opening_debit": totals["opening_debit"],
            "opening_credit": totals["opening_credit"],
            "debit": totals["debit"],
            "credit": totals["credit"],
            "closing_debit": totals["closing_debit"],
            "closing_credit": totals["closing_credit"]
        })
    
    return data


def get_opening_balance(account, from_date):
    """Get opening balance before from_date"""
    if not from_date:
        return {"debit": 0, "credit": 0}
    
    query = """
        SELECT 
            COALESCE(SUM(jea.debit), 0) as debit,
            COALESCE(SUM(jea.credit), 0) as credit
        FROM `tabSACCO Journal Entry Account` jea
        INNER JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name
        WHERE jea.account = %s 
        AND je.docstatus = 1
        AND je.posting_date < %s
    """
    
    result = frappe.db.sql(query, (account, from_date), as_dict=True)
    return result[0] if result else {"debit": 0, "credit": 0}


def get_period_balance(account, from_date, to_date):
    """Get balance for the period"""
    conditions = ""
    params = [account]
    
    if from_date:
        conditions += " AND je.posting_date >= %s"
        params.append(from_date)
    if to_date:
        conditions += " AND je.posting_date <= %s"
        params.append(to_date)
    
    query = f"""
        SELECT 
            COALESCE(SUM(jea.debit), 0) as debit,
            COALESCE(SUM(jea.credit), 0) as credit
        FROM `tabSACCO Journal Entry Account` jea
        INNER JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name
        WHERE jea.account = %s 
        AND je.docstatus = 1
        {conditions}
    """
    
    result = frappe.db.sql(query, tuple(params), as_dict=True)
    return result[0] if result else {"debit": 0, "credit": 0}
