"""
OpenSCAD execution engine for FLUDO CAD Studio.
Executes OpenSCAD code and generates STL files for 3D preview.
"""

import os
import subprocess
import tempfile
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
import traceback as tb


class OpenSCADEngine:
    """Execute OpenSCAD scripts and generate STL files."""
    
    def __init__(self, output_dir: str = "models"):
        """Initialize OpenSCAD engine.
        
        Args:
            output_dir: Directory to store generated STL files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Find OpenSCAD executable
        self.openscad_path = self._find_openscad()
        if not self.openscad_path:
            raise RuntimeError("OpenSCAD not found. Please install OpenSCAD.")
    
    def _find_openscad(self) -> Optional[str]:
        """Find OpenSCAD executable on the system."""
        # Common installation paths
        paths = [
            "C:\\Program Files\\OpenSCAD\\openscad.exe",
            "C:\\Program Files (x86)\\OpenSCAD\\openscad.exe",
            "/usr/bin/openscad",
            "/usr/local/bin/openscad",
            "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
        ]
        
        for path in paths:
            if os.path.exists(path):
                return path
        
        # Try to find in PATH
        try:
            result = subprocess.run(
                ["where" if os.name == "nt" else "which", "openscad"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass
        
        return None
    
    def execute_script(self, script: str, fallback_on_error: bool = True) -> Dict[str, Any]:
        """Execute OpenSCAD script and return the result.
        
        Args:
            script: OpenSCAD code to execute
            fallback_on_error: Not used (kept for API compatibility)
            
        Returns:
            Dict with keys:
            - success: True if execution succeeded
            - stl_path: Path to generated STL file (if success)
            - stl_filename: Filename of STL (if success)
            - error: Error message (if failed)
            - traceback: Full traceback (if failed)
            - script: Original script
            - warnings: List of warnings
        """
        warnings = []
        
        # Validate script
        if not script or not script.strip():
            return {
                'success': False,
                'error': 'Empty script',
                'traceback': '',
                'script': script,
                'warnings': []
            }
        
        # Check for basic OpenSCAD syntax
        if not any(keyword in script for keyword in ['cube', 'sphere', 'cylinder', 'difference', 'union', 'intersection']):
            warnings.append("Script doesn't contain common OpenSCAD primitives")
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.scad', delete=False) as scad_file:
            scad_file.write(script)
            scad_path = scad_file.name
        
        try:
            # Generate hash for unique STL filename
            script_hash = hashlib.md5(script.encode()).hexdigest()[:16]
            stl_filename = f"{script_hash}.stl"
            stl_path = self.output_dir / stl_filename
            
            # Execute OpenSCAD
            result = subprocess.run(
                [
                    self.openscad_path,
                    "-o", str(stl_path),
                    "--export-format", "binstl",
                    scad_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Check if STL was generated
            if stl_path.exists() and stl_path.stat().st_size > 0:
                return {
                    'success': True,
                    'stl_path': str(stl_path),
                    'stl_filename': stl_filename,
                    'script': script,
                    'warnings': warnings,
                    'openscad_output': result.stderr  # OpenSCAD logs to stderr
                }
            else:
                # Execution failed
                error_msg = result.stderr or result.stdout or "Unknown error"
                return {
                    'success': False,
                    'error': f'OpenSCAD execution failed: {error_msg}',
                    'traceback': error_msg,
                    'script': script,
                    'warnings': warnings
                }
        
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'OpenSCAD execution timed out (>30s)',
                'traceback': 'Timeout after 30 seconds',
                'script': script,
                'warnings': warnings
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': tb.format_exc(),
                'script': script,
                'warnings': warnings
            }
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(scad_path)
            except Exception:
                pass
    
    def get_stl_path(self, filename: str) -> Path:
        """Get full path to STL file.
        
        Args:
            filename: STL filename
            
        Returns:
            Full path to STL file
        """
        return self.output_dir / filename
