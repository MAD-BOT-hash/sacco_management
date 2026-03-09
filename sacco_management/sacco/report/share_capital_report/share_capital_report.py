# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart(data, filters)
    summary = get_summary(filters)
    return columns, data, None, chart, summary


def get_columns(filters):
    group_by = filters.get("group_by", "Share Type")
    columns = []
    
    if group_by == "Share Type":
        columns.extend([
            {
                "fieldname": "share_type",
                "label": _("Share Type"),
                "fieldtype": "Link",
                "options": "Share Type",
                "width": 150
            },
            {
                "fieldname": "price_per_share",
                "label": _("Price/Share"),
                "fieldtype": "Currency",
                "width": 120
            }
        ])
    elif group_by == "Branch":
        columns.append({
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
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
            "fieldname": "total_shares",
            "label": _("Total Shares"),
            "fieldtype": "Float",
            "precision": "2",
            "width": 120
        },
        {
            "fieldname": "total_amount",
            "label": _("Total Value"),
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "fieldname": "member_count",
            "label": _("No. of Shareholders"),
            "fieldtype": "Int",
            "width": 140
        },
        {
            "fieldname": "avg_shares_per_member",
            "label": _("Avg Shares/Member"),
            "fieldtype": "Float",
            "precision": "2",
            "width": 140
        }
    ])
    
    return columns


def get_data(filters):
    conditions = get_conditions(filters)
    group_by = filters.get("group_by", "Share Type")
    
    if group_by == "Share Type":
        group_field = "sa.share_type"
        select_field = "sa.share_type as share_type, st.price_per_share"
        join_clause = "LEFT JOIN `tabShare Type` st ON sa.share_type = st.name"
    elif group_by == "Branch":
        group_field = "m.branch"
        select_field = "m.branch as branch"
        join_clause = ""
    elif group_by == "Member":
        group_field = "sa.member"
        select_field = "sa.member as member, m.member_name as member_name"
        join_clause = ""
    else:
        group_field = "sa.share_type"
        select_field = "sa.share_type as share_type, st.price_per_share"
        join_clause = "LEFT JOIN `tabShare Type` st ON sa.share_type = st.name"
    
    query = f"""
        SELECT 
            {select_field},
            SUM(sa.quantity) as total_shares,
            SUM(sa.amount) as total_amount,
            COUNT(DISTINCT sa.member) as member_count
        FROM `tabShare Allocation` sa
        INNER JOIN `tabSACCO Member` m ON sa.member = m.name
        {join_clause}
        WHERE sa.docstatus = 1 AND sa.status = 'Allocated'
        {conditions}
        GROUP BY {group_field}
        ORDER BY total_amount DESC
    """
    
    data = frappe.db.sql(query, filters, as_dict=True)
    
    for row in data:
        member_count = row.get("member_count", 1) or 1
        row["avg_shares_per_member"] = flt(row.get("total_shares", 0)) / member_count
    
    return data


def get_conditions(filters):
    conditions = ""
    
    if filters.get("from_date"):
        conditions += " AND sa.allocation_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND sa.allocation_date <= %(to_date)s"
    if filters.get("branch"):
        conditions += " AND m.branch = %(branch)s"
    if filters.get("share_type"):
        conditions += " AND sa.share_type = %(share_type)s"
    
    return conditions


def get_chart(data, filters):
    if not data:
        return None
    
    group_by = filters.get("group_by", "Share Type")
    
    if group_by == "Member":
        labels = [row.get("member_name", row.get("member", "")) for row in data[:10]]
    else:
        label_field = group_by.lower().replace(" ", "_")
        labels = [row.get(label_field, "") for row in data[:10]]
    
    values = [row.get("total_amount", 0) for row in data[:10]]
    
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Share Capital"),
                    "values": values
                }
            ]
        },
        "type": "pie",
        "colors": ["#5e64ff", "#28a745", "#ffc107", "#dc3545", "#17a2b8", "#6c757d", "#fd7e14", "#20c997", "#e83e8c", "#6610f2"]
    }


def get_summary(filters):
    conditions = get_conditions(filters)
    
    summary_query = f"""
        SELECT 
            SUM(sa.quantity) as total_shares,
            SUM(sa.amount) as total_capital,
            COUNT(DISTINCT sa.member) as total_shareholders,
            COUNT(DISTINCT sa.share_type) as share_types
        FROM `tabShare Allocation` sa
        INNER JOIN `tabSACCO Member` m ON sa.member = m.name
        WHERE sa.docstatus = 1 AND sa.status = 'Allocated'
        {conditions}
    """
    
    result = frappe.db.sql(summary_query, filters, as_dict=True)
    data = result[0] if result else {}
    
    return [
        {
            "value": flt(data.get("total_capital", 0)),
            "indicator": "Blue",
            "label": _("Total Share Capital"),
            "datatype": "Currency"
        },
        {
            "value": flt(data.get("total_shares", 0)),
            "indicator": "Green",
            "label": _("Total Shares"),
            "datatype": "Float"
        },
        {
            "value": data.get("total_shareholders", 0),
            "indicator": "Orange",
            "label": _("Total Shareholders"),
            "datatype": "Int"
        },
        {
            "value": data.get("share_types", 0),
            "indicator": "Grey",
            "label": _("Share Types"),
            "datatype": "Int"
        }
    ]
