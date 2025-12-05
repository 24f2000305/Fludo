# Import/Export Functionality Enhancement

## Overview
Added robust import/export functionality with OBJ file support to FLUDO CAD Studio.

## Changes Made

### 1. Backend Changes (`app/cad_engine.py`)
- **Added `export_obj()` method**: Exports CadQuery models to Wavefront OBJ format
  - Converts STL to OBJ format with proper vertex deduplication
  - Handles binary STL parsing with struct module
  - Generates valid OBJ file with vertices and faces

### 2. Backend API (`app/server.py`)
- **Added `tempfile` import**: For temporary file handling
- **Updated `/api/cad/export/{format}` endpoint**: Now supports 'obj' format
  - Added OBJ export case with `text/plain` media type
  - Updated format validation to include 'obj'
- **Added `/api/upload/obj` endpoint**: Handles OBJ file uploads
  - Validates .obj file extension
  - Checks for valid OBJ content (vertex lines)
  - Saves to temporary directory with unique ID
  - Returns URL for viewer to load
- **Added `/api/temp/obj/{temp_id}` endpoint**: Serves temporary OBJ files
  - Returns OBJ file content with proper headers
  - Handles file not found errors

### 3. Frontend UI (`app/cad_studio_v2.html`)
- **Added Import section** in left sidebar:
  - "Import OBJ" button with 📥 icon
- **Added Export OBJ button**:
  - "Export OBJ" button with "O" icon in Export section
- **Added hidden file input**: `<input id="obj-import-input" accept=".obj">`
- **Enhanced export handlers**:
  - All export functions now send the CadQuery script in request body
  - Proper error handling with user feedback
  - URL cleanup with `revokeObjectURL()`
- **Added Import OBJ handler**:
  - Opens file picker on button click
  - Uploads file via FormData to `/api/upload/obj`
  - Posts message to viewer iframe to load OBJ
  - Shows success/error messages via LUDO chat
- **Updated tool filter**: Excludes "Import OBJ" and "Export OBJ" from code template tools

### 4. Viewer (`app/viewer.html`)
- **Added `loadOBJ` message handler**:
  - Uses THREE.OBJLoader (already imported)
  - Clears scene before loading
  - Applies material preset to all meshes
  - Enables shadows (cast and receive)
  - Fits view to imported model
  - Restores grid if enabled

## Supported File Formats

### Import
- ✅ **OBJ** (Wavefront Object) - via Upload

### Export
- ✅ **STL** (Stereolithography) - CadQuery native
- ✅ **STEP** (ISO 10303) - CadQuery native
- ✅ **IGES** (Initial Graphics Exchange) - via STEP conversion
- ✅ **DXF** (Drawing Exchange Format) - 2D export
- ✅ **OBJ** (Wavefront Object) - via STL conversion

## User Workflow

### Exporting
1. Generate or write a CadQuery model in the editor
2. Click "Export STL", "Export STEP", or "Export OBJ" in left sidebar
3. File downloads automatically with appropriate extension

### Importing OBJ
1. Click "Import OBJ" in left sidebar
2. Select .obj file from file picker
3. File uploads to server
4. Model appears in 3D viewer with grid restored
5. LUDO provides success feedback

## Technical Notes

### OBJ Export Conversion
- CadQuery doesn't natively support OBJ export
- Solution: Export as STL (binary), then convert to OBJ
- Vertex deduplication prevents file bloat
- Precision: 6 decimal places for vertex coordinates

### Temporary File Handling
- Uploaded OBJ files stored in system temp directory
- Unique 8-byte hex ID prevents collisions
- Files served via `/api/temp/obj/{temp_id}` endpoint
- No automatic cleanup (system temp cleanup handles this)

### Security Considerations
- File extension validation (.obj only)
- Content validation (checks for 'v ' vertex lines)
- UTF-8 encoding required (text format)
- File size limit: FastAPI default (16MB)

## Future Enhancements
- Add GLTF/GLB import support
- Add STL import support
- Implement automatic temp file cleanup (TTL)
- Add file size validation and user feedback
- Support MTL materials for OBJ files
- Add drag-and-drop import
