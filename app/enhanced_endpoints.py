"""Enhanced API endpoints for production CAD system."""
from __future__ import annotations

import secrets
import sys
from pathlib import Path
from typing import Any
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

# Ensure proper imports
app_dir = str(Path(__file__).parent)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from cad_agent_v2 import get_agent, CADContext, have_gemini
from cad_engine_v2 import get_engine

router = APIRouter(prefix="/api/cad/v2")

UPLOAD_DIR = Path(__file__).parent / "uploads"


@router.post("/generate")
async def enhanced_generate(request: Request) -> JSONResponse:
    """Enhanced CAD generation with multi-stage refinement."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "missing prompt"}, status_code=400)
    
    # Optional context
    context_data = body.get("context", {})
    context = CADContext(
        design_intent=context_data.get("design_intent", ""),
        manufacturing_method=context_data.get("manufacturing_method"),
        material=context_data.get("material"),
    ) if context_data else None
    
    try:
        if not have_gemini():
            return JSONResponse({"error": "Gemini API key not configured"}, status_code=400)
        
        agent = get_agent()
        result = await agent.generate_cad_model(prompt, context)
        
        if 'error' in result:
            return JSONResponse({"error": result['error']}, status_code=500)
        
        return JSONResponse({
            "code": result['code'],
            "specification": result.get('specification', ''),
            "parameters": result.get('parameters', {}),
            "features": result.get('features', []),
            "success": True
        })
        
    except Exception as exc:
        import traceback
        return JSONResponse({
            "error": f"generation failed: {str(exc)}",
            "traceback": traceback.format_exc()
        }, status_code=500)


@router.post("/modify")
async def enhanced_modify(request: Request) -> JSONResponse:
    """Enhanced CAD modification with context awareness."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    current_script = str(body.get("script") or "").strip()
    modification = str(body.get("modification") or "").strip()
    
    if not current_script or not modification:
        return JSONResponse({"error": "missing script or modification"}, status_code=400)
    
    # Optional context
    context_data = body.get("context", {})
    context = CADContext(
        current_script=current_script,
        design_intent=context_data.get("design_intent", ""),
        manufacturing_method=context_data.get("manufacturing_method"),
        material=context_data.get("material"),
    ) if context_data else None
    
    try:
        if not have_gemini():
            return JSONResponse({"error": "Gemini API key not configured"}, status_code=400)
        
        agent = get_agent()
        result = await agent.modify_cad_model(current_script, modification, context)
        
        if 'error' in result:
            return JSONResponse({"error": result['error']}, status_code=500)
        
        return JSONResponse({
            "code": result['code'],
            "parameters": result.get('parameters', {}),
            "success": True
        })
        
    except Exception as exc:
        import traceback
        return JSONResponse({
            "error": f"modification failed: {str(exc)}",
            "traceback": traceback.format_exc()
        }, status_code=500)


@router.post("/execute")
async def enhanced_execute(request: Request) -> JSONResponse:
    """Execute script with enhanced validation and metadata."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    script = str(body.get("script") or "").strip()
    part_name = str(body.get("part_name") or "Generated Part")
    
    if not script:
        return JSONResponse({"error": "missing script"}, status_code=400)
    
    try:
        engine = get_engine()
        result = engine.execute_script(script, part_name)
        
        if not result['success']:
            return JSONResponse({
                "success": False,
                "error": result.get('error', 'Unknown error'),
                "traceback": result.get('traceback', '')
            }, status_code=400)
        
        # Export to STL for visualization
        stl_bytes = engine.export_stl(result['result'])
        
        # Save STL file
        token = secrets.token_hex(8) + ".stl"
        dest = UPLOAD_DIR / token
        dest.write_bytes(stl_bytes)
        
        return JSONResponse({
            "success": True,
            "url": f"/models/{token}",
            "part_id": result['part_id'],
            "part_info": result['part_info'],
            "validation": result['validation'],
            "parameters": engine.get_part_parameters()
        })
        
    except Exception as exc:
        import traceback
        return JSONResponse({
            "success": False,
            "error": f"execution failed: {str(exc)}",
            "traceback": traceback.format_exc()
        }, status_code=500)


@router.post("/drawing/{format}")
async def generate_drawing(format: str, request: Request) -> Response:
    """Generate technical drawing (PDF or DXF)."""
    if format.lower() not in ['pdf', 'dxf']:
        return JSONResponse({"error": f"unsupported format: {format}"}, status_code=400)
    
    try:
        engine = get_engine()
        
        if engine.last_result is None:
            return JSONResponse({"error": "No part to generate drawing for. Execute a script first."}, 
                              status_code=400)
        
        drawing_bytes = engine.generate_technical_drawing(format=format.lower())
        
        media_type = 'application/pdf' if format.lower() == 'pdf' else 'application/dxf'
        filename = f"drawing_{secrets.token_hex(4)}.{format.lower()}"
        
        return Response(
            content=drawing_bytes,
            media_type=media_type,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as exc:
        import traceback
        return JSONResponse({
            "error": f"drawing generation failed: {str(exc)}",
            "traceback": traceback.format_exc()
        }, status_code=500)


@router.get("/bom")
async def get_bom() -> JSONResponse:
    """Get Bill of Materials for current assembly."""
    try:
        engine = get_engine()
        bom = engine.generate_bom()
        
        return JSONResponse(bom)
        
    except Exception as exc:
        return JSONResponse({
            "error": f"BOM generation failed: {str(exc)}"
        }, status_code=500)


@router.post("/parameters/update")
async def update_parameter(request: Request) -> JSONResponse:
    """Update a parameter value."""
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        body = {}
    
    param_name = str(body.get("parameter") or "").strip()
    value = body.get("value")
    
    if not param_name or value is None:
        return JSONResponse({"error": "missing parameter or value"}, status_code=400)
    
    try:
        engine = get_engine()
        result = engine.update_parameter(param_name, float(value))
        
        return JSONResponse(result)
        
    except Exception as exc:
        return JSONResponse({
            "error": f"parameter update failed: {str(exc)}"
        }, status_code=500)


@router.get("/parameters")
async def get_parameters() -> JSONResponse:
    """Get current part parameters."""
    try:
        engine = get_engine()
        parameters = engine.get_part_parameters()
        
        return JSONResponse({"parameters": parameters})
        
    except Exception as exc:
        return JSONResponse({
            "error": f"failed to get parameters: {str(exc)}"
        }, status_code=500)


@router.get("/validation")
async def get_validation() -> JSONResponse:
    """Get validation report for current part."""
    try:
        engine = get_engine()
        
        if engine.last_part is None:
            return JSONResponse({"error": "No part to validate"}, status_code=400)
        
        validation = engine.kernel.validate_geometry(engine.last_part)
        manufacturing = engine.kernel.validate_manufacturing(engine.last_part)
        
        return JSONResponse({
            "geometry": validation,
            "manufacturing": manufacturing
        })
        
    except Exception as exc:
        return JSONResponse({
            "error": f"validation failed: {str(exc)}"
        }, status_code=500)
