# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    validate_filters(filters)
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def validate_filters(filters):
    if not filters.get("account") and not filters.get("party"):
        frappe.throw(_("Please select either an Account or a Party"))


def get_columns():
    return [
        {
            "fieldname": "posting_date",
            "label": _("Posting Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "account",
            "label": _("Account"),
            "fieldtype": "Link",
            "options": "SACCO GL Account",
            "width": 200
        },
        {
            "fieldname": "voucher_type",
            "label": _("Voucher Type"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "voucher_no",
            "label": _("Voucher No"),
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 180
        },
        {
            "fieldname": "party_type",
            "label": _("Party Type"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "party",
            "label": _("Party"),
            "fieldtype": "Dynamic Link",
            "options": "party_type",
            "width": 150
        },
        {
            "fieldname": "debit",
            "label": _("Debit"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "credit",
            "label": _("Credit"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "balance",
            "label": _("Balance"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "remarks",
            "label": _("Remarks"),
            "fieldtype": "Data",
            "width": 200
        }
    ]


def get_data(filters):
    conditions = get_conditions(filters)
    from_date = filters.get("from_date")
    
    data = []
    opening_balance = 0
    
    # Calculate opening balance if from_date is specified
    if from_date:
        opening_balance = get_opening_balance(filters)
        if opening_balance != 0:
            data.append({
                "posting_date": from_date,
                "account": _("Opening Balance"),
                "voucher_type": "",
                "voucher_no": "",
                "party_type": "",
                "party": "",
                "debit": opening_balance if opening_balance > 0 else 0,
                "credit": abs(opening_balance) if opening_balance < 0 else 0,
                "balance": opening_balance,
                "remarks": _("Balance brought forward")
            })
    
    running_balance = opening_balance
    
    # Get GL entries
    query = f"""
        SELECT 
            je.posting_date,
            jea.account,
            je.reference_type as voucher_type,
            je.reference_name as voucher_no,
            jea.party_type,
            jea.party,
            jea.debit,
            jea.credit,
            je.remarks
        FROM `tabSACCO Journal Entry Account` jea
        INNER JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name
        WHERE je.docstatus = 1
        {conditions}
        ORDER BY je.posting_date, je.creation
    """
    
    entries = frappe.db.sql(query, filters, as_dict=True)
    
    for entry in entries:
        debit = flt(entry.get("debit", 0))
        credit = flt(entry.get("credit", 0))
        running_balance += debit - credit
        
        entry["balance"] = running_balance
        data.append(entry)
    
    # Add closing balance row
    if data:
        total_debit = sum(flt(row.get("debit", 0)) for row in data if row.get("voucher_type"))
        total_credit = sum(flt(row.get("credit", 0)) for row in data if row.get("voucher_type"))
        
        data.append({
            "posting_date": "",
            "account": _("Total / Closing Balance"),
            "voucher_type": "",
            "voucher_no": "",
            "party_type": "",
            "party": "",
            "debit": total_debit,
            "credit": total_credit,
            "balance": running_balance,
            "remarks": ""
        })
    
    return data


def get_conditions(filters):
    conditions = ""
    
    if filters.get("account"):
        conditions += " AND jea.account = %(account)s"
    if filters.get("party_type"):
        conditions += " AND jea.party_type = %(party_type)s"
    if filters.get("party"):
        conditions += " AND jea.party = %(party)s"
    if filters.get("from_date"):
        conditions += " AND je.posting_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND je.posting_date <= %(to_date)s"
    if filters.get("voucher_type"):
        conditions += " AND je.reference_type = %(voucher_type)s"
    
    return conditions


def get_opening_balance(filters):
    """Calculate opening balance before from_date"""
    opening_conditions = ""
    
    if filters.get("account"):
        opening_conditions += " AND jea.account = %(account)s"
    if filters.get("party_type"):
        opening_conditions += " AND jea.party_type = %(party_type)s"
    if filters.get("party"):
        opening_conditions += " AND jea.party = %(party)s"
    
    query = f"""
        SELECT 
            COALESCE(SUM(jea.debit), 0) - COALESCE(SUM(jea.credit), 0) as balance
        FROM `tabSACCO Journal Entry Account` jea
        INNER JOIN `tabSACCO Journal Entry` je ON jea.parent = je.name
        WHERE je.docstatus = 1
        AND je.posting_date < %(from_date)s
        {opening_conditions}
    """
    
    result = frappe.db.sql(query, filters, as_dict=True)
    return flt(result[0].balance if result else 0)
