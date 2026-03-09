# Copyright (c) 2024, SACCO and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    chart = get_chart(data, filters)
    summary = get_summary(data)
    return columns, data, None, chart, summary


def get_columns(filters):
    columns = []
    
    group_by = filters.get("group_by", "Branch")
    
    if group_by == "Branch":
        columns.append({
            "fieldname": "branch",
            "label": _("Branch"),
            "fieldtype": "Link",
            "options": "Branch",
            "width": 150
        })
    elif group_by == "Member Group":
        columns.append({
            "fieldname": "member_group",
            "label": _("Member Group"),
            "fieldtype": "Link",
            "options": "Member Group",
            "width": 150
        })
    elif group_by == "Contribution Type":
        columns.append({
            "fieldname": "contribution_type",
            "label": _("Contribution Type"),
            "fieldtype": "Link",
            "options": "Contribution Type",
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
            "fieldname": "total_contributions",
            "label": _("Total Amount"),
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "fieldname": "contribution_count",
            "label": _("No. of Contributions"),
            "fieldtype": "Int",
            "width": 130
        },
        {
            "fieldname": "member_count",
            "label": _("No. of Members"),
            "fieldtype": "Int",
            "width": 120
        },
        {
            "fieldname": "avg_contribution",
            "label": _("Avg per Contribution"),
            "fieldtype": "Currency",
            "width": 140
        }
    ])
    
    return columns


def get_data(filters):
    conditions = get_conditions(filters)
    group_by = filters.get("group_by", "Branch")
    
    if group_by == "Branch":
        group_field = "m.branch"
        select_field = "m.branch as branch"
    elif group_by == "Member Group":
        group_field = "m.member_group"
        select_field = "m.member_group as member_group"
    elif group_by == "Contribution Type":
        group_field = "mc.contribution_type"
        select_field = "mc.contribution_type as contribution_type"
    elif group_by == "Member":
        group_field = "mc.member"
        select_field = "mc.member as member, m.member_name as member_name"
    else:
        group_field = "m.branch"
        select_field = "m.branch as branch"
    
    query = f"""
        SELECT 
            {select_field},
            SUM(mc.amount) as total_contributions,
            COUNT(mc.name) as contribution_count,
            COUNT(DISTINCT mc.member) as member_count,
            AVG(mc.amount) as avg_contribution
        FROM `tabMember Contribution` mc
        INNER JOIN `tabSACCO Member` m ON mc.member = m.name
        WHERE mc.docstatus = 1
        {conditions}
        GROUP BY {group_field}
        ORDER BY total_contributions DESC
    """
    
    data = frappe.db.sql(query, filters, as_dict=True)
    
    for row in data:
        row["avg_contribution"] = flt(row.get("avg_contribution"), 2)
    
    return data


def get_conditions(filters):
    conditions = ""
    
    if filters.get("from_date"):
        conditions += " AND mc.contribution_date >= %(from_date)s"
    if filters.get("to_date"):
        conditions += " AND mc.contribution_date <= %(to_date)s"
    if filters.get("branch"):
        conditions += " AND m.branch = %(branch)s"
    if filters.get("contribution_type"):
        conditions += " AND mc.contribution_type = %(contribution_type)s"
    if filters.get("member_group"):
        conditions += " AND m.member_group = %(member_group)s"
    
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
    
    values = [row.get("total_contributions", 0) for row in data[:10]]
    
    return {
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Total Contributions"),
                    "values": values
                }
            ]
        },
        "type": "bar",
        "colors": ["#5e64ff"]
    }


def get_summary(data):
    total_amount = sum(row.get("total_contributions", 0) for row in data)
    total_count = sum(row.get("contribution_count", 0) for row in data)
    total_members = sum(row.get("member_count", 0) for row in data)
    
    return [
        {
            "value": total_amount,
            "indicator": "Blue",
            "label": _("Total Contributions"),
            "datatype": "Currency"
        },
        {
            "value": total_count,
            "indicator": "Green",
            "label": _("Total Transactions"),
            "datatype": "Int"
        },
        {
            "value": total_members,
            "indicator": "Orange",
            "label": _("Contributing Members"),
            "datatype": "Int"
        }
    ]
