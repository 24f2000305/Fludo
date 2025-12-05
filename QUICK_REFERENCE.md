# 🔧 Quick Reference - CAD Studio

## 🚀 Start Commands

```bash
# Set API key (required for AI features)
export GEMINI_API_KEY="your-key-here"

# Test system
python test_cad_system.py

# Start server
python -m uvicorn app.server:app --host 127.0.0.1 --port 7860 --reload

# Open browser
http://localhost:7860
```

---

## 📝 CadQuery Cheat Sheet

### Basic Structure
```python
import cadquery as cq

result = (cq.Workplane("XY")
    # Chain operations here
)
```

### 2D Sketching
```python
.rect(width, height)              # Rectangle
.circle(radius)                   # Circle
.polygon(sides, diameter)         # Polygon
.slot2D(length, diameter)         # Slot
```

### 3D Operations
```python
.extrude(distance)                # Extrude up
.extrude(-distance)               # Extrude down
.revolve(degrees)                 # Revolve around axis
.sweep(path)                      # Sweep along path
```

### Holes & Features
```python
.hole(diameter)                   # Through hole
.hole(diameter, depth)            # Blind hole
.cboreHole(diameter, cbore_dia, cbore_depth)  # Counterbore
.cskHole(diameter, csk_dia, csk_angle)        # Countersink
```

### Edge Operations
```python
.edges("|Z").fillet(radius)       # Fillet vertical edges
.edges(">Z").chamfer(length)      # Chamfer top edges
.edges("<Z").chamfer(length)      # Chamfer bottom edges
```

### Patterns
```python
.rarray(xSpacing, ySpacing, xCount, yCount)   # Rectangular array
.polarArray(radius, startAngle, angle, count) # Circular pattern
```

### Selection
```python
.faces(">Z")                      # Top face
.faces("<Z")                      # Bottom face
.faces("|Z")                      # Vertical faces
.edges("|Z")                      # Vertical edges
.vertices()                       # All vertices
```

### Boolean Operations
```python
.union(other)                     # Add
.cut(other)                       # Subtract
.intersect(other)                 # Intersect
```

---

## 💡 Common Patterns

### Bracket with Holes
```python
import cadquery as cq

result = (cq.Workplane("XY")
    .rect(80, 60).extrude(5)
    .faces(">Z").workplane()
    .rect(60, 40, forConstruction=True)
    .vertices().hole(6)
    .edges("|Z").fillet(3)
)
```

### Cylinder with Hole
```python
import cadquery as cq

result = (cq.Workplane("XY")
    .circle(25).extrude(50)
    .faces(">Z").workplane()
    .hole(10)
)
```

### Flange
```python
import cadquery as cq

result = (cq.Workplane("XY")
    .circle(40).extrude(10)
    .faces(">Z").workplane()
    .circle(15).cutThruAll()
    .faces(">Z").workplane()
    .pushPoints([(30, 0), (-30, 0), (0, 30), (0, -30)])
    .hole(6)
)
```

### Gearlike Part
```python
import cadquery as cq
import math

teeth = 16
result = cq.Workplane("XY").circle(20).extrude(10)

for i in range(teeth):
    angle = i * 360 / teeth
    tooth = (cq.Workplane("XY")
        .move(20, 0)
        .rect(3, 5)
        .extrude(10)
        .rotate((0,0,0), (0,0,1), angle)
    )
    result = result.union(tooth)

result = result.faces(">Z").hole(8)
```

---

## 🎯 Example Prompts

### Mechanical
- "Create a mounting bracket 80x60x5mm with 4 M6 holes"
- "Design a flange coupling 100mm diameter with 6 bolt holes"
- "Make a linear bearing block with 16mm bore"

### Robotics
- "Create a robot gripper jaw with serrations"
- "Design a motor mount for NEMA 17"
- "Make a robot arm joint bracket"

### Enclosures
- "Create a Raspberry Pi enclosure with ventilation"
- "Design a weatherproof sensor housing"
- "Make a battery holder for 4x AA batteries"

---

## 🔍 Debugging Tips

### Check Workplane
```python
# Print info
print(result.val().isValid())

# Get bounding box
bb = result.val().BoundingBox()
print(f"Size: {bb.xlen} x {bb.ylen} x {bb.zlen}")
```

### Validate Result
```python
# Check if solid
if result.val().Volume() > 0:
    print("Valid solid")
```

### Export for Debugging
```python
# Save to file to inspect
result.exportStl("debug.stl")
```

---

## ⚡ Performance Tips

1. **Use lower tolerance for preview** (0.1)
2. **Use higher tolerance for export** (0.01)
3. **Cache complex operations**
4. **Use construction geometry** (forConstruction=True)
5. **Minimize face/edge selections**

---

## 🐛 Common Errors

### "No result found"
```python
# ✗ Wrong
cq.Workplane("XY").box(10, 10, 10)

# ✓ Correct
result = cq.Workplane("XY").box(10, 10, 10)
```

### "Invalid geometry"
```python
# Check dimensions are positive
result = cq.Workplane("XY").box(10, 10, 10)  # ✓
result = cq.Workplane("XY").box(-10, 10, 10)  # ✗
```

### "Hole failed"
```python
# Make sure face is selected
result = (cq.Workplane("XY")
    .box(10, 10, 10)
    .faces(">Z").workplane()  # Select face first
    .hole(5)
)
```

---

## 📦 Export Guide

### STEP (Recommended for CAD)
- Industry standard
- Preserves geometry exactly
- Use for: CNC, CAM, further CAD work

### STL (Recommended for 3D Printing)
- Mesh format
- Adjust tolerance (0.01 - 0.001)
- Use for: 3D printing, visualization

### IGES (Legacy CAD)
- Older format
- Use when STEP not supported

### DXF (2D Drawings)
- 2D only
- Use for: Laser cutting, technical drawings

---

## 🎨 UI Shortcuts

- `Ctrl/Cmd + S` - Save editor content (browser default)
- `Ctrl/Cmd + /` - Comment/uncomment line
- `Ctrl/Cmd + F` - Find in editor
- `Ctrl/Cmd + Z` - Undo
- `Ctrl/Cmd + Shift + Z` - Redo

---

## 📞 Quick Help

```bash
# Test if working
python test_cad_system.py

# Check logs
tail -f /tmp/server.log

# Verify API key
echo $GEMINI_API_KEY

# Check dependencies
pip list | grep cadquery
```

---

**Keep this handy while designing!** 📋
