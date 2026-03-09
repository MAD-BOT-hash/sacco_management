app_name = "sacco_management"
app_title = "SACCO Management"
app_publisher = "SACCO Developer"
app_description = "Complete SACCO Management System for ERPNext - Handles Members, Contributions, Loans, Shares, Dividends, Fines with full GL integration"
app_email = "developer@sacco.com"
app_license = "MIT"
app_version = "1.0.0"

# Required Apps
required_apps = ["frappe", "erpnext"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/sacco_management/css/sacco_management.css"
# app_include_js = "/assets/sacco_management/js/sacco_management.js"

# include js, css files in header of web template
# web_include_css = "/assets/sacco_management/css/sacco_management.css"
# web_include_js = "/assets/sacco_management/js/sacco_management.js"

# include custom scss in every website theme (without signing in)
# website_theme_scss = "sacco_management/public/scss/website"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "SACCO Member": "sacco/doctype/sacco_member/sacco_member.js",
    "Loan Application": "sacco/doctype/loan_application/loan_application.js",
    "Member Contribution": "sacco/doctype/member_contribution/member_contribution.js",
}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#     "Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#     "methods": "sacco_management.utils.jinja_methods",
#     "filters": "sacco_management.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "sacco_management.install.before_install"
# after_install is commented out because DocTypes need to be migrated first
# Run: bench --site your-site migrate
# Then: bench --site your-site execute sacco_management.sacco.setup.install.setup_sacco_data
# after_install = "sacco_management.sacco.setup.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "sacco_management.uninstall.before_uninstall"
# after_uninstall = "sacco_management.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "sacco_management.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
    "SACCO Member": "sacco_management.sacco.doctype.sacco_member.sacco_member.get_permission_query_conditions",
    "Loan Application": "sacco_management.sacco.doctype.loan_application.loan_application.get_permission_query_conditions",
    "Member Contribution": "sacco_management.sacco.doctype.member_contribution.member_contribution.get_permission_query_conditions",
    "SACCO Meeting": "sacco_management.sacco.doctype.sacco_meeting.sacco_meeting.get_permission_query_conditions",
}

has_permission = {
    "SACCO Member": "sacco_management.sacco.doctype.sacco_member.sacco_member.has_permission",
    "Loan Application": "sacco_management.sacco.doctype.loan_application.loan_application.has_permission",
    "Member Contribution": "sacco_management.sacco.doctype.member_contribution.member_contribution.has_permission",
    "SACCO Meeting": "sacco_management.sacco.doctype.sacco_meeting.sacco_meeting.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#     "ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Member Contribution": {
        "on_submit": "sacco_management.sacco.doctype.member_contribution.member_contribution.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.member_contribution.member_contribution.on_cancel",
    },
    "Loan Application": {
        "on_submit": "sacco_management.sacco.doctype.loan_application.loan_application.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.loan_application.loan_application.on_cancel",
        "on_update_after_submit": "sacco_management.sacco.doctype.loan_application.loan_application.on_update_after_submit",
    },
    "Loan Repayment": {
        "on_submit": "sacco_management.sacco.doctype.loan_repayment.loan_repayment.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.loan_repayment.loan_repayment.on_cancel",
    },
    "Share Allocation": {
        "on_submit": "sacco_management.sacco.doctype.share_allocation.share_allocation.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.share_allocation.share_allocation.on_cancel",
    },
    "Dividend Declaration": {
        "on_submit": "sacco_management.sacco.doctype.dividend_declaration.dividend_declaration.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.dividend_declaration.dividend_declaration.on_cancel",
    },
    "Member Fine": {
        "on_submit": "sacco_management.sacco.doctype.member_fine.member_fine.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.member_fine.member_fine.on_cancel",
    },
    "Member Attendance Fine": {
        "on_submit": "sacco_management.sacco.doctype.member_attendance_fine.member_attendance_fine.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.member_attendance_fine.member_attendance_fine.on_cancel",
    },
    "Savings Deposit": {
        "on_submit": "sacco_management.sacco.doctype.savings_deposit.savings_deposit.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.savings_deposit.savings_deposit.on_cancel",
    },
    "Savings Withdrawal": {
        "on_submit": "sacco_management.sacco.doctype.savings_withdrawal.savings_withdrawal.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.savings_withdrawal.savings_withdrawal.on_cancel",
    },
    "Savings Interest Posting": {
        "on_submit": "sacco_management.sacco.doctype.savings_interest_posting.savings_interest_posting.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.savings_interest_posting.savings_interest_posting.on_cancel",
    },
    "Loan Agreement": {
        "on_submit": "sacco_management.sacco.doctype.loan_agreement.loan_agreement.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.loan_agreement.loan_agreement.on_cancel",
    },
    "Loan Disbursement": {
        "on_submit": "sacco_management.sacco.doctype.loan_disbursement.loan_disbursement.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.loan_disbursement.loan_disbursement.on_cancel",
    },
    "Loan Restructure": {
        "on_submit": "sacco_management.sacco.doctype.loan_restructure.loan_restructure.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.loan_restructure.loan_restructure.on_cancel",
    },
    "Loan Write Off": {
        "on_submit": "sacco_management.sacco.doctype.loan_write_off.loan_write_off.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.loan_write_off.loan_write_off.on_cancel",
    },
    "Loan Settlement": {
        "on_submit": "sacco_management.sacco.doctype.loan_settlement.loan_settlement.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.loan_settlement.loan_settlement.on_cancel",
    },
    "Share Purchase": {
        "on_submit": "sacco_management.sacco.doctype.share_purchase.share_purchase.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.share_purchase.share_purchase.on_cancel",
    },
    "Share Redemption": {
        "on_submit": "sacco_management.sacco.doctype.share_redemption.share_redemption.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.share_redemption.share_redemption.on_cancel",
    },
    "Share Ledger": {
        "on_submit": "sacco_management.sacco.doctype.share_ledger.share_ledger.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.share_ledger.share_ledger.on_cancel",
    },
    "Dividend Calculation": {
        "on_submit": "sacco_management.sacco.doctype.dividend_calculation.dividend_calculation.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.dividend_calculation.dividend_calculation.on_cancel",
    },
    "Dividend Ledger": {
        "on_submit": "sacco_management.sacco.doctype.dividend_ledger.dividend_ledger.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.dividend_ledger.dividend_ledger.on_cancel",
    },
    "Meeting Resolution": {
        "on_submit": "sacco_management.sacco.doctype.meeting_resolution.meeting_resolution.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.meeting_resolution.meeting_resolution.on_cancel",
    },
    "Fine Payment": {
        "on_submit": "sacco_management.sacco.doctype.fine_payment.fine_payment.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.fine_payment.fine_payment.on_cancel",
    },
    "Fine Waiver": {
        "on_submit": "sacco_management.sacco.doctype.fine_waiver.fine_waiver.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.fine_waiver.fine_waiver.on_cancel",
    },
    "Inter Branch Transfer": {
        "on_submit": "sacco_management.sacco.doctype.inter_branch_transfer.inter_branch_transfer.on_submit",
        "on_cancel": "sacco_management.sacco.doctype.inter_branch_transfer.inter_branch_transfer.on_cancel",
    },
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "daily": [
        "sacco_management.sacco.tasks.daily.calculate_loan_penalties",
        "sacco_management.sacco.tasks.daily.send_payment_reminders",
        "sacco_management.sacco.tasks.daily.accrue_savings_interest",  # Daily savings interest accrual
        "sacco_management.sacco.tasks.daily.accrue_loan_interest",  # Daily loan interest accrual
        "sacco_management.sacco.utils.optimized_utils.scheduled_cache_warming",  # Cache warming
    ],
    "weekly": [
        "sacco_management.sacco.tasks.weekly.generate_weekly_reports",
        "sacco_management.sacco.utils.optimized_utils.scheduled_cache_cleanup",  # Cache cleanup
    ],
    "monthly": [
        "sacco_management.sacco.tasks.monthly.calculate_interest_on_savings",
        "sacco_management.sacco.tasks.monthly.generate_monthly_statements",
        "sacco_management.sacco.tasks.monthly.process_savings_interest_posting",  # Monthly interest posting
        "sacco_management.sacco.tasks.monthly.accrue_monthly_loan_interest",  # Monthly loan interest accrual
    ],
}

# Testing
# -------

before_tests = "sacco_management.tests.test_config.setup_test_environment"

# Overriding Methods
# ------------------------------

# override_whitelisted_methods = {
#     "frappe.desk.doctype.event.event.get_events": "sacco_management.event.get_events"
# }

#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#     "Task": "sacco_management.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]


# User Data Protection
# --------------------

# user_data_fields = [
#     {
#         "doctype": "{doctype_1}",
#         "filter_by": "{filter_by}",
#         "redact_fields": ["{field_1}", "{field_2}"],
#         "partial": 1,
#     },
#     {
#         "doctype": "{doctype_2}",
#         "filter_by": "{filter_by}",
#         "partial": 1,
#     },
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#     "sacco_management.auth.validate"
# ]

# Fixtures - Export these documents when running bench export-fixtures
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [["module", "=", "SACCO"]]
    },
    {
        "doctype": "Property Setter",
        "filters": [["module", "=", "SACCO"]]
    },
    {
        "doctype": "Role",
        "filters": [["name", "in", ["SACCO Teller", "SACCO Loan Officer", "SACCO Branch Manager", "SACCO Admin", "SACCO Auditor"]]]
    },
    {
        "doctype": "Workflow",
        "filters": [["name", "in", ["Loan Application Workflow", "Share Allocation Workflow", "Dividend Declaration Workflow"]]]
    },
    {
        "doctype": "Workflow State",
        "filters": [["name", "like", "SACCO%"]]
    },
    {
        "doctype": "Workflow Action Master",
        "filters": [["name", "like", "SACCO%"]]
    },
    {
        "doctype": "Number Card",
        "filters": [["module", "=", "SACCO"]]
    },
]

# Website Route Rules
website_route_rules = [
    {"from_route": "/sacco/<path:app_path>", "to_route": "sacco"},
]

# Accounting
# -----------

# Override standard accounts
# accounting_dimension_doctypes = ["SACCO Member", "Branch", "Member Group"]

# Performance Optimization
# ------------------------

# Enable GZip compression for API responses
compress_response = True

# Rate limiting for API calls (calls per minute)
rate_limit = {
    "default": 100,
    "/api/method/sacco_management.sacco.api.*": 60,  # SACCO APIs
}

# Scheduler configuration
scheduler_events = {
    "cron": {
        # Run cache warming every 6 hours
        "0 */6 * * *": [
            "sacco_management.sacco.utils.optimized_utils.scheduled_cache_warming"
        ],
    }
}
