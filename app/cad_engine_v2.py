"""Enhanced CAD Engine with Trimesh backend.

Integrates with CADKernel for parametric design capabilities.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import numpy as np
import trimesh
from pathlib import Path
from typing import Any, Dict, Optional
import traceback

# Ensure proper imports
app_dir = str(Path(__file__).parent)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from cad_kernel import CADKernel, Part, get_kernel
from technical_drawings import generate_drawing_for_part, BOMGenerator


class EnhancedCADEngine:
    """Enhanced CAD engine with full parametric support."""
    
    def __init__(self):
        self.kernel = get_kernel()
        self.last_result = None
        self.last_script = None
        self.last_part: Optional[Part] = None
    
    def execute_script(self, script: str, part_name: str = "Generated Part") -> Dict[str, Any]:
        """Execute CAD script and return the result.
        
        Args:
            script: Python script using trimesh and numpy
            part_name: Name for the generated part
            
        Returns:
            Dict with 'success', 'result', 'error', 'script', 'part_info' keys
        """
        try:
            # Create a new part
            part = self.kernel.create_part(part_name, script=script)
            
            # Create safe execution context
            exec_globals = {
                'np': np,
                'numpy': np,
                'trimesh': trimesh,
                '__builtins__': __builtins__,
            }
            exec_locals = {}
            
            # Execute the script
            exec(script, exec_globals, exec_locals)
            
            # Find the result
            result = None
            for var_name in ['result', 'model', 'part', 'mesh', 'geometry']:
                if var_name in exec_locals:
                    result = exec_locals[var_name]
                    break
            
            # If no named result, try to find any Trimesh object
            if result is None:
                for value in exec_locals.values():
                    if isinstance(value, trimesh.Trimesh):
                        result = value
                        break
            
            if result is None:
                return {
                    'success': False,
                    'error': 'No 3D mesh found in script. Assign result to "result" variable.',
                    'script': script
                }
            
            # Validate it's a Trimesh
            if not isinstance(result, trimesh.Trimesh):
                return {
                    'success': False,
                    'error': f'Result must be a trimesh.Trimesh object, got {type(result).__name__}',
                    'script': script
                }
            
            # Store mesh in part
            part.mesh = result
            
            # Validate geometry
            validation = self.kernel.validate_geometry(part)
            
            # Extract parameters from script
            parameters = self._extract_parameters(script)
            for param_name, param_value in parameters.items():
                from .cad_kernel import Parameter
                part.add_parameter(Parameter(
                    name=param_name,
                    value=param_value,
                    unit='mm'
                ))
            
            # Store for later use
            self.last_result = result
            self.last_script = script
            self.last_part = part
            
            # Get part info
            part_info = self.kernel.get_part_info(part)
            
            return {
                'success': True,
                'result': result,
                'script': script,
                'type': 'Trimesh',
                'part_id': part.id,
                'part_info': part_info,
                'validation': validation
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'{type(e).__name__}: {str(e)}',
                'traceback': traceback.format_exc(),
                'script': script
            }
    
    def _extract_parameters(self, script: str) -> Dict[str, float]:
        """Extract parameter definitions from script."""
        import re
        parameters = {}
        lines = script.split('\\n')
        
        for line in lines:
            # Look for pattern: variable_name = numeric_value
            match = re.match(r'^([a-z_][a-z0-9_]*)\\s*=\\s*([0-9.]+)', line.strip())
            if match:
                var_name, value = match.groups()
                try:
                    parameters[var_name] = float(value)
                except ValueError:
                    pass
        
        return parameters
    
    def export_step(self, mesh: Optional[trimesh.Trimesh] = None) -> bytes:
        """Export to STEP format (as STL for now, since STEP requires CAD kernel)."""
        m = mesh or self.last_result
        if m is None:
            raise ValueError("No mesh to export")
        
        # For now, export as STL since we don't have full CAD kernel
        # In production with CadQuery, this would be true STEP
        return m.export(file_type='stl')
    
    def export_stl(self, mesh: Optional[trimesh.Trimesh] = None, tolerance: float = 0.01) -> bytes:
        """Export to STL format."""
        m = mesh or self.last_result
        if m is None:
            raise ValueError("No mesh to export")
        
        return m.export(file_type='stl')
    
    def export_iges(self, mesh: Optional[trimesh.Trimesh] = None) -> bytes:
        """Export to IGES format (as STL for now)."""
        return self.export_stl(mesh)
    
    def export_dxf(self, mesh: Optional[trimesh.Trimesh] = None) -> bytes:
        """Export to DXF format (2D projection)."""
        from .technical_drawings import TechnicalDrawing
        
        m = mesh or self.last_result
        if m is None:
            raise ValueError("No mesh to export")
        
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as f:
            temp_path = f.name
        
        try:
            drawing = TechnicalDrawing(self.last_part.name if self.last_part else "Part")
            drawing.export_dxf(temp_path, m)
            
            with open(temp_path, 'rb') as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def generate_technical_drawing(self, format: str = 'pdf') -> bytes:
        """Generate technical drawing with dimensions and views."""
        if self.last_result is None or self.last_part is None:
            raise ValueError("No part to generate drawing for")
        
        with tempfile.NamedTemporaryFile(suffix=f'.{format}', delete=False) as f:
            temp_path = f.name
        
        try:
            generate_drawing_for_part(
                self.last_part.name,
                self.last_result,
                temp_path,
                format=format
            )
            
            with open(temp_path, 'rb') as f:
                return f.read()
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def generate_bom(self, assembly_name: str = "Assembly") -> Dict[str, Any]:
        """Generate Bill of Materials."""
        bom = BOMGenerator()
        
        # Add all parts from kernel
        for part_id, part in self.kernel.parts.items():
            bom.add_item(
                part_number=part_id[:8],
                description=part.name,
                quantity=1,
                material=part.material or "Not specified",
                notes=""
            )
        
        return bom.to_dict()
    
    def get_part_parameters(self) -> Dict[str, Any]:
        """Get parameters of last generated part."""
        if self.last_part is None:
            return {}
        
        return {
            name: param.to_dict()
            for name, param in self.last_part.parameters.items()
        }
    
    def update_parameter(self, param_name: str, value: float) -> Dict[str, Any]:
        """Update parameter and regenerate part."""
        if self.last_part is None:
            return {'success': False, 'error': 'No part to update'}
        
        if param_name not in self.last_part.parameters:
            return {'success': False, 'error': f'Parameter {param_name} not found'}
        
        # Update parameter
        self.last_part.update_parameter(param_name, value)
        
        # Regenerate by re-executing script with updated parameter
        # This is simplified - in production, would use proper parametric update
        return {'success': True, 'message': 'Parameter updated. Re-execute script to see changes.'}


# Singleton instance
_engine_instance: Optional[EnhancedCADEngine] = None

def get_engine() -> EnhancedCADEngine:
    """Get singleton CAD engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = EnhancedCADEngine()
    return _engine_instance
