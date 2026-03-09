# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, getdate, nowdate


class SavingsInterestRule(Document):
    def validate(self):
        self.validate_dates()
        self.validate_interest_rates()
        self.validate_thresholds()
        
    def validate_dates(self):
        """Validate date range"""
        if self.valid_from and self.valid_to:
            if getdate(self.valid_from) > getdate(self.valid_to):
                frappe.throw(_("Valid From date cannot be after Valid To date"))
    
    def validate_interest_rates(self):
        """Validate interest rates are positive"""
        if flt(self.special_interest_rate) < 0:
            frappe.throw(_("Special Interest Rate cannot be negative"))
        
        if self.bonus_interest_applicable and flt(self.bonus_interest_rate) < 0:
            frappe.throw(_("Bonus Interest Rate cannot be negative"))
    
    def validate_thresholds(self):
        """Validate balance thresholds"""
        if (flt(self.min_balance_threshold) > flt(self.max_balance_threshold) and 
            flt(self.max_balance_threshold) > 0):
            frappe.throw(_("Minimum balance threshold cannot exceed maximum balance threshold"))
    
    def is_applicable(self, account):
        """
        Check if this rule is applicable to given account
        
        Args:
            account: Savings Account object or name
        
        Returns:
            Boolean
        """
        if not self.is_active:
            return False
        
        # Get account object if string passed
        if isinstance(account, str):
            account = frappe.get_doc("Savings Account", account)
        
        # Check product match
        if self.product != account.product:
            return False
        
        # Check validity period
        today = getdate(nowdate())
        if self.valid_from and today < getdate(self.valid_from):
            return False
        if self.valid_to and today > getdate(self.valid_to):
            return False
        
        # Check balance thresholds
        if flt(self.min_balance_threshold) > 0 and flt(account.balance) < flt(self.min_balance_threshold):
            return False
        
        if flt(self.max_balance_threshold) > 0 and flt(account.balance) > flt(self.max_balance_threshold):
            return False
        
        # Check account age
        if flt(self.min_account_age_days) > 0:
            account_age = (today - getdate(account.opening_date)).days
            if account_age < flt(self.min_account_age_days):
                return False
        
        # Check member type eligibility
        if self.member_type_eligible and self.member_type_eligible != "All":
            member = frappe.get_doc("SACCO Member", account.member)
            
            if self.member_type_eligible == "Active Only" and member.status != "Active":
                return False
            elif self.member_type_eligible == "Senior Members":
                # Assuming age > 60 is senior
                dob = member.date_of_birth
                if dob:
                    age = (today - getdate(dob)).days / 365
                    if age < 60:
                        return False
            elif self.member_type_eligible == "Youth Members":
                dob = member.date_of_birth
                if dob:
                    age = (today - getdate(dob)).days / 365
                    if age > 35:
                        return False
        
        # Check applicable days
        if self.applicable_days:
            days_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6
            }
            applicable_day_list = [d.strip().lower() for d in self.applicable_days.split(',')]
            current_weekday = today.weekday()
            
            is_applicable_day = False
            for day_name in applicable_day_list:
                if day_name in days_map and days_map[day_name] == current_weekday:
                    is_applicable_day = True
                    break
            
            if not is_applicable_day:
                return False
        
        return True
    
    def calculate_interest(self, account, from_date=None, to_date=None):
        """
        Calculate interest for the account based on this rule
        
        Args:
            account: Savings Account object or name
            from_date: Start date
            to_date: End date
        
        Returns:
            Calculated interest amount
        """
        if isinstance(account, str):
            account = frappe.get_doc("Savings Account", account)
        
        if not self.is_applicable(account):
            return 0
        
        # Determine interest rate to use
        interest_rate = flt(self.special_interest_rate) if flt(self.special_interest_rate) > 0 else flt(account.interest_rate)
        
        if interest_rate <= 0:
            return 0
        
        # Get calculation method
        method = self.interest_calculation_method or account.interest_calculation_method or "Daily Balance"
        
        # Get dates
        from_date = getdate(from_date) or getdate(account.last_interest_calculation_date) or getdate(account.opening_date)
        to_date = getdate(to_date) or nowdate()
        days_in_period = (to_date - from_date).days or 1
        
        # Calculate principal based on method
        if method == "Daily Balance":
            principal = self.get_daily_average_balance(account, from_date, to_date)
        elif method == "Monthly Balance":
            principal = flt(account.balance)
        elif method == "Average Balance":
            principal = self.get_daily_average_balance(account, from_date, to_date)
        elif method == "Minimum Balance":
            principal = self.get_minimum_balance(account, from_date, to_date)
        else:
            principal = flt(account.balance)
        
        # Check minimum balance for interest
        product = frappe.get_doc("Savings Product", account.product)
        if flt(product.min_balance_for_interest) > 0 and principal < flt(product.min_balance_for_interest):
            return 0
        
        # Base interest calculation
        days_in_year = 365
        base_interest = (principal * interest_rate * days_in_period) / (100 * days_in_year)
        
        # Apply compounding if applicable
        if self.compounding_frequency or product.interest_compounding_frequency:
            frequency = self.compounding_frequency or product.interest_compounding_frequency
            base_interest = self.apply_compounding(base_interest, frequency, days_in_period)
        
        # Add bonus interest if applicable
        total_interest = base_interest
        if self.bonus_interest_applicable and self.check_bonus_condition(account):
            bonus_interest = (principal * flt(self.bonus_interest_rate) * days_in_period) / (100 * days_in_year)
            total_interest += bonus_interest
        
        return flt(total_interest)
    
    def get_daily_average_balance(self, account, from_date, to_date):
        """Calculate daily average balance for period"""
        transactions = frappe.db.sql("""
            SELECT 
                DATE(transaction_date) as trans_date,
                SUM(CASE WHEN transaction_type IN ('Deposit', 'Interest Credit', 'Transfer In') THEN amount ELSE 0 END) as inflows,
                SUM(CASE WHEN transaction_type IN ('Withdrawal', 'Penalty Debit', 'Transfer Out') THEN amount ELSE 0 END) as outflows
            FROM `tabSavings Transaction`
            WHERE account = %s 
            AND DATE(transaction_date) BETWEEN %s AND %s
            GROUP BY DATE(transaction_date)
            ORDER BY trans_date
        """, (account.name, from_date, to_date), as_dict=True)
        
        if not transactions:
            return flt(account.balance)
        
        total_balance_days = 0
        running_balance = flt(account.balance)
        
        for row in transactions:
            balance = running_balance - flt(row.inflows) + flt(row.outflows)
            total_balance_days += balance
            running_balance = balance
        
        days_in_period = (to_date - from_date).days or 1
        return total_balance_days / days_in_period
    
    def get_minimum_balance(self, account, from_date, to_date):
        """Get minimum balance during the period"""
        min_balance = frappe.db.sql("""
            SELECT MIN(balance_after_transaction)
            FROM `tabSavings Transaction`
            WHERE account = %s 
            AND DATE(transaction_date) BETWEEN %s AND %s
        """, (account.name, from_date, to_date))[0][0]
        
        return flt(min_balance) if min_balance else flt(account.balance)
    
    def apply_compounding(self, interest, frequency, days):
        """Apply compounding to interest"""
        if frequency == "Daily":
            compounding_periods = days
        elif frequency == "Monthly":
            compounding_periods = days / 30
        elif frequency == "Quarterly":
            compounding_periods = days / 90
        elif frequency == "Annually":
            compounding_periods = days / 365
        else:
            compounding_periods = 1
        
        # Simple compounding adjustment
        if compounding_periods > 1:
            return interest * (1 + (1 / compounding_periods)) ** compounding_periods - interest
        
        return interest
    
    def check_bonus_condition(self, account):
        """Check if bonus condition is met"""
        if not self.bonus_condition:
            return True
        
        condition = self.bonus_condition.lower()
        
        # Example: "no withdrawal for 6 months"
        if "no withdrawal" in condition:
            # Extract months
            import re
            match = re.search(r'(\d+)\s*month', condition)
            if match:
                months = int(match.group(1))
                last_withdrawal = account.last_withdrawal_date
                
                if not last_withdrawal:
                    return True
                
                from frappe.utils import date_diff
                days_since_withdrawal = date_diff(nowdate(), last_withdrawal)
                
                return days_since_withdrawal >= (months * 30)
        
        return True


@frappe.whitelist()
def get_applicable_rules(account):
    """Get all applicable interest rules for an account"""
    account_doc = frappe.get_doc("Savings Account", account)
    rules = frappe.get_all("Savings Interest Rule", 
        filters={"is_active": 1},
        fields=["name", "rule_name", "special_interest_rate", "priority"],
        order_by="priority ASC")
    
    applicable_rules = []
    for rule_data in rules:
        rule = frappe.get_doc("Savings Interest Rule", rule_data.name)
        if rule.is_applicable(account_doc):
            applicable_rules.append({
                "rule_name": rule.rule_name,
                "special_interest_rate": rule.special_interest_rate,
                "bonus_interest_rate": rule.bonus_interest_rate if rule.bonus_interest_applicable else 0,
                "priority": rule.priority
            })
    
    return applicable_rules
