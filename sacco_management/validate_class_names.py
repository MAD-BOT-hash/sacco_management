#!/usr/bin/env python3
"""
Validate that all Python class names match Frappe's naming convention
"""

import os
import re
import json


def get_doctype_name(json_path):
    """Extract DocType name from JSON file"""
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            return data.get('name', '')
    except:
        return None


def get_python_class_name(py_path):
    """Extract class name from Python file"""
    try:
        with open(py_path, 'r') as f:
            content = f.read()
            match = re.search(r'^class\s+(\w+)\s*\(', content, re.MULTILINE)
            if match:
                return match.group(1)
    except:
        pass
    return None


def to_pascal_case(snake_str):
    """Convert snake_case to PascalCase"""
    return ''.join(word.capitalize() for word in snake_str.split('_'))


def validate_naming(doctype_dir):
    """Validate naming convention for a doctype directory"""
    dir_name = os.path.basename(doctype_dir)
    
    json_file = os.path.join(doctype_dir, f"{dir_name}.json")
    py_file = os.path.join(doctype_dir, f"{dir_name}.py")
    
    # Skip if no Python file
    if not os.path.exists(py_file):
        return None
    
    # Get DocType name from JSON
    doctype_name = get_doctype_name(json_file)
    if not doctype_name:
        return None
    
    # Get Python class name
    python_class = get_python_class_name(py_file)
    if not python_class:
        return {
            'directory': dir_name,
            'doctype_name': doctype_name,
            'python_class': None,
            'expected_class': None,
            'error': 'No class found'
        }
    
    # Calculate expected class name from directory name
    expected_class = to_pascal_case(dir_name)
    
    # Check if they match
    is_valid = python_class == expected_class
    
    return {
        'directory': dir_name,
        'doctype_name': doctype_name,
        'python_class': python_class,
        'expected_class': expected_class,
        'is_valid': is_valid,
        'error': None
    }


def main():
    base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                            'sacco', 'doctype')
    
    issues = []
    valid = []
    
    for item in sorted(os.listdir(base_path)):
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path):
            result = validate_naming(item_path)
            if result:
                if result.get('error'):
                    issues.append(result)
                elif not result['is_valid']:
                    issues.append(result)
                else:
                    valid.append(result)
    
    print("="*80)
    print("NAMING CONVENTION VALIDATION REPORT")
    print("="*80)
    print(f"\nTotal DocTypes checked: {len(valid) + len(issues)}")
    print(f"Valid: {len(valid)}")
    print(f"Issues found: {len(issues)}\n")
    
    if issues:
        print("-"*80)
        print("ISSUES FOUND:")
        print("-"*80)
        
        for issue in issues:
            print(f"\n❌ {issue['directory']}")
            print(f"   DocType Name: {issue['doctype_name']}")
            print(f"   Python Class: {issue['python_class']}")
            print(f"   Expected:     {issue['expected_class']}")
            
            if issue.get('error'):
                print(f"   Error: {issue['error']}")
    
    print("\n" + "="*80)
    
    return len(issues) == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
