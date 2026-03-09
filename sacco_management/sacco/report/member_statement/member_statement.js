frappe.query_reports["Member Statement"] = {
    "filters": [
        {
            "fieldname": "member",
            "label": __("Member"),
            "fieldtype": "Link",
            "options": "SACCO Member",
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -12)
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        }
    ]
};
