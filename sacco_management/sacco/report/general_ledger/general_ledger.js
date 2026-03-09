frappe.query_reports["General Ledger"] = {
    "filters": [
        {
            "fieldname": "account",
            "label": __("Account"),
            "fieldtype": "Link",
            "options": "SACCO GL Account"
        },
        {
            "fieldname": "party_type",
            "label": __("Party Type"),
            "fieldtype": "Link",
            "options": "DocType",
            "get_query": function() {
                return {
                    filters: {
                        "name": ["in", ["SACCO Member", "Supplier", "Employee"]]
                    }
                };
            }
        },
        {
            "fieldname": "party",
            "label": __("Party"),
            "fieldtype": "Dynamic Link",
            "options": "party_type"
        },
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
            "fieldname": "voucher_type",
            "label": __("Voucher Type"),
            "fieldtype": "Select",
            "options": "\nMember Contribution\nLoan Application\nLoan Repayment\nShare Allocation\nMember Fine\nDividend Declaration"
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (data && (data.account === __("Opening Balance") || data.account === __("Total / Closing Balance"))) {
            value = "<b>" + value + "</b>";
        }
        return value;
    }
};
