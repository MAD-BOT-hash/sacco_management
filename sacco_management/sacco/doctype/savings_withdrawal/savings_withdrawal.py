# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class SavingsWithdrawal(Document):
    def validate(self):
        self.validate_account()
        self.validate_amount()
        self.validate_sufficient_balance()
        
    def validate_account(self):
        """Validate account exists and is active"""
        account_status = frappe.db.get_value("Savings Account", self.account, "status")
        if account_status != "Active":
            frappe.throw(_("Cannot withdraw from {0} account").format(account_status))
    
    def validate_amount(self):
        """Validate amount is positive"""
        if flt(self.amount) <= 0:
            frappe.throw(_("Withdrawal amount must be positive"))
    
    def validate_sufficient_balance(self):
        """Validate sufficient balance for withdrawal"""
        account = frappe.get_doc("Savings Account", self.account)
        product = frappe.get_doc("Savings Product", account.product)
        
        # Check minimum balance requirement
        available_for_withdrawal = flt(account.balance) - flt(product.min_balance)
        
        if flt(self.amount) > available_for_withdrawal:
            if not product.allow_overdraft or flt(self.amount) > (available_for_withdrawal + flt(product.overdraft_limit)):
                frappe.throw(_("Insufficient balance. Available: {}, Minimum required: {}").format(
                    account.balance, product.min_balance
                ))
        
        # Check withdrawal limits
        if product.withdrawal_limits and flt(product.max_withdrawals_per_month) > 0:
            if account.withdrawals_this_month >= flt(product.max_withdrawals_per_month):
                frappe.throw(_("Maximum withdrawals per month ({}) exceeded").format(
                    product.max_withdrawals_per_month))
        
        # Check notice period
        if flt(product.notice_period_days) > 0:
            last_withdrawal = account.last_withdrawal_date
            if last_withdrawal:
                days_since_last = (getdate(nowdate()) - getdate(last_withdrawal)).days
                if days_since_last < flt(product.notice_period_days):
                    frappe.throw(_("Notice period of {} days not met. Last withdrawal was {} days ago").format(
                        product.notice_period_days, days_since_last
                    ))
    
    def on_submit(self):
        """Process withdrawal on submit"""
        self.process_withdrawal()
    
    def on_cancel(self):
        """Reverse withdrawal on cancel"""
        self.reverse_withdrawal()
    
    def process_withdrawal(self):
        """Process the savings withdrawal"""
        account = frappe.get_doc("Savings Account", self.account)
        
        # Set balance before withdrawal
        self.balance_before_withdrawal = flt(account.balance)
        
        # Calculate penalty if applicable
        product = frappe.get_doc("Savings Product", account.product)
        self.penalty_applied = 0
        
        if product.penalty_for_below_min_balance:
            new_balance = flt(account.balance) - flt(self.amount)
            if new_balance < flt(product.min_balance):
                self.penalty_applied = flt(product.penalty_amount)
        
        # Calculate net amount
        self.net_amount_paid = flt(self.amount) - flt(self.penalty_applied)
        
        # Update account balance
        account.update_balance(
            amount=self.amount,
            transaction_type="Withdrawal"
        )
        
        # Apply penalty if any
        if self.penalty_applied > 0:
            account.balance = flt(account.balance) - flt(self.penalty_applied)
            account.save(ignore_permissions=True)
            
            # Post penalty to GL separately
            self.post_penalty_to_gl(account, product)
        
        # Set balance after withdrawal
        self.balance_after_withdrawal = flt(account.balance)
        
        # Set approval details
        self.approved_by = frappe.session.user
        self.approval_date = nowdate()
        
        # Post to GL
        self.post_to_gl(account, product)
        
        self.status = "Paid"
        self.save(ignore_permissions=True)
        
        frappe.msgprint(_("Withdrawal of {} processed successfully").format(self.net_amount_paid), alert=True)
    
    def reverse_withdrawal(self):
        """Reverse the withdrawal"""
        if self.status != "Paid":
            frappe.throw(_("Can only reverse paid withdrawals"))
        
        account = frappe.get_doc("Savings Account", self.account)
        
        # Reverse the balance update
        account.balance = flt(account.balance) + flt(self.amount)
        account.available_balance = flt(account.balance)
        account.total_withdrawal = flt(account.total_withdrawal) - flt(self.amount)
        
        # Reverse penalty if applied
        if self.penalty_applied > 0:
            account.balance = flt(account.balance) + flt(self.penalty_applied)
        
        account.save(ignore_permissions=True)
        
        # Reverse GL entries
        if self.gl_posted and self.journal_entry:
            from sacco_management.sacco.utils.gl_utils import reverse_gl_entry
            reverse_gl_entry("Savings Withdrawal", self.name)
        
        self.status = "Cancelled"
        self.save(ignore_permissions=True)
    
    def post_to_gl(self, account, product):
        """Post withdrawal to General Ledger"""
        payment_account = frappe.db.get_value("Payment Mode", self.payment_mode, "gl_account")
        
        if not payment_account:
            frappe.throw(_("Payment Mode GL Account not configured"))
        
        from sacco_management.sacco.utils.gl_utils import create_gl_entry
        
        accounts = [
            {
                "gl_account": product.default_gl_account,
                "debit": self.amount,
                "credit": 0,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Withdrawal from {account.account_name}"
            },
            {
                "gl_account": payment_account,
                "debit": 0,
                "credit": self.net_amount_paid,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Savings Withdrawal - {account.account_name}"
            }
        ]
        
        # Add penalty income account if penalty applied
        if self.penalty_applied > 0 and product.penalty_gl_account:
            accounts.append({
                "gl_account": product.penalty_gl_account,
                "debit": 0,
                "credit": self.penalty_applied,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Penalty for below minimum balance"
            })
        
        je = create_gl_entry(
            voucher_type="Payment Voucher",
            posting_date=self.withdrawal_date,
            accounts=accounts,
            remarks=f"Savings Withdrawal: {account.account_name} - {self.member_name}",
            reference_type="Savings Withdrawal",
            reference_name=self.name,
            branch=self.branch
        )
        
        self.journal_entry = je.name
        self.gl_posted = 1
    
    def post_penalty_to_gl(self, account, product):
        """Post penalty to GL"""
        if not product.penalty_gl_account:
            return
        
        from sacco_management.sacco.utils.gl_utils import create_gl_entry
        
        accounts = [
            {
                "gl_account": product.default_gl_account,
                "debit": self.penalty_applied,
                "credit": 0,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Penalty debit from {account.account_name}"
            },
            {
                "gl_account": product.penalty_gl_account,
                "debit": 0,
                "credit": self.penalty_applied,
                "party_type": "SACCO Member",
                "party": self.member,
                "remarks": f"Penalty for below minimum balance"
            }
        ]
        
        create_gl_entry(
            voucher_type="Journal Entry",
            posting_date=self.withdrawal_date,
            accounts=accounts,
            remarks=f"Penalty Applied: {account.account_name} - {self.member_name}",
            reference_type="Savings Withdrawal",
            reference_name=self.name,
            branch=self.branch
        )


@frappe.whitelist()
def create_withdrawal(account, amount, payment_mode, reference_number=None, remarks=None):
    """
    Create a savings withdrawal
    
    Args:
        account: Savings Account ID
        amount: Withdrawal amount
        payment_mode: Payment mode
        reference_number: Reference number
        remarks: Remarks
    
    Returns:
        Created Savings Withdrawal document
    """
    doc = frappe.new_doc("Savings Withdrawal")
    doc.account = account
    doc.amount = flt(amount)
    doc.payment_mode = payment_mode
    doc.reference_number = reference_number
    doc.remarks = remarks
    doc.withdrawal_date = nowdate()
    
    doc.insert(ignore_permissions=True)
    doc.submit()
    
    frappe.db.commit()
    return doc.as_dict()
