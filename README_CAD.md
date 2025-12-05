# 🔧 CAD Studio - Production-Level CAD Tool

**Powered by CadQuery + OpenCascade (OCCT)**

A professional-grade, AI-powered CAD modeling tool that generates production-quality 3D models from natural language descriptions. Think of it as "Cursor IDE for Hardware Engineers" - combining the power of AI with precision parametric CAD.

---

## 🚀 What's New - Production CAD System

### Complete Architecture Overhaul

#### ✅ **CadQuery + OCCT Integration**
- Replaced primitive geometry system with **CadQuery 2.4** (professional parametric CAD library)
- **OpenCascade Technology (OCCT)** for industry-standard CAD kernel
- Accurate measurements, constraints, and engineering-grade precision

#### ✅ **Dual Editing Modes**
1. **AI Agent Mode**: Natural language → CadQuery Python scripts
   - Generate complete CAD models from descriptions
   - Modify existing designs with natural language
   - AI understands engineering constraints and best practices

2. **Manual Mode**: Direct script editing
   - Monaco Editor (same as VS Code) with Python syntax highlighting
   - Full CadQuery API access
   - Real-time error detection

#### ✅ **Professional CAD Export**
- **STEP (.step)** - Industry standard for CAD interchange
- **STL (.stl)** - 3D printing and visualization
- **IGES (.iges)** - Legacy CAD format support
- **DXF (.dxf)** - 2D drawings

#### ✅ **Production-Ready Features**
- Accurate dimensional modeling (millimeters)
- Parametric design capabilities
- Constraint-based modeling
- Manufacturing-ready output
- Real-time 3D visualization

---

## 📦 Installation

### Prerequisites
- Python 3.11+
- Google Gemini API Key (for AI features)

### Setup

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Set Gemini API Key**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

3. **Run the Server**
```bash
python -m uvicorn app.server:app --host 127.0.0.1 --port 7860 --reload
```

4. **Open in Browser**
```
http://localhost:7860
```

---

## 🎯 Quick Start Guide

### AI Agent Mode (Recommended for Quick Designs)

1. **Select "AI Agent" mode** in the sidebar
2. **Enter a description** in the prompt box:
   ```
   Create a mounting bracket 80mm x 60mm x 5mm thick 
   with 4 mounting holes (M6) at the corners
   ```
3. **Click "Generate CAD"** - AI generates CadQuery script
4. **Click "Execute & Visualize"** - See your 3D model
5. **Export** to STEP, STL, IGES, or DXF

### Manual Mode (For Expert Users)

1. **Select "Manual Edit" mode**
2. **Write CadQuery code** directly:
   ```python
   import cadquery as cq
   
   result = (cq.Workplane("XY")
       .rect(80, 60)
       .extrude(5)
       .faces(">Z").workplane()
       .rect(60, 40, forConstruction=True)
       .vertices()
       .hole(6)
       .edges("|Z").fillet(3)
   )
   ```
3. **Click "Execute & Visualize"**
4. **Export** when ready

### Modifying Existing Designs

1. **Generate or load a design**
2. **Enter modification** in prompt:
   ```
   Make the holes 8mm diameter instead of 6mm
   Add chamfers on all edges
   ```
3. **Click "Modify Existing"**
4. **Execute & visualize** the updated design

---

## 📚 CadQuery Basics

### Core Concepts

```python
import cadquery as cq

# Start with a workplane (XY, XZ, or YZ)
result = cq.Workplane("XY")

# 2D Sketching
.rect(width, height)           # Rectangle
.circle(radius)                # Circle
.polygon(sides, diameter)      # Polygon

# 3D Operations
.extrude(height)              # Extrude sketch
.revolve(degrees)             # Revolve around axis
.loft([profile1, profile2])   # Loft between profiles

# Features
.hole(diameter, depth=None)   # Create holes (depth=None = through)
.fillet(radius)               # Round edges
.chamfer(length)              # Chamfer edges

# Patterns
.rarray(xSpace, ySpace, xCount, yCount)  # Rectangular array
.polarArray(radius, 0, 360, count)       # Circular pattern

# Boolean Operations
.union(other)                 # Add
.cut(other)                   # Subtract
.intersect(other)             # Intersect
```

### Example: Gear

```python
import cadquery as cq
import math

# Parameters
module = 2.0
teeth = 20
pressure_angle = 20
thickness = 10

# Calculate dimensions
pitch_diameter = module * teeth
base_radius = pitch_diameter / 2

# Create gear
result = (cq.Workplane("XY")
    .circle(base_radius)
    .extrude(thickness)
    .faces(">Z").workplane()
    .hole(10)  # Center bore
)

# Add teeth (simplified involute profile)
tooth_profile = (cq.Workplane("XY")
    .move(base_radius, 0)
    .lineTo(base_radius + module, module * 0.5)
    .lineTo(base_radius + module, -module * 0.5)
    .close()
)

for i in range(teeth):
    angle = i * 360 / teeth
    tooth = tooth_profile.rotate((0, 0, 0), (0, 0, 1), angle)
    result = result.union(tooth.extrude(thickness))

result = result.edges("|Z").fillet(0.5)
```

---

## 🎨 Example Prompts

### Mechanical Parts
- "Create a flange coupling 100mm diameter, 20mm thick, with 6 M8 bolt holes on a 75mm PCD"
- "Design a linear bearing block with 4 mounting holes and a 16mm bore"
- "Make a GT2 timing pulley with 20 teeth and a 5mm bore"

### Brackets & Mounts
- "Create an L-bracket 50x50mm, 5mm thick, with 2 mounting holes on each leg"
- "Design a motor mount for NEMA 17 stepper motor"
- "Make a camera gimbal mount with pan/tilt capability"

### Enclosures
- "Create a Raspberry Pi enclosure 90x60x25mm with ventilation slots"
- "Design a weatherproof sensor housing with cable glands"
- "Make a battery holder for 4x AA batteries"

### Robotics
- "Create a robot gripper with parallel jaws, 40mm grip range"
- "Design a robot arm joint with 90-degree rotation"
- "Make a wheel hub adapter for 6mm shaft to 50mm wheel"

---

## 🏗️ Architecture

### Backend (`/app/`)
- `cad_engine.py` - CadQuery execution engine, CAD export (STEP, STL, IGES, DXF)
- `cad_agent.py` - AI agent for script generation/modification using Gemini
- `server.py` - FastAPI server with CAD endpoints
- `agent.py` - Legacy agent (kept for reference)
- `generator.py` - Legacy generator (kept for reference)

### Frontend
- `cad_index.html` - New CAD Studio interface
- Monaco Editor - Professional code editor
- Three.js - 3D visualization
- `viewer.html` - 3D model viewer

### API Endpoints

#### POST `/api/cad/generate`
Generate CadQuery script from natural language
```json
{
  "prompt": "Create a mounting bracket..."
}
```

#### POST `/api/cad/modify`
Modify existing script
```json
{
  "script": "import cadquery as cq...",
  "modification": "Make it bigger"
}
```

#### POST `/api/cad/execute`
Execute script and return STL for visualization
```json
{
  "script": "import cadquery as cq..."
}
```

#### POST `/api/cad/export/{format}`
Export to STEP, STL, IGES, or DXF
```json
{
  "script": "import cadquery as cq..."
}
```

---

## 🔧 Configuration

### Environment Variables

```bash
# Required for AI features
export GEMINI_API_KEY="your-gemini-api-key"

# Optional
export CADQUERY_TOLERANCE=0.01  # STL export tolerance
```

---

## 📖 CadQuery Resources

- [CadQuery Documentation](https://cadquery.readthedocs.io/)
- [CadQuery Examples](https://github.com/CadQuery/cadquery/tree/master/examples)
- [OpenCascade Documentation](https://dev.opencascade.org/)

---

## 🎯 Roadmap

### Phase 1 (Current) ✅
- [x] CadQuery + OCCT integration
- [x] AI script generation
- [x] Professional CAD export (STEP, STL, IGES, DXF)
- [x] Monaco Editor integration
- [x] Dual editing modes

### Phase 2 (Next)
- [ ] Assembly support
- [ ] Constraint solver UI
- [ ] Parameter inspector panel
- [ ] BREP export
- [ ] BOM generation
- [ ] Technical drawings (DXF 2D)

### Phase 3 (Future)
- [ ] Collaboration features
- [ ] Version control integration
- [ ] FEA integration
- [ ] CAM toolpath generation
- [ ] Cloud rendering

---

## 🤝 Contributing

Contributions welcome! This is a production-grade CAD system built for real engineering work.

---

## 📄 License

MIT License

---

## 🙏 Acknowledgments

- **CadQuery** - Parametric CAD for Python
- **OpenCascade** - Professional CAD kernel
- **Google Gemini** - AI model
- **Monaco Editor** - VS Code editor
- **Three.js** - 3D visualization

---

## 💡 Tips & Tricks

### Best Practices for AI Prompts
- Be specific with dimensions (always include units)
- Mention material/manufacturing constraints
- Describe the function/use case
- Reference standard parts (M6 bolt, NEMA 17, etc.)

### Performance Optimization
- Use lower STL tolerance for faster previews (0.1)
- Use higher tolerance for exports (0.01 or 0.001)
- Cache complex operations in variables
- Use constraints instead of hardcoded values

### Debugging Scripts
- Check console for detailed error messages
- Use comments to document complex operations
- Test incrementally (build up complexity)
- Verify dimensions with .val() method

---

**Built with ❤️ for hardware engineers, makers, and CAD enthusiasts**
