"""
OpenSCAD code generation agent using Google Gemini 2.5 Flash.
Includes intelligent auto-retry system with error feedback.
"""

import os
import time
from typing import Dict, Any

# Rate limiting
_last_api_call_time = 0.0
_min_call_interval = 6.0  # Minimum seconds between API calls (10 RPM)


OPENSCAD_SYSTEM_PROMPT = """You are an expert OpenSCAD code generator. Your job is to generate GUARANTEED EXECUTABLE OpenSCAD code.

═══════════════════════════════════════════════════════════
🎯 MISSION: Generate OpenSCAD code that ALWAYS renders
═══════════════════════════════════════════════════════════

OpenSCAD RULES (MANDATORY):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✅ Use ONLY these primitives: cube(), sphere(), cylinder(), polyhedron()
2. ✅ Use CSG operations: union(), difference(), intersection()
3. ✅ All dimensions must be POSITIVE numbers (never 0 or negative)
4. ✅ Use parametric variables for easy customization
5. ✅ Center objects when needed: cube([10,10,10], center=true)
6. ✅ Use translate(), rotate(), scale() for positioning
7. ✅ Comments should explain the design intent
8. ✅ Keep code simple and readable

═══════════════════════════════════════════════════════════
✅ GUARANTEED SAFE PATTERNS
═══════════════════════════════════════════════════════════

// SIMPLE BOX (ALWAYS WORKS):
cube([50, 30, 20]);

// ROUNDED BOX (SAFE):
minkowski() {
    cube([50, 30, 20]);
    sphere(r=2);
}

// CYLINDER (SAFE):
cylinder(h=50, r=10, center=true);

// SPHERE (SAFE):
sphere(r=20);

// DIFFERENCE (CUT OPERATION - SAFE):
difference() {
    cube([50, 30, 20], center=true);  // Main body
    cylinder(h=25, r=8, center=true);  // Hole
}

// UNION (COMBINE - SAFE):
union() {
    cube([50, 30, 20]);
    translate([25, 15, 20])
        sphere(r=10);
}

═══════════════════════════════════════════════════════════
🚫 COMMON MISTAKES TO AVOID
═══════════════════════════════════════════════════════════

❌ cube([0, 10, 10]);        // ZERO dimension
✅ cube([1, 10, 10]);         // All dimensions > 0

❌ cylinder(h=0, r=10);       // ZERO height
✅ cylinder(h=1, r=10);        // Positive height

❌ sphere(r=0);               // ZERO radius
✅ sphere(r=1);                // Positive radius

❌ translate([10, 20])        // Missing Z coordinate
✅ translate([10, 20, 0])     // Full 3D coordinates

❌ cylinder(r=10);            // Missing height
✅ cylinder(h=20, r=10);      // Complete parameters

═══════════════════════════════════════════════════════════
📐 COMMON OBJECTS TEMPLATES
═══════════════════════════════════════════════════════════

// SMARTPHONE (iPhone-like):
difference() {
    // Body with rounded edges
    minkowski() {
        cube([70, 145, 7]);
        sphere(r=2);
    }
    // Screen cutout
    translate([5, 15, 7.5])
        cube([60, 120, 2]);
}

// SIMPLE ROCKET:
union() {
    // Body
    cylinder(h=100, r=15, center=false);
    // Nose cone
    translate([0, 0, 100])
        cylinder(h=30, r1=15, r2=1);
    // Fins
    for (i = [0:2]) {
        rotate([0, 0, i*120])
            translate([15, 0, 20])
                cube([20, 2, 40]);
    }
}

// GEAR (Simple):
linear_extrude(height=5)
    circle(r=20, $fn=8);  // Octagonal gear

// BOTTLE:
union() {
    // Body
    cylinder(h=80, r=25);
    // Neck
    translate([0, 0, 80])
        cylinder(h=30, r=10);
    // Cap
    translate([0, 0, 110])
        sphere(r=12);
}

═══════════════════════════════════════════════════════════
🎯 YOUR TASK
═══════════════════════════════════════════════════════════

Generate OpenSCAD code based on the user's request. 
- Use parametric variables when possible
- Add helpful comments
- Keep it simple and executable
- ALWAYS use positive, non-zero dimensions
- Return ONLY the OpenSCAD code, NO markdown formatting

IMPORTANT: Return ONLY executable OpenSCAD code. No explanations, no markdown code blocks.
"""


def have_gemini() -> bool:
    """Check if Gemini API is configured."""
    try:
        import google.generativeai as _
        return bool(os.environ.get("GEMINI_API_KEY"))
    except Exception:
        return False


def _get_available_model() -> str:
    """Get the best available Gemini model."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        
        # Prefer gemini-2.5-flash
        preferred_models = [
            'gemini-2.5-flash',
            'gemini-2.5-flash-preview-05-20',
            'gemini-2.0-flash-exp',
            'gemini-2.0-flash',
            'gemini-1.5-flash'
        ]
        
        for model_name in preferred_models:
            try:
                model = genai.GenerativeModel(model_name)
                # Test if model is available
                model.count_tokens("test")
                print(f"Selected OpenSCAD model: {model_name}")
                return model_name
            except Exception:
                continue
        
        return None
    except Exception:
        return None


def _extract_code(text: str) -> str:
    """Extract OpenSCAD code from markdown or plain text."""
    text = text.strip()
    
    # Remove markdown code blocks
    if "```" in text:
        # Find code between ``` markers
        parts = text.split("```")
        for i, part in enumerate(parts):
            if i % 2 == 1:  # Odd indices are code blocks
                # Remove language identifier
                lines = part.strip().split('\n')
                if lines[0].strip().lower() in ['openscad', 'scad', '']:
                    lines = lines[1:]
                return '\n'.join(lines).strip()
    
    return text


def generate_openscad_script(prompt: str) -> Dict[str, Any]:
    """Generate OpenSCAD script from natural language using Gemini.
    
    Args:
        prompt: Natural language description of the CAD model
        
    Returns:
        Dict with 'code', 'error' keys
    """
    if not have_gemini():
        return {'error': 'Gemini API key not configured'}
    
    try:
        import google.generativeai as genai
        global _last_api_call_time
        
        # Rate limiting
        elapsed = time.time() - _last_api_call_time
        if elapsed < _min_call_interval:
            time.sleep(_min_call_interval - elapsed)
        
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        
        model_name = _get_available_model()
        if not model_name:
            return {'error': 'No compatible Gemini models available'}
        
        model = genai.GenerativeModel(
            model_name,
            generation_config={
                'temperature': 0.2,  # Lower temperature for precise code
            },
        )
        
        full_prompt = f"{OPENSCAD_SYSTEM_PROMPT}\n\nUser request: {prompt}\n\nOpenSCAD code:"
        
        _last_api_call_time = time.time()
        response = model.generate_content(full_prompt)
        
        text = getattr(response, 'text', None)
        if not text and getattr(response, 'candidates', None):
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                text = None
        
        if not text:
            return {'error': 'Empty response from Gemini'}
        
        code = _extract_code(text)
        
        return {'code': code}
        
    except Exception as e:
        return {'error': f'Failed to generate script: {str(e)}'}


def fix_openscad_error(failing_code: str, error_message: str, traceback_info: str, original_prompt: str) -> Dict[str, Any]:
    """Fix OpenSCAD code based on execution error feedback.
    
    Args:
        failing_code: The code that failed to execute
        error_message: The error message from execution
        traceback_info: Full traceback/output from OpenSCAD
        original_prompt: The original user request
        
    Returns:
        Dict with 'code', 'error' keys
    """
    if not have_gemini():
        return {'error': 'Gemini API key not configured'}
    
    try:
        import google.generativeai as genai
        global _last_api_call_time
        
        # Rate limiting
        elapsed = time.time() - _last_api_call_time
        if elapsed < _min_call_interval:
            time.sleep(_min_call_interval - elapsed)
        
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        
        model_name = _get_available_model()
        if not model_name:
            return {'error': 'No compatible Gemini models available'}
        
        model = genai.GenerativeModel(
            model_name,
            generation_config={
                'temperature': 0.1,  # Very low temperature for error fixing
            },
        )
        
        # Construct error-fixing prompt
        fix_prompt = f"""🔧 OPENSCAD EXECUTION ERROR - FIX REQUIRED 🔧

Original user request: {original_prompt}

❌ CODE THAT FAILED:
{failing_code}

❌ ERROR MESSAGE:
{error_message}

❌ OPENSCAD OUTPUT:
{traceback_info}

🎯 YOUR TASK:
Analyze the error and generate CORRECTED OpenSCAD code that will render successfully.

COMMON ERRORS & FIXES:
1. Syntax errors → Fix OpenSCAD syntax
2. Zero dimensions → Change to positive values (min 1)
3. Missing parameters → Add required parameters (h, r, etc.)
4. Invalid operations → Use valid CSG operations
5. Undefined variables → Define all variables before use

{OPENSCAD_SYSTEM_PROMPT}

Return ONLY the CORRECTED OpenSCAD code. No markdown, no explanations.
"""
        
        _last_api_call_time = time.time()
        response = model.generate_content(fix_prompt)
        
        text = getattr(response, 'text', None)
        if not text and getattr(response, 'candidates', None):
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                text = None
        
        if not text:
            return {'error': 'Empty response from Gemini'}
        
        code = _extract_code(text)
        
        return {'code': code}
        
    except Exception as e:
        return {'error': f'Failed to fix script: {str(e)}'}


def generate_with_auto_fix(prompt: str, max_retries: int = 3) -> Dict[str, Any]:
    """Generate OpenSCAD code with automatic error correction.
    
    This function implements an intelligent retry loop:
    1. Generate initial code from prompt
    2. Test execution using OpenSCADEngine
    3. If error occurs, feed error back to AI
    4. AI generates fixed version
    5. Retry execution
    6. Continue until success or max retries exceeded
    
    Args:
        prompt: Natural language description of the CAD model
        max_retries: Maximum number of fix attempts (default: 3)
        
    Returns:
        Dict with keys:
        - 'success': True if code rendered successfully
        - 'code': The working code (or last attempt if failed)
        - 'attempts': Number of attempts made
        - 'error': Error message if all attempts failed
        - 'execution_result': Final execution result from OpenSCADEngine
    """
    # Import with proper path handling
    import sys
    from pathlib import Path
    app_dir = str(Path(__file__).parent)
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from openscad_engine import OpenSCADEngine
    
    engine = OpenSCADEngine()
    code = None
    error = None
    traceback_info = None
    
    for attempt in range(1, max_retries + 1):
        # Generate or fix code
        if attempt == 1:
            # First attempt: Generate from prompt
            result = generate_openscad_script(prompt)
        else:
            # Subsequent attempts: Fix based on error
            result = fix_openscad_error(code, error, traceback_info, prompt)
        
        if 'error' in result:
            return {
                'success': False,
                'code': code or '',
                'attempts': attempt,
                'error': f'AI generation error: {result["error"]}'
            }
        
        code = result['code']
        
        # Test execution
        exec_result = engine.execute_script(code)
        
        if exec_result['success']:
            # Success! Return working code
            return {
                'success': True,
                'code': code,
                'attempts': attempt,
                'message': f'Code validated and working (fixed in {attempt} attempt{"s" if attempt > 1 else ""})',
                'execution_result': exec_result
            }
        
        # Extract error info for next iteration
        error = exec_result.get('error', 'Unknown error')
        traceback_info = exec_result.get('traceback', 'No traceback available')
        
        # Log attempt for debugging
        print(f"🔄 Auto-fix attempt {attempt}/{max_retries} failed: {error}")
    
    # All retries exhausted
    return {
        'success': False,
        'code': code,
        'attempts': max_retries,
        'error': f'Max retries ({max_retries}) exceeded. Last error: {error}',
        'last_traceback': traceback_info
    }
