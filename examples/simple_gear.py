"""Simple Spur Gear - Parametric Design"""
import cadquery as cq
import math

# Gear parameters
num_teeth = 20
module = 2.0  # mm (controls tooth size)
thickness = 10  # mm
bore_diameter = 8  # mm (shaft hole)
pressure_angle = 20  # degrees (standard)

# Calculate dimensions
pitch_diameter = module * num_teeth
outer_diameter = pitch_diameter + (2 * module)
root_diameter = pitch_diameter - (2.5 * module)

# Create gear body
result = (cq.Workplane("XY")
    .circle(outer_diameter / 2)
    .extrude(thickness)
    
    # Add center bore
    .faces(">Z").workplane()
    .hole(bore_diameter)
    
    # Add keyway slot (for shaft connection)
    .faces(">Z").workplane()
    .rect(bore_diameter * 0.3, outer_diameter)
    .cutBlind(-thickness * 0.5)
)

# Simplified teeth (for demonstration)
# Note: Real involute teeth would require more complex geometry
tooth_width = (math.pi * pitch_diameter) / (2 * num_teeth)

for i in range(num_teeth):
    angle = i * 360 / num_teeth
    tooth = (cq.Workplane("XY")
        .move(pitch_diameter / 2, 0)
        .rect(module * 1.5, tooth_width * 0.6)
        .extrude(thickness)
        .rotate((0, 0, 0), (0, 0, 1), angle)
    )
    result = result.union(tooth)

# Add chamfer to top edge
result = result.faces(">Z").chamfer(0.5)
