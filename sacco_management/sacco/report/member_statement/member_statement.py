# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "fieldname": "posting_date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 100
        },
        {
            "fieldname": "transaction_type",
            "label": _("Transaction Type"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "reference_doctype",
            "label": _("Voucher Type"),
            "fieldtype": "Data",
            "width": 150
        },
        {
            "fieldname": "reference_name",
            "label": _("Voucher No"),
            "fieldtype": "Dynamic Link",
            "options": "reference_doctype",
            "width": 180
        },
        {
            "fieldname": "description",
            "label": _("Description"),
            "fieldtype": "Data",
            "width": 250
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
        }
    ]


def get_data(filters):
    if not filters.get("member"):
        frappe.throw(_("Please select a Member"))
    
    member = filters.get("member")
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    data = []
    running_balance = 0
    
    # Get opening balance if from_date is specified
    if from_date:
        opening_balance = get_opening_balance(member, from_date)
        running_balance = opening_balance
        if opening_balance != 0:
            data.append({
                "posting_date": from_date,
                "transaction_type": "Opening Balance",
                "reference_doctype": "",
                "reference_name": "",
                "description": "Balance brought forward",
                "debit": 0 if opening_balance >= 0 else abs(opening_balance),
                "credit": opening_balance if opening_balance >= 0 else 0,
                "balance": running_balance
            })
    
    # Get all transactions
    transactions = get_member_transactions(member, from_date, to_date)
    
    for txn in transactions:
        if txn.get("credit"):
            running_balance += flt(txn.get("credit"))
        if txn.get("debit"):
            running_balance -= flt(txn.get("debit"))
        
        txn["balance"] = running_balance
        data.append(txn)
    
    # Add closing balance row
    if data:
        data.append({
            "posting_date": "",
            "transaction_type": "Closing Balance",
            "reference_doctype": "",
            "reference_name": "",
            "description": "",
            "debit": "",
            "credit": "",
            "balance": running_balance
        })
    
    return data


def get_opening_balance(member, from_date):
    """Calculate opening balance before the from_date"""
    opening_balance = 0
    
    # Contributions before from_date
    contributions = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM `tabMember Contribution`
        WHERE member = %s AND docstatus = 1 AND contribution_date < %s
    """, (member, from_date), as_dict=True)
    opening_balance += flt(contributions[0].total if contributions else 0)
    
    # Shares before from_date
    shares = frappe.db.sql("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM `tabShare Allocation`
        WHERE member = %s AND docstatus = 1 AND allocation_date < %s AND status = 'Allocated'
    """, (member, from_date), as_dict=True)
    opening_balance += flt(shares[0].total if shares else 0)
    
    # Loan disbursements (debit to member)
    loans_disbursed = frappe.db.sql("""
        SELECT COALESCE(SUM(approved_amount), 0) as total
        FROM `tabLoan Application`
        WHERE member = %s AND docstatus = 1 AND disbursement_date < %s AND status = 'Disbursed'
    """, (member, from_date), as_dict=True)
    opening_balance -= flt(loans_disbursed[0].total if loans_disbursed else 0)
    
    # Loan repayments before from_date
    repayments = frappe.db.sql("""
        SELECT COALESCE(SUM(amount_paid), 0) as total
        FROM `tabLoan Repayment`
        WHERE member = %s AND docstatus = 1 AND payment_date < %s
    """, (member, from_date), as_dict=True)
    opening_balance += flt(repayments[0].total if repayments else 0)
    
    # Fines before from_date
    fines = frappe.db.sql("""
        SELECT COALESCE(SUM(amount - COALESCE(waived_amount, 0)), 0) as total
        FROM `tabMember Fine`
        WHERE member = %s AND docstatus = 1 AND fine_date < %s
    """, (member, from_date), as_dict=True)
    opening_balance -= flt(fines[0].total if fines else 0)
    
    return opening_balance


def get_member_transactions(member, from_date=None, to_date=None):
    """Get all transactions for a member"""
    transactions = []
    
    date_condition = ""
    if from_date:
        date_condition += f" AND {{date_field}} >= '{from_date}'"
    if to_date:
        date_condition += f" AND {{date_field}} <= '{to_date}'"
    
    # Contributions
    contribution_query = f"""
        SELECT 
            contribution_date as posting_date,
            'Contribution' as transaction_type,
            'Member Contribution' as reference_doctype,
            name as reference_name,
            CONCAT(contribution_type, ' - ', COALESCE(reference_no, '')) as description,
            0 as debit,
            amount as credit
        FROM `tabMember Contribution`
        WHERE member = %s AND docstatus = 1
        {date_condition.format(date_field='contribution_date')}
    """
    contributions = frappe.db.sql(contribution_query, (member,), as_dict=True)
    transactions.extend(contributions)
    
    # Share Allocations
    share_query = f"""
        SELECT 
            allocation_date as posting_date,
            'Share Purchase' as transaction_type,
            'Share Allocation' as reference_doctype,
            name as reference_name,
            CONCAT(share_type, ' - ', quantity, ' shares') as description,
            0 as debit,
            amount as credit
        FROM `tabShare Allocation`
        WHERE member = %s AND docstatus = 1 AND status = 'Allocated'
        {date_condition.format(date_field='allocation_date')}
    """
    shares = frappe.db.sql(share_query, (member,), as_dict=True)
    transactions.extend(shares)
    
    # Loan Disbursements
    loan_query = f"""
        SELECT 
            disbursement_date as posting_date,
            'Loan Disbursement' as transaction_type,
            'Loan Application' as reference_doctype,
            name as reference_name,
            CONCAT(loan_type, ' - Approved: ', approved_amount) as description,
            approved_amount as debit,
            0 as credit
        FROM `tabLoan Application`
        WHERE member = %s AND docstatus = 1 AND status = 'Disbursed' AND disbursement_date IS NOT NULL
        {date_condition.format(date_field='disbursement_date')}
    """
    loans = frappe.db.sql(loan_query, (member,), as_dict=True)
    transactions.extend(loans)
    
    # Loan Repayments
    repayment_query = f"""
        SELECT 
            payment_date as posting_date,
            'Loan Repayment' as transaction_type,
            'Loan Repayment' as reference_doctype,
            name as reference_name,
            CONCAT('Principal: ', principal_paid, ', Interest: ', interest_paid) as description,
            0 as debit,
            amount_paid as credit
        FROM `tabLoan Repayment`
        WHERE member = %s AND docstatus = 1
        {date_condition.format(date_field='payment_date')}
    """
    repayments = frappe.db.sql(repayment_query, (member,), as_dict=True)
    transactions.extend(repayments)
    
    # Fines
    fine_query = f"""
        SELECT 
            fine_date as posting_date,
            'Fine' as transaction_type,
            'Member Fine' as reference_doctype,
            name as reference_name,
            CONCAT(fine_type, ' - ', COALESCE(reason, '')) as description,
            (amount - COALESCE(waived_amount, 0)) as debit,
            0 as credit
        FROM `tabMember Fine`
        WHERE member = %s AND docstatus = 1
        {date_condition.format(date_field='fine_date')}
    """
    fines = frappe.db.sql(fine_query, (member,), as_dict=True)
    transactions.extend(fines)
    
    # Dividends
    dividend_query = f"""
        SELECT 
            dp.payment_date as posting_date,
            'Dividend' as transaction_type,
            'Dividend Declaration' as reference_doctype,
            dd.name as reference_name,
            CONCAT(dd.share_type, ' - Rate: ', dd.dividend_rate, '%') as description,
            0 as debit,
            dp.net_amount as credit
        FROM `tabDividend Payment` dp
        INNER JOIN `tabDividend Declaration` dd ON dp.parent = dd.name
        WHERE dp.member = %s AND dd.docstatus = 1 AND dp.status = 'Paid'
        {date_condition.format(date_field='dp.payment_date')}
    """
    dividends = frappe.db.sql(dividend_query, (member,), as_dict=True)
    transactions.extend(dividends)
    
    # Sort by date
    transactions.sort(key=lambda x: x.get("posting_date") or "")
    
    return transactions
