# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt, date_diff, getdate


class DividendCalculation(Document):
    def validate(self):
        self.calculate_eligible_shares()
        self.calculate_dividend()
        
    def calculate_eligible_shares(self):
        """Calculate eligible shares for the dividend period"""
        if not self.dividend_period:
            return
        
        period = frappe.get_doc("Dividend Period", self.dividend_period)
        
        # Get shares held by member as of period end date
        shares_data = frappe.db.sql("""
            SELECT 
                sa.share_type,
                SUM(sa.quantity) as total_shares,
                MIN(sa.allocation_date) as first_allocation
            FROM `tabShare Allocation` sa
            WHERE sa.member = %s 
            AND sa.docstatus = 1 
            AND sa.status = 'Allocated'
            AND sa.allocation_date <= %s
            GROUP BY sa.share_type
        """, (self.member, period.end_date), as_dict=True)
        
        if shares_data:
            self.eligible_shares = flt(shares_data[0].total_shares)
            self.share_type = shares_data[0].share_type
            
            # Calculate days held
            if shares_data[0].first_allocation:
                self.days_held = date_diff(period.end_date, shares_data[0].first_allocation)
        
        # Set dividend rate from period
        self.dividend_rate = period.approved_dividend_rate or period.recommended_dividend_rate
    
    def calculate_dividend(self):
        """Calculate gross and net dividend"""
        if self.eligible_shares and self.dividend_rate:
            # Gross dividend = Shares × Dividend Rate
            self.gross_dividend = flt(self.eligible_shares) * flt(self.dividend_rate) / 100
            
            # Calculate withholding tax
            if self.withholding_tax_rate:
                self.withholding_tax_amount = flt(self.gross_dividend) * flt(self.withholding_tax_rate) / 100
            
            # Net dividend payable
            self.net_dividend_payable = flt(self.gross_dividend) - flt(self.withholding_tax_amount)
    
    def before_submit(self):
        """Set status to calculated"""
        self.status = "Calculated"
    
    def on_submit(self):
        """Create dividend ledger entry"""
        self.create_dividend_ledger()
    
    def create_dividend_ledger(self):
        """Create entry in dividend ledger"""
        ledger = frappe.get_doc({
            "doctype": "Dividend Ledger",
            "dividend_period": self.dividend_period,
            "member": self.member,
            "dividend_calculation": self.name,
            "transaction_date": self.calculation_date,
            "gross_dividend": self.gross_dividend,
            "withholding_tax": self.withholding_tax_amount,
            "net_dividend": self.net_dividend_payable,
            "remarks": f"Dividend calculation for {self.dividend_period}"
        })
        
        ledger.insert(ignore_permissions=True)
        ledger.submit()
