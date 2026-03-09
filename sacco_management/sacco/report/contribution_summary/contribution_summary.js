frappe.query_reports["Contribution Summary"] = {
    "filters": [
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -12),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "group_by",
            "label": __("Group By"),
            "fieldtype": "Select",
            "options": "Branch\nMember Group\nContribution Type\nMember",
            "default": "Branch"
        },
        {
            "fieldname": "branch",
            "label": __("Branch"),
            "fieldtype": "Link",
            "options": "Branch"
        },
        {
            "fieldname": "member_group",
            "label": __("Member Group"),
            "fieldtype": "Link",
            "options": "Member Group",
            "get_query": function() {
                var branch = frappe.query_report.get_filter_value("branch");
                if (branch) {
                    return {
                        filters: {
                            "branch": branch
                        }
                    };
                }
            }
        },
        {
            "fieldname": "contribution_type",
            "label": __("Contribution Type"),
            "fieldtype": "Link",
            "options": "Contribution Type"
        }
    ]
};
