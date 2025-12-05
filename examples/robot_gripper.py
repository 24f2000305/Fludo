"""Robot Gripper Jaw - Precision Manufacturing"""
import cadquery as cq

# Parameters
jaw_length = 60  # mm
jaw_width = 25  # mm
jaw_thickness = 10  # mm
grip_depth = 5  # mm
grip_width = 15  # mm
mounting_hole_diameter = 4  # mm

# Create gripper jaw
result = (cq.Workplane("XY")
    # Main jaw body
    .rect(jaw_length, jaw_width)
    .extrude(jaw_thickness)
    
    # Add grip serrations (for better grip)
    .faces(">Y").workplane()
    .rect(jaw_length * 0.6, grip_depth)
    .extrude(-grip_width)
    
    # Create serrated pattern
    .faces(">Y").workplane(offset=-grip_width)
    .rarray(5, 1, 8, 1)
    .rect(3, grip_depth * 0.8)
    .cutBlind(-2)
    
    # Add mounting holes
    .faces(">Z").workplane()
    .rarray(jaw_length * 0.7, 1, 2, 1)
    .hole(mounting_hole_diameter)
    
    # Add alignment pin hole
    .faces("<Z").workplane()
    .center(jaw_length * 0.3, 0)
    .hole(3, depth=jaw_thickness * 0.5)
    
    # Round all edges for safety
    .edges().fillet(1)
)

# Add text marking (optional)
result = (result
    .faces(">Z").workplane()
    .text("GRIP", 4, -1.5)
)
