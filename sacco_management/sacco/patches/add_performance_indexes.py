"""
Database Performance Migration

This script adds recommended indexes to improve query performance.
Run this during maintenance window as it may lock tables briefly.

Usage:
    bench execute sacco_management.sacco.patches.add_performance_indexes
"""

import frappe
from frappe import _


def get_existing_indexes(doctype):
    """Get existing indexes for a doctype"""
    table_name = f"`tab{doctype}`"
    indexes = frappe.db.sql(f"SHOW INDEX FROM {table_name}", as_dict=True)
    
    index_map = {}
    for idx in indexes:
        if idx.Key_name not in index_map:
            index_map[idx.Key_name] = {
                "columns": [],
                "unique": idx.Non_unique == 0,
                "primary": idx.Key_name == "PRIMARY"
            }
        index_map[idx.Key_name]["columns"].append(idx.Column_name)
    
    return index_map


def add_index_if_missing(doctype, fieldname, unique=False):
    """
    Add index if it doesn't exist
    
    Args:
        doctype (str): Document type
        fieldname (str): Field to index
        unique (bool): Whether index should be unique
    
    Returns:
        bool: True if index was added, False if already exists
    """
    table_name = f"`tab{doctype}`"
    index_name = f"idx_{fieldname}"
    
    # Check if index exists
    existing_indexes = get_existing_indexes(doctype)
    
    # Check if field is already indexed
    for idx_name, idx_info in existing_indexes.items():
        if fieldname in idx_info["columns"]:
            print(f"✓ Index on {fieldname} already exists ({idx_name})")
            return False
    
    try:
        # Create index
        unique_str = "UNIQUE " if unique else ""
        sql = f"ALTER TABLE {table_name} ADD {unique_str}INDEX {index_name} ({fieldname})"
        frappe.db.sql(sql)
        
        print(f"✓ Added index: {index_name} on {doctype}.{fieldname}")
        return True
        
    except Exception as e:
        frappe.log_error(f"Failed to add index {index_name} on {doctype}.{fieldname}: {str(e)}")
        return False


def add_composite_index(doctype, fields, index_name=None):
    """
    Add composite index on multiple fields
    
    Args:
        doctype (str): Document type
        fields (list): List of fields to index
        index_name (str): Optional custom index name
    
    Returns:
        bool: True if index was added
    """
    table_name = f"`tab{doctype}`"
    
    if not index_name:
        index_name = "idx_" + "_".join(fields)
    
    try:
        fields_str = ", ".join(fields)
        sql = f"ALTER TABLE {table_name} ADD INDEX {index_name} ({fields_str})"
        frappe.db.sql(sql)
        
        print(f"✓ Added composite index: {index_name} on {doctype}.({', '.join(fields)})")
        return True
        
    except Exception as e:
        frappe.log_error(f"Failed to add composite index {index_name} on {doctype}: {str(e)}")
        return False


def execute():
    """Main execution function"""
    
    frappe.db.auto_commit_on_many_writes = 1
    
    indexes_added = []
    indexes_skipped = []
    errors = []
    
    # Define recommended indexes
    recommended_indexes = [
        # SACCO Member
        {"doctype": "SACCO Member", "field": "email"},
        {"doctype": "SACCO Member", "field": "membership_status"},
        {"doctype": "SACCO Member", "field": "branch"},
        {"doctype": "SACCO Member", "field": "joining_date"},
        {"doctype": "SACCO Member", "field": "employer_name"},
        
        # Loan Application
        {"doctype": "Loan Application", "field": "member"},
        {"doctype": "Loan Application", "field": "status"},
        {"doctype": "Loan Application", "field": "application_date"},
        {"doctype": "Loan Application", "field": "loan_type"},
        {"doctype": "Loan Application", "field": "disbursement_date"},
        
        # Savings Account
        {"doctype": "Savings Account", "field": "member"},
        {"doctype": "Savings Account", "field": "status"},
        {"doctype": "Savings Account", "field": "account_type"},
        
        # Share Allocation
        {"doctype": "Share Allocation", "field": "member"},
        {"doctype": "Share Allocation", "field": "share_type"},
        {"doctype": "Share Allocation", "field": "allocation_date"},
        
        # Member Contribution
        {"doctype": "Member Contribution", "field": "member"},
        {"doctype": "Member Contribution", "field": "posting_date"},
        {"doctype": "Member Contribution", "field": "contribution_type"},
        
        # Dividend Declaration
        {"doctype": "Dividend Declaration", "field": "declaration_date"},
        {"doctype": "Dividend Declaration", "field": "fiscal_year"},
        
        # Meeting Register
        {"doctype": "Meeting Register", "field": "meeting"},
        {"doctype": "Meeting Register", "field": "member"},
        {"doctype": "Meeting Register", "field": "attendance_status"},
        
        # SACCO GL Entry
        {"doctype": "SACCO GL Entry", "field": "posting_date"},
        {"doctype": "SACCO GL Entry", "field": "account"},
        {"doctype": "SACCO GL Entry", "field": "voucher_no"},
    ]
    
    # Add single-field indexes
    print("\n" + "="*60)
    print("Adding Performance Indexes")
    print("="*60)
    
    for rec in recommended_indexes:
        try:
            result = add_index_if_missing(
                rec["doctype"],
                rec["field"],
                rec.get("unique", False)
            )
            
            if result:
                indexes_added.append(f"{rec['doctype']}.{rec['field']}")
            else:
                indexes_skipped.append(f"{rec['doctype']}.{rec['field']}")
                
        except Exception as e:
            error_msg = f"Error adding index on {rec['doctype']}.{rec['field']}: {str(e)}"
            errors.append(error_msg)
            frappe.log_error(error_msg)
    
    # Add composite indexes
    composite_indexes = [
        {"doctype": "Loan Application", "fields": ["member", "status"]},
        {"doctype": "Loan Application", "fields": ["status", "disbursement_date"]},
        {"doctype": "Savings Account", "fields": ["member", "status"]},
        {"doctype": "Share Allocation", "fields": ["member", "status"]},
        {"doctype": "Member Contribution", "fields": ["member", "posting_date"]},
        {"doctype": "SACCO GL Entry", "fields": ["posting_date", "account"]},
    ]
    
    print("\nAdding Composite Indexes:")
    for comp in composite_indexes:
        try:
            index_name = f"idx_{'_'.join(comp['fields'])}"
            result = add_composite_index(
                comp["doctype"],
                comp["fields"],
                index_name
            )
            
            if result:
                indexes_added.append(f"{comp['doctype']}.({' ,'.join(comp['fields'])})")
                
        except Exception as e:
            error_msg = f"Error adding composite index on {comp['doctype']}: {str(e)}"
            errors.append(error_msg)
            frappe.log_error(error_msg)
    
    # Print summary
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    print(f"Indexes Added: {len(indexes_added)}")
    print(f"Indexes Skipped (already exist): {len(indexes_skipped)}")
    print(f"Errors: {len(errors)}")
    
    if indexes_added:
        print("\nNew Indexes:")
        for idx in indexes_added:
            print(f"  - {idx}")
    
    if errors:
        print("\nErrors:")
        for err in errors:
            print(f"  - {err}")
    
    # Commit changes
    frappe.db.commit()
    
    print("\n✓ Database optimization completed!")
    print("="*60 + "\n")
    
    return {
        "indexes_added": len(indexes_added),
        "indexes_skipped": len(indexes_skipped),
        "errors": len(errors)
    }


if __name__ == "__main__":
    execute()
