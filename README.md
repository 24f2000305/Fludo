# 🔧 CAD Studio - Production-Level CAD Tool

**"Cursor for Hardware Engineers"** - AI-Powered Parametric CAD System

A professional-grade CAD modeling tool powered by **CadQuery + OpenCascade (OCCT)** that generates production-quality 3D models from natural language descriptions. Perfect for engineers, makers, and hardware developers.

---

## 🚀 Major Upgrade - Production CAD System

### What's New

✅ **CadQuery + OCCT Integration** - Industry-standard parametric CAD kernel  
✅ **AI-Powered Code Generation** - Generate CadQuery Python scripts from natural language  
✅ **Dual Editing Modes** - AI Agent mode OR Manual script editing  
✅ **Professional CAD Export** - STEP, STL, IGES, DXF formats  
✅ **Monaco Editor** - VS Code-quality code editor with syntax highlighting  
✅ **Accurate Measurements** - Real engineering dimensions (millimeters)  
✅ **Manufacturing-Ready** - Export formats for CNC, 3D printing, and CAM  

---

## 🎯 Features

### AI Agent Mode
- 🤖 Generate CAD models from natural language descriptions
- ✏️ Modify existing designs with simple instructions
- 🧠 AI understands engineering constraints and best practices
- 📝 Produces clean, documented CadQuery Python code

### Manual Editing Mode
- 💻 Professional code editor (Monaco - same as VS Code)
- 🐍 Full CadQuery API access
- 🔍 Real-time syntax checking
- 📚 Extensive examples and documentation

### Professional Output
- 📐 STEP format - Industry standard CAD interchange
- 🖨️ STL format - 3D printing and visualization
- 🔧 IGES format - Legacy CAD system support
- 📄 DXF format - 2D technical drawings

---

## 🏗️ Tech Stack

- **CAD Engine**: CadQuery 2.4 + OpenCascade (OCCT)
- **Backend**: FastAPI (Python 3.11+)
- **AI**: Google Gemini API
- **Frontend**: Monaco Editor + Three.js
- **3D Visualization**: Three.js with STLLoader

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Google Gemini API Key (for AI features)

### Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set Gemini API Key:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

3. **Test the system:**
```bash
python test_cad_system.py
```

4. **Run the server:**
```bash
python -m uvicorn app.server:app --host 127.0.0.1 --port 7860 --reload
```

5. **Open in browser:**
```
http://localhost:7860
```

---

## 📖 Usage Guide

### AI Agent Mode (Quick Start)

1. Select **"AI Agent"** mode in the sidebar
2. Enter a description:
   ```
   Create a mounting bracket 80mm x 60mm x 5mm 
   with 4 M6 mounting holes at corners
   ```
3. Click **"Generate CAD"**
4. Click **"Execute & Visualize"**
5. Export to STEP, STL, IGES, or DXF

### Manual Mode (Expert Users)

1. Select **"Manual Edit"** mode
2. Write CadQuery Python code:
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
3. Click **"Execute & Visualize"**
4. Export when ready

### Modifying Designs

1. Generate or load a design
2. Enter modification in prompt:
   ```
   Make holes 8mm diameter
   Add 2mm chamfers on top edges
   ```
3. Click **"Modify Existing"**
4. Execute & visualize

## Deployment on Vercel

1. Install Vercel CLI:
```bash
npm install -g vercel
```

2. Login to Vercel:
```bash
vercel login
```

3. Deploy:
```bash
vercel
```

4. Set environment variable in Vercel dashboard:
   - Go to your project settings
   - Add `GEMINI_API_KEY` with your API key

## Usage

### Creating Models

1. **Text Prompt**: Type a description like "create a red bicycle" in the chat
2. **Click Render**: The AI will generate a 3D model based on your description
3. **Edit**: Select objects and use the inspector to modify properties

### Multi-Selection

- **Checkboxes**: Use checkboxes in the Scene Objects list
- **Shift+Click**: Hold Shift and click objects in the 3D viewer

### Color Editing

1. Select one or more objects
2. Choose a color from the color chips or color picker
3. Click "Apply" to update all selected objects

### Transform Controls

- **W Key**: Move/Translate mode
- **E Key**: Rotate mode
- **R Key**: Scale mode
- **F Key**: Fit view to object

## API Endpoints

- `GET /` - Main application
- `GET /viewer.html` - 3D viewer iframe
- `POST /api/build_spec` - Generate 3D specifications from text
- `POST /api/enhance` - Enhance prompts with detailed specifications
- `POST /api/ask` - Q&A endpoint
- `POST /api/upload_model` - Upload 3D model files
- `POST /api/fetch_model` - Fetch models from URL

## Project Structure

```
├── app/
│   ├── server.py          # FastAPI server
│   ├── agent.py           # AI agent logic
│   ├── web_index.html     # Main application UI
│   ├── viewer.html        # 3D viewer component
│   └── uploads/           # Uploaded models directory
├── requirements.txt       # Python dependencies
├── vercel.json           # Vercel configuration
└── README.md             # This file
```

## Environment Variables

- `GEMINI_API_KEY` - Your Google Gemini API key (required)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License

## Author

Sachin Maurya ([@sachinmaurya-agi](https://github.com/sachinmaurya-agi))

## Acknowledgments

- Three.js for 3D rendering
- Google Gemini for AI capabilities
- FastAPI for the backend framework
