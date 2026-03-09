"""
Performance Optimization Utilities for SACCO Management System

This module provides:
- Query optimization helpers
- Caching decorators and utilities
- Database indexing recommendations
- Performance monitoring tools
"""

import frappe
from frappe import _
from functools import wraps
import time
import json
from typing import Any, Callable, Dict, List


# =============================================================================
# CACHING DECORATORS
# =============================================================================

def cache_result(ttl_seconds=300, key_prefix="sacco_cache"):
    """
    Decorator to cache function results
    
    Args:
        ttl_seconds (int): Time to live in seconds
        key_prefix (str): Prefix for cache key
    
    Usage:
        @cache_result(ttl_seconds=600)
        def get_expensive_data(member_id):
            # Your code here
            return data
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{func.__name__}"
            if args:
                cache_key += f":{':'.join(str(arg) for arg in args)}"
            if kwargs:
                cache_key += f":{':'.join(f'{k}={v}' for k, v in kwargs.items())}"
            
            # Try to get from cache
            cached_value = frappe.cache().get(cache_key)
            if cached_value is not None:
                return json.loads(cached_value) if isinstance(cached_value, str) else cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            
            # Store in cache
            frappe.cache().setex(
                cache_key,
                ttl_seconds,
                json.dumps(result, default=str)
            )
            
            return result
        
        return wrapper
    return decorator


def cache_member_data(ttl_seconds=300):
    """
    Specialized cache decorator for member data
    
    Automatically handles member-specific cache invalidation
    """
    def decorator(func):
        @wraps(func)
        def wrapper(member_id, *args, **kwargs):
            cache_key = f"member:{member_id}:{func.__name__}"
            
            cached_value = frappe.cache().get(cache_key)
            if cached_value:
                return json.loads(cached_value)
            
            result = func(member_id, *args, **kwargs)
            
            frappe.cache().setex(
                cache_key,
                ttl_seconds,
                json.dumps(result, default=str)
            )
            
            return result
        
        return wrapper
    return decorator


def invalidate_member_cache(member_id):
    """
    Invalidate all cached data for a specific member
    
    Args:
        member_id (str): Member ID to invalidate
    """
    keys = frappe.cache().get_keys(f"member:{member_id}:*")
    for key in keys:
        frappe.cache().delete(key)


# =============================================================================
# QUERY OPTIMIZATION UTILITIES
# =============================================================================

def optimize_query(sql_query, params=None):
    """
    Analyze and optimize SQL query
    
    Args:
        sql_query (str): SQL query to optimize
        params (tuple): Query parameters
    
    Returns:
        dict: Optimization suggestions
    """
    suggestions = []
    
    # Check for SELECT *
    if "SELECT *" in sql_query.upper():
        suggestions.append("Avoid SELECT * - specify only needed columns")
    
    # Check for missing WHERE clause
    if "WHERE" not in sql_query.upper() and "JOIN" in sql_query.upper():
        suggestions.append("Add WHERE clause to filter joined results")
    
    # Check for LIKE with leading wildcard
    if "LIKE '%" in sql_query:
        suggestions.append("Leading wildcard in LIKE prevents index usage")
    
    # Check for functions on indexed columns
    if any(func in sql_query.upper() for func in ["DATE(", "YEAR(", "MONTH("]):
        suggestions.append("Functions on columns can prevent index usage")
    
    return {
        "query": sql_query,
        "suggestions": suggestions,
        "has_issues": len(suggestions) > 0
    }


def add_index_if_missing(doctype, fieldname):
    """
    Add database index if it doesn't exist
    
    Args:
        doctype (str): Document type
        fieldname (str): Field to index
    """
    table_name = f"`tab{doctype}`"
    index_name = f"idx_{fieldname}"
    
    # Check if index exists
    existing_indexes = frappe.db.sql(f"SHOW INDEX FROM {table_name}")
    index_exists = any(idx[2] == index_name for idx in existing_indexes)
    
    if not index_exists:
        try:
            frappe.db.sql(f"ALTER TABLE {table_name} ADD INDEX {index_name} ({fieldname})")
            frappe.log_error(f"Added index {index_name} on {doctype}.{fieldname}")
            return True
        except Exception as e:
            frappe.log_error(f"Failed to add index: {e}")
            return False
    
    return False


def get_recommended_indexes():
    """
    Get recommended indexes for common queries
    
    Returns:
        list: Recommended indexes to add
    """
    recommendations = [
        {"doctype": "SACCO Member", "field": "email"},
        {"doctype": "SACCO Member", "field": "membership_status"},
        {"doctype": "SACCO Member", "field": "branch"},
        {"doctype": "Loan Application", "field": "member"},
        {"doctype": "Loan Application", "field": "status"},
        {"doctype": "Loan Application", "field": "application_date"},
        {"doctype": "Savings Account", "field": "member"},
        {"doctype": "Savings Account", "field": "status"},
        {"doctype": "Share Allocation", "field": "member"},
        {"doctype": "Member Contribution", "field": "member"},
        {"doctype": "Member Contribution", "field": "posting_date"},
    ]
    
    return recommendations


def apply_recommended_indexes():
    """Apply all recommended indexes"""
    recommendations = get_recommended_indexes()
    applied = []
    
    for rec in recommendations:
        if add_index_if_missing(rec["doctype"], rec["field"]):
            applied.append(f"{rec['doctype']}.{rec['field']}")
    
    return {
        "applied": applied,
        "count": len(applied)
    }


# =============================================================================
# BATCH PROCESSING UTILITIES
# =============================================================================

def process_in_batches(doctype, filters, batch_size=100, processor_func=None):
    """
    Process large datasets in batches to avoid memory issues
    
    Args:
        doctype (str): Document type to process
        filters (dict): Filters to apply
        batch_size (int): Number of records per batch
        processor_func (callable): Function to process each batch
    
    Returns:
        dict: Processing statistics
    """
    total_count = frappe.db.count(doctype, filters=filters or {})
    processed = 0
    errors = []
    
    for start in range(0, total_count, batch_size):
        try:
            # Get batch
            records = frappe.get_all(
                doctype,
                filters=filters or {},
                fields=["name"],
                limit_start=start,
                limit_page_length=batch_size
            )
            
            # Process batch
            if processor_func:
                for record in records:
                    doc = frappe.get_doc(doctype, record.name)
                    processor_func(doc)
                    processed += 1
            
            # Commit after each batch
            frappe.db.commit()
            
        except Exception as e:
            errors.append({
                "batch": start // batch_size,
                "error": str(e)
            })
            frappe.db.rollback()
    
    return {
        "total": total_count,
        "processed": processed,
        "errors": errors,
        "batches": (total_count + batch_size - 1) // batch_size
    }


# =============================================================================
# PERFORMANCE MONITORING
# =============================================================================

class PerformanceMonitor:
    """Context manager for monitoring query performance"""
    
    def __init__(self, operation_name, threshold_ms=100):
        self.operation_name = operation_name
        self.threshold_ms = threshold_ms
        self.start_time = None
        self.queries = []
        self.query_count = 0
    
    def __enter__(self):
        self.start_time = time.time()
        frappe.db._sql_messages = []
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = (time.time() - self.start_time) * 1000
        
        if elapsed_ms > self.threshold_ms:
            frappe.log_error(
                message=f"Slow operation detected: {self.operation_name}\n"
                       f"Execution time: {elapsed_ms:.2f}ms\n"
                       f"Threshold: {self.threshold_ms}ms",
                title="Performance Warning"
            )
        
        print(f"\n{'='*60}")
        print(f"Operation: {self.operation_name}")
        print(f"Execution Time: {elapsed_ms:.2f}ms")
        print(f"Queries Executed: {self.query_count}")
        print(f"{'='*60}\n")


def monitor_queries(func):
    """Decorator to monitor database queries in a function"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        with PerformanceMonitor(func.__name__):
            result = func(*args, **kwargs)
        return result
    return wrapper


# =============================================================================
# LAZY LOADING HELPERS
# =============================================================================

def lazy_load_member_details(member_id):
    """
    Load member details lazily to avoid N+1 queries
    
    Args:
        member_id (str): Member ID
    
    Returns:
        dict: Cached member details
    """
    cache_key = f"member_details:{member_id}"
    
    cached = frappe.cache().get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Load all related data in single query
    member = frappe.get_doc("SACCO Member", member_id)
    
    details = {
        "basic_info": member.as_dict(),
        "savings_accounts": frappe.get_all(
            "Savings Account",
            filters={"member": member_id, "docstatus": 1},
            fields=["name", "account_type", "current_balance", "status"]
        ),
        "loans": frappe.get_all(
            "Loan Application",
            filters={"member": member_id, "docstatus": 1},
            fields=["name", "loan_type", "amount_requested", "outstanding_principal", "status"]
        ),
        "shares": frappe.get_all(
            "Share Allocation",
            filters={"member": member_id, "docstatus": 1, "status": "Allocated"},
            fields=["name", "share_type", "quantity", "total_amount"]
        )
    }
    
    frappe.cache().setex(
        cache_key,
        300,  # 5 minutes
        json.dumps(details, default=str)
    )
    
    return details


# =============================================================================
# QUERY BUILDER WITH OPTIMIZATION
# =============================================================================

class OptimizedQueryBuilder:
    """Build optimized queries with automatic indexing hints"""
    
    def __init__(self, doctype):
        self.doctype = doctype
        self.filters = {}
        self.fields = ["name"]
        self.order_by = "creation DESC"
        self.limit = None
        self.use_index = None
    
    def select(self, fields):
        """Specify fields to select"""
        self.fields = fields if isinstance(fields, list) else [fields]
        return self
    
    def where(self, filters):
        """Add filters"""
        self.filters.update(filters)
        return self
    
    def order_by(self, field, direction="DESC"):
        """Set ordering"""
        self.order_by = f"{field} {direction}"
        return self
    
    def limit(self, count):
        """Set limit"""
        self.limit = count
        return self
    
    def use_index_hint(self, index_name):
        """Hint to use specific index"""
        self.use_index = index_name
        return self
    
    def execute(self):
        """Execute optimized query"""
        kwargs = {
            "doctype": self.doctype,
            "filters": self.filters,
            "fields": self.fields,
            "order_by": self.order_by
        }
        
        if self.limit:
            kwargs["limit"] = self.limit
        
        return frappe.get_all(**kwargs)


# =============================================================================
# CACHE MANAGEMENT
# =============================================================================

def clear_sacco_caches():
    """Clear all SACCO-related caches"""
    patterns = [
        "sacco_cache:*",
        "member:*",
        "loan:*",
        "savings:*",
        "shares:*"
    ]
    
    cleared_count = 0
    for pattern in patterns:
        keys = frappe.cache().get_keys(pattern)
        for key in keys:
            frappe.cache().delete(key)
            cleared_count += 1
    
    return {"cleared_keys": cleared_count}


def warm_up_caches():
    """Pre-warm caches for frequently accessed data"""
    warmed = []
    
    # Warm up member count cache
    member_count = frappe.db.count("SACCO Member", {"membership_status": "Active"})
    frappe.cache().setex("stats:active_members", 3600, member_count)
    warmed.append("active_members_count")
    
    # Warm up loan portfolio cache
    loan_stats = frappe.db.sql("""
        SELECT status, COUNT(*) as count, SUM(outstanding_principal) as total
        FROM `tabLoan Application`
        WHERE docstatus = 1
        GROUP BY status
    """, as_dict=True)
    
    frappe.cache().setex("stats:loan_portfolio", 1800, json.dumps(loan_stats, default=str))
    warmed.append("loan_portfolio_stats")
    
    return {"warmed_caches": warmed}


# =============================================================================
# PERFORMANCE TIPS
# =============================================================================

def get_performance_tips():
    """Get performance optimization tips"""
    return [
        {
            "category": "Database Queries",
            "tips": [
                "Use specific field lists instead of SELECT *",
                "Add indexes on frequently filtered columns",
                "Use LIMIT to restrict result set size",
                "Avoid functions on indexed columns in WHERE clauses",
                "Use JOINs instead of multiple separate queries"
            ]
        },
        {
            "category": "Caching Strategy",
            "tips": [
                "Cache expensive calculations for 5-10 minutes",
                "Cache member data with short TTL (5 min)",
                "Cache statistical data with longer TTL (1 hour)",
                "Invalidate caches on data updates",
                "Use Redis for distributed caching"
            ]
        },
        {
            "category": "Code Optimization",
            "tips": [
                "Use batch processing for large datasets",
                "Implement lazy loading for related data",
                "Minimize database calls in loops",
                "Use frappe.get_all() instead of frappe.get_list() for better performance",
                "Profile code to identify bottlenecks"
            ]
        },
        {
            "category": "API Performance",
            "tips": [
                "Implement pagination for list endpoints",
                "Use field filtering to reduce response size",
                "Compress API responses with gzip",
                "Implement request rate limiting",
                "Cache API responses for read-only endpoints"
            ]
        }
    ]
