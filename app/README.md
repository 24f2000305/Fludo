## Desktop Agent & Viewer

### Highlights
- PySide6 desktop UI that streams text prompts into a JSON CAD spec and renders everything live in a Three.js viewer (Blender no longer required).
- Spec side-panel mirrors the latest JSON so you can inspect or tweak it; reuse the prompt box to edit previous outputs in natural language.
- "Record GIF" captures a turntable animation and drops the file path into the log for quick sharing.

### Requirements
- Python 3.10+ on Windows or macOS.
- Install dependencies from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# optional for cloud LLM support
pip install google-generativeai
```

- Optional: export `GEMINI_API_KEY` to route prompts through Google Gemini. Without it, a built-in heuristic handles primitives, transforms, add/remove operations, and hosted GLTF/OBJ URLs.

### Run
```powershell
$env:GEMINI_API_KEY = "<your-api-key>"  # optional
python .\app\main.py
```

### Flow
1. `app/main.py` collects prompts, hands them to `app/agent.py`, and forwards the returned spec to `app/viewer.html` as a base64 payload.
2. `app/agent.py` prefers Gemini when available; otherwise the local agent supports boxes, cylinders, spheres, cones, tori, external models, add/remove verbs, and simple transform adjustments.
3. `app/viewer.html` re-creates the scene with Three.js, including optional grid/axes/spin helpers. External models load through the OBJ/GLTF loaders and inherit the spec transform automatically.
4. GIF capture rotates the scene for ~2 seconds, saves to the temp folder (`%TEMP%\hase_app_*`), and logs the path.

### Tips
- Chain instructions: “add a torus radius 3”, “move it to 10 0 5”, “replace it with a cone height 8”.
- Toggle Grid/Axes/Spin above the viewer; “Fit View” recentres the camera via a quick JavaScript call.
- Click “Save Spec as JSON” to persist the current scene for later use.
- Paste a hosted `.gltf`, `.glb`, or `.obj` URL to preview richer CAD content alongside primitives.
- GIF files are lightweight; drop them into documentation or send to teammates as instant CAD previews.


