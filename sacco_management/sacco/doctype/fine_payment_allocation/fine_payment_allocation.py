# Copyright (c) 2024, SACCO Developer and contributors
# For license information, see license.txt

import frappe
from frappe.model.document import Document


class FinePaymentAllocation(Document):
	"""Child table for Fine Payment allocations to individual fines"""
	
	def validate(self):
		"""Validate allocation data"""
		self.validate_amount()
		self.calculate_outstanding()
	
	def validate_amount(self):
		"""Validate that amount paid is not negative"""
		if self.amount_paid < 0:
			frappe.throw(f"Row {self.idx}: Amount paid cannot be negative")
	
	def calculate_outstanding(self):
		"""Calculate outstanding amount"""
		if self.fine_reference:
			fine = frappe.get_doc("Member Fine", self.fine_reference)
			self.outstanding_amount = fine.amount - self.amount_paid

