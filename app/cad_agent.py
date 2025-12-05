"""AI Agent for generating and modifying CadQuery scripts using Gemini."""
from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, Optional

# Import Gemini at module level to avoid repeated imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None


_last_api_call_time = 0
_min_call_interval = 6.0  # Minimum seconds between API calls (10 RPM)


CADQUERY_SYSTEM_PROMPT = """You are an expert CAD engineer and CadQuery 2.6.1 code generator. Your ONLY job is to generate GUARANTEED EXECUTABLE CadQuery code.

═══════════════════════════════════════════════════════════
🎯 MISSION: Generate code that NEVER crashes or errors
═══════════════════════════════════════════════════════════

EXECUTION GUARANTEE RULES (MANDATORY):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✅ ALWAYS assign final object to 'result' variable
2. ✅ ALWAYS import cadquery as cq at the top
3. ✅ Import math only if using math.pi, math.sin, math.cos, etc.
4. ✅ Use ONLY CadQuery 2.x compatible APIs (NO deprecated selectors)
5. ✅ Test EVERY selector before using (does it actually select something?)
6. ✅ Use CONSERVATIVE fillet/chamfer sizes (< 30% of edge length)
7. ✅ NEVER assume edge/face selection works - validate the geometry type first
8. ✅ ALWAYS use NON-ZERO dimensions (never 0 length, 0 radius, 0 height)
9. ✅ NEVER create degenerate geometry (zero-volume shapes, coincident points)

═══════════════════════════════════════════════════════════
🚫 CRITICAL: gp_VectorWithNullMagnitude ERROR PREVENTION
═══════════════════════════════════════════════════════════

THIS IS THE #1 CAUSE OF FAILURES. NEVER EVER:
❌ ZERO dimensions: .extrude(0), .circle(0), .sphere(0)
❌ ZERO offsets: .workplane(offset=0) when creating different geometry
❌ SAME start/end points in line operations
❌ ZERO-length extrusions or lofts
❌ Coincident vertices in polygon/polyline operations
❌ Zero-radius circles, spheres, cylinders

✅ ALWAYS ENSURE:
- All dimensions > 0.1mm minimum
- Extrude heights ≥ 1mm
- Circle/sphere radii ≥ 1mm  
- Offset workplanes by at least 1mm when creating different geometry
- All polyline/polygon points are distinct (not coincident)

═══════════════════════════════════════════════════════════
🚫 FORBIDDEN APIS (Will cause immediate crash)
═══════════════════════════════════════════════════════════

❌ cq.selectors.StringSelector(">Z")  → Use ">Z" directly
❌ cq.selectors.DirectionMinMaxSelector() → Removed in 2.0+
❌ .edges().fillet()  → Must select specific edges first
❌ .fillet(50) on 10mm edge → Radius too large
❌ .edges("|Z").fillet() on cylinders → Cylinders have no discrete vertical edges
❌ .extrude(0) → NULL MAGNITUDE ERROR
❌ .circle(0) → NULL MAGNITUDE ERROR
❌ .workplane(offset=0) then different geometry → RISK OF NULL MAGNITUDE

═══════════════════════════════════════════════════════════
🎯 GEOMETRY-SPECIFIC RULES (Critical for success)
═══════════════════════════════════════════════════════════

📦 BOXES (.box(), .rect().extrude()):
✅ .edges("|Z").fillet(r)    # Vertical edges
✅ .edges(">Z").fillet(r)    # Top edges
✅ .edges("<Z").fillet(r)    # Bottom edges
✅ .edges("#Z").fillet(r)    # Horizontal edges

🔵 CYLINDERS (.circle().extrude()):
❌ .edges("|Z").fillet(r)    # NO! Cylinders have no discrete vertical edges
❌ .edges().fillet(r)        # Will select nothing and crash
✅ .faces(">Z").chamfer(r)   # Chamfer top circular edge
✅ .faces("<Z").chamfer(r)   # Chamfer bottom circular edge
✅ .faces(">Z").fillet(r)    # Fillet top face (if needed)

⚪ SPHERES (.sphere()):
❌ .edges().fillet()         # Spheres have no edges
✅ Use as-is or boolean operations only

🔷 CONES (.circle().workplane().circle().loft()):
❌ .cone()                   # NOT A VALID METHOD! Use loft instead
❌ cq.Workplane("XY").cone() # DOES NOT EXIST!
❌ .edges("|Z").fillet()     # Variable geometry, unreliable
✅ .circle().workplane(offset>0).circle().loft()  # Correct way to make cone
✅ .faces(">Z").chamfer(r)   # Safer to chamfer faces

📐 CUSTOM SKETCHES (.polygon(), custom shapes):
✅ Always test with simple operations first
✅ Use .faces(">Z") instead of edge selection when unsure
✅ Chamfer is safer than fillet for complex geometries

═══════════════════════════════════════════════════════════
🚨 METHODS THAT DON'T EXIST (WILL CRASH)
═══════════════════════════════════════════════════════════

❌ .cone() - DOES NOT EXIST! Use .circle().workplane().circle().loft()
❌ .cylinder() - DOES NOT EXIST! Use .circle().extrude()
❌ .sphere() - THIS ONE EXISTS! cq.Workplane("XY").sphere(radius)
❌ .torus() - DOES NOT EXIST! Use revolve operations
❌ .prism() - DOES NOT EXIST! Use polygon().extrude()

✅ CORRECT PRIMITIVES:
- Box: .box(length, width, height) ✓
- Cylinder: .circle(radius).extrude(height) ✓
- Sphere: .sphere(radius) ✓
- Cone: .circle(r1).workplane(offset=h).circle(r2).loft() ✓

═══════════════════════════════════════════════════════════
✅ GUARANTEED SAFE PATTERNS
═══════════════════════════════════════════════════════════

# BOX with rounded edges (SAFE):
import cadquery as cq
result = (cq.Workplane("XY")
    .box(50, 40, 30)
    .edges("|Z").fillet(2)  # Vertical edges only, conservative radius
)

# CYLINDER with chamfered top (SAFE):
import cadquery as cq
result = (cq.Workplane("XY")
    .circle(20)
    .extrude(40)
    .faces(">Z").chamfer(1.5)  # Chamfer face, NOT edges
)

# BRACKET with holes (SAFE):
import cadquery as cq
result = (cq.Workplane("XY")
    .rect(80, 60).extrude(5)
    .faces(">Z").workplane()
    .rect(60, 40, forConstruction=True).vertices().hole(6)
)

# SPHERE (SAFE - no edge operations):
import cadquery as cq
result = cq.Workplane("XY").sphere(25)

# CONE using loft (SAFE):
import cadquery as cq
result = (cq.Workplane("XY")
    .circle(20)
    .workplane(offset=40)  # MUST be > 0!
    .circle(10)
    .loft()
    .faces(">Z").chamfer(1)  # Chamfer top, safe
)

# ROCKET (SAFE - Common request):
import cadquery as cq
import math

# Body cylinder
body = (cq.Workplane("XY")
    .circle(15)  # Body radius
    .extrude(100)  # Body height - NEVER 0!
)

# Nose cone
nose = (cq.Workplane("XY")
    .workplane(offset=100)  # Start where body ends - NEVER 0!
    .circle(15)  # Base radius matches body
    .workplane(offset=30)  # Nose height - MUST be > 0!
    .circle(0.1)  # Tiny tip (NOT 0!)
    .loft()
)

# Fins (using solid geometry, not surfaces)
fin = (cq.Workplane("XZ")
    .moveTo(0, 10)  # All points MUST be distinct!
    .lineTo(20, 10)
    .lineTo(20, 30)
    .lineTo(0, 20)
    .close()
    .extrude(2)  # Fin thickness - NEVER 0!
)

# Combine all parts
result = body.union(nose).union(fin)

# Alternative SIMPLE ROCKET (if complex version fails):
import cadquery as cq
result = (cq.Workplane("XY")
    .circle(15)
    .extrude(100)  # Body
    .faces(">Z").workplane()
    .circle(15)
    .workplane(offset=30)  # MUST be > 0!
    .circle(1)  # NOT 0!
    .loft()  # Nose cone
)

# SMARTPHONE / iPHONE (SAFE - Common request):
import cadquery as cq

# Simple rounded rectangle body
body = (cq.Workplane("XY")
    .rect(70, 145)  # Width x Height
    .extrude(8)  # Thickness
    .edges("|Z")  # Vertical edges
    .fillet(4)  # Rounded corners
)

# Screen bezel (raised edges, not cut)
screen_area = (cq.Workplane("XY")
    .workplane(offset=8)  # On top surface
    .center(0, 5)  # Slightly offset up
    .rect(60, 120)  # Screen dimensions
    .extrude(0.5)  # Slight raise
)

result = body.union(screen_area)

# Alternative FLAT SMARTPHONE (if screen raises cause issues):
import cadquery as cq
result = (cq.Workplane("XY")
    .rect(70, 145)
    .extrude(8)
    .edges("|Z").fillet(4)
)

# BOTTLE (SAFE):
import cadquery as cq
body = cq.Workplane("XY").circle(25).extrude(80)
neck = body.faces(">Z").workplane().circle(10).extrude(30)
result = body.union(neck)

═══════════════════════════════════════════════════════════
🧪 VALIDATION CHECKLIST (Run mentally before generating)
═══════════════════════════════════════════════════════════

Before generating code, ask yourself:
1. ✓ ALL dimensions > 0? (No zeros anywhere!)
2. ✓ Is this a cylinder? → Use .faces().chamfer() NOT .edges().fillet()
3. ✓ Am I using fillet/chamfer? → Are edges selected first?
4. ✓ Is fillet radius < 30% of smallest dimension?
5. ✓ Am I using deprecated selectors? → Use string selectors
6. ✓ Does 'result' variable exist at the end?
7. ✓ Are all imports present (cq, math if needed)?
8. ✓ All workplane offsets > 0 when creating different geometry?
9. ✓ No coincident points in polygons/polylines?
10. ✓ Would this code run without errors on CadQuery 2.6.1?

IF ANY ANSWER IS NO → FIX BEFORE GENERATING!

═══════════════════════════════════════════════════════════
📝 OUTPUT FORMAT
═══════════════════════════════════════════════════════════

Return ONLY executable Python code. NO markdown, NO explanations, NO ```python``` tags.
Just pure Python code that can be executed immediately.

MANDATORY RULES:
1. ✅ import cadquery as cq (always first line)
2. ✅ Import math if using math functions
3. ✅ result = ... (assign final object)
4. ✅ Comments explaining the design
5. ✅ Conservative dimensions and radii
6. ✅ Geometry-appropriate operations (chamfer cylinders, fillet boxes)
7. ✅ NO deprecated APIs, NO risky selectors
8. ✅ Code that NEVER crashes"""


EDIT_SYSTEM_PROMPT = """You are an expert CAD engineer modifying existing CadQuery 2.6.1 scripts.

MISSION: Modify code while GUARANTEEING it remains executable.

Given:
1. Current working CadQuery script
2. User's modification request

Your task:
- Understand the current design and geometry type
- Apply changes intelligently based on geometry (cylinder vs box vs custom)
- Maintain code quality and EXECUTION GUARANTEE
- Preserve existing features unless explicitly asked to change
- Use geometry-appropriate operations (chamfer for cylinders, fillet for boxes)
- Return ONLY executable Python code

CRITICAL - Same rules as code generation:
✅ Cylinders → .faces().chamfer() NOT .edges().fillet()
✅ Boxes → .edges().fillet() OK
✅ Select edges before fillet/chamfer
✅ Conservative radii (< 30% of dimension)
✅ NO deprecated APIs
✅ Assign to 'result' variable

Return ONLY Python code, no markdown, no explanations.

Example - Simple box with rounded edges:
import cadquery as cq

result = (cq.Workplane("XY")
    .box(50, 40, 30)
    .edges("|Z").fillet(2)  # Use string selector, not StringSelector
)

# Cylinder with hole
result = (cq.Workplane("XY")
    .circle(25)
    .extrude(50)
    .faces(">Z").workplane()  # String selector for top face
    .hole(10)
)

# Cylinder with chamfered edges (CORRECT METHOD!)
# ⚠️ IMPORTANT: Cylinders don't have selectable vertical edges
# Use .faces(">Z").chamfer() or .faces("<Z").chamfer() instead
result = (cq.Workplane("XY")
    .circle(20)
    .extrude(40)
    .faces(">Z").chamfer(1.5)  # Chamfer top face edge
    .faces("<Z").chamfer(1.5)  # Chamfer bottom face edge
)

# ❌ NEVER do this for cylinders: .edges("|Z").fillet(2)
# Cylinders created with .circle().extrude() don't have discrete vertical edges!

# Bracket with mounting holes
result = (cq.Workplane("XY")
    .rect(80, 60)
    .extrude(5)
    .faces(">Z").workplane()
    .rect(60, 40, forConstruction=True)
    .vertices()
    .hole(6)
    .edges("|Z").fillet(3)  # Conservative fillet radius
)

# Gear with teeth (using math)
import math
result = (cq.Workplane("XY")
    .circle(30)
    .extrude(10)
    .faces(">Z").workplane()
    .polarArray(20, 0, 360, 16)  # 16 teeth
    .rect(3, 8)
    .cutThruAll()
)

Example code ends here.
"""


EDIT_SYSTEM_PROMPT = """You are an expert CAD engineer modifying existing CadQuery 2.x+ scripts.

Given:
1. Current CadQuery script
2. User's modification request

Your task:
- Understand the current design
- Apply the requested changes intelligently
- Maintain code quality and engineering principles
- Preserve existing features unless explicitly asked to change
- Ensure CadQuery 2.x+ and OCCT compatibility
- Return ONLY the modified Python code, no explanations

CRITICAL - CadQuery 2.x+ Compatibility:
⚠️ NEVER use:
- cq.selectors.StringSelector() - REMOVED in CadQuery 2.0+
- cq.selectors.DirectionMinMaxSelector() - REMOVED

✅ Use string selectors directly:
- .edges(">Z") NOT .edges(cq.selectors.StringSelector(">Z"))
- .faces("<X") NOT .faces(cq.selectors.DirectionMinMaxSelector(...))

Mandatory Rules:
1. ✅ Keep 'import cadquery as cq' at the top
2. ✅ Import math if using math functions
3. ✅ Assign result to 'result' variable
4. ✅ Use string selectors directly (">Z", "|Y", "#X")
5. ✅ Use conservative fillet/chamfer radii
6. ✅ Maintain or improve code comments
7. ✅ Use realistic engineering dimensions
8. ✅ Return executable Python code only (no markdown)
9. ✅ Ensure compatibility with CadQuery 2.x+ and OCCT
"""


def have_gemini() -> bool:
    """Check if Gemini API is configured."""
    return GEMINI_AVAILABLE and bool(os.environ.get("GEMINI_API_KEY"))


def generate_cadquery_script(prompt: str) -> Dict[str, Any]:
    """Generate a CadQuery script from natural language using Gemini.
    
    Args:
        prompt: Natural language description of the CAD model
        
    Returns:
        Dict with 'code', 'error' keys
    """
    if not have_gemini():
        return {'error': 'Gemini API key not configured'}
    
    try:
        global _last_api_call_time
        
        # Rate limiting
        elapsed = time.time() - _last_api_call_time
        if elapsed < _min_call_interval:
            time.sleep(_min_call_interval - elapsed)
        
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        
        # Try to get an available model
        model_name = _get_available_model()
        if not model_name:
            return {'error': 'No compatible Gemini models available'}
        
        model = genai.GenerativeModel(
            model_name,
            generation_config={
                'temperature': 0.2,  # Lower temperature for more precise code
            },
        )
        
        full_prompt = f"{CADQUERY_SYSTEM_PROMPT}\n\nUser request: {prompt}\n\nCadQuery Python code:"
        
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
        
        # Extract code from markdown if needed
        code = _extract_code(text)
        
        return {'code': code}
        
    except Exception as e:
        return {'error': f'Failed to generate script: {str(e)}'}


def fix_cadquery_error(failing_code: str, error_message: str, traceback_info: str, original_prompt: str) -> Dict[str, Any]:
    """Fix CadQuery code based on execution error feedback.
    
    Args:
        failing_code: The code that failed to execute
        error_message: The error message from execution
        traceback_info: Full traceback from execution
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
        
        # Construct error-fixing prompt with detailed guidance
        fix_prompt = f"""🔧 CADQUERY EXECUTION ERROR - INTELLIGENT FIX REQUIRED 🔧

Original user request: {original_prompt}

❌ CODE THAT FAILED TO EXECUTE:
```python
{failing_code}
```

❌ ERROR MESSAGE:
{error_message}

❌ FULL TRACEBACK:
{traceback_info}

🎯 YOUR TASK:
You are an expert CadQuery debugger. Analyze this specific error and generate CORRECTED code.

🔍 ERROR ANALYSIS CHECKLIST:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **gp_VectorWithNullMagnitude** (Most common):
   - Caused by: .extrude(0), .circle(0), .sphere(0), coincident points
   - Fix: Change ALL 0 dimensions to positive (min 1mm)
   - Check: All extrude heights, circle radii, workplane offsets

2. **ValueError: Cannot cut type** (Type mismatch):
   - Caused by: Cutting wrong type (float, int) instead of Workplane
   - Fix: Ensure all objects are Workplanes before .cut()/.union()
   - Example: 
     ❌ result.cut(5) → ✅ result.cut(cq.Workplane("XY").box(5,5,5))

3. **AttributeError: 'Workplane' object has no attribute 'X'**:
   - Caused by: Using non-existent methods
   - Fix: Use only valid CadQuery 2.x methods
   - Check: .cutExtrude() doesn't exist → use .extrude().cut() separately

4. **Selection errors** ("no edges/faces selected"):
   - Caused by: Invalid selectors or geometry doesn't have requested feature
   - Fix: Use different selector or check if geometry supports it
   - Cylinders: Use faces(">Z") not edges("|Z")
   - Boxes: edges("|Z") works fine

5. **StdFail_NotDone** (Boolean operation failed):
   - Caused by: Geometries don't intersect properly for cut/union
   - Fix: Check positioning with .translate(), ensure overlap
   - Add workplane context: .faces(">Z").workplane() before operations

🛠️ SPECIFIC FIX STRATEGIES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For SMARTPHONES (if original prompt mentions smartphone/phone/iPhone):
```python
import cadquery as cq

# Safe smartphone template
body = cq.Workplane("XY").box(70, 145, 8).edges("|Z").fillet(2)

# Screen (as separate feature, not cut)
screen = body.faces(">Z").workplane(offset=-1).center(0, 5).rect(60, 120).extrude(1)

# Combine
result = body
```

For BOTTLES/CONTAINERS (if mentions bottle/container/cup):
```python
import cadquery as cq

# Safe bottle template
body = cq.Workplane("XY").circle(25).extrude(80)
neck = body.faces(">Z").workplane().circle(10).extrude(30)
result = body.union(neck)
```

For GEARS (if mentions gear/cog):
```python
import cadquery as cq

# Safe gear template
result = cq.Workplane("XY").polygon(8, 20).extrude(5)
```

🚨 CRITICAL RULES:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ✅ NEVER use 0 dimensions anywhere
2. ✅ Import cadquery as cq at top
3. ✅ Assign final result to 'result' variable
4. ✅ Use .faces(">Z").workplane() before creating new features on top
5. ✅ For cuts, ensure geometries actually overlap in 3D space
6. ✅ Keep it simple - complex code = more errors
7. ✅ Use union() instead of complex cut() when possible
8. ✅ Test each operation mentally: "does this geometry exist?"

{CADQUERY_SYSTEM_PROMPT}

NOW GENERATE THE CORRECTED CODE:
Return ONLY executable Python code. No markdown, no explanations, no comments except essential ones.
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
        
        # Extract code from markdown if needed
        code = _extract_code(text)
        
        return {'code': code}
        
    except Exception as e:
        return {'error': f'Failed to fix script: {str(e)}'}


def generate_with_auto_fix(prompt: str, max_retries: int = 3) -> Dict[str, Any]:
    """Generate CadQuery code with automatic error correction.
    
    This function implements an intelligent retry loop:
    1. Generate initial code from prompt
    2. Test execution using CADEngine
    3. If error occurs, feed error back to AI
    4. AI generates fixed version
    5. Retry execution
    6. Continue until success or max retries exceeded
    
    Args:
        prompt: Natural language description of the CAD model
        max_retries: Maximum number of fix attempts (default: 3)
        
    Returns:
        Dict with keys:
        - 'success': True if code executed successfully
        - 'code': The working code (or last attempt if failed)
        - 'attempts': Number of attempts made
        - 'error': Error message if all attempts failed
        - 'execution_result': Final execution result from CADEngine
    """
    # Import with proper path handling
    import sys
    from pathlib import Path
    app_dir = str(Path(__file__).parent)
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from cad_engine import CADEngine
    
    engine = CADEngine()
    code = None
    error = None
    traceback_info = None
    
    for attempt in range(1, max_retries + 1):
        # Generate or fix code
        if attempt == 1:
            # First attempt: Generate from prompt
            result = generate_cadquery_script(prompt)
        else:
            # Subsequent attempts: Fix based on error
            result = fix_cadquery_error(code, error, traceback_info, prompt)
        
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


def modify_cadquery_script(current_script: str, modification: str) -> Dict[str, Any]:
    """Modify existing CadQuery script based on natural language instruction.
    
    Args:
        current_script: Current CadQuery Python code
        modification: Natural language description of changes
        
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
                'temperature': 0.2,
            },
        )
        
        full_prompt = f"{EDIT_SYSTEM_PROMPT}\n\nCurrent script:\n```python\n{current_script}\n```\n\nModification request: {modification}\n\nModified CadQuery Python code:"
        
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
        return {'error': f'Failed to modify script: {str(e)}'}


def _extract_code(text: str) -> str:
    """Extract Python code from markdown or raw text."""
    # Remove markdown code blocks
    if '```python' in text:
        parts = text.split('```python')
        if len(parts) > 1:
            code_part = parts[1].split('```')[0]
            return code_part.strip()
    elif '```' in text:
        parts = text.split('```')
        if len(parts) > 1:
            return parts[1].strip()
    
    return text.strip()


_cached_model_name = None

def _get_available_model() -> Optional[str]:
    """Get an available Gemini model (cached)."""
    global _cached_model_name
    if _cached_model_name:
        return _cached_model_name
    
    import google.generativeai as genai
    
    # List available models from API
    try:
        available_models = []
        print("Listing available Gemini models...")
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                available_models.append(model.name)
                print(f"  Found: {model.name}")
        
        # Prefer Flash models (higher free tier quotas)
        preferred_order = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-flash-latest",
            "gemini-1.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash-lite",
        ]
        
        for preferred in preferred_order:
            for available in available_models:
                # Check if preferred model name is in the available model
                if preferred in available:
                    print(f"Selected model: {available}")
                    _cached_model_name = available
                    return available
        
        # If no preferred model found, use first available
        if available_models:
            print(f"Using first available model: {available_models[0]}")
            _cached_model_name = available_models[0]
            return available_models[0]
            
    except Exception as e:
        print(f"Error listing models: {e}")
        import traceback
        traceback.print_exc()
    
    # Fallback to try common models with proper prefix
    test_models = [
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.5-pro-latest", 
        "gemini-1.5-pro",
        "gemini-pro",
    ]
    
    print("Trying fallback models...")
    for model_name in test_models:
        try:
            print(f"  Trying: {model_name}")
            _cached_model_name = model_name
            return model_name
        except Exception:
            continue
    
    return None


def edit_with_context(current_code: str, edit_instruction: str, preserve_measurements: bool = True) -> Dict[str, str]:
    """
    Edit existing code while preserving context and measurements.
    This is the robust way to modify existing models.
    
    Args:
        current_code: The existing CadQuery code
        edit_instruction: What to change (e.g., "add a hole in the center", "make it taller")
        preserve_measurements: If True, try to keep measurement variables unchanged
    
    Returns:
        Dict with 'code' or 'error'
    """
    if not have_gemini():
        return {"error": "Gemini API key not configured"}
    
    try:
        import google.generativeai as genai
        from .cad_validator import extract_measurements_from_code, validate_cadquery_code, auto_fix_code
        
        global _last_api_call_time
        
        # Rate limiting
        elapsed = time.time() - _last_api_call_time
        if elapsed < _min_call_interval:
            time.sleep(_min_call_interval - elapsed)
        
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        
        # Extract current measurements
        measurements = extract_measurements_from_code(current_code) if preserve_measurements else {}
        
        model_name = _get_available_model()
        if not model_name:
            return {"error": "No Gemini model available"}
        
        model = genai.GenerativeModel(
            model_name,
            generation_config={'temperature': 0.2}
        )
        
        context_prompt = f"""You are modifying an existing CadQuery design. 

CURRENT CODE:
```python
{current_code}
```

USER REQUEST: {edit_instruction}

INSTRUCTIONS:
1. Understand the current design structure
2. Apply ONLY the requested changes
3. Preserve all other features and measurements unless explicitly asked to change them
4. Maintain code quality and CadQuery 2.x+ compatibility
5. If the request is unclear, make reasonable engineering decisions

CURRENT MEASUREMENTS (preserve these unless asked to change):
{json.dumps(measurements, indent=2)}

Return ONLY the complete modified Python code, no explanations, no markdown.
The code must be executable and compatible with CadQuery 2.x+ and OCCT.
"""
        
        _last_api_call_time = time.time()
        response = model.generate_content(context_prompt)
        
        text = getattr(response, 'text', None)
        if not text and getattr(response, 'candidates', None):
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                text = None
        
        if not text:
            return {"error": "Empty response from Gemini"}
        
        code = _extract_code(text)
        
        if not code:
            return {"error": "Failed to extract code from response"}
        
        # Validate the generated code
        validation = validate_cadquery_code(code)
        if not validation["valid"]:
            # Try to auto-fix
            code, fixes = auto_fix_code(code, validation)
            
            # Re-validate
            validation = validate_cadquery_code(code)
            if not validation["valid"]:
                error_msg = "\n".join(validation["errors"])
                return {"error": f"Generated invalid code: {error_msg}", "code": code}
        
        return {"code": code}
        
    except Exception as e:
        import traceback
        return {"error": f"Context-aware edit failed: {str(e)}", "traceback": traceback.format_exc()}

