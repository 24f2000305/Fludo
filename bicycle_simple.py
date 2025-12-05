import cadquery as cq

# Simple bicycle that actually works in CadQuery
# Create a basic frame with wheels

# Wheel parameters
wheel_radius = 350
tire_thickness = 15
hub_radius = 15

# Frame parameters
tube_radius = 14
frame_height = 500
frame_length = 600

# Create rear wheel
rear_wheel = (
    cq.Workplane("YZ")
    .circle(wheel_radius)
    .circle(wheel_radius - tire_thickness)
    .extrude(10)
    .union(
        cq.Workplane("YZ")
        .circle(hub_radius)
        .extrude(50)
        .translate((0, -20, 0))
    )
)

# Create front wheel
front_wheel = rear_wheel.translate((frame_length, 0, 0))

# Create frame tubes
# Down tube (from head tube to bottom bracket)
down_tube = (
    cq.Workplane("XY")
    .circle(tube_radius)
    .extrude(frame_height)
    .translate((frame_length * 0.8, 0, 0))
    .rotate((0, 0, 0), (0, 1, 0), -25)
)

# Seat tube (from bottom bracket to seat)
seat_tube = (
    cq.Workplane("XY")
    .circle(tube_radius)
    .extrude(frame_height)
    .rotate((0, 0, 0), (0, 1, 0), -15)
)

# Top tube (horizontal)
top_tube = (
    cq.Workplane("XY")
    .circle(tube_radius)
    .extrude(frame_length * 0.6)
    .rotate((0, 0, 0), (1, 0, 0), 90)
    .translate((frame_length * 0.2, 0, frame_height * 0.8))
)

# Chain stays (rear triangle)
chain_stay_left = (
    cq.Workplane("XY")
    .circle(tube_radius * 0.8)
    .extrude(frame_length * 0.5)
    .rotate((0, 0, 0), (0, 1, 0), 15)
    .translate((0, 30, 50))
)

chain_stay_right = chain_stay_left.translate((0, -60, 0))

# Seat stays
seat_stay_left = (
    cq.Workplane("XY")
    .circle(tube_radius * 0.8)
    .extrude(frame_height * 0.6)
    .rotate((0, 0, 0), (0, 1, 0), 25)
    .translate((0, 30, frame_height * 0.5))
)

seat_stay_right = seat_stay_left.translate((0, -60, 0))

# Handlebars
handlebar = (
    cq.Workplane("XZ")
    .circle(tube_radius * 0.7)
    .extrude(300)
    .translate((frame_length, -150, frame_height * 0.9))
)

# Combine everything
result = (
    rear_wheel
    .add(front_wheel)
    .add(down_tube)
    .add(seat_tube)
    .add(top_tube)
    .add(chain_stay_left)
    .add(chain_stay_right)
    .add(seat_stay_left)
    .add(seat_stay_right)
    .add(handlebar)
)

show_object(result)
