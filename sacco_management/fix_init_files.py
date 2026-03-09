#!/usr/bin/env python3
"""
Fix all __init__.py files in doctype directories
"""

import os
import re

def to_pascal_case(snake_str):
    """Convert snake_case to PascalCase"""
    return ''.join(word.capitalize() for word in snake_str.split('_'))

def fix_init_file(dir_path):
    """Fix __init__.py file in a doctype directory"""
    dir_name = os.path.basename(dir_path.rstrip('/\\'))
    py_file = f"{dir_name}.py"
    init_file = os.path.join(dir_path, "__init__.py")
    
    # Check if Python file exists
    if not os.path.exists(os.path.join(dir_path, py_file)):
        return False
    
    # Generate class name
    class_name = to_pascal_case(dir_name)
    
    # Write fixed __init__.py
    content = f"""# Copyright (c) 2024, SACCO Developer and contributors
# For license information, see license.txt

from .{dir_name} import {class_name}

__all__ = ["{class_name}"]
"""
    
    with open(init_file, 'w') as f:
        f.write(content)
    
    return True

def main():
    # Get the sacco/doctype directory
    base_path = os.path.dirname(os.path.abspath(__file__))
    doctype_path = os.path.join(base_path, "sacco", "doctype")
    
    fixed_count = 0
    for item in os.listdir(doctype_path):
        item_path = os.path.join(doctype_path, item)
        if os.path.isdir(item_path):
            if fix_init_file(item_path):
                print(f"✓ Fixed: {item}")
                fixed_count += 1
    
    print(f"\nTotal fixed: {fixed_count} __init__.py files")

if __name__ == "__main__":
    main()
