"""Mounting Bracket with Holes - Manufacturing Ready"""
import cadquery as cq

# Parameters (easy to modify)
width = 80  # mm
depth = 60  # mm
thickness = 5  # mm
hole_diameter = 6  # mm (for M6 bolts)
hole_spacing_x = 60  # mm
hole_spacing_y = 40  # mm
fillet_radius = 3  # mm

# Create the bracket
result = (cq.Workplane("XY")
    # Base plate
    .rect(width, depth)
    .extrude(thickness)
    
    # Add mounting holes at corners
    .faces(">Z").workplane()
    .rect(hole_spacing_x, hole_spacing_y, forConstruction=True)
    .vertices()
    .hole(hole_diameter)
    
    # Add fillets to all vertical edges
    .edges("|Z").fillet(fillet_radius)
)
