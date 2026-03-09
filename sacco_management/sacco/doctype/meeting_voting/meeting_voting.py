# Copyright (c) 2024, SACCO Developer and contributors
# For license information, see license.txt

import frappe
from frappe.model.document import Document


class MeetingVoting(Document):
	"""Child table for recording member votes in meetings"""
	
	def validate(self):
		"""Validate voting data"""
		self.validate_member()
		self.validate_vote_type()
	
	def validate_member(self):
		"""Validate that member exists and is active"""
		if not self.member:
			frappe.throw(f"Row {self.idx}: Member is required")
		
		# Check if member exists
		if not frappe.db.exists("SACCO Member", self.member):
			frappe.throw(f"Row {self.idx}: Member {self.member} does not exist")
	
	def validate_vote_type(self):
		"""Validate vote type is selected"""
		if not self.vote_type:
			frappe.throw(f"Row {self.idx}: Please select a vote type (In Favor/Against/Abstained)")

