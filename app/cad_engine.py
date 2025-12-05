"""Production-level CAD engine using CadQuery and OCCT."""
from __future__ import annotations

import io
import os
import re
import tempfile
from typing import Any, Dict, List, Tuple
import traceback

import cadquery as cq
from cadquery import exporters


def validate_cadquery_compatibility(script: str) -> Tuple[bool, List[str]]:
    """Validate script for CadQuery 2.x+ and OCCT compatibility.
    
    Args:
        script: CadQuery Python script to validate
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []
    
    # Check for deprecated StringSelector usage
    if re.search(r'cq\.selectors\.StringSelector', script):
        errors.append(
            "❌ StringSelector is deprecated in CadQuery 2.x+. "
            "Use string selectors directly: .edges('>Z') instead of .edges(cq.selectors.StringSelector('>Z'))"
        )
    
    # Check for deprecated DirectionMinMaxSelector
    if re.search(r'cq\.selectors\.DirectionMinMaxSelector', script):
        errors.append(
            "❌ DirectionMinMaxSelector is deprecated in CadQuery 2.x+. "
            "Use string selectors directly: .faces('>Z') instead"
        )
    
    # Check for other deprecated selectors
    deprecated_selectors = ['NearestToPointSelector', 'BoxSelector', 'RadiusNthSelector']
    for selector in deprecated_selectors:
        if f'cq.selectors.{selector}' in script:
            errors.append(
                f"❌ {selector} may not be compatible with CadQuery 2.x+. "
                f"Use string selectors or modern selection methods."
            )
    
    # Check for math usage without import
    if re.search(r'\bmath\.(pi|sin|cos|tan|sqrt|radians|degrees)', script):
        if not re.search(r'^import\s+math', script, re.MULTILINE):
            errors.append(
                "⚠️ Using math functions without importing math module. "
                "Add 'import math' at the top of your script."
            )
    
    # Check for fillet/chamfer without edge selection (common error)
    # Look for patterns like: ).fillet( or ).chamfer( without .edges( before
    if re.search(r'\)\s*\.\s*(fillet|chamfer)\s*\(', script):
        # Check if there's an .edges() call before fillet/chamfer
        lines = script.split('\n')
        for i, line in enumerate(lines):
            if re.search(r'\.(fillet|chamfer)\s*\(', line):
                # Look back a few lines to see if edges() was called
                lookback = '\n'.join(lines[max(0, i-3):i+1])
                if '.edges(' not in lookback and '.faces(' not in lookback:
                    errors.append(
                        f"❌ Line {i+1}: fillet/chamfer without edge selection. "
                        f"MUST call .edges() before .fillet()/.chamfer(). "
                        f"Example: .edges('|Z').fillet(2)"
                    )
    
    # Warning for potentially problematic fillet sizes (heuristic)
    fillet_matches = re.findall(r'\.fillet\((\d+(?:\.\d+)?)\)', script)
    for fillet_size in fillet_matches:
        if float(fillet_size) > 20:
            errors.append(
                f"⚠️ Large fillet radius ({fillet_size}mm) detected. "
                f"Ensure it's smaller than edge lengths to avoid geometry failures."
            )
    
    # Check for chamfer without edge selection
    if '.chamfer(' in script:
        # Similar check for chamfer
        lines = script.split('\n')
        for i, line in enumerate(lines):
            if '.chamfer(' in line:
                lookback = '\n'.join(lines[max(0, i-3):i+1])
                if '.edges(' not in lookback and '.faces(' not in lookback:
                    errors.append(
                        f"❌ Line {i+1}: .chamfer() requires edge selection first. "
                        f"Use .edges() before .chamfer(). Example: .edges('>Z').chamfer(1)"
                    )
    
    return len(errors) == 0, errors


class CADEngine:
    """CadQuery-based CAD generation and manipulation engine."""
    
    def __init__(self):
        self.last_result = None
        self.last_script = None
    
    def execute_script(self, script: str, fallback_on_error: bool = True) -> Dict[str, Any]:
        """Execute CadQuery script and return the result.
        
        Args:
            script: CadQuery Python script
            fallback_on_error: If True, try to recover by removing problematic operations
            
        Returns:
            Dict with 'success', 'result', 'error', 'script', 'warnings' keys
        """
        warnings = []
        
        # Validate CadQuery compatibility first
        is_valid, validation_errors = validate_cadquery_compatibility(script)
        if not is_valid:
            # Return validation errors as warnings but continue execution
            warnings.extend(validation_errors)
            # If there are critical errors (deprecated selectors), fail immediately
            if any('StringSelector' in err or 'DirectionMinMaxSelector' in err for err in validation_errors):
                return {
                    'success': False,
                    'error': 'Script contains deprecated CadQuery syntax:\n' + '\n'.join(validation_errors),
                    'script': script,
                    'warnings': warnings
                }
        
        try:
            # Create a safe execution context with common imports
            import math
            import numpy as np
            
            exec_globals = {
                'cq': cq,
                'cadquery': cq,
                'math': math,
                'np': np,
                'numpy': np,
                '__builtins__': __builtins__,
            }
            exec_locals = {}
            
            # Execute the script
            exec(script, exec_globals, exec_locals)
            
            # Find the result (look for common variable names)
            result = None
            for var_name in ['result', 'model', 'part', 'assembly', 'workplane', 'show_object']:
                if var_name in exec_locals:
                    result = exec_locals[var_name]
                    break
            
            # If no named result, try to find any Workplane object
            if result is None:
                for value in exec_locals.values():
                    if isinstance(value, cq.Workplane):
                        result = value
                        break
            
            if result is None:
                return {
                    'success': False,
                    'error': 'No CAD object found in script. Assign result to "result" variable.',
                    'script': script
                }
            
            self.last_result = result
            self.last_script = script
            
            return {
                'success': True,
                'result': result,
                'script': script,
                'type': type(result).__name__,
                'warnings': warnings
            }
            
        except Exception as e:
            error_msg = str(e)
            tb = traceback.format_exc()
            
            # Try to recover by removing problematic operations
            recovery_conditions = [
                'StdFail_NotDone' in error_msg,
                'command not done' in error_msg,
                'Chamfer requires that edges be selected' in error_msg,
                'Fillet requires that edges be selected' in error_msg
            ]
            
            if fallback_on_error and any(recovery_conditions):
                recovery_attempted = False
                modified_script = script
                
                # Try to comment out fillet operations
                if '.fillet(' in script:
                    lines = script.split('\n')
                    new_lines = []
                    for line in lines:
                        if '.fillet(' in line and not line.strip().startswith('#'):
                            new_lines.append('    # ' + line.strip() + '  # Auto-commented: fillet failed')
                            recovery_attempted = True
                            warnings.append('Fillet operation was skipped due to geometry constraints')
                        else:
                            new_lines.append(line)
                    modified_script = '\n'.join(new_lines)
                
                # Try to comment out chamfer operations
                if '.chamfer(' in script and not recovery_attempted:
                    lines = script.split('\n')
                    new_lines = []
                    for line in lines:
                        if '.chamfer(' in line and not line.strip().startswith('#'):
                            new_lines.append('    # ' + line.strip() + '  # Auto-commented: chamfer failed')
                            recovery_attempted = True
                            warnings.append('Chamfer operation was skipped due to geometry constraints')
                        else:
                            new_lines.append(line)
                    modified_script = '\n'.join(new_lines)
                
                # Try executing the modified script
                if recovery_attempted:
                    warnings.append('Attempting to render model without problematic operations...')
                    recovery_result = self.execute_script(modified_script, fallback_on_error=False)
                    if recovery_result['success']:
                        recovery_result['warnings'] = warnings
                        recovery_result['script'] = modified_script
                        recovery_result['original_script'] = script
                        return recovery_result
            
            # If recovery failed or wasn't attempted, return error with helpful message
            if 'Chamfer requires that edges be selected' in error_msg:
                error_msg = (
                    "❌ Chamfer Error: Must select edges first!\n"
                    "WRONG: .box(10,10,10).chamfer(1)\n"
                    "CORRECT: .box(10,10,10).edges('|Z').chamfer(1)"
                )
            elif 'Fillet requires that edges be selected' in error_msg:
                error_msg = (
                    "❌ Fillet Error: Must select edges first!\n"
                    "WRONG: .box(10,10,10).fillet(2)\n"
                    "CORRECT: .box(10,10,10).edges('|Z').fillet(2)"
                )
            elif 'StdFail_NotDone' in error_msg or 'command not done' in error_msg:
                if 'fillet' in tb.lower():
                    error_msg = "Fillet operation failed - radius may be too large or edges invalid. The model will render without fillets."
                elif 'chamfer' in tb.lower():
                    error_msg = "Chamfer operation failed - parameters may be invalid. The model will render without chamfers."
                else:
                    error_msg = f"CAD operation failed: {error_msg}"
            
            return {
                'success': False,
                'error': f'{type(e).__name__}: {error_msg}',
                'traceback': tb,
                'script': script,
                'warnings': warnings
            }
    
    def execute_and_export_individual_objects(self, script: str) -> Dict[str, Any]:
        """Execute script and detect individual objects before union/combine.
        
        Returns dict with:
            - 'success': bool
            - 'objects': list of object names found (e.g., ['box', 'cylinder'])
            - 'stl_exports': list of STL bytes for each object
            - 'combined_result': the final combined workplane
        """
        try:
            import math
            import numpy as np
            
            exec_globals = {
                'cq': cq,
                'cadquery': cq,
                'math': math,
                'np': np,
                'numpy': np,
                '__builtins__': __builtins__,
            }
            exec_locals = {}
            
            # Execute the script
            exec(script, exec_globals, exec_locals)
            
            # Detect individual CadQuery Workplane objects (before union/combine)
            individual_objects = []
            object_names = []
            
            # Look for variables that are Workplanes (excluding 'result')
            for var_name, value in exec_locals.items():
                if isinstance(value, cq.Workplane) and var_name != 'result':
                    individual_objects.append(value)
                    object_names.append(var_name)
            
            # Get the final result
            result = exec_locals.get('result')
            
            # If we found individual objects, export each as separate STL
            stl_exports = []
            if individual_objects:
                for obj in individual_objects:
                    stl_bytes = self.export_stl(obj, tolerance=0.01)
                    stl_exports.append(stl_bytes)
            
            return {
                'success': True,
                'objects': object_names,
                'stl_exports': stl_exports,
                'combined_result': result,
                'num_objects': len(individual_objects)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    def export_step(self, workplane: cq.Workplane | None = None) -> bytes:
        """Export CAD model to STEP format."""
        wp = workplane or self.last_result
        if wp is None:
            raise ValueError("No CAD model to export")
        
        with tempfile.NamedTemporaryFile(suffix='.step', delete=False) as f:
            temp_path = f.name
        
        try:
            exporters.export(wp, temp_path, exportType='STEP')
            with open(temp_path, 'rb') as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def export_stl(self, workplane: cq.Workplane | None = None, tolerance: float = 0.01) -> bytes:
        """Export CAD model to STL format."""
        wp = workplane or self.last_result
        if wp is None:
            raise ValueError("No CAD model to export")
        
        with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
            temp_path = f.name
        
        try:
            exporters.export(wp, temp_path, exportType='STL', tolerance=tolerance)
            with open(temp_path, 'rb') as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def export_iges(self, workplane: cq.Workplane | None = None) -> bytes:
        """Export CAD model to IGES format."""
        wp = workplane or self.last_result
        if wp is None:
            raise ValueError("No CAD model to export")
        
        with tempfile.NamedTemporaryFile(suffix='.iges', delete=False) as f:
            temp_path = f.name
        
        try:
            # IGES export via STEP then conversion (CadQuery doesn't have direct IGES)
            # For now, we'll use STEP as it's more modern
            exporters.export(wp, temp_path, exportType='STEP')
            with open(temp_path, 'rb') as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def export_dxf(self, workplane: cq.Workplane | None = None) -> bytes:
        """Export CAD model to DXF format (2D)."""
        wp = workplane or self.last_result
        if wp is None:
            raise ValueError("No CAD model to export")
        
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as f:
            temp_path = f.name
        
        try:
            exporters.export(wp, temp_path, exportType='DXF')
            with open(temp_path, 'rb') as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def export_obj(self, workplane: cq.Workplane | None = None, tolerance: float = 0.01) -> bytes:
        """Export CAD model to OBJ format (Wavefront).
        
        Note: CadQuery doesn't natively support OBJ export, so we export as STL 
        and convert to OBJ format with basic triangulation.
        """
        wp = workplane or self.last_result
        if wp is None:
            raise ValueError("No CAD model to export")
        
        # Export as STL first (CadQuery native support)
        stl_bytes = self.export_stl(wp, tolerance)
        
        # Convert STL bytes to OBJ format
        # Parse STL and create OBJ text format
        import struct
        
        obj_lines = ["# OBJ file generated by FLUDO CAD Studio", "# Exported from CadQuery model", ""]
        
        # Parse binary STL
        if len(stl_bytes) < 84:
            raise ValueError("Invalid STL file")
        
        # Skip 80-byte header + 4-byte triangle count
        num_triangles = struct.unpack('<I', stl_bytes[80:84])[0]
        
        vertices = []
        vertex_map = {}
        current_vertex_index = 1  # OBJ indices start at 1
        
        offset = 84
        for i in range(num_triangles):
            # Each triangle: 3 floats (normal) + 9 floats (3 vertices) + 2 bytes (attribute)
            if offset + 50 > len(stl_bytes):
                break
                
            # Skip normal (12 bytes)
            offset += 12
            
            # Read 3 vertices
            triangle_indices = []
            for j in range(3):
                if offset + 12 > len(stl_bytes):
                    break
                    
                x, y, z = struct.unpack('<fff', stl_bytes[offset:offset+12])
                offset += 12
                
                # Round to avoid floating point duplicates
                vertex_key = (round(x, 6), round(y, 6), round(z, 6))
                
                if vertex_key not in vertex_map:
                    vertex_map[vertex_key] = current_vertex_index
                    vertices.append(vertex_key)
                    current_vertex_index += 1
                
                triangle_indices.append(vertex_map[vertex_key])
            
            # Skip attribute bytes
            offset += 2
        
        # Write vertices
        for v in vertices:
            obj_lines.append(f"v {v[0]} {v[1]} {v[2]}")
        
        obj_lines.append("")
        
        # Write faces (reconstruct from vertex indices)
        offset = 84
        for i in range(num_triangles):
            if offset + 50 > len(stl_bytes):
                break
                
            offset += 12  # Skip normal
            
            triangle_indices = []
            for j in range(3):
                if offset + 12 > len(stl_bytes):
                    break
                x, y, z = struct.unpack('<fff', stl_bytes[offset:offset+12])
                offset += 12
                vertex_key = (round(x, 6), round(y, 6), round(z, 6))
                triangle_indices.append(vertex_map[vertex_key])
            
            offset += 2
            
            if len(triangle_indices) == 3:
                obj_lines.append(f"f {triangle_indices[0]} {triangle_indices[1]} {triangle_indices[2]}")
        
        return '\n'.join(obj_lines).encode('utf-8')
    
    def to_stl_mesh_data(self, workplane: cq.Workplane | None = None, tolerance: float = 0.01) -> Dict[str, Any]:
        """Convert CAD model to STL mesh data for Three.js visualization."""
        stl_bytes = self.export_stl(workplane, tolerance)
        return {'stl': stl_bytes.decode('latin1') if isinstance(stl_bytes, bytes) else stl_bytes}


# Singleton instance
_engine = None

def get_engine() -> CADEngine:
    """Get singleton CAD engine instance."""
    global _engine
    if _engine is None:
        _engine = CADEngine()
    return _engine
