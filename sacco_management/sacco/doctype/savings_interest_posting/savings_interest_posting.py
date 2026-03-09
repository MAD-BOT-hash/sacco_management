# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate, date_diff


class SavingsInterestPosting(Document):
    def validate(self):
        self.validate_dates()
        self.validate_account()
        
    def validate_dates(self):
        """Validate date range"""
        if getdate(self.period_start_date) > getdate(self.period_end_date):
            frappe.throw(_("Period Start Date cannot be after Period End Date"))
        
        if getdate(self.posting_date) < getdate(self.period_end_date):
            frappe.throw(_("Posting Date cannot be before Period End Date"))
    
    def validate_account(self):
        """Validate account exists and is active"""
        account_status = frappe.db.get_value("Savings Account", self.account, "status")
        if account_status != "Active":
            frappe.throw(_("Cannot post interest for {0} account").format(account_status))
    
    def on_submit(self):
        """Post interest on submit"""
        self.post_interest()
    
    def on_cancel(self):
        """Reverse interest posting on cancel"""
        self.reverse_interest()
    
    def calculate_interest(self):
        """Calculate interest for the period"""
        account = frappe.get_doc("Savings Account", self.account)
        
        # Set period dates
        self.period_start_date = self.period_start_date or account.last_interest_calculation_date or account.opening_date
        self.period_end_date = self.period_end_date or nowdate()
        self.posting_date = self.posting_date or nowdate()
        
        # Calculate days in period
        self.days_in_period = date_diff(self.period_end_date, self.period_start_date) or 1
        
        # Get applicable interest rules
        rules = frappe.get_all("Savings Interest Rule",
            filters={"is_active": 1, "product": account.product},
            fields=["name"],
            order_by="priority ASC")
        
        total_interest = 0
        applied_rules = []
        principal_amount = 0
        effective_rate = flt(account.interest_rate)
        
        # Try each rule
        for rule_data in rules:
            rule = frappe.get_doc("Savings Interest Rule", rule_data.name)
            
            if rule.is_applicable(account):
                interest = rule.calculate_interest(account, self.period_start_date, self.period_end_date)
                
                if interest > 0:
                    total_interest += interest
                    applied_rules.append(f"{rule.rule_name}: {interest:.2f}")
                    
                    if flt(rule.special_interest_rate) > 0:
                        effective_rate = flt(rule.special_interest_rate)
                    
                    # Get principal from first rule
                    if principal_amount == 0:
                        method = rule.interest_calculation_method or account.interest_calculation_method
                        if method == "Daily Balance":
                            principal_amount = rule.get_daily_average_balance(account, self.period_start_date, self.period_end_date)
                        elif method == "Minimum Balance":
                            principal_amount = rule.get_minimum_balance(account, self.period_start_date, self.period_end_date)
                        else:
                            principal_amount = flt(account.balance)
        
        # If no rules applied, use default calculation
        if not applied_rules:
            product = frappe.get_doc("Savings Product", account.product)
            
            if flt(product.min_balance_for_interest) > 0 and flt(account.balance) < flt(product.min_balance_for_interest):
                total_interest = 0
            else:
                # Default daily balance method
                principal_amount = flt(account.balance)
                days_in_year = 365
                total_interest = (principal_amount * effective_rate * self.days_in_period) / (100 * days_in_year)
                applied_rules.append(f"Default ({product.interest_calculation_method}): {total_interest:.2f}")
        
        # Set values
        self.principal_amount = flt(principal_amount)
        self.interest_rate = flt(effective_rate)
        self.calculated_interest = flt(total_interest)
        self.total_interest = flt(total_interest)
        self.bonus_interest = 0  # Already included in total
        self.calculation_method = account.interest_calculation_method
        self.applied_rules = ", ".join(applied_rules) if applied_rules else "Default Calculation"
        
        # Set balance before posting
        self.balance_before_posting = flt(account.balance)
        self.balance_after_posting = flt(account.balance) + flt(self.total_interest)
        
        self.status = "Calculated"
        self.save(ignore_permissions=True)
        
        return self
    
    def post_interest(self):
        """Post calculated interest to account"""
        if self.status != "Calculated":
            self.calculate_interest()
        
        if flt(self.total_interest) <= 0:
            frappe.msgprint(_("No interest to post"), alert=True)
            return
        
        account = frappe.get_doc("Savings Account", self.account)
        product = frappe.get_doc("Savings Product", account.product)
        
        # Update account balances
        account.balance = flt(account.balance) + flt(self.total_interest)
        account.available_balance = flt(account.balance)
        account.accrued_interest = 0
        account.total_interest_earned = flt(account.total_interest_earned) + flt(self.total_interest)
        account.last_interest_calculation_date = self.posting_date
        
        # Update next posting date
        if product.interest_posting_frequency == "Monthly":
            from frappe.utils import add_months
            account.next_interest_posting_date = add_months(getdate(self.posting_date), 1)
        elif product.interest_posting_frequency == "Quarterly":
            from frappe.utils import add_months
            account.next_interest_posting_date = add_months(getdate(self.posting_date), 3)
        elif product.interest_posting_frequency == "Annually":
            from frappe.utils import add_months
            account.next_interest_posting_date = add_months(getdate(self.posting_date), 12)
        
        account.save(ignore_permissions=True)
        
        # Create transaction record
        self.create_transaction_entry(account)
        
        # Post to GL
        self.post_to_gl(account, product)
        
        self.status = "Posted"
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Interest of {} posted successfully").format(self.total_interest), alert=True)
    
    def create_transaction_entry(self, account):
        """Create a savings transaction for the interest"""
        transaction = frappe.new_doc("Savings Transaction")
        transaction.account = self.account
        transaction.member = self.member
        transaction.transaction_date = self.posting_date
        transaction.transaction_type = "Interest Credit"
        transaction.amount = self.total_interest
        transaction.interest_component = self.total_interest
        transaction.remarks = f"Interest for {self.period_start_date} to {self.period_end_date}"
        transaction.insert(ignore_permissions=True)
        transaction.submit()
    
    def post_to_gl(self, account, product):
        """Post interest to General Ledger"""
        if not product.interest_gl_account:
            frappe.throw(_("Interest GL Account not configured in product"))
        
        from sacco_management.sacco.utils.gl_utils import create_gl_entry
        
        accounts = [
            {
                "gl_account": product.interest_gl_account,
                "debit": self.total_interest,
                "credit": 0,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Interest expense for {account.account_name}"
            },
            {
                "gl_account": product.default_gl_account,
                "debit": 0,
                "credit": self.total_interest,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Interest credited to {account.account_name}"
            }
        ]
        
        je = create_gl_entry(
            voucher_type="Journal Entry",
            posting_date=self.posting_date,
            accounts=accounts,
            remarks=f"Savings Interest Posting: {account.account_name} - Period: {self.period_start_date} to {self.period_end_date}",
            reference_type="Savings Interest Posting",
            reference_name=self.name,
            branch=account.branch
        )
        
        self.journal_entry = je.name
        self.gl_posted = 1
        self.save(ignore_permissions=True)
    
    def reverse_interest(self):
        """Reverse the interest posting"""
        if self.status != "Posted":
            frappe.throw(_("Can only reverse posted interest"))
        
        account = frappe.get_doc("Savings Account", self.account)
        
        # Reverse account balance
        account.balance = flt(account.balance) - flt(self.total_interest)
        account.available_balance = flt(account.balance)
        account.total_interest_earned = flt(account.total_interest_earned) - flt(self.total_interest)
        account.save(ignore_permissions=True)
        
        # Reverse GL entry
        if self.gl_posted and self.journal_entry:
            from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
            reverse_gl_entry("Savings Interest Posting", self.name)
        
        self.status = "Cancelled"
        self.save(ignore_permissions=True)


@frappe.whitelist()
def calculate_interest_for_account(account, period_start, period_end, posting_date=None):
    """Calculate interest for an account"""
    doc = frappe.new_doc("Savings Interest Posting")
    doc.account = account
    doc.period_start_date = period_start
    doc.period_end_date = period_end
    doc.posting_date = posting_date or nowdate()
    
    doc.calculate_interest()
    return doc.as_dict()


@frappe.whitelist()
def post_interest_for_account(account, period_start, period_end, posting_date=None):
    """Calculate and post interest for an account"""
    doc = frappe.new_doc("Savings Interest Posting")
    doc.account = account
    doc.period_start_date = period_start
    doc.period_end_date = period_end
    doc.posting_date = posting_date or nowdate()
    
    doc.calculate_interest()
    doc.insert(ignore_permissions=True)
    doc.submit()
    
    frappe.db.commit()
    return doc.as_dict()
