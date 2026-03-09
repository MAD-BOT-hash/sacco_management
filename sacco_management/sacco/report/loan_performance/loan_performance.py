# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, today


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart(data, filters)
    summary = get_summary(filters)
    return columns, data, None, chart, summary


def get_columns(filters):
    group_by = filters.get("group_by", "Branch")
    columns = []
    
    if group_by == "Branch":
        columns.append({
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 150
        })
    elif group_by == "Loan Type":
        columns.append({
            "fieldname": "loan_type",
            "label": _("Loan Type"),
            "fieldtype": "Link",
            "options": "Loan Type",
            "width": 150
        })
    elif group_by == "Member":
        columns.extend([
            {
                "fieldname": "member",
                "label": _("Member"),
                "fieldtype": "Link",
                "options": "SACCO Member",
                "width": 120
            },
            {
                "fieldname": "member_name",
                "label": _("Member Name"),
                "fieldtype": "Data",
                "width": 150
            }
        ])
    
    columns.extend([
        {
            "fieldname": "total_disbursed",
            "label": _("Total Disbursed"),
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "fieldname": "total_principal_due",
            "label": _("Principal Due"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "total_interest_due",
            "label": _("Interest Due"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "total_collected",
            "label": _("Total Collected"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "outstanding_balance",
            "label": _("Outstanding"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "arrears",
            "label": _("Arrears (Overdue)"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "par_30",
            "label": _("PAR > 30 Days"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "loan_count",
            "label": _("No. of Loans"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "collection_rate",
            "label": _("Collection Rate %"),
            "fieldtype": "Percent",
            "width": 120
        }
    ])
    
    return columns


def get_data(filters):
    conditions = get_conditions(filters)
    group_by = filters.get("group_by", "Branch")
    
    if group_by == "Branch":
        group_field = "m.branch"
        select_field = "m.branch as branch"
    elif group_by == "Loan Type":
        group_field = "la.loan_type"
        select_field = "la.loan_type as loan_type"
    elif group_by == "Member":
        group_field = "la.member"
        select_field = "la.member as member, m.member_name as member_name"
    else:
        group_field = "m.branch"
        select_field = "m.branch as branch"
    
    query = f"""
        SELECT 
            {select_field},
            SUM(la.approved_amount) as total_disbursed,
            SUM(la.total_principal) as total_principal_due,
            SUM(la.total_interest) as total_interest_due,
            SUM(la.total_paid) as total_collected,
            SUM(la.outstanding_amount) as outstanding_balance,
            COUNT(la.name) as loan_count
        FROM `tabLoan Application` la
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE la.docstatus = 1 AND la.status IN ('Disbursed', 'Partially Paid', 'Fully Paid')
        {conditions}
        GROUP BY {group_field}
        ORDER BY total_disbursed DESC
    """
    
    data = frappe.db.sql(query, filters, as_dict=True)
    
    # Calculate arrears and PAR for each row
    for row in data:
        arrears_data = get_arrears_data(filters, group_by, row)
        row["arrears"] = arrears_data.get("arrears", 0)
        row["par_30"] = arrears_data.get("par_30", 0)
        
        # Calculate collection rate
        total_due = flt(row.get("total_principal_due", 0)) + flt(row.get("total_interest_due", 0))
        total_collected = flt(row.get("total_collected", 0))
        row["collection_rate"] = (total_collected / total_due * 100) if total_due > 0 else 0
    
    return data


def get_arrears_data(filters, group_by, row):
    """Calculate arrears and PAR > 30 days"""
    today_date = today()
    
    if group_by == "Branch":
        filter_field = "m.branch"
        filter_value = row.get("branch")
    elif group_by == "Loan Type":
        filter_field = "la.loan_type"
        filter_value = row.get("loan_type")
    elif group_by == "Member":
        filter_field = "la.member"
        filter_value = row.get("member")
    else:
        filter_field = "m.branch"
        filter_value = row.get("branch")
    
    if not filter_value:
        return {"arrears": 0, "par_30": 0}
    
    # Get overdue amounts from repayment schedules
    arrears_query = f"""
        SELECT 
            COALESCE(SUM(lrs.total_due - lrs.paid_amount), 0) as arrears,
            COALESCE(SUM(
                CASE WHEN DATEDIFF('{today_date}', lrs.due_date) > 30 
                THEN (lrs.total_due - lrs.paid_amount) ELSE 0 END
            ), 0) as par_30
        FROM `tabLoan Repayment Schedule` lrs
        INNER JOIN `tabLoan Application` la ON lrs.parent = la.name
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE la.docstatus = 1 
        AND la.status IN ('Disbursed', 'Partially Paid')
        AND lrs.due_date < '{today_date}'
        AND lrs.status != 'Paid'
        AND {filter_field} = %s
    """
    
    result = frappe.db.sql(arrears_query, (filter_value,), as_dict=True)
    
    if result:
        return result[0]
    return {"arrears": 0, "par_30": 0}


def get_conditions(filters):
    conditions = ""
    
    if filters.get("from_date"):
        conditions += " AND la.disbursement_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND la.disbursement_date <= %(to_date)s"
    if filters.get("branch"):
        conditions += " AND m.branch = %(branch)s"
    if filters.get("loan_type"):
        conditions += " AND la.loan_type = %(loan_type)s"
    if filters.get("status"):
        conditions += " AND la.status = %(status)s"
    
    return conditions


def get_chart(data, filters):
    if not data:
        return None
    
    group_by = filters.get("group_by", "Branch")
    label_field = group_by.lower().replace(" ", "_")
    
    if group_by == "Member":
        labels = [row.get("member_name", row.get("member", "")) for row in data[:10]]
    else:
        labels = [row.get(label_field, "") for row in data[:10]]
    
    disbursed = [row.get("total_disbursed", 0) for row in data[:10]]
    collected = [row.get("total_collected", 0) for row in data[:10]]
    outstanding = [row.get("outstanding_balance", 0) for row in data[:10]]
    
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Disbursed"),
                    "values": disbursed
                },
                {
                    "name": _("Collected"),
                    "values": collected
                },
                {
                    "name": _("Outstanding"),
                    "values": outstanding
                }
            ]
        },
        "type": "bar",
        "colors": ["#5e64ff", "#28a745", "#dc3545"]
    }


def get_summary(filters):
    conditions = get_conditions(filters)
    
    summary_query = f"""
        SELECT 
            SUM(la.approved_amount) as total_disbursed,
            SUM(la.total_paid) as total_collected,
            SUM(la.outstanding_amount) as total_outstanding,
            COUNT(la.name) as total_loans,
            COUNT(DISTINCT la.member) as total_borrowers
        FROM `tabLoan Application` la
        INNER JOIN `tabSACCO Member` m ON la.member = m.name
        WHERE la.docstatus = 1 AND la.status IN ('Disbursed', 'Partially Paid', 'Fully Paid')
        {conditions}
    """
    
    result = frappe.db.sql(summary_query, filters, as_dict=True)
    data = result[0] if result else {}
    
    total_disbursed = flt(data.get("total_disbursed", 0))
    total_collected = flt(data.get("total_collected", 0))
    total_outstanding = flt(data.get("total_outstanding", 0))
    
    collection_rate = (total_collected / total_disbursed * 100) if total_disbursed > 0 else 0
    
    return [
        {
            "value": total_disbursed,
            "indicator": "Blue",
            "label": _("Total Disbursed"),
            "datatype": "Currency"
        },
        {
            "value": total_collected,
            "indicator": "Green",
            "label": _("Total Collected"),
            "datatype": "Currency"
        },
        {
            "value": total_outstanding,
            "indicator": "Orange",
            "label": _("Outstanding Balance"),
            "datatype": "Currency"
        },
        {
            "value": collection_rate,
            "indicator": "Blue",
            "label": _("Collection Rate"),
            "datatype": "Percent"
        }
    ]
