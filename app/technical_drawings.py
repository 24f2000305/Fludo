"""Technical Drawings Generator for CAD Parts.

Generates professional 2D engineering drawings with dimensions, annotations, and title blocks.
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle, FancyArrowPatch
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment
import trimesh


class TechnicalDrawing:
    """Generate professional 2D technical drawings."""
    
    def __init__(self, part_name: str, scale: float = 1.0):
        self.part_name = part_name
        self.scale = scale
        self.dimensions: List[Dict[str, Any]] = []
        self.notes: List[str] = []
        self.views: List[Dict[str, Any]] = []
        
    def add_dimension(self, measurement: Dict[str, Any]):
        """Add dimension to drawing."""
        self.dimensions.append(measurement)
    
    def add_note(self, note: str):
        """Add note to drawing."""
        self.notes.append(note)
    
    def add_view(self, view_type: str, projection: np.ndarray, bounds: Tuple):
        """Add orthographic view."""
        self.views.append({
            'type': view_type,
            'projection': projection,
            'bounds': bounds
        })
    
    def generate_pdf(self, filepath: str, part_mesh: Optional[trimesh.Trimesh] = None):
        """Generate PDF drawing with multiple views."""
        fig = plt.figure(figsize=(11, 8.5))  # Letter size
        
        # Create layout: Front, Top, Right views + Title block
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3,
                             left=0.08, right=0.95, top=0.92, bottom=0.08)
        
        # Generate views if mesh provided
        if part_mesh:
            self._generate_orthographic_views(part_mesh)
        
        # Front view
        ax_front = fig.add_subplot(gs[1, 0])
        self._draw_view(ax_front, 'Front View', 'XZ')
        
        # Top view  
        ax_top = fig.add_subplot(gs[0, 0])
        self._draw_view(ax_top, 'Top View', 'XY')
        
        # Right view
        ax_right = fig.add_subplot(gs[1, 1])
        self._draw_view(ax_right, 'Right View', 'YZ')
        
        # Isometric view
        ax_iso = fig.add_subplot(gs[0:2, 2], projection='3d')
        if part_mesh:
            self._draw_isometric(ax_iso, part_mesh)
        
        # Title block
        ax_title = fig.add_subplot(gs[2, :])
        self._draw_title_block(ax_title)
        
        # Add notes
        if self.notes:
            ax_notes = fig.add_subplot(gs[0, 1])
            self._draw_notes(ax_notes)
        
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
    
    def _generate_orthographic_views(self, mesh: trimesh.Trimesh):
        """Generate orthographic projections from 3D mesh."""
        # Get mesh bounds
        bounds = mesh.bounds
        
        # Front view (looking along Y-axis)
        vertices_xz = mesh.vertices[:, [0, 2]]
        self.views.append({
            'type': 'front',
            'points': vertices_xz,
            'bounds': (bounds[0, 0], bounds[1, 0], bounds[0, 2], bounds[1, 2])
        })
        
        # Top view (looking along Z-axis)
        vertices_xy = mesh.vertices[:, [0, 1]]
        self.views.append({
            'type': 'top',
            'points': vertices_xy,
            'bounds': (bounds[0, 0], bounds[1, 0], bounds[0, 1], bounds[1, 1])
        })
        
        # Right view (looking along X-axis)
        vertices_yz = mesh.vertices[:, [1, 2]]
        self.views.append({
            'type': 'right',
            'points': vertices_yz,
            'bounds': (bounds[0, 1], bounds[1, 1], bounds[0, 2], bounds[1, 2])
        })
    
    def _draw_view(self, ax, title: str, plane: str):
        """Draw a single orthographic view."""
        ax.set_title(title, fontsize=10, fontweight='bold')
        ax.set_aspect('equal')
        ax.grid(True, linestyle=':', alpha=0.3)
        
        # Find matching view
        view_data = None
        for view in self.views:
            if plane.lower() in view['type'].lower():
                view_data = view
                break
        
        if view_data and 'points' in view_data:
            points = view_data['points']
            bounds = view_data['bounds']
            
            # Draw outline (convex hull of projection)
            if len(points) > 0:
                from scipy.spatial import ConvexHull
                try:
                    hull = ConvexHull(points)
                    hull_points = points[hull.vertices]
                    hull_points = np.vstack([hull_points, hull_points[0]])
                    ax.plot(hull_points[:, 0], hull_points[:, 1], 'k-', linewidth=1.5)
                except:
                    # If convex hull fails, just plot points
                    ax.plot(points[:, 0], points[:, 1], 'k.', markersize=1)
            
            # Set limits
            margin = 5
            ax.set_xlim(bounds[0] - margin, bounds[1] + margin)
            ax.set_ylim(bounds[2] - margin, bounds[3] + margin)
        
        ax.set_xlabel('mm', fontsize=8)
        ax.set_ylabel('mm', fontsize=8)
    
    def _draw_isometric(self, ax, mesh: trimesh.Trimesh):
        """Draw isometric view."""
        ax.set_title('Isometric View', fontsize=10, fontweight='bold')
        
        # Plot mesh
        faces = mesh.faces
        vertices = mesh.vertices
        
        # Simple wireframe
        for face in faces[::max(1, len(faces)//1000)]:  # Subsample for performance
            triangle = vertices[face]
            triangle = np.vstack([triangle, triangle[0]])
            ax.plot(triangle[:, 0], triangle[:, 1], triangle[:, 2], 
                   'k-', linewidth=0.3, alpha=0.3)
        
        ax.set_xlabel('X (mm)', fontsize=8)
        ax.set_ylabel('Y (mm)', fontsize=8)
        ax.set_zlabel('Z (mm)', fontsize=8)
        ax.grid(True, alpha=0.3)
    
    def _draw_title_block(self, ax):
        """Draw title block with part information."""
        ax.axis('off')
        
        # Title block rectangle
        bbox = FancyBboxPatch((0.05, 0.1), 0.9, 0.8,
                              boxstyle="round,pad=0.01",
                              edgecolor='black', facecolor='white',
                              linewidth=2)
        ax.add_patch(bbox)
        
        # Part name
        ax.text(0.5, 0.7, self.part_name,
               ha='center', va='center', fontsize=16, fontweight='bold')
        
        # Details
        details = f"Scale: {self.scale}:1\nDate: {datetime.now().strftime('%Y-%m-%d')}"
        ax.text(0.1, 0.35, details,
               ha='left', va='center', fontsize=10)
        
        # Standard info
        ax.text(0.1, 0.2, "Unless otherwise specified:\nDimensions in mm\nTolerances: ±0.1mm",
               ha='left', va='top', fontsize=8, style='italic')
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    
    def _draw_notes(self, ax):
        """Draw notes section."""
        ax.axis('off')
        ax.set_title('Notes', fontsize=10, fontweight='bold', loc='left')
        
        notes_text = "\n".join([f"{i+1}. {note}" for i, note in enumerate(self.notes)])
        ax.text(0.05, 0.9, notes_text,
               ha='left', va='top', fontsize=8,
               transform=ax.transAxes)
        
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
    
    def export_dxf(self, filepath: str, part_mesh: Optional[trimesh.Trimesh] = None):
        """Export drawing to DXF format."""
        doc = ezdxf.new('R2010')
        doc.units = units.MM
        
        msp = doc.modelspace()
        
        # Generate views if mesh provided
        if part_mesh:
            self._generate_orthographic_views(part_mesh)
        
        # Add views to DXF
        offset_x = 0
        for view in self.views:
            if 'points' in view:
                points = view['points']
                
                # Draw outline
                if len(points) > 2:
                    from scipy.spatial import ConvexHull
                    try:
                        hull = ConvexHull(points)
                        hull_points = points[hull.vertices]
                        
                        # Add polyline
                        points_3d = [(p[0] + offset_x, p[1], 0) for p in hull_points]
                        points_3d.append(points_3d[0])  # Close path
                        msp.add_lwpolyline(points_3d, close=True)
                        
                    except:
                        pass
                
                # Add view label
                bounds = view['bounds']
                label_pos = (offset_x + (bounds[0] + bounds[1])/2, bounds[3] + 10, 0)
                msp.add_text(view['type'].upper(), height=5).set_placement(label_pos)
                
                offset_x += (bounds[1] - bounds[0]) + 50
        
        # Add title block
        title_y = -50
        msp.add_text(f"PART: {self.part_name}", height=10).set_placement((10, title_y, 0))
        msp.add_text(f"DATE: {datetime.now().strftime('%Y-%m-%d')}", height=5).set_placement((10, title_y - 15, 0))
        
        doc.saveas(filepath)


class BOMGenerator:
    """Bill of Materials generator."""
    
    def __init__(self):
        self.items: List[Dict[str, Any]] = []
    
    def add_item(self, part_number: str, description: str, quantity: int,
                material: str = "", notes: str = ""):
        """Add item to BOM."""
        self.items.append({
            'part_number': part_number,
            'description': description,
            'quantity': quantity,
            'material': material,
            'notes': notes
        })
    
    def generate_csv(self, filepath: str):
        """Generate BOM as CSV file."""
        import csv
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Item', 'Part Number', 'Description', 'Quantity', 'Material', 'Notes'])
            
            for i, item in enumerate(self.items, 1):
                writer.writerow([
                    i,
                    item['part_number'],
                    item['description'],
                    item['quantity'],
                    item['material'],
                    item['notes']
                ])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'items': self.items,
            'total_items': len(self.items),
            'total_quantity': sum(item['quantity'] for item in self.items)
        }


def generate_drawing_for_part(part_name: str, mesh: trimesh.Trimesh, 
                              output_path: str, format: str = 'pdf') -> str:
    """Convenience function to generate drawing for a part."""
    drawing = TechnicalDrawing(part_name)
    
    # Add default notes
    drawing.add_note("All dimensions in millimeters")
    drawing.add_note("Remove all burrs and sharp edges")
    drawing.add_note("Break sharp edges 0.5mm max")
    
    if format.lower() == 'pdf':
        drawing.generate_pdf(output_path, mesh)
    elif format.lower() == 'dxf':
        drawing.export_dxf(output_path, mesh)
    else:
        raise ValueError(f"Unsupported format: {format}")
    
    return output_path
