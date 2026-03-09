# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate, add_months


class SavingsAccount(Document):
    def validate(self):
        self.validate_member()
        self.validate_product()
        self.set_account_details()
        
    def validate_member(self):
        """Validate member is active"""
        member_status = frappe.db.get_value("SACCO Member", self.member, "status")
        if member_status != "Active":
            frappe.throw(_("Cannot create savings account for {0} member").format(member_status))
    
    def validate_product(self):
        """Validate product is active"""
        product_active = frappe.db.get_value("Savings Product", self.product, "is_active")
        if not product_active:
            frappe.throw(_("Savings Product {0} is not active").format(self.product))
    
    def set_account_details(self):
        """Set account details from product"""
        product = frappe.get_doc("Savings Product", self.product)
        self.min_balance = flt(product.min_balance)
        self.max_balance = flt(product.max_balance)
        self.overdraft_limit = flt(product.overdraft_limit) if product.allow_overdraft else 0
        self.interest_rate = flt(product.interest_rate) if product.interest_applicable else 0
        self.interest_calculation_method = product.interest_calculation_method
        
        # Set next interest posting date
        if product.interest_posting_frequency == "Daily":
            self.next_interest_posting_date = add_months(getdate(), 0)
        elif product.interest_posting_frequency == "Weekly":
            self.next_interest_posting_date = add_months(getdate(), 0)
        elif product.interest_posting_frequency == "Monthly":
            self.next_interest_posting_date = add_months(getdate(), 1)
        elif product.interest_posting_frequency == "Quarterly":
            self.next_interest_posting_date = add_months(getdate(), 3)
        else:
            self.next_interest_posting_date = add_months(getdate(), 12)
    
    def on_update(self):
        """Update member balance on account update"""
        self.update_member_balance()
    
    def update_balance(self, amount, transaction_type="Deposit"):
        """
        Update account balance after transaction
        
        Args:
            amount: Transaction amount
            transaction_type: Deposit or Withdrawal
        """
        product = frappe.get_doc("Savings Product", self.product)
        
        if transaction_type == "Deposit":
            new_balance = flt(self.balance) + flt(amount)
            self.total_deposit = flt(self.total_deposit) + flt(amount)
        else:  # Withdrawal
            new_balance = flt(self.balance) - flt(amount)
            self.total_withdrawal = flt(self.total_withdrawal) + flt(amount)
            
            # Check minimum balance
            if product.penalty_for_below_min_balance and new_balance < flt(product.min_balance):
                frappe.msgprint(
                    _("Warning: Balance will go below minimum required ({})").format(product.min_balance),
                    alert=True
                )
        
        # Check overdraft limit
        if new_balance < 0 and abs(new_balance) > flt(self.overdraft_limit):
            frappe.throw(_("Withdrawal exceeds allowed overdraft limit"))
        
        # Check max balance
        if flt(product.max_balance) > 0 and new_balance > flt(product.max_balance):
            frappe.throw(_("Deposit exceeds maximum balance limit of {}").format(product.max_balance))
        
        self.balance = new_balance
        self.available_balance = new_balance
        
        # Update withdrawal count
        if transaction_type == "Withdrawal":
            self.withdrawals_this_month += 1
            self.last_withdrawal_date = nowdate()
            
            # Check withdrawal limits
            if product.withdrawal_limits and flt(product.max_withdrawals_per_month) > 0:
                if self.withdrawals_this_month > flt(product.max_withdrawals_per_month):
                    frappe.throw(_("Maximum withdrawals per month ({}) exceeded").format(
                        product.max_withdrawals_per_month))
        
        self.save(ignore_permissions=True)
        self.update_member_balance()
    
    def update_member_balance(self):
        """Update total savings in member master"""
        member = frappe.get_doc("SACCO Member", self.member)
        
        # Get all active savings accounts for this member
        total_savings = frappe.db.sql("""
            SELECT COALESCE(SUM(balance), 0) as total
            FROM `tabSavings Account`
            WHERE member = %s AND status = 'Active' AND docstatus = 1
        """, (self.member,), as_dict=True)[0].total
        
        member.total_savings = flt(total_savings)
        member.db_update()
    
    def calculate_accrued_interest(self, from_date=None, to_date=None):
        """
        Calculate accrued interest for the period
        
        Args:
            from_date: Start date (default: last calculation date)
            to_date: End date (default: today)
        
        Returns:
            Accrued interest amount
        """
        from_date = getdate(from_date) or getdate(self.last_interest_calculation_date) or getdate(self.opening_date)
        to_date = getdate(to_date) or nowdate()
        
        if not self.interest_rate or self.interest_rate <= 0:
            return 0
        
        product = frappe.get_doc("Savings Product", self.product)
        
        # Get daily balances
        daily_balances = frappe.db.sql("""
            SELECT 
                DATE(transaction_date) as trans_date,
                SUM(CASE WHEN transaction_type = 'Deposit' THEN amount ELSE 0 END) as deposits,
                SUM(CASE WHEN transaction_type = 'Withdrawal' THEN amount ELSE 0 END) as withdrawals
            FROM `tabSavings Transaction`
            WHERE account = %s 
            AND DATE(transaction_date) BETWEEN %s AND %s
            GROUP BY DATE(transaction_date)
        """, (self.name, from_date, to_date), as_dict=True)
        
        if not daily_balances:
            return 0
        
        # Calculate average daily balance
        total_balance_days = 0
        current_balance = flt(self.balance)
        
        for row in daily_balances:
            balance = current_balance - flt(row.deposits) + flt(row.withdrawals)
            total_balance_days += balance
            current_balance = balance
        
        days_in_period = (to_date - from_date).days or 1
        average_daily_balance = total_balance_days / days_in_period
        
        # Calculate interest based on method
        if product.interest_calculation_method == "Daily Balance":
            principal = average_daily_balance
        elif product.interest_calculation_method == "Monthly Balance":
            principal = flt(self.balance)
        elif product.interest_calculation_method == "Average Balance":
            principal = average_daily_balance
        else:  # Minimum Balance
            min_balance = frappe.db.sql("""
                SELECT MIN(balance) FROM `tabSavings Transaction`
                WHERE account = %s AND DATE(transaction_date) BETWEEN %s AND %s
            """, (self.name, from_date, to_date))[0][0]
            principal = flt(min_balance) if min_balance else flt(self.balance)
        
        # Interest calculation
        days_in_year = 365
        interest = (principal * flt(self.interest_rate) * days_in_period) / (100 * days_in_year)
        
        return flt(interest)
    
    def post_interest(self, interest_amount, posting_date=None):
        """
        Post calculated interest to account
        
        Args:
            interest_amount: Interest to post
            posting_date: Posting date
        """
        if not interest_amount or interest_amount <= 0:
            return
        
        product = frappe.get_doc("Savings Product", self.product)
        
        # Update account balances
        self.balance = flt(self.balance) + flt(interest_amount)
        self.available_balance = flt(self.balance)
        self.accrued_interest = 0
        self.total_interest_earned = flt(self.total_interest_earned) + flt(interest_amount)
        self.last_interest_calculation_date = posting_date or nowdate()
        
        # Update next posting date
        if product.interest_posting_frequency == "Monthly":
            self.next_interest_posting_date = add_months(getdate(posting_date), 1)
        elif product.interest_posting_frequency == "Quarterly":
            self.next_interest_posting_date = add_months(getdate(posting_date), 3)
        elif product.interest_posting_frequency == "Annually":
            self.next_interest_posting_date = add_months(getdate(posting_date), 12)
        
        self.save(ignore_permissions=True)
        
        # Create GL entry
        if product.interest_gl_account:
            from sacco_management.sacco.utils.gl_utils import create_gl_entry
            
            accounts = [
                {
                    "gl_account": product.interest_gl_account,
                    "debit": interest_amount,
                    "credit": 0,
                    "party_type": "SACCO Member",
                    "party": self.member,
                    "remarks": f"Interest expense for {self.account_name}"
                },
                {
                    "gl_account": self.default_gl_account,
                    "debit": 0,
                    "credit": interest_amount,
                    "party_type": "SACCO Member",
                    "party": self.member,
                    "remarks": f"Interest credited to {self.account_name}"
                }
            ]
            
            je = create_gl_entry(
                voucher_type="Journal Entry",
                posting_date=posting_date or nowdate(),
                accounts=accounts,
                remarks=f"Savings Interest Posting - {self.account_name}",
                reference_type="Savings Account",
                reference_name=self.name,
                branch=self.branch
            )
    
    def close_account(self, reason=None):
        """Close the savings account"""
        if flt(self.balance) != 0:
            frappe.throw(_("Cannot close account with non-zero balance. Please withdraw/transfer remaining balance."))
        
        self.status = "Closed"
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Savings Account closed successfully"), alert=True)


@frappe.whitelist()
def open_savings_account(member, product, opening_deposit=0, payment_mode=None):
    """
    Open a new savings account with optional opening deposit
    
    Args:
        member: Member ID
        product: Savings Product ID
        opening_deposit: Initial deposit amount
        payment_mode: Payment mode for opening deposit
    
    Returns:
        New Savings Account document
    """
    account = frappe.new_doc("Savings Account")
    account.member = member
    account.product = product
    account.opening_date = nowdate()
    account.insert(ignore_permissions=True)
    
    # Process opening deposit
    if flt(opening_deposit) > 0 and payment_mode:
        from sacco_management.sacco.doctype.savings_deposit.savings_deposit import create_deposit
        deposit = create_deposit(
            account=account.name,
            amount=opening_deposit,
            payment_mode=payment_mode,
            remarks="Opening deposit"
        )
    
    frappe.db.commit()
    return account.as_dict()
