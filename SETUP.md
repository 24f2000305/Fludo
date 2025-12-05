# 🔧 Setup Guide - CAD Studio

## System Requirements

- **Python**: 3.11 or higher
- **RAM**: 4GB minimum (8GB recommended)
- **Storage**: 500MB for dependencies
- **OS**: Linux, macOS, or Windows (WSL recommended)

---

## Step-by-Step Setup

### 1. Install Dependencies

All required packages are in `requirements.txt`:

```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- `cadquery==2.4.0` - Parametric CAD library
- `cadquery-ocp==7.7.2` - OpenCascade bindings
- `fastapi>=0.112` - Web framework
- `google-generativeai>=0.8` - Gemini AI
- `uvicorn>=0.30` - ASGI server

### 2. Configure Gemini API

**Get your API key:**
1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Copy the key

**Set the environment variable:**

**Linux/macOS:**
```bash
export GEMINI_API_KEY="your-api-key-here"
```

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

**Permanent setup (Linux/macOS):**
Add to `~/.bashrc` or `~/.zshrc`:
```bash
echo 'export GEMINI_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### 3. Verify Installation

Run the test suite:

```bash
python test_cad_system.py
```

You should see:
```
============================================================
Testing CadQuery Engine
============================================================

1. Testing simple box generation...
   ✓ Box generated successfully
   ✓ STL export: 684 bytes
   ✓ STEP export: 15504 bytes

✓ Engine tests completed!
```

### 4. Start the Server

**Development mode (auto-reload):**
```bash
python -m uvicorn app.server:app --host 127.0.0.1 --port 7860 --reload
```

**Production mode:**
```bash
python -m uvicorn app.server:app --host 0.0.0.0 --port 7860 --workers 4
```

### 5. Access the Application

Open your browser and navigate to:
```
http://localhost:7860
```

You should see the CAD Studio interface with:
- Left sidebar: AI prompt and mode selection
- Center: Monaco code editor
- Right: 3D viewer

---

## 🧪 Testing the System

### Test 1: Simple Box (Manual Mode)

1. Select **"Manual Edit"** mode
2. Enter this code:
```python
import cadquery as cq

result = cq.Workplane("XY").box(50, 40, 30)
```
3. Click **"Execute & Visualize"**
4. You should see a 3D box in the viewer

### Test 2: AI Generation (AI Agent Mode)

1. Select **"AI Agent"** mode
2. Enter prompt:
```
Create a simple mounting bracket 80mm x 60mm x 5mm
with 4 mounting holes
```
3. Click **"Generate CAD"**
4. Click **"Execute & Visualize"**
5. Export to STEP format

### Test 3: Complex Part

Try this prompt:
```
Design a robot gripper jaw with:
- Length 60mm, width 25mm, thickness 10mm
- Serrated gripping surface
- 2 mounting holes
- Rounded edges for safety
```

---

## 🐛 Troubleshooting

### Issue: "Module numpy has no attribute 'bool8'"

**Solution:** Downgrade numpy
```bash
pip install 'numpy<2.0.0' --force-reinstall
```

### Issue: "Gemini API key not configured"

**Solution:** Verify the environment variable
```bash
echo $GEMINI_API_KEY  # Linux/macOS
echo $env:GEMINI_API_KEY  # Windows PowerShell
```

If empty, set it:
```bash
export GEMINI_API_KEY="your-key-here"
```

### Issue: "No compatible Gemini models available"

**Solutions:**
1. Check API key is valid
2. Verify internet connection
3. Try a different model in `cad_agent.py`:
```python
test_models = [
    "gemini-1.5-flash",  # Try this first
    "gemini-1.5-pro",
]
```

### Issue: STL export fails

**Solution:** Install additional dependencies
```bash
pip install numpy-stl
```

### Issue: Server won't start

**Check port availability:**
```bash
# Linux/macOS
lsof -i :7860

# Windows
netstat -ano | findstr :7860
```

**Use different port:**
```bash
python -m uvicorn app.server:app --port 8000
```

### Issue: Monaco Editor not loading

**Check browser console** (F12) for errors. Usually caused by:
1. Ad blockers (disable for localhost)
2. CDN blocked (check internet)
3. Browser compatibility (use Chrome/Firefox/Edge)

---

## 📁 Project Structure

```
/app/
├── app/
│   ├── server.py           # FastAPI server + endpoints
│   ├── cad_engine.py       # CadQuery execution engine
│   ├── cad_agent.py        # AI script generation
│   ├── cad_index.html      # Main CAD Studio UI
│   ├── viewer.html         # 3D viewer (Three.js)
│   ├── uploads/            # Temporary model storage
│   └── agent.py            # Legacy agent (kept for reference)
│
├── examples/               # Example CadQuery scripts
│   ├── mounting_bracket.py
│   ├── simple_gear.py
│   └── robot_gripper.py
│
├── requirements.txt        # Python dependencies
├── test_cad_system.py     # Test suite
├── README.md              # Main documentation
├── README_CAD.md          # Detailed CAD guide
└── SETUP.md               # This file
```

---

## 🔒 Security Considerations

### For Production Deployment

1. **API Key Security:**
   - Never commit API keys to git
   - Use environment variables
   - Consider key rotation

2. **CORS Configuration:**
   - Update `allow_origins` in `server.py`
   - Restrict to your domain

3. **Rate Limiting:**
   - Implement rate limiting for `/api/cad/*` endpoints
   - Monitor API usage

4. **Code Execution:**
   - CadQuery scripts run in restricted context
   - Consider sandboxing for public deployment
   - Validate inputs

---

## 🚀 Performance Optimization

### For Large Models

1. **Increase STL tolerance:**
```python
# In cad_engine.py
tolerance = 0.1  # Faster, lower quality
tolerance = 0.001  # Slower, higher quality
```

2. **Use caching:**
```bash
# Enable response caching
pip install fastapi-cache2
```

3. **Increase workers:**
```bash
uvicorn app.server:app --workers 4
```

---

## 📞 Support

### Getting Help

1. Check `README_CAD.md` for detailed CadQuery documentation
2. Review examples in `/examples/` folder
3. Check console logs for error messages
4. Verify all tests pass: `python test_cad_system.py`

### Useful Resources

- [CadQuery Docs](https://cadquery.readthedocs.io/)
- [CadQuery Examples](https://github.com/CadQuery/cadquery/tree/master/examples)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Three.js Docs](https://threejs.org/docs/)

---

## ✅ Verification Checklist

Before using the system, verify:

- [ ] Python 3.11+ installed: `python --version`
- [ ] All dependencies installed: `pip list | grep cadquery`
- [ ] Gemini API key set: `echo $GEMINI_API_KEY`
- [ ] Tests pass: `python test_cad_system.py`
- [ ] Server starts: `uvicorn app.server:app`
- [ ] Browser loads UI: `http://localhost:7860`
- [ ] Manual mode works (test simple box)
- [ ] AI mode works (test simple prompt)
- [ ] Export works (test STEP export)

---

**Ready to build production-quality CAD models!** 🎉
