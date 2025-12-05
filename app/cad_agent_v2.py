"""Enhanced AI Agent for Professional CAD Generation.

Multi-stage pipeline:
1. Enhance prompt → detailed engineering specification
2. Generate CAD script → executable code
3. Validate & refine → ensure quality
4. Add metadata → parameters, constraints, measurements
"""
from __future__ import annotations

import os
import time
import json
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


_last_api_call_time = 0
_min_call_interval = 6.0  # Minimum seconds between API calls (10 RPM for Gemini)


@dataclass
class CADContext:
    """Complete CAD context for AI agent."""
    current_script: Optional[str] = None
    parameters: Dict[str, Any] = None
    constraints: List[Dict[str, Any]] = None
    measurements: Dict[str, Any] = None
    design_intent: str = ""
    manufacturing_method: Optional[str] = None
    material: Optional[str] = None
    tolerances: Optional[Dict[str, float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_script": self.current_script,
            "parameters": self.parameters or {},
            "constraints": self.constraints or [],
            "measurements": self.measurements or {},
            "design_intent": self.design_intent,
            "manufacturing_method": self.manufacturing_method,
            "material": self.material,
            "tolerances": self.tolerances
        }


CADQUERY_EXPERT_PROMPT = """You are an expert CAD engineer and Python programmer specializing in parametric CAD modeling.

**Your Expertise:**
- Parametric CAD modeling with Python
- Manufacturing constraints (CNC machining, 3D printing, injection molding)
- Geometric dimensioning & tolerancing (GD&T)
- Design for manufacturing (DFM) principles
- Material properties and selection
- Assembly design and kinematics
- Robotics components and mechanical systems

**Your Task:** Generate production-quality Python CAD scripts that create 3D models using trimesh and numpy.

**Code Requirements:**
1. Use `import trimesh` and `import numpy as np`
2. Assign final 3D mesh to variable named `result`
3. Use accurate measurements in millimeters
4. Include parametric variables at the top
5. Add comprehensive comments explaining design decisions
6. Consider manufacturing constraints
7. Create realistic, functional parts

**Example Structure:**
```python
import trimesh
import numpy as np

# Parameters (all dimensions in mm)
width = 80.0
depth = 60.0
height = 5.0
hole_diameter = 6.0

# Create geometry
# ... trimesh operations ...

result = combined_mesh
```

**Important Notes:**
- For robotics: Consider joint clearances, mounting patterns (e.g., NEMA motor mounts)
- For mechanical parts: Add fillets for stress reduction, chamfers for assembly
- For 3D printing: Consider overhangs, support requirements
- For CNC: Avoid undercuts, sharp internal corners
- Always explain your design choices in comments

**Manufacturing Methods:**
- CNC 3-axis: Avoid undercuts, add tool clearance radii
- FDM 3D printing: Max 45° overhangs, 0.4mm+ wall thickness
- Injection molding: Add draft angles (1-3°), uniform wall thickness
- Laser cutting: 2D profiles only, minimum feature size based on material
"""


ENHANCEMENT_PROMPT = """You are an engineering requirements analyst. Transform user requests into detailed technical specifications.

**Your Task:** Convert informal CAD requests into precise engineering specifications.

**Output Format:**
```
ENGINEERING SPECIFICATION:

1. PART TYPE & FUNCTION:
   [Describe what the part is and its purpose]

2. KEY DIMENSIONS (in mm):
   - [Dimension 1]: [value] mm
   - [Dimension 2]: [value] mm
   - [...]

3. FEATURES:
   - [Feature 1]: [specifications]
   - [Feature 2]: [specifications]
   - [...]

4. MANUFACTURING:
   - Method: [CNC/3D printing/etc.]
   - Material: [suggested material]
   - Special considerations: [undercuts, draft angles, etc.]

5. DESIGN INTENT:
   [Explain how the part should work and key design considerations]
```

**Example:**
User: "Create a robot gripper"

Your output:
```
ENGINEERING SPECIFICATION:

1. PART TYPE & FUNCTION:
   Parallel jaw gripper for small robot arm. Used to grasp cylindrical objects 10-40mm diameter.

2. KEY DIMENSIONS (in mm):
   - Jaw stroke: 30 mm (15mm per jaw)
   - Jaw length: 60 mm
   - Jaw width: 20 mm
   - Grip force: Light-duty (manual actuation)
   - Mounting: 4x M4 holes on 40mm PCD

3. FEATURES:
   - Parallel jaws with linear guides
   - Serrated grip surface (1mm pitch)
   - Linear bearing mounts
   - Actuation: Manual screw drive
   - Hard stops for max/min position

4. MANUFACTURING:
   - Method: CNC machining or FDM 3D printing
   - Material: Aluminum 6061 or PLA+
   - Considerations: Add 3mm tool clearance radii on internal corners

5. DESIGN INTENT:
   Gripper should provide parallel motion for consistent grip. Serrations prevent slippage.
   Design allows for easy actuation and provides visual feedback of grip state.
```
"""


REFINEMENT_PROMPT = """You are a CAD code reviewer. Review and improve CAD scripts.

**Your Task:** Analyze CAD code and fix issues while maintaining functionality.

**Check for:**
1. Syntax errors
2. Missing imports
3. Undefined variables
4. Unrealistic dimensions
5. Manufacturing issues
6. Missing comments
7. Code efficiency

**Output:** Provide the complete corrected code with improvements noted in comments.
"""


def have_gemini() -> bool:
    """Check if Gemini API is configured."""
    try:
        import google.generativeai as _
        return bool(os.environ.get("GEMINI_API_KEY"))
    except Exception:
        return False


def _rate_limit():
    """Apply rate limiting for API calls."""
    global _last_api_call_time
    elapsed = time.time() - _last_api_call_time
    if elapsed < _min_call_interval:
        time.sleep(_min_call_interval - elapsed)
    _last_api_call_time = time.time()


def _call_gemini(prompt: str, system_prompt: str, temperature: float = 0.2) -> Optional[str]:
    """Make API call to Gemini."""
    try:
        import google.generativeai as genai
        
        _rate_limit()
        
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        
        model_name = _get_available_model()
        if not model_name:
            return None
        
        model = genai.GenerativeModel(
            model_name,
            generation_config={'temperature': temperature}
        )
        
        full_prompt = f"{system_prompt}\n\n{prompt}"
        response = model.generate_content(full_prompt)
        
        text = getattr(response, 'text', None)
        if not text and getattr(response, 'candidates', None):
            try:
                text = response.candidates[0].content.parts[0].text
            except Exception:
                return None
        
        return text
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        return None


_cached_model_name = None

def _get_available_model() -> Optional[str]:
    """Get an available Gemini model (cached)."""
    global _cached_model_name
    if _cached_model_name:
        return _cached_model_name
    
    import google.generativeai as genai
    
    test_models = [
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "models/gemini-2.0-flash-exp",
        "models/gemini-1.5-flash",
    ]
    
    for model_name in test_models:
        try:
            model = genai.GenerativeModel(model_name)
            model.generate_content("test")
            _cached_model_name = model_name
            return model_name
        except Exception:
            continue
    
    return None


def _extract_code(text: str) -> str:
    """Extract Python code from markdown or raw text."""
    if '```python' in text:
        parts = text.split('```python')
        if len(parts) > 1:
            return parts[1].split('```')[0].strip()
    elif '```' in text:
        parts = text.split('```')
        if len(parts) > 1:
            return parts[1].strip()
    return text.strip()


def _extract_parameters(code: str) -> Dict[str, float]:
    """Extract parameter definitions from code."""
    parameters = {}
    lines = code.split('\n')
    
    for line in lines:
        # Look for pattern: variable_name = numeric_value
        match = re.match(r'^([a-z_][a-z0-9_]*)\s*=\s*([0-9.]+)', line.strip())
        if match:
            var_name, value = match.groups()
            try:
                parameters[var_name] = float(value)
            except ValueError:
                pass
    
    return parameters


class EnhancedCADAgent:
    """Production-grade CAD AI agent with multi-stage pipeline."""
    
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
    
    async def generate_cad_model(self, prompt: str, 
                                 context: Optional[CADContext] = None) -> Dict[str, Any]:
        """Generate CAD model with multi-stage refinement."""
        if not have_gemini():
            return {'error': 'Gemini API not configured'}
        
        try:
            # Stage 1: Enhance prompt to engineering specification
            print("Stage 1: Enhancing prompt...")
            enhanced_spec = self._enhance_prompt(prompt, context)
            if not enhanced_spec:
                return {'error': 'Failed to enhance prompt'}
            
            # Stage 2: Generate CAD script
            print("Stage 2: Generating CAD script...")
            cad_script = self._generate_script(enhanced_spec, context)
            if not cad_script:
                return {'error': 'Failed to generate script'}
            
            # Stage 3: Validate and refine
            print("Stage 3: Validating and refining...")
            refined_script = self._validate_and_refine(cad_script)
            
            # Stage 4: Extract metadata
            print("Stage 4: Extracting metadata...")
            parameters = _extract_parameters(refined_script)
            
            result = {
                'code': refined_script,
                'specification': enhanced_spec,
                'parameters': parameters,
                'features': self._identify_features(refined_script),
                'success': True
            }
            
            self.history.append({
                'prompt': prompt,
                'result': result
            })
            
            return result
            
        except Exception as e:
            return {'error': f'Generation failed: {str(e)}'}
    
    def _enhance_prompt(self, prompt: str, context: Optional[CADContext]) -> Optional[str]:
        """Stage 1: Transform prompt into detailed engineering specification."""
        context_str = ""
        if context:
            context_str = f"\n\nEXISTING CONTEXT:\n{json.dumps(context.to_dict(), indent=2)}"
        
        full_prompt = f"""Transform this CAD request into a detailed engineering specification:

USER REQUEST: {prompt}{context_str}

Provide a complete engineering specification following the format.
"""
        
        return _call_gemini(full_prompt, ENHANCEMENT_PROMPT, temperature=0.3)
    
    def _generate_script(self, specification: str, context: Optional[CADContext]) -> Optional[str]:
        """Stage 2: Generate CAD script from specification."""
        context_str = ""
        if context and context.manufacturing_method:
            context_str = f"\n\nMANUFACTURING METHOD: {context.manufacturing_method}"
        if context and context.material:
            context_str += f"\nMATERIAL: {context.material}"
        
        full_prompt = f"""Generate a complete Python CAD script for this specification:

{specification}{context_str}

Requirements:
- Use trimesh and numpy
- Assign final mesh to 'result'
- Include all parameters as variables
- Add detailed comments
- Consider manufacturing constraints

Python code:
"""
        
        response = _call_gemini(full_prompt, CADQUERY_EXPERT_PROMPT, temperature=0.2)
        if response:
            return _extract_code(response)
        return None
    
    def _validate_and_refine(self, script: str) -> str:
        """Stage 3: Validate and refine the generated script."""
        # Try to execute for syntax check
        try:
            compile(script, '<string>', 'exec')
            # Script is syntactically valid
            return script
        except SyntaxError as e:
            # Ask AI to fix
            print(f"Syntax error detected: {e}")
            fix_prompt = f"""Fix this Python code:

```python
{script}
```

Error: {str(e)}

Provide corrected code:
"""
            fixed = _call_gemini(fix_prompt, REFINEMENT_PROMPT, temperature=0.1)
            if fixed:
                return _extract_code(fixed)
            return script  # Return original if fix fails
    
    def _identify_features(self, script: str) -> List[str]:
        """Identify features in the script."""
        features = []
        
        # Look for common CAD operations
        if 'box' in script.lower() or 'cube' in script.lower():
            features.append('box')
        if 'cylinder' in script.lower():
            features.append('cylinder')
        if 'sphere' in script.lower():
            features.append('sphere')
        if 'extrude' in script.lower():
            features.append('extrusion')
        if 'union' in script.lower() or '+' in script:
            features.append('boolean_union')
        if 'difference' in script.lower() or '-' in script:
            features.append('boolean_difference')
        
        return features
    
    async def modify_cad_model(self, current_script: str, modification: str, 
                              context: Optional[CADContext] = None) -> Dict[str, Any]:
        """Modify existing CAD script."""
        if not have_gemini():
            return {'error': 'Gemini API not configured'}
        
        try:
            context_str = ""
            if context:
                context_str = f"\n\nCONTEXT:\n{json.dumps(context.to_dict(), indent=2)}"
            
            prompt = f"""Modify this CAD script according to the request:

CURRENT SCRIPT:
```python
{current_script}
```

MODIFICATION REQUEST: {modification}{context_str}

Provide the complete modified script:
"""
            
            response = _call_gemini(prompt, CADQUERY_EXPERT_PROMPT, temperature=0.2)
            if not response:
                return {'error': 'Failed to generate modification'}
            
            modified_script = _extract_code(response)
            refined_script = self._validate_and_refine(modified_script)
            
            return {
                'code': refined_script,
                'parameters': _extract_parameters(refined_script),
                'success': True
            }
            
        except Exception as e:
            return {'error': f'Modification failed: {str(e)}'}


# Singleton instance
_agent_instance: Optional[EnhancedCADAgent] = None

def get_agent() -> EnhancedCADAgent:
    """Get singleton CAD agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = EnhancedCADAgent()
    return _agent_instance
