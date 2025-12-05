import cadquery as cq

# Define dimensions for the cylinder
CYLINDER_RADIUS = 20.0
CYLINDER_HEIGHT = 40.0

# Create a simple cylinder (no fillet to avoid selector issues)
result = (cq.Workplane("XY")
    .circle(CYLINDER_RADIUS)
    .extrude(CYLINDER_HEIGHT)
)

# Alternative: Cylinder with chamfered top edge
# result = (cq.Workplane("XY")
#     .circle(CYLINDER_RADIUS)
#     .extrude(CYLINDER_HEIGHT)
#     .faces(">Z").chamfer(1.5)
# )
