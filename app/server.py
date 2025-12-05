from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List
import secrets
import shutil
import urllib.request
import mimetypes

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

# Import heavy libraries once at startup to avoid delays
import google.generativeai as genai
from PIL import Image
import io
import base64

# Configure Gemini API once at startup
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Add current directory to path for imports when running as script
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))


def safe_import(module_name: str, item_names: list[str] = None):
    """
    Safely import modules that work both as relative imports (package) and absolute (script).
    """
    # Ensure the app directory is in sys.path for absolute imports
    app_dir = str(Path(__file__).parent)
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    
    try:
        # Simple absolute import (works when app dir is in sys.path)
        module = __import__(module_name, fromlist=item_names or [])
        if item_names:
            return tuple(getattr(module, name) for name in item_names)
        return module
    except Exception as e:
        # Log the error for debugging
        print(f"Warning: Failed to import {module_name}: {e}")
        raise ImportError(f"Could not import {module_name}: {e}")



# JSON IR Schema for CAD objects
CAD_IR_SCHEMA = {
    "type": "object",
    "properties": {
        "units": {"type": "string", "enum": ["mm", "cm", "in"]},
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": ["box", "cylinder", "sphere", "cone", "torus"]},
                    "origin": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    "w": {"type": "number"},
                    "d": {"type": "number"},
                    "h": {"type": "number"},
                    "r": {"type": "number"},
                    "r2": {"type": "number"},
                    "axis": {"type": "string", "enum": ["X", "Y", "Z"]},
                    "ops": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {"type": "string", "enum": ["fillet", "chamfer", "hole", "cut", "union"]},
                                "radius": {"type": "number"},
                                "distance": {"type": "number"},
                                "position": {"type": "array", "items": {"type": "number"}},
                                "target": {"type": "string"}
                            }
                        }
                    }
                },
                "required": ["id", "type", "origin"]
            }
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "object"}
    },
    "required": ["units", "objects"]
}


BASE = Path(__file__).parent
app = FastAPI(
    title="Text2Mesh – Parametric CAD",
    description="AI-powered 3D parametric CAD modeling tool",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers to always return JSON
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": f"Internal server error: {str(exc)}"}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": f"Validation error: {str(exc)}"}
    )

UPLOAD_DIR = BASE / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/models", StaticFiles(directory=str(UPLOAD_DIR)), name="models")

# Chat history storage (in-memory, per session)
# In production, use Redis or database
chat_sessions: dict[str, list[dict]] = {}

def get_or_create_session(session_id: str) -> list[dict]:
    """Get or create a chat session history."""
    if session_id not in chat_sessions:
        chat_sessions[session_id] = []
    return chat_sessions[session_id]

def add_to_history(session_id: str, role: str, content: str, code: str = None, has_image: bool = False):
    """Add a message to the session history with image indicator."""
    history = get_or_create_session(session_id)
    entry = {
        "role": role,
        "content": content,
        "has_image": has_image
    }
    if code:
        entry["code"] = code
    history.append(entry)
    # Keep only last 8 messages (user + assistant pairs) to maintain context
    if len(history) > 8:
        chat_sessions[session_id] = history[-8:]

def build_context_from_history(session_id: str, current_code: str = None) -> str:
    """Build context string from conversation history and current code."""
    history = get_or_create_session(session_id)
    
    if not history and not current_code:
        return ""
    
    context = ""
    
    # Add conversation history
    if history:
        context = "\n\nCONVERSATION HISTORY:\n"
        for entry in history:
            if entry['role'] == 'user':
                user_msg = entry['content']
                if entry.get('has_image'):
                    user_msg += " [with image reference]"
                context += f"User: {user_msg}\n"
            elif entry['role'] == 'assistant':
                if 'code' in entry:
                    # Show truncated code preview
                    code_preview = entry['code'][:150] + "..." if len(entry['code']) > 150 else entry['code']
                    context += f"Assistant: {entry['content']}\nGenerated code preview:\n```python\n{code_preview}\n```\n"
                else:
                    context += f"Assistant: {entry['content']}\n"
    
    # Add current code context
    if current_code and current_code.strip():
        context += f"\n\nCURRENT CODE IN EDITOR:\n```python\n{current_code}\n```\n"
    
    return context


def generate_from_image_with_auto_fix(image: Any, prompt: str, context: str = "", max_retries: int = 5) -> Dict[str, Any]:
    """
    Generate CadQuery code from an image with automatic error fixing.
    
    Args:
        image: PIL Image object
        prompt: User's text prompt describing what to generate or modify
        context: Conversation history context
        max_retries: Maximum number of attempts (default 5)
        
    Returns:
        Dict with keys:
        - 'success': True if code executed successfully
        - 'code': The working code (or last attempt if failed)
        - 'attempts': Number of attempts made
        - 'error': Error message if all attempts failed
        - 'execution_result': Final execution result from CADEngine
    """
    # Import CADEngine for validation
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
            # First attempt: Generate from image
            full_prompt = f"{context}\n\nNEW REQUEST: {prompt if prompt else 'Create a 3D CAD model from this image'}"
            
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            system_instruction = """You are an expert CAD engineer. Generate CadQuery Python code to create 3D models.

RULES:
- Analyze the image carefully and create accurate 3D models
- Use realistic dimensions (if it's a cup, make it cup-sized!)
- ALWAYS include: import cadquery as cq
- ALWAYS end with: result = [your final shape]
- Use clear variable names
- Add comments explaining the design
- Listen to user feedback and improve the model based on their corrections
- NEVER use zero dimensions or degenerate geometry
- Ensure all extrusions, circles, spheres have positive non-zero values

Output ONLY executable Python code, no explanations."""

            response = model.generate_content([
                system_instruction,
                full_prompt,
                image
            ])
            
            code = response.text.strip()
            
            # Clean up code (remove markdown code blocks if present)
            if '```python' in code:
                code = code.split('```python')[1].split('```')[0].strip()
            elif '```' in code:
                code = code.split('```')[1].split('```')[0].strip()
        else:
            # Retry: Fix the code based on error
            fix_prompt = f"""The following CadQuery code from the image failed to execute.

IMAGE CONTEXT: {prompt if prompt else 'User uploaded an image for 3D CAD model generation'}

FAILING CODE:
```python
{code}
```

ERROR:
{error}

TRACEBACK:
{traceback_info}

Fix the code to make it executable. Common issues:
- Zero dimensions (use positive values)
- Missing imports
- Wrong CadQuery API usage
- Degenerate geometry

Output ONLY the fixed executable Python code, no explanations."""

            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content([fix_prompt, image])
            
            code = response.text.strip()
            
            # Clean up code
            if '```python' in code:
                code = code.split('```python')[1].split('```')[0].strip()
            elif '```' in code:
                code = code.split('```')[1].split('```')[0].strip()
        
        # Test the code
        result = engine.execute_script(code)
        
        if result['success']:
            return {
                'success': True,
                'code': code,
                'attempts': attempt,
                'execution_result': result
            }
        else:
            error = result.get('error', 'Unknown error')
            traceback_info = result.get('traceback', '')
    
    # All attempts failed
    return {
        'success': False,
        'code': code,
        'attempts': max_retries,
        'error': f'Failed after {max_retries} attempts. Last error: {error}',
        'execution_result': result
    }


def ir_to_cadquery(ir: Dict[str, Any]) -> str:
    """
    Deterministic IR → CadQuery code generator.
    Takes a JSON intermediate representation and produces executable CadQuery code.
    """
    lines = ["import cadquery as cq", ""]
    
    # Add comments from assumptions
    if "assumptions" in ir and ir["assumptions"]:
        lines.append("# Assumptions:")
        for assumption in ir["assumptions"]:
            lines.append(f"#   - {assumption}")
        lines.append("")
    
    # Generate objects
    objects_code = {}
    for obj in ir.get("objects", []):
        obj_id = obj["id"]
        obj_type = obj["type"]
        origin = obj.get("origin", [0, 0, 0])
        
        obj_lines = []
        
        # Create workplane
        obj_lines.append(f"{obj_id} = cq.Workplane('XY')")
        
        # Apply origin offset if needed
        if origin != [0, 0, 0]:
            obj_lines.append(f"{obj_id} = {obj_id}.workplane(offset={origin[2]})")
            if origin[0] != 0 or origin[1] != 0:
                obj_lines.append(f"{obj_id} = {obj_id}.center({origin[0]}, {origin[1]})")
        
        # Create primitive
        if obj_type == "box":
            w, d, h = obj.get("w", 10), obj.get("d", 10), obj.get("h", 10)
            obj_lines.append(f"{obj_id} = {obj_id}.box({w}, {d}, {h})")
        
        elif obj_type == "cylinder":
            r, h = obj.get("r", 5), obj.get("h", 10)
            obj_lines.append(f"{obj_id} = {obj_id}.circle({r}).extrude({h})")
        
        elif obj_type == "sphere":
            r = obj.get("r", 5)
            obj_lines.append(f"{obj_id} = {obj_id}.sphere({r})")
        
        elif obj_type == "cone":
            r, r2, h = obj.get("r", 10), obj.get("r2", 5), obj.get("h", 10)
            # Cone as a lofted shape
            obj_lines.append(f"{obj_id} = {obj_id}.circle({r}).workplane(offset={h}).circle({r2}).loft()")
        
        elif obj_type == "torus":
            r, r2 = obj.get("r", 10), obj.get("r2", 2)
            obj_lines.append(f"{obj_id} = {obj_id}.circle({r + r2}).circle({r - r2}).extrude(0.1)")
        
        # Apply operations
        for op in obj.get("ops", []):
            op_type = op["op"]
            
            if op_type == "fillet":
                radius = op.get("radius", 1)
                obj_lines.append(f"{obj_id} = {obj_id}.edges().fillet({radius})")
            
            elif op_type == "chamfer":
                distance = op.get("distance", 1)
                obj_lines.append(f"{obj_id} = {obj_id}.edges().chamfer({distance})")
            
            elif op_type == "hole":
                position = op.get("position", [0, 0])
                radius = op.get("radius", 2)
                depth = op.get("depth", 10)
                obj_lines.append(f"{obj_id} = {obj_id}.faces('>Z').workplane().center({position[0]}, {position[1]}).hole({radius * 2}, {depth})")
            
            elif op_type == "cut":
                target = op.get("target", "")
                if target:
                    obj_lines.append(f"{obj_id} = {obj_id}.cut({target})")
            
            elif op_type == "union":
                target = op.get("target", "")
                if target:
                    obj_lines.append(f"{obj_id} = {obj_id}.union({target})")
        
        objects_code[obj_id] = obj_lines
    
    # Write all object code
    for obj_id, obj_lines in objects_code.items():
        lines.extend(obj_lines)
        lines.append("")
    
    # Combine all objects into result
    if objects_code:
        first_obj = list(objects_code.keys())[0]
        if len(objects_code) == 1:
            lines.append(f"result = {first_obj}")
        else:
            # Union all objects
            other_objs = list(objects_code.keys())[1:]
            lines.append(f"result = {first_obj}")
            for obj_id in other_objs:
                lines.append(f"result = result.union({obj_id})")
    else:
        # Fallback: create a simple box
        lines.append("result = cq.Workplane('XY').box(10, 10, 10)")
    
    return "\n".join(lines)


def generate_ir_from_image(image: Any, prompt: str, context: str = "") -> Dict[str, Any]:
    """
    Generate JSON IR from image using Gemini with constrained output.
    Uses JSON schema to force structured output.
    """
    # Gemini API already configured at startup
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set. Please set your Gemini API key.")
    
    system_prompt = f"""You are an expert CAD engineer converting images into precise 3D models.

Analyze the image carefully and convert it into a JSON intermediate representation (IR) for CAD modeling.

OUTPUT SCHEMA:
{json.dumps(CAD_IR_SCHEMA, indent=2)}

CRITICAL RULES:
1. **Analyze Carefully**: Study the image to identify all major shapes, proportions, and features
2. **Units**: Always use "mm" as the unit
3. **Primitive Selection**: 
   - Choose the RIGHT primitive for each part (box, cylinder, sphere, cone, torus)
   - Use cylinders for round parts, boxes for rectangular parts
4. **Dimensions**: 
   - Estimate realistic dimensions based on visible proportions
   - If you see a recognizable object (cup, box, etc.), use realistic sizes
   - Document all dimensional assumptions
5. **Origins**: 
   - Place origins strategically for proper alignment
   - Use [0, 0, 0] for the main base object
   - Offset other objects relative to the base
6. **Operations**:
   - Use "fillet" for rounded edges (specify radius)
   - Use "chamfer" for beveled edges (specify distance)
   - Use "hole" for cylindrical holes (specify position, radius, depth)
   - Use "cut" to subtract one object from another
   - Use "union" to combine objects
7. **Assumptions**: 
   - List ANY assumptions you make about dimensions, features, or proportions
   - Be honest about uncertainty
8. **Quality**: Aim for a model that closely resembles the input image

{context}"""

    user_prompt = f"""Analyze this image and create a detailed CAD model.

User instructions: {prompt if prompt else "Create an accurate 3D model of the object in the image"}

Steps:
1. Identify the main object and its basic shape
2. Estimate realistic dimensions (if it's a cup, make it cup-sized!)
3. Break down the object into primitive shapes (boxes, cylinders, etc.)
4. Add operations for details (holes, fillets, chamfers)
5. List all assumptions you made

Output ONLY the JSON IR - no explanations, no markdown."""

    model = genai.GenerativeModel(
        'gemini-2.5-flash',
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.1  # Lower temperature for more consistent output
        }
    )
    
    response = model.generate_content([system_prompt, user_prompt, image])
    ir_json = response.text.strip()
    
    # Parse and validate
    try:
        ir = json.loads(ir_json)
        return ir
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse IR JSON: {e}")


def repair_ir_from_feedback(ir: Dict[str, Any], feedback: str, image: Any) -> Dict[str, Any]:
    """
    Repair IR based on validation/comparison feedback.
    """
    # Gemini API already configured at startup
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    repair_prompt = f"""You repair JSON IRs for CAD.

Previous IR:
{json.dumps(ir, indent=2)}

Failure report:
{feedback}

Return ONLY corrected JSON IR. Keep unchanged fields as-is.
Output must match this schema:
{json.dumps(CAD_IR_SCHEMA, indent=2)}"""

    model = genai.GenerativeModel(
        'gemini-2.5-flash',
        generation_config={
            "response_mime_type": "application/json"
        }
    )
    
    response = model.generate_content([repair_prompt, image])
    repaired_json = response.text.strip()
    
    try:
        repaired_ir = json.loads(repaired_json)
        return repaired_ir
    except json.JSONDecodeError as e:
        # Return original if repair fails
        return ir


def validate_ir(ir: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate IR against schema and basic sanity checks.
    Returns (is_valid, error_message)
    """
    # Check required fields
    if "units" not in ir:
        return False, "Missing 'units' field"
    
    if "objects" not in ir or not ir["objects"]:
        return False, "Missing or empty 'objects' array"
    
    # Validate each object
    for i, obj in enumerate(ir["objects"]):
        if "id" not in obj:
            return False, f"Object {i} missing 'id'"
        if "type" not in obj:
            return False, f"Object {i} missing 'type'"
        if "origin" not in obj:
            return False, f"Object {i} missing 'origin'"
        
        obj_type = obj["type"]
        
        # Type-specific validation
        if obj_type == "box":
            if not all(k in obj for k in ["w", "d", "h"]):
                return False, f"Box object '{obj['id']}' missing w/d/h dimensions"
        elif obj_type in ["cylinder", "sphere"]:
            if "r" not in obj:
                return False, f"{obj_type} object '{obj['id']}' missing radius 'r'"
            if obj_type == "cylinder" and "h" not in obj:
                return False, f"Cylinder object '{obj['id']}' missing height 'h'"
    
    return True, ""


def generate_from_image_with_verification(image: Any, prompt: str, session_id: str, current_code: str = None, max_iterations: int = 3) -> dict:
    """
    Two-stage pipeline: Image+text → JSON IR → CadQuery code
    
    This approach is more reliable than direct code generation:
    1. Generate structured JSON IR (schema-constrained)
    2. Convert IR to CadQuery deterministically
    3. Validate and repair if needed
    
    Returns:
        dict: {
            'success': bool,
            'code': str,
            'ir': dict,
            'iterations': int,
            'progress_steps': list[dict],
            'message': str
        }
    """
    try:
        CADEngine = safe_import('cad_engine', ['CADEngine'])[0]
        engine = CADEngine()
    except Exception as e:
        print(f"Error importing CADEngine: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    context = build_context_from_history(session_id, current_code)
    
    progress_steps = []
    best_code = None
    best_ir = None
    
    print(f"\n=== Starting Image-to-Model Generation ===")
    print(f"Prompt: {prompt}")
    print(f"Session ID: {session_id}")
    
    # Stage 1: Generate IR from image (20%)
    progress_steps.append({'stage': 'Analyzing image and creating IR', 'progress': 20})
    
    try:
        print("Stage 1: Generating IR from image...")
        ir = generate_ir_from_image(image, prompt, context)
        print(f"IR generated successfully: {json.dumps(ir, indent=2)}")
    except Exception as e:
        error_detail = f"Failed to generate IR: {type(e).__name__}: {str(e)}"
        print(f"ERROR in generate_ir_from_image: {error_detail}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'code': f'# {error_detail}',
            'ir': {},
            'iterations': 1,
            'progress_steps': progress_steps,
            'message': error_detail,
            'error_detail': error_detail
        }
    
    # Stage 2: Validate IR (40%)
    progress_steps.append({'stage': 'Validating IR schema', 'progress': 40})
    
    print("Stage 2: Validating IR...")
    is_valid, error_msg = validate_ir(ir)
    if not is_valid:
        print(f"IR validation failed: {error_msg}")
        # Try to repair IR
        feedback = f"IR validation failed: {error_msg}"
        try:
            print("Attempting to repair IR...")
            ir = repair_ir_from_feedback(ir, feedback, image)
            is_valid, error_msg = validate_ir(ir)
            if is_valid:
                print("IR repaired successfully")
            else:
                print(f"IR repair failed: {error_msg}")
        except Exception as e:
            print(f"Error during IR repair: {e}")
            pass
    else:
        print("IR validation passed")
    
    # Stage 3: Convert IR to CadQuery (60%)
    progress_steps.append({'stage': 'Converting IR to CadQuery code', 'progress': 60})
    
    try:
        print("Stage 3: Converting IR to CadQuery code...")
        code = ir_to_cadquery(ir)
        print(f"Code generated ({len(code)} chars):")
        print(code)
    except Exception as e:
        error_detail = f"Failed to convert IR to code: {type(e).__name__}: {str(e)}"
        print(f"ERROR: {error_detail}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'code': '',
            'ir': ir,
            'iterations': len(progress_steps),
            'progress_steps': progress_steps,
            'message': error_detail
        }
    
    # Stage 4: Validate code execution (80%)
    progress_steps.append({'stage': 'Validating code execution', 'progress': 80})
    
    print("Stage 4: Validating code execution...")
    validation = engine.execute_script(code, fallback_on_error=False)
    print(f"Execution result: success={validation['success']}")
    if not validation['success']:
        print(f"Execution error: {validation.get('error', 'Unknown')}")
    
    attempts = 1
    while not validation['success'] and attempts < max_iterations:
        print(f"Repair attempt {attempts}/{max_iterations-1}...")
        # Repair IR based on execution error
        feedback = f"Code execution failed: {validation.get('error', 'Unknown error')}\nGenerated code had issues. Please fix the IR to produce valid CadQuery."
        
        try:
            ir = repair_ir_from_feedback(ir, feedback, image)
            code = ir_to_cadquery(ir)
            validation = engine.execute_script(code, fallback_on_error=False)
            attempts += 1
        except Exception as e:
            print(f"Error during repair: {e}")
            break
    
    # Stage 5: Complete (100%)
    progress_steps.append({'stage': 'Complete', 'progress': 100})
    
    if validation['success']:
        best_code = code
        best_ir = ir
        print("✓ Generation successful!")
    else:
        print("✗ Generation failed after all repair attempts")
    
    # Calculate metrics
    code_lines = len([l for l in code.split('\n') if l.strip() and not l.strip().startswith('#')])
    num_objects = len(ir.get('objects', []))
    assumptions = ir.get('assumptions', [])
    
    print(f"Final stats: {num_objects} objects, {code_lines} lines, {len(assumptions)} assumptions")
    print("=" * 50)
    
    message_parts = [f"Generated {num_objects} object(s) with {code_lines} lines of code"]
    if assumptions:
        message_parts.append(f"Assumptions: {', '.join(assumptions[:2])}")
    
    return {
        'success': validation['success'],
        'code': code,
        'ir': ir,
        'iterations': len(progress_steps),
        'progress_steps': progress_steps,
        'code_lines': code_lines,
        'num_objects': num_objects,
        'assumptions': assumptions,
        'message': '. '.join(message_parts)
    }
    
    return context

# Include enhanced CAD endpoints
try:
    from .enhanced_endpoints import router as enhanced_router
    app.include_router(enhanced_router)
except Exception as e:
    print(f"Warning: Could not load enhanced endpoints: {e}")



@app.get("/")
async def index() -> HTMLResponse:
    # Serve the landing page
    page = (BASE / "landing.html")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/v1")
async def old_interface() -> HTMLResponse:
    # Serve the old professional CAD Studio interface
    page = (BASE / "cad_pro.html")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/legacy")
async def legacy_index() -> HTMLResponse:
    # Keep old interface for reference
    page = (BASE / "web_index.html")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/landing.html")
async def landing_page() -> FileResponse:
    return FileResponse(BASE / "landing.html", media_type="text/html")

@app.get("/viewer.html")
async def viewer() -> FileResponse:
    return FileResponse(BASE / "viewer.html", media_type="text/html")


@app.get("/test_selection.html")
async def test_selection() -> FileResponse:
    return FileResponse(BASE.parent / "test_selection.html", media_type="text/html")


@app.get("/cad_studio_v2.html")
async def cad_studio_v2() -> HTMLResponse:
    # Serve the CAD Studio V2 interface
    page = (BASE / "cad_studio_v2.html")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/cascade_studio.html")
async def cascade_studio() -> HTMLResponse:
    # Serve the CASCADE Studio interface
    page = (BASE / "cascade_studio.html")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/fludo_cascade_enhanced.html")
async def fludo_cascade_enhanced() -> HTMLResponse:
    # Serve the FLUDO CASCADE Enhanced interface
    page = (BASE / "fludo_cascade_enhanced.html")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.post("/api/build_spec")
async def build_spec(request: Request) -> JSONResponse:
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    prompt = str(body.get("prompt") or "").strip()
    existing = body.get("existing")
    existing_json = json.dumps(existing) if isinstance(existing, dict) else None

    if not prompt:
        return JSONResponse({"error": "missing prompt"}, status_code=400)

    # Use the local agent to generate or edit the spec
    from .agent import build_spec as _build
    spec = _build(prompt, existing_json)
    return JSONResponse(spec)


@app.post("/api/build_script")
async def build_script(request: Request) -> JSONResponse:
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "missing prompt"}, status_code=400)
    try:
        from .agent import have_gemini, build_script as _build_script
        if not have_gemini():
            return JSONResponse({"error": "gemini_required"}, status_code=400)
        data = _build_script(prompt)
        code = str(data.get("code") or "")
        if not code:
            return JSONResponse({"error": "empty_code"}, status_code=500)
        return JSONResponse({"code": code})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"codegen failed: {exc}"}, status_code=500)


@app.post("/api/enhance")
async def enhance(request: Request) -> JSONResponse:
    """Stage 1: Enhance simple prompt into detailed technical specification."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "missing prompt"}, status_code=400)
    try:
        from .agent import have_gemini, enhance_prompt as _enhance
        if not have_gemini():
            return JSONResponse({"error": "gemini_required"}, status_code=400)
        data = _enhance(prompt)
        enhanced = str(data.get("enhanced") or "")
        return JSONResponse({"enhanced": enhanced})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"enhance failed: {exc}"}, status_code=500)


@app.post("/api/ask")
async def ask(request: Request) -> JSONResponse:
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "missing prompt"}, status_code=400)
    try:
        from .agent import have_gemini, ask_question as _ask
        if not have_gemini():
            return JSONResponse({"error": "gemini_required"}, status_code=400)
        data = _ask(prompt)
        ans = str(data.get("answer") or "")
        return JSONResponse({"answer": ans})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"ask failed: {exc}"}, status_code=500)


@app.post("/api/upload_model")
async def upload_model(file: UploadFile = File(...)) -> JSONResponse:
    try:
        name = file.filename or ""
        suffix = ("." + name.split(".")[-1]).lower() if "." in name else ""
        allowed = {".glb", ".gltf", ".obj", ".stl", ".fbx"}
        if suffix not in allowed:
            return JSONResponse({"error": "unsupported file type"}, status_code=400)
        token = secrets.token_hex(8) + suffix
        dest = UPLOAD_DIR / token
        with dest.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        return JSONResponse({"url": f"/models/{token}"})
    except Exception as e:
        return JSONResponse({"error": f"upload failed: {str(e)}"}, status_code=500)


@app.post("/api/fetch_model")
async def fetch_model(request: Request) -> JSONResponse:
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    url = str(body.get("url") or "").strip()
    if not url:
        return JSONResponse({"error": "missing url"}, status_code=400)
    # Determine extension
    allowed = {".glb", ".gltf", ".obj", ".stl", ".fbx"}
    suffix = "." + url.split("?")[0].split(".")[-1].lower() if "." in url.split("?")[0] else ""
    if suffix not in allowed:
        try:
            with urllib.request.urlopen(url) as resp:
                ctype = resp.headers.get("Content-Type", "").lower()
                cdisp = resp.headers.get("Content-Disposition", "")
                default_ext = mimetypes.guess_extension(ctype) or ""
                # Map common GLTF MIME types
                if ctype == "model/gltf-binary":
                    suffix = ".glb"
                elif ctype in ("model/gltf+json", "application/json"):
                    suffix = ".gltf"
                elif default_ext in allowed:
                    suffix = default_ext
                # Try to parse filename from Content-Disposition
                if (not suffix or suffix not in allowed) and cdisp:
                    # naive parse; looks for filename= or filename*
                    fname = None
                    for part in cdisp.split(';'):
                        part = part.strip()
                        if part.lower().startswith('filename*='):
                            # RFC 5987: filename*=UTF-8''<encoded>
                            try:
                                enc_name = part.split("'',",1)[-1]
                            except Exception:
                                enc_name = part.split("=",1)[-1]
                            fname = enc_name.strip('"')
                            break
                        if part.lower().startswith('filename='):
                            fname = part.split('=',1)[-1].strip('"')
                            break
                    if fname and '.' in fname:
                        ext = '.' + fname.split('.')[-1].lower()
                        if ext in allowed:
                            suffix = ext
                # Rewind not possible; we need to read bytes and write
                token = secrets.token_hex(8) + (suffix or "")
                dest = UPLOAD_DIR / token
                data = resp.read()
                if not suffix or suffix not in allowed:
                    return JSONResponse({"error": "unsupported content type"}, status_code=400)
                dest.write_bytes(data)
        except Exception as e:
            return JSONResponse({"error": f"download failed: {e}"}, status_code=400)
        else:
            return JSONResponse({"url": f"/models/{token}"})
    # Simple streaming if URL already contains a valid suffix
    try:
        with urllib.request.urlopen(url) as resp:
            token = secrets.token_hex(8) + suffix
            dest = UPLOAD_DIR / token
            data = resp.read()
            dest.write_bytes(data)
            return JSONResponse({"url": f"/models/{token}"})
    except Exception as e:
        return JSONResponse({"error": f"download failed: {e}"}, status_code=400)


@app.post("/api/generate_model")
async def generate_model(request: Request) -> JSONResponse:
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "missing prompt"}, status_code=400)
    try:
        from . import generator
        data = generator.generate_glb(prompt)
        token = secrets.token_hex(8) + ".glb"
        dest = UPLOAD_DIR / token
        dest.write_bytes(data)
        return JSONResponse({"url": f"/models/{token}"})
    except Exception as exc:
        return JSONResponse({"error": f"generation failed: {str(exc)}"}, status_code=500)


# ============ NEW CADQUERY ENDPOINTS ============

@app.post("/api/cad/generate")
async def cad_generate(request: Request) -> JSONResponse:
    """Generate CadQuery script from natural language and optional image with conversation history."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    prompt = str(body.get("prompt") or "").strip()
    image_data = body.get("image")  # Base64 encoded image
    session_id = str(body.get("session_id", "default"))  # Session ID for history
    current_code = str(body.get("current_code") or "").strip()  # Current editor code
    
    if not prompt and not image_data:
        return JSONResponse({"error": "missing prompt or image"}, status_code=400)
    
    try:
        generate_with_auto_fix, have_gemini = safe_import('cad_agent', ['generate_with_auto_fix', 'have_gemini'])
        
        if not have_gemini():
            return JSONResponse({"error": "Gemini API key not configured"}, status_code=400)
        
        # Build context from conversation history (last 8 messages)
        context = build_context_from_history(session_id, current_code)
        
        # If image is provided, use vision-enabled generation with auto-fix
        if image_data:
            # Parse base64 image
            if ',' in image_data:
                image_data = image_data.split(',')[1]  # Remove data:image/...;base64, prefix
            
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Use the new auto-fix function for image generation (5 attempts)
            result = generate_from_image_with_auto_fix(
                image=image,
                prompt=prompt if prompt else 'Create a 3D CAD model from this image',
                context=context,
                max_retries=5
            )
            
            # Add to history with image flag
            add_to_history(session_id, "user", prompt if prompt else "Uploaded image", has_image=True)
            
            if result['success']:
                add_to_history(session_id, "assistant", f"Generated 3D model from image (attempt {result['attempts']}/5)", code=result['code'], has_image=False)
                return JSONResponse({
                    "code": result['code'],
                    "attempts": result['attempts'],
                    "message": f"Model generated from image after {result['attempts']} attempt(s). Code validated and working!",
                    "validated": True,
                    "from_image": True
                })
            else:
                add_to_history(session_id, "assistant", "Failed to generate working model from image", code=result.get('code', ''), has_image=False)
                return JSONResponse({
                    "error": result.get('error', 'Failed to generate working code from image'),
                    "code": result.get('code', ''),
                    "attempts": result['attempts'],
                    "validated": False
                }, status_code=500)
        
        # No image - use standard text-based generation with history context
        context = build_context_from_history(session_id, current_code)
        context_prompt = f"{context}\n\nNEW REQUEST: {prompt}" if context else prompt
        
        result = generate_with_auto_fix(context_prompt, max_retries=5)
        
        # Add to history with has_image flag
        add_to_history(session_id, "user", prompt, has_image=False)
        
        if result['success']:
            add_to_history(session_id, "assistant", "Generated code", code=result['code'], has_image=False)
            return JSONResponse({
                "code": result['code'],
                "attempts": result['attempts'],
                "message": result.get('message', 'Code validated and working'),
                "validated": True
            })
        else:
            return JSONResponse({
                "error": result.get('error', 'Failed to generate working code'),
                "code": result.get('code', ''),
                "attempts": result['attempts'],
                "validated": False
            }, status_code=500)
        
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": f"generation failed: {str(exc)}"}, status_code=500)


@app.post("/api/cad/chat")
async def cad_chat(request: Request) -> JSONResponse:
    """Chat with AI about CAD designs, with optional image analysis."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    message = str(body.get("message") or "").strip()
    image_data = body.get("image")  # Base64 encoded image
    
    if not message and not image_data:
        return JSONResponse({"error": "missing message or image"}, status_code=400)
    
    try:
        have_gemini = safe_import('cad_agent', ['have_gemini'])[0]
        
        if not have_gemini():
            return JSONResponse({"error": "Gemini API key not configured"}, status_code=400)
        
        # Use Gemini 2.5 Flash for fast conversational responses (already configured at startup)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        if image_data:
            # Parse base64 image
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            chat_prompt = f"""You are a helpful CAD design assistant. Analyze this image and provide insights about the design.

User message: {message if message else "What can you tell me about this design?"}

Provide a detailed, conversational response about:
- What you see in the image (shapes, features, components)
- Design characteristics and notable features
- Possible manufacturing considerations
- Suggested improvements or variations
- How it could be modeled in CAD

Be specific and technical but friendly."""

            response = model.generate_content([chat_prompt, image])
        else:
            chat_prompt = f"""You are a helpful CAD design assistant. The user wants to have a conversation about CAD design, 3D modeling, or CadQuery.

Provide helpful, conversational responses. If they ask about specific CAD operations or design advice, explain clearly without generating code.

User message: {message}"""

            response = model.generate_content(chat_prompt)
        
        return JSONResponse({"response": response.text})
        
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return JSONResponse({"error": f"chat failed: {str(exc)}"}, status_code=500)


@app.post("/api/cad/modify")
async def cad_modify(request: Request) -> JSONResponse:
    """Modify existing CadQuery script based on instruction."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    current_script = str(body.get("script") or "").strip()
    modification = str(body.get("modification") or "").strip()
    
    if not current_script or not modification:
        return JSONResponse({"error": "missing script or modification"}, status_code=400)
    
    try:
        modify_cadquery_script, have_gemini = safe_import('cad_agent', ['modify_cadquery_script', 'have_gemini'])
        
        if not have_gemini():
            return JSONResponse({"error": "Gemini API key not configured"}, status_code=400)
        
        result = modify_cadquery_script(current_script, modification)
        
        if 'error' in result:
            return JSONResponse({"error": result['error']}, status_code=500)
        
        return JSONResponse({"code": result['code']})
        
    except Exception as exc:
        return JSONResponse({"error": f"modification failed: {str(exc)}"}, status_code=500)


@app.post("/api/cad/edit_context")
async def cad_edit_context(request: Request) -> JSONResponse:
    """Context-aware editing - modify existing code while preserving structure."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    current_code = str(body.get("code") or "").strip()
    instruction = str(body.get("instruction") or "").strip()
    preserve_measurements = body.get("preserve_measurements", True)
    session_id = body.get("session_id", "default")
    
    if not current_code or not instruction:
        return JSONResponse({"error": "missing code or instruction"}, status_code=400)
    
    try:
        edit_with_context, have_gemini = safe_import('cad_agent', ['edit_with_context', 'have_gemini'])
        get_manager = safe_import('undo_manager', ['get_manager'])[0]
        
        if not have_gemini():
            return JSONResponse({"error": "Gemini API key not configured"}, status_code=400)
        
        # Save current state to history
        manager = get_manager(session_id)
        manager.push(current_code, f"Before: {instruction}")
        
        # Perform context-aware edit
        result = edit_with_context(current_code, instruction, preserve_measurements)
        
        if 'error' in result:
            return JSONResponse({"error": result['error']}, status_code=500)
        
        # Save new state to history
        manager.push(result['code'], f"After: {instruction}")
        
        return JSONResponse({
            "code": result['code'],
            "can_undo": manager.can_undo(),
            "can_redo": manager.can_redo()
        })
        
    except Exception as exc:
        return JSONResponse({"error": f"context edit failed: {str(exc)}"}, status_code=500)


@app.post("/api/cad/execute")
async def cad_execute(request: Request) -> JSONResponse:
    """Execute CadQuery script and return STL for visualization.
    
    Now supports multi-object detection - if script has box, cylinder, etc.,
    each will be exported as a separate STL for individual selection in viewer.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    script = str(body.get("script") or "").strip()
    if not script:
        return JSONResponse({"error": "missing script"}, status_code=400)
    
    try:
        get_engine = safe_import('cad_engine', ['get_engine'])[0]
        
        engine = get_engine()
        
        # Try to detect and export individual objects
        multi_result = engine.execute_and_export_individual_objects(script)
        
        if multi_result['success'] and multi_result['num_objects'] > 0:
            # We found individual objects! Export each as separate STL
            stl_urls = []
            
            for i, (name, stl_bytes) in enumerate(zip(multi_result['objects'], multi_result['stl_exports'])):
                token = f"{secrets.token_hex(6)}_{name}.stl"
                dest = UPLOAD_DIR / token
                dest.write_bytes(stl_bytes)
                stl_urls.append({
                    'url': f"/models/{token}",
                    'name': name,
                    'index': i
                })
            
            return JSONResponse({
                "success": True,
                "multi_object": True,
                "objects": stl_urls,
                "num_objects": len(stl_urls)
            })
        
        # Fallback: single object export (original behavior)
        result = engine.execute_script(script)
        
        if not result['success']:
            return JSONResponse({
                "success": False,
                "error": result.get('error', 'Unknown error'),
                "traceback": result.get('traceback', '')
            }, status_code=400)
        
        # Export to STL for visualization
        stl_bytes = engine.export_stl(result['result'], tolerance=0.01)
        
        # Save STL file
        token = secrets.token_hex(8) + ".stl"
        dest = UPLOAD_DIR / token
        dest.write_bytes(stl_bytes)
        
        return JSONResponse({
            "success": True,
            "url": f"/models/{token}",
            "type": result.get('type', 'Workplane'),
            "multi_object": False
        })
        
    except Exception as exc:
        import traceback
        return JSONResponse({
            "success": False,
            "error": f"execution failed: {str(exc)}",
            "traceback": traceback.format_exc()
        }, status_code=500)


@app.post("/api/cad/export/{format}")
async def cad_export(format: str, request: Request) -> Response:
    """Export CAD model to specified format (step, stl, iges, dxf, obj)."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    script = str(body.get("script") or "").strip()
    if not script:
        return JSONResponse({"error": "missing script"}, status_code=400)
    
    format_lower = format.lower()
    if format_lower not in ['step', 'stp', 'stl', 'iges', 'igs', 'dxf', 'obj']:
        return JSONResponse({"error": f"unsupported format: {format}"}, status_code=400)
    
    try:
        get_engine = safe_import('cad_engine', ['get_engine'])[0]
        
        engine = get_engine()
        result = engine.execute_script(script)
        
        if not result['success']:
            return JSONResponse({
                "error": result.get('error', 'Script execution failed')
            }, status_code=400)
        
        # Export to requested format
        if format_lower in ['step', 'stp']:
            data = engine.export_step(result['result'])
            media_type = 'application/step'
            extension = 'step'
        elif format_lower == 'stl':
            data = engine.export_stl(result['result'])
            media_type = 'application/vnd.ms-pki.stl'
            extension = 'stl'
        elif format_lower in ['iges', 'igs']:
            data = engine.export_iges(result['result'])
            media_type = 'application/iges'
            extension = 'iges'
        elif format_lower == 'dxf':
            data = engine.export_dxf(result['result'])
            media_type = 'application/dxf'
            extension = 'dxf'
        elif format_lower == 'obj':
            data = engine.export_obj(result['result'])
            media_type = 'text/plain'
            extension = 'obj'
        else:
            return JSONResponse({"error": "format not implemented"}, status_code=400)
        
        filename = f"model_{secrets.token_hex(4)}.{extension}"
        
        return Response(
            content=data,
            media_type=media_type,
            headers={
                'Content-Disposition': f'attachment; filename=\"{filename}\"'
            }
        )
        
    except Exception as exc:
        import traceback
        return JSONResponse({
            "error": f"export failed: {str(exc)}",
            "traceback": traceback.format_exc()
        }, status_code=500)


@app.post("/api/upload/obj")
async def upload_obj(file: UploadFile = File(...)) -> JSONResponse:
    """Upload an OBJ file and return a temporary URL for viewing."""
    try:
        # Validate file extension
        if not file.filename or not file.filename.lower().endswith('.obj'):
            return JSONResponse({"error": "Only .obj files are allowed"}, status_code=400)
        
        # Read file content
        content = await file.read()
        
        # Validate it's valid OBJ content (basic check for 'v ' vertex lines)
        try:
            text_content = content.decode('utf-8')
            if not any(line.strip().startswith('v ') for line in text_content.split('\n')[:100]):
                return JSONResponse({"error": "Invalid OBJ file format"}, status_code=400)
        except UnicodeDecodeError:
            return JSONResponse({"error": "OBJ file must be text format"}, status_code=400)
        
        # Save to temporary file
        temp_id = secrets.token_hex(8)
        temp_path = os.path.join(tempfile.gettempdir(), f"fludo_obj_{temp_id}.obj")
        
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        # Return URL that can be used to load the file
        return JSONResponse({
            "success": True,
            "url": f"/api/temp/obj/{temp_id}",
            "filename": file.filename,
            "size": len(content)
        })
        
    except Exception as exc:
        import traceback
        return JSONResponse({
            "error": f"upload failed: {str(exc)}",
            "traceback": traceback.format_exc()
        }, status_code=500)


@app.get("/api/temp/obj/{temp_id}")
async def get_temp_obj(temp_id: str) -> Response:
    """Serve a temporary OBJ file."""
    try:
        temp_path = os.path.join(tempfile.gettempdir(), f"fludo_obj_{temp_id}.obj")
        
        if not os.path.exists(temp_path):
            return JSONResponse({"error": "File not found or expired"}, status_code=404)
        
        with open(temp_path, 'rb') as f:
            content = f.read()
        
        return Response(
            content=content,
            media_type='text/plain',
            headers={'Content-Type': 'text/plain; charset=utf-8'}
        )
        
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/upload/stl")
async def upload_stl(file: UploadFile = File(...)) -> JSONResponse:
    """Upload an STL file and return a temporary URL for viewing."""
    try:
        # Validate file extension
        if not file.filename or not file.filename.lower().endswith('.stl'):
            return JSONResponse({"error": "Only .stl files are allowed"}, status_code=400)
        
        # Read file content
        content = await file.read()
        
        # Validate it's valid STL content (check for binary STL header or ASCII "solid")
        is_valid = False
        if len(content) >= 84:
            # Binary STL check (has 80-byte header + 4-byte count)
            is_valid = True
        else:
            # ASCII STL check
            try:
                text_content = content.decode('utf-8', errors='ignore')[:100]
                if 'solid' in text_content.lower():
                    is_valid = True
            except:
                pass
        
        if not is_valid:
            return JSONResponse({"error": "Invalid STL file format"}, status_code=400)
        
        # Save to temporary file
        temp_id = secrets.token_hex(8)
        temp_path = os.path.join(tempfile.gettempdir(), f"fludo_stl_{temp_id}.stl")
        
        with open(temp_path, 'wb') as f:
            f.write(content)
        
        # Return URL that can be used to load the file
        return JSONResponse({
            "success": True,
            "url": f"/api/temp/stl/{temp_id}",
            "filename": file.filename,
            "size": len(content)
        })
        
    except Exception as exc:
        import traceback
        return JSONResponse({
            "error": f"upload failed: {str(exc)}",
            "traceback": traceback.format_exc()
        }, status_code=500)


@app.get("/api/temp/stl/{temp_id}")
async def get_temp_stl(temp_id: str) -> Response:
    """Serve a temporary STL file."""
    try:
        temp_path = os.path.join(tempfile.gettempdir(), f"fludo_stl_{temp_id}.stl")
        
        if not os.path.exists(temp_path):
            return JSONResponse({"error": "File not found or expired"}, status_code=404)
        
        with open(temp_path, 'rb') as f:
            content = f.read()
        
        return Response(
            content=content,
            media_type='application/vnd.ms-pki.stl',
            headers={'Content-Type': 'application/octet-stream'}
        )
        
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/api/colab_notebook")
async def colab_notebook() -> Response:
    nb = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "colab": {"name": "text2mesh_rocket.ipynb"},
            "kernelspec": {"name": "python3", "display_name": "Python 3"}
        },
        "cells": [
            {
                "cell_type": "code",
                "metadata": {},
                "source": ["!pip -q install trimesh\n"],
                "outputs": [],
                "execution_count": None
            },
            {
                "cell_type": "code",
                "metadata": {},
                "source": [
                    "import numpy as np\n",
                    "import trimesh\n",
                    "from trimesh.creation import cylinder, cone, box\n",
                    "try:\n",
                    "    from google.colab import files\n",
                    "except Exception:\n",
                    "    files = None\n",
                    "\n",
                    "body = cylinder(radius=0.6, height=6.0, sections=64)\n",
                    "nose = cone(radius=0.58, height=1.8, sections=64)\n",
                    "nose.apply_translation([0, 0, 6.9])\n",
                    "fins = []\n",
                    "fin_proto = box(extents=[0.2, 1.0, 0.8])\n",
                    "T = np.eye(4); T[:3, 3] = [0.7, 0.0, 0.4]\n",
                    "fin_proto.apply_transform(T)\n",
                    "for ang in [0, np.pi/2, np.pi, 3*np.pi/2]:\n",
                    "    R = trimesh.transformations.rotation_matrix(ang, [0,0,1])\n",
                    "    f = fin_proto.copy(); f.apply_transform(R); fins.append(f)\n",
                    "mesh = trimesh.util.concatenate([body, nose] + fins)\n",
                    "mesh.export('rocket.stl')\n",
                    "print('Saved rocket.stl')\n",
                    "if files: files.download('rocket.stl')\n"
                ],
                "outputs": [],
                "execution_count": None
            }
        ]
    }
    return Response(content=json.dumps(nb), media_type="application/x-ipynb+json", headers={"Content-Disposition": "attachment; filename=\"text2mesh_rocket.ipynb\""})


# ============ CODE VALIDATION AND ROBUSTNESS ============

@app.post("/api/cad/validate")
async def cad_validate(request: Request) -> JSONResponse:
    """Validate CadQuery code before execution."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    code = str(body.get("code") or "").strip()
    if not code:
        return JSONResponse({"error": "missing code"}, status_code=400)
    
    try:
        from .cad_validator import validate_cadquery_code, auto_fix_code
        
        validation_result = validate_cadquery_code(code)
        
        # Attempt auto-fix if requested
        auto_fix = body.get("auto_fix", False)
        if auto_fix and not validation_result["valid"]:
            fixed_code, fixes_applied = auto_fix_code(code, validation_result)
            # Re-validate fixed code
            new_validation = validate_cadquery_code(fixed_code)
            return JSONResponse({
                **new_validation,
                "fixed_code": fixed_code,
                "fixes_applied": fixes_applied
            })
        
        return JSONResponse(validation_result)
        
    except Exception as exc:
        return JSONResponse({"error": f"validation failed: {str(exc)}"}, status_code=500)


@app.post("/api/cad/extract_measurements")
async def cad_extract_measurements(request: Request) -> JSONResponse:
    """Extract measurement variables from code."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    code = str(body.get("code") or "").strip()
    if not code:
        return JSONResponse({"error": "missing code"}, status_code=400)
    
    try:
        from .cad_validator import extract_measurements_from_code
        
        measurements = extract_measurements_from_code(code)
        return JSONResponse({"measurements": measurements})
        
    except Exception as exc:
        return JSONResponse({"error": f"extraction failed: {str(exc)}"}, status_code=500)


@app.post("/api/cad/update_measurement")
async def cad_update_measurement(request: Request) -> JSONResponse:
    """Update a measurement in the code."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    code = str(body.get("code") or "").strip()
    var_name = str(body.get("var_name") or "").strip()
    new_value = body.get("new_value")
    
    if not code or not var_name or new_value is None:
        return JSONResponse({"error": "missing required parameters"}, status_code=400)
    
    try:
        update_measurement_in_code = safe_import('cad_validator', ['update_measurement_in_code'])[0]
        get_manager = safe_import('undo_manager', ['get_manager'])[0]
        
        # Get session ID from request
        session_id = body.get("session_id", "default")
        
        # Save to undo history
        manager = get_manager(session_id)
        manager.push(code, f"Update {var_name} to {new_value}")
        
        # Update the measurement
        updated_code = update_measurement_in_code(code, var_name, float(new_value))
        
        return JSONResponse({
            "code": updated_code,
            "can_undo": manager.can_undo(),
            "can_redo": manager.can_redo()
        })
        
    except Exception as exc:
        return JSONResponse({"error": f"update failed: {str(exc)}"}, status_code=500)


# ============ UNDO/REDO FUNCTIONALITY ============

@app.post("/api/cad/undo")
async def cad_undo(request: Request) -> JSONResponse:
    """Undo to previous code state."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    session_id = body.get("session_id", "default")
    
    try:
        get_manager = safe_import('undo_manager', ['get_manager'])[0]
        
        manager = get_manager(session_id)
        entry = manager.undo()
        
        if entry is None:
            return JSONResponse({"error": "nothing to undo"}, status_code=400)
        
        return JSONResponse({
            "code": entry.code,
            "description": entry.description,
            "can_undo": manager.can_undo(),
            "can_redo": manager.can_redo()
        })
        
    except Exception as exc:
        return JSONResponse({"error": f"undo failed: {str(exc)}"}, status_code=500)


@app.post("/api/cad/redo")
async def cad_redo(request: Request) -> JSONResponse:
    """Redo to next code state."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    session_id = body.get("session_id", "default")
    
    try:
        get_manager = safe_import('undo_manager', ['get_manager'])[0]
        
        manager = get_manager(session_id)
        entry = manager.redo()
        
        if entry is None:
            return JSONResponse({"error": "nothing to redo"}, status_code=400)
        
        return JSONResponse({
            "code": entry.code,
            "description": entry.description,
            "can_undo": manager.can_undo(),
            "can_redo": manager.can_redo()
        })
        
    except Exception as exc:
        return JSONResponse({"error": f"redo failed: {str(exc)}"}, status_code=500)


@app.post("/api/cad/save_history")
async def cad_save_history(request: Request) -> JSONResponse:
    """Save current code to history."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    code = str(body.get("code") or "").strip()
    description = str(body.get("description") or "Manual save").strip()
    session_id = body.get("session_id", "default")
    
    if not code:
        return JSONResponse({"error": "missing code"}, status_code=400)
    
    try:
        get_manager = safe_import('undo_manager', ['get_manager'])[0]
        
        manager = get_manager(session_id)
        manager.push(code, description)
        
        return JSONResponse({
            "success": True,
            "can_undo": manager.can_undo(),
            "can_redo": manager.can_redo()
        })
        
    except Exception as exc:
        return JSONResponse({"error": f"save failed: {str(exc)}"}, status_code=500)


@app.get("/api/cad/history")
async def cad_get_history(request: Request) -> JSONResponse:
    """Get code history for session."""
    session_id = request.query_params.get("session_id", "default")
    limit = int(request.query_params.get("limit", "20"))
    
    try:
        get_manager = safe_import('undo_manager', ['get_manager'])[0]
        
        manager = get_manager(session_id)
        history = manager.get_history_list(limit)
        
        return JSONResponse({
            "history": history,
            "can_undo": manager.can_undo(),
            "can_redo": manager.can_redo()
        })
        
    except Exception as exc:
        return JSONResponse({"error": f"get history failed: {str(exc)}"}, status_code=500)


def main() -> None:  # pragma: no cover
    import uvicorn
    # Use environment variable for port, default to 8001 for production
    port = int(os.environ.get("PORT", 8001))
    # Bind to 0.0.0.0 for external access in production
    host = os.environ.get("HOST", "0.0.0.0")
    # Run directly without module path when executed as script
    uvicorn.run("server:app", host=host, port=port, reload=True)


if __name__ == "__main__":  # pragma: no cover
    main()


