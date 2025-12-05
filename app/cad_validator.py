"""CadQuery code validator and sanitizer for robust execution."""
from __future__ import annotations

import ast
import re
from typing import Dict, List, Tuple, Optional


def validate_cadquery_code(code: str) -> Dict[str, any]:
    """
    Validate CadQuery code before execution.
    Returns: {"valid": bool, "errors": List[str], "warnings": List[str]}
    """
    errors = []
    warnings = []
    
    # Check if code is empty
    if not code.strip():
        errors.append("Code is empty")
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    # Check for syntax errors
    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
        return {"valid": False, "errors": errors, "warnings": warnings}
    
    # Check for required import
    if "import cadquery" not in code and "import cq" not in code:
        errors.append("Missing 'import cadquery as cq' statement")
    
    # Check for result variable
    if not re.search(r'\bresult\s*=', code):
        errors.append("Missing 'result' variable assignment")
    
    # Check for deprecated CadQuery 1.x APIs
    deprecated_apis = [
        (r'cq\.selectors\.StringSelector', "StringSelector is removed in CadQuery 2.x. Use string selectors directly like '>Z', '<X', '|Y'"),
        (r'cq\.selectors\.DirectionMinMaxSelector', "DirectionMinMaxSelector is removed in CadQuery 2.x. Use string selectors"),
        (r'\.faces\(cq\.selectors\.', "Use string selectors: .faces('>Z') instead of .faces(cq.selectors...)"),
        (r'\.edges\(cq\.selectors\.', "Use string selectors: .edges('|Z') instead of .edges(cq.selectors...)"),
    ]
    
    for pattern, msg in deprecated_apis:
        if re.search(pattern, code):
            errors.append(f"Deprecated API: {msg}")
    
    # Check for fillet/chamfer without edge selection
    fillet_pattern = r'\.fillet\('
    chamfer_pattern = r'\.chamfer\('
    
    lines = code.split('\n')
    for i, line in enumerate(lines, 1):
        if re.search(fillet_pattern, line) or re.search(chamfer_pattern, line):
            # Check if previous line has .edges() or .vertices()
            prev_lines = '\n'.join(lines[max(0, i-5):i])
            if '.edges(' not in prev_lines and '.vertices(' not in prev_lines:
                warnings.append(f"Line {i}: fillet/chamfer without edge selection may fail. Add .edges() before .fillet()")
    
    # Check for dangerous operations
    dangerous_patterns = [
        (r'import\s+os', "Using 'os' module - potentially unsafe"),
        (r'import\s+sys', "Using 'sys' module - potentially unsafe"),
        (r'open\(', "File operations detected - potentially unsafe"),
        (r'exec\(', "Using exec() - potentially unsafe"),
        (r'eval\(', "Using eval() - potentially unsafe"),
        (r'__import__', "Using __import__ - potentially unsafe"),
    ]
    
    for pattern, msg in dangerous_patterns:
        if re.search(pattern, code):
            warnings.append(msg)
    
    # Check if math is imported when math functions are used
    math_functions = ['sin', 'cos', 'tan', 'sqrt', 'pi', 'radians', 'degrees']
    uses_math = any(re.search(rf'\bmath\.{func}\b', code) for func in math_functions)
    if uses_math and 'import math' not in code:
        errors.append("Using math functions but 'import math' is missing")
    
    is_valid = len(errors) == 0
    
    return {
        "valid": is_valid,
        "errors": errors,
        "warnings": warnings
    }


def extract_measurements_from_code(code: str) -> Dict[str, float]:
    """
    Extract numeric measurements from CadQuery code.
    Returns dict of variable_name -> value
    """
    measurements = {}
    
    # Find all numeric assignments
    # Pattern: variable = number or variable = number.number
    pattern = r'([A-Z_][A-Z0-9_]*)\s*=\s*([0-9]+\.?[0-9]*)'
    matches = re.findall(pattern, code, re.IGNORECASE)
    
    for var_name, value in matches:
        try:
            measurements[var_name] = float(value)
        except ValueError:
            pass
    
    return measurements


def update_measurement_in_code(code: str, var_name: str, new_value: float) -> str:
    """
    Update a measurement variable in the code.
    """
    # Pattern: VAR_NAME = old_value
    pattern = rf'(\b{re.escape(var_name)}\s*=\s*)([0-9]+\.?[0-9]*)'
    
    def replace_value(match):
        return f"{match.group(1)}{new_value}"
    
    updated_code = re.sub(pattern, replace_value, code)
    return updated_code


def sanitize_code(code: str) -> str:
    """
    Sanitize code by removing potentially unsafe operations.
    """
    # Remove dangerous imports
    dangerous_imports = ['os', 'sys', 'subprocess', 'socket', 'urllib', 'requests']
    for module in dangerous_imports:
        code = re.sub(rf'import\s+{module}\b.*\n?', '', code)
        code = re.sub(rf'from\s+{module}\s+import.*\n?', '', code)
    
    # Remove file operations
    code = re.sub(r'open\([^)]+\)', '# removed unsafe operation', code)
    code = re.sub(r'\bexec\([^)]+\)', '# removed unsafe operation', code)
    code = re.sub(r'\beval\([^)]+\)', '# removed unsafe operation', code)
    
    return code


def suggest_fix(code: str, error_message: str) -> Optional[str]:
    """
    Suggest automatic fixes for common errors.
    """
    suggestions = []
    
    # Fix missing imports
    if "cadquery" in error_message.lower() or "module" in error_message.lower():
        if "import cadquery" not in code:
            suggestions.append("Add: import cadquery as cq")
    
    if "math" in error_message.lower() and "import math" not in code:
        suggestions.append("Add: import math")
    
    # Fix missing result variable
    if "result" in error_message.lower() and "result =" not in code:
        # Try to find the last assignment and suggest renaming it to result
        last_assignment = re.findall(r'(\w+)\s*=\s*\(', code)
        if last_assignment:
            suggestions.append(f"Rename '{last_assignment[-1]}' to 'result'")
    
    # Fix deprecated selectors
    if "StringSelector" in error_message or "DirectionMinMaxSelector" in error_message:
        suggestions.append("Replace cq.selectors.StringSelector('>Z') with just '>Z'")
        suggestions.append("Replace cq.selectors usage with string selectors")
    
    # Fix fillet/chamfer errors
    if "fillet" in error_message.lower() or "chamfer" in error_message.lower():
        suggestions.append("Add .edges() selection before .fillet()/.chamfer()")
        suggestions.append("Reduce fillet/chamfer radius (it may be too large for the geometry)")
    
    return "\n".join(suggestions) if suggestions else None


def auto_fix_code(code: str, validation_result: Dict) -> Tuple[str, List[str]]:
    """
    Attempt to automatically fix common issues in the code.
    Returns: (fixed_code, list_of_fixes_applied)
    """
    fixed_code = code
    fixes_applied = []
    
    # Fix missing imports
    if any("import cadquery" in err for err in validation_result.get("errors", [])):
        if "import cadquery" not in fixed_code:
            fixed_code = "import cadquery as cq\n" + fixed_code
            fixes_applied.append("Added: import cadquery as cq")
    
    if any("import math" in err for err in validation_result.get("errors", [])):
        if "import math" not in fixed_code:
            # Add after cadquery import if it exists
            if "import cadquery" in fixed_code:
                fixed_code = fixed_code.replace("import cadquery as cq", "import cadquery as cq\nimport math")
            else:
                fixed_code = "import math\n" + fixed_code
            fixes_applied.append("Added: import math")
    
    # Fix deprecated StringSelector
    if "StringSelector" in fixed_code:
        # Replace cq.selectors.StringSelector(">Z") with just ">Z"
        fixed_code = re.sub(
            r'cq\.selectors\.StringSelector\(["\']([^"\']+)["\']\)',
            r'"\1"',
            fixed_code
        )
        fixes_applied.append("Fixed: Replaced StringSelector with string selectors")
    
    # Fix .edges(cq.selectors.StringSelector(...)) -> .edges("...")
    if "cq.selectors" in fixed_code:
        fixed_code = re.sub(
            r'\.edges\(cq\.selectors\.StringSelector\(["\']([^"\']+)["\']\)\)',
            r'.edges("\1")',
            fixed_code
        )
        fixed_code = re.sub(
            r'\.faces\(cq\.selectors\.StringSelector\(["\']([^"\']+)["\']\)\)',
            r'.faces("\1")',
            fixed_code
        )
        fixes_applied.append("Fixed: Updated edge/face selectors to CadQuery 2.x format")
    
    return fixed_code, fixes_applied
