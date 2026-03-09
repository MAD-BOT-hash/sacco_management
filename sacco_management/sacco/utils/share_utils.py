"""
Share Capital Utilities for SACCO Management System

This module provides utility functions for share capital management:
- Share purchase processing
- Share redemption calculations
- Dividend calculations
- Share ledger maintenance
- Member share balance updates

"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, date_diff


def get_member_shares(member_name, as_of_date=None):
    """
    Get total shares held by a member
    
    Args:
        member_name: Member ID
        as_of_date: Date to calculate shares (default: today)
    
    Returns:
        dict with share breakdown by type
    """
    if not as_of_date:
        as_of_date = nowdate()
    
    shares = frappe.db.sql("""
        SELECT 
            sa.share_type,
            st.share_name as share_type_name,
            SUM(sa.quantity) as total_quantity,
            SUM(sa.total_amount) as total_value
        FROM `tabShare Allocation` sa
        INNER JOIN `tabShare Type` st ON sa.share_type = st.name
        WHERE sa.member = %s 
        AND sa.docstatus = 1
        AND sa.status = 'Allocated'
        AND sa.allocation_date <= %s
        GROUP BY sa.share_type, st.share_name
    """, (member_name, as_of_date), as_dict=True)
    
    total_shares = sum([flt(s.total_quantity) for s in shares])
    total_value = sum([flt(s.total_value) for s in shares])
    
    return {
        "shares_by_type": shares,
        "total_shares": flt(total_shares),
        "total_value": flt(total_value),
        "as_of_date": as_of_date
    }


def calculate_dividend_for_member(member_name, dividend_period, shares=None):
    """
    Calculate dividend entitlement for a member
    
    Args:
        member_name: Member ID
        dividend_period: Dividend Period document name
        shares: Optional pre-calculated shares data
    
    Returns:
        dict with dividend calculation details
    """
    period = frappe.get_doc("Dividend Period", dividend_period)
    
    # Get member shares if not provided
    if not shares:
        shares = get_member_shares(member_name, period.end_date)
    
    dividend_rate = period.approved_dividend_rate or period.recommended_dividend_rate
    
    # Calculate gross dividend
    gross_dividend = flt(shares['total_shares']) * flt(dividend_rate) / 100
    
    # Calculate withholding tax
    withholding_tax_rate = period.get("withholding_tax_rate", 0)
    withholding_tax = flt(gross_dividend) * flt(withholding_tax_rate) / 100
    
    # Net dividend
    net_dividend = flt(gross_dividend) - flt(withholding_tax)
    
    return {
        "member": member_name,
        "dividend_period": dividend_period,
        "eligible_shares": shares['total_shares'],
        "dividend_rate": dividend_rate,
        "gross_dividend": flt(gross_dividend, 2),
        "withholding_tax_rate": withholding_tax_rate,
        "withholding_tax": flt(withholding_tax, 2),
        "net_dividend": flt(net_dividend, 2),
        "calculation_date": nowdate()
    }


def process_bulk_dividend_calculation(dividend_period):
    """
    Process dividend calculation for all eligible members
    
    Args:
        dividend_period: Dividend Period document name
    
    Returns:
        dict with processing statistics
    """
    period = frappe.get_doc("Dividend Period", dividend_period)
    
    # Get all members with shares
    members_with_shares = frappe.db.sql("""
        SELECT DISTINCT sa.member
        FROM `tabShare Allocation` sa
        WHERE sa.docstatus = 1
        AND sa.status = 'Allocated'
        AND sa.allocation_date <= %s
    """, (period.end_date,), as_dict=True)
    
    stats = {
        "processed": 0,
        "total_gross_dividend": 0,
        "total_net_dividend": 0,
        "errors": []
    }
    
    for member_data in members_with_shares:
        try:
            # Check if already calculated
            existing = frappe.db.exists("Dividend Calculation", {
                "dividend_period": dividend_period,
                "member": member_data.member,
                "docstatus": 1
            })
            
            if not existing:
                # Calculate dividend
                calc_data = calculate_dividend_for_member(member_data.member, dividend_period)
                
                # Create dividend calculation document
                calc = frappe.get_doc({
                    "doctype": "Dividend Calculation",
                    "dividend_period": dividend_period,
                    "member": member_data.member,
                    "calculation_date": nowdate(),
                    "eligible_shares": calc_data["eligible_shares"],
                    "dividend_rate": calc_data["dividend_rate"],
                    "gross_dividend": calc_data["gross_dividend"],
                    "withholding_tax_rate": calc_data["withholding_tax_rate"],
                    "withholding_tax_amount": calc_data["withholding_tax"],
                    "net_dividend_payable": calc_data["net_dividend"]
                })
                
                calc.insert(ignore_permissions=True)
                calc.submit()
                
                stats["processed"] += 1
                stats["total_gross_dividend"] += calc_data["gross_dividend"]
                stats["total_net_dividend"] += calc_data["net_dividend"]
                
        except Exception as e:
            stats["errors"].append(f"{member_data.member}: {str(e)}")
            frappe.log_error(
                message=f"Error calculating dividend for {member_data.member}: {str(e)}",
                title="Dividend Calculation Error"
            )
    
    # Update period totals
    frappe.db.set_value("Dividend Period", dividend_period, "total_shares_for_dividend", 
                       flt(period.total_shares_for_dividend))
    frappe.db.set_value("Dividend Period", dividend_period, "total_dividend_amount",
                       flt(stats["total_net_dividend"]))
    
    return stats


def create_share_ledger_entry(member, share_type, quantity_change, transaction_type, 
                             reference_doctype, reference_document, remarks=None):
    """
    Create entry in share ledger
    
    Args:
        member: Member ID
        share_type: Share Type
        quantity_change: Change in shares (+ve for increase, -ve for decrease)
        transaction_type: Type of transaction (Purchase/Redemption/etc.)
        reference_doctype: Source document type
        reference_document: Source document name
        remarks: Optional remarks
    
    Returns:
        Created Share Ledger document name
    """
    try:
        # Get price per share
        price_per_share = frappe.db.get_value("Share Type", share_type, "price_per_share")
        
        ledger = frappe.get_doc({
            "doctype": "Share Ledger",
            "member": member,
            "share_type": share_type,
            "transaction_date": nowdate(),
            "transaction_type": transaction_type,
            "quantity_change": quantity_change,
            "reference_doctype": reference_doctype,
            "reference_document": reference_document,
            "price_per_share": price_per_share or 0,
            "total_amount": flt(quantity_change) * flt(price_per_share or 0),
            "remarks": remarks or f"{transaction_type} transaction"
        })
        
        ledger.insert(ignore_permissions=True)
        ledger.submit()
        
        return ledger.name
        
    except Exception as e:
        frappe.log_error(
            message=f"Error creating share ledger entry: {str(e)}",
            title="Share Ledger Error"
        )
        raise


def get_eligible_shares_for_redemption(member_name, share_type=None):
    """
    Get shares eligible for redemption
    
    Args:
        member_name: Member ID
        share_type: Optional specific share type
    
    Returns:
        list of eligible shares with quantities
    """
    filters = {
        "member": member_name,
        "docstatus": 1,
        "status": "Allocated"
    }
    
    if share_type:
        filters["share_type"] = share_type
    
    shares = frappe.get_all("Share Allocation",
                           filters=filters,
                           fields=["share_type", "SUM(quantity) as quantity"],
                           group_by="share_type")
    
    # Subtract any pending redemptions
    for share in shares:
        pending = frappe.db.sql("""
            SELECT COALESCE(SUM(quantity_requested), 0)
            FROM `tabShare Redemption`
            WHERE member = %s 
            AND share_type = %s
            AND docstatus = 1
            AND status IN ('Pending Approval', 'Approved')
        """, (member_name, share.share_type))[0][0] or 0
        
        share.eligible_quantity = flt(share.quantity) - flt(pending)
    
    return shares


def update_member_total_shares(member_name):
    """
    Recalculate and update member's total shares
    
    Args:
        member_name: Member ID
    
    Returns:
        Updated total shares count
    """
    total = frappe.db.sql("""
        SELECT COALESCE(SUM(quantity), 0)
        FROM `tabShare Allocation`
        WHERE member = %s 
        AND docstatus = 1
        AND status = 'Allocated'
    """, (member_name,))[0][0] or 0
    
    member = frappe.get_doc("SACCO Member", member_name)
    member.total_shares = flt(total)
    member.save(ignore_permissions=True)
    
    return flt(total)
