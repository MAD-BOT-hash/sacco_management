# Copyright (c) 2024, SACCO Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import flt


class DividendPeriod(Document):
    def validate(self):
        self.validate_dates()
        self.calculate_dividend_pool()
        
    def validate_dates(self):
        """Validate date range"""
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                frappe.throw(_("Start Date cannot be after End Date"))
    
    def calculate_dividend_pool(self):
        """Calculate dividend pool after reserve allocations"""
        if self.opening_profit:
            # Calculate available surplus
            total_reserves = flt(self.statutory_reserve) + flt(self.general_reserve)
            self.available_surplus = flt(self.opening_profit) - total_reserves
            
            # Dividend pool is the available surplus
            self.dividend_pool = self.available_surplus
            
            # Calculate total shares eligible for dividend
            self.total_shares_for_dividend = self.get_total_eligible_shares()
            
            # Calculate total dividend required
            if self.approved_dividend_rate and self.total_shares_for_dividend:
                self.total_dividend_amount = flt(self.total_shares_for_dividend) * flt(self.approved_dividend_rate) / 100
    
    def get_total_eligible_shares(self):
        """Get total shares eligible for dividend as of period end"""
        total_shares = frappe.db.sql("""
            SELECT COALESCE(SUM(quantity), 0)
            FROM `tabShare Allocation`
            WHERE docstatus = 1 
            AND status = 'Allocated'
            AND allocation_date <= %s
        """, (self.end_date,))[0][0] or 0
        
        return flt(total_shares)
    
    def before_submit(self):
        """Set status based on approval stage"""
        if self.board_resolution_number and self.board_resolution_date:
            self.status = "Board Approved"
        
        if self.agm_approval_date and self.agm_resolution_number:
            self.status = "AGM Approved"
