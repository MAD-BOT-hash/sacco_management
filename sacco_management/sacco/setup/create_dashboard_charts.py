"""
Dashboard Chart Installation Script

This script properly installs dashboard charts avoiding the 'name' field issue.
"""

import frappe


def create_performance_metrics_chart():
    """Create System Performance Metrics dashboard chart"""
    
    chart_data = {
        "doctype": "Dashboard Chart",
        "chart_name": "System Performance Metrics",
        "chart_type": "Custom",
        "document_type": "SACCO Member",
        "dynamic_filters_json": "[]",
        "filters_json": '[["SACCO Member","membership_status","=","Active",false]]',
        "group_by_type": "Count",
        "is_public": 1,
        "is_standard": 1,
        "module": "SACCO",
        "number_of_groups": 0,
        "timeseries": 1,
        "timespan": "Last Year",
        "time_interval": "Monthly",
        "value_based_on": "",
        "y_axis": [{"color": "green", "label": "New Members"}]
    }
    
    try:
        # Check if already exists
        existing = frappe.db.exists("Dashboard Chart", {"chart_name": "System Performance Metrics"})
        
        if existing:
            print(f"✅ Dashboard Chart 'System Performance Metrics' already exists")
            return None
        
        # Create new chart
        doc = frappe.get_doc(chart_data)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        print(f"✅ Created Dashboard Chart: System Performance Metrics")
        return doc.name
        
    except Exception as e:
        frappe.log_error(f"Error creating dashboard chart: {str(e)}", "Dashboard Chart Creation")
        print(f"❌ Error creating dashboard chart: {str(e)}")
        return None


def install_all_dashboard_charts():
    """Install all dashboard charts for the SACCO system"""
    
    charts = [
        {
            "chart_name": "Member Growth",
            "chart_type": "Standard",
            "document_type": "SACCO Member",
            "based_on": "creation",
            "value_based_on": "",
            "filters_json": '[["SACCO Member","docstatus","=",1,false]]',
            "timeseries": 1,
            "timespan": "Last Year",
            "time_interval": "Monthly",
            "group_by_type": "Count",
            "is_public": 1,
            "is_standard": 1,
            "module": "SACCO"
        },
        {
            "chart_name": "Loan Disbursement Trend",
            "chart_type": "Standard",
            "document_type": "Loan Application",
            "based_on": "disbursement_date",
            "value_based_on": "amount_approved",
            "filters_json": '[["Loan Application","status","=","Disbursed",false]]',
            "timeseries": 1,
            "timespan": "Last Year",
            "time_interval": "Monthly",
            "group_by_type": "Sum",
            "is_public": 1,
            "is_standard": 1,
            "module": "SACCO"
        },
        {
            "chart_name": "Savings Growth",
            "chart_type": "Standard",
            "document_type": "Savings Account",
            "based_on": "creation",
            "value_based_on": "current_balance",
            "filters_json": '[["Savings Account","status","=","Active",false],["Savings Account","docstatus","=",1,false]]',
            "timeseries": 1,
            "timespan": "Last Year",
            "time_interval": "Monthly",
            "group_by_type": "Sum",
            "is_public": 1,
            "is_standard": 1,
            "module": "SACCO"
        },
        {
            "chart_name": "Share Capital Growth",
            "chart_type": "Standard",
            "document_type": "Share Allocation",
            "based_on": "allocation_date",
            "value_based_on": "total_amount",
            "filters_json": '[["Share Allocation","status","=","Allocated",false],["Share Allocation","docstatus","=",1,false]]',
            "timeseries": 1,
            "timespan": "Last Year",
            "time_interval": "Monthly",
            "group_by_type": "Sum",
            "is_public": 1,
            "is_standard": 1,
            "module": "SACCO"
        }
    ]
    
    created = []
    errors = []
    
    for chart_data in charts:
        try:
            # Check if already exists
            existing = frappe.db.exists("Dashboard Chart", {"chart_name": chart_data["chart_name"]})
            
            if existing:
                print(f"✅ Dashboard Chart '{chart_data['chart_name']}' already exists")
                continue
            
            # Create new chart
            doc = frappe.get_doc(chart_data)
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            
            created.append(chart_data["chart_name"])
            print(f"✅ Created Dashboard Chart: {chart_data['chart_name']}")
            
        except Exception as e:
            error_msg = f"Error creating {chart_data['chart_name']}: {str(e)}"
            errors.append(error_msg)
            frappe.log_error(error_msg, "Dashboard Chart Creation")
            print(f"❌ {error_msg}")
    
    print(f"\n{'='*60}")
    print(f"Dashboard Charts Created: {len(created)}")
    print(f"Errors: {len(errors)}")
    print(f"{'='*60}\n")
    
    return {
        "created": created,
        "errors": errors
    }


if __name__ == "__main__":
    # Run the installation
    result = install_all_dashboard_charts()
    
    if result["errors"]:
        print("\n⚠️  Some charts failed to create. Check error log for details.")
    else:
        print("\n✅ All dashboard charts created successfully!")
