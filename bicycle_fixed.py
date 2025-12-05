import cadquery as cq
import math

# --- Constants for dimensions (in mm) ---
TUBE_OD = 28.0
BB_SHELL_WIDTH = 70.0
BB_SHELL_OD = 40.0
HEAD_TUBE_LENGTH = 150.0
HEAD_TUBE_OD = 40.0
SEAT_TUBE_LENGTH_EFFECTIVE = 450.0
CHAIN_STAY_LENGTH_EFFECTIVE = 420.0
FORK_LEG_OD = 25.0

# Frame Angles
HEAD_TUBE_ANGLE = 70.0
SEAT_TUBE_ANGLE = 73.0

# Wheels
WHEEL_DIAMETER = 700.0
TIRE_WIDTH = 30.0
RIM_WIDTH = 25.0
RIM_HEIGHT = 30.0
HUB_DIAMETER = 30.0
HUB_WIDTH = 100.0

# Handlebars
HANDLEBAR_DIAMETER = 22.0
HANDLEBAR_WIDTH = 600.0

# Seat
SEAT_POST_DIAMETER = 27.2
SEAT_POST_LENGTH = 200.0
SADDLE_LENGTH = 250.0
SADDLE_WIDTH = 150.0
SADDLE_HEIGHT = 50.0

# Crankset
CRANK_ARM_LENGTH = 170.0
CRANK_ARM_WIDTH = 15.0
CRANK_ARM_THICKNESS = 5.0
CHAINRING_DIAMETER = 150.0
CHAINRING_THICKNESS = 3.0

# Derived
WHEEL_RADIUS = WHEEL_DIAMETER / 2
FILLET_RADIUS = 2.0

# --- Frame Geometry Points ---
BB_POINT = (0, 0, 0)

ST_ANGLE_RAD = math.radians(SEAT_TUBE_ANGLE)
STT_POINT = (
    SEAT_TUBE_LENGTH_EFFECTIVE * math.cos(ST_ANGLE_RAD),
    0,
    SEAT_TUBE_LENGTH_EFFECTIVE * math.sin(ST_ANGLE_RAD)
)

HTB_X_OFFSET = 600.0
HTB_Z_OFFSET = 100.0
HTB_POINT = (HTB_X_OFFSET, 0, HTB_Z_OFFSET)

HT_ANGLE_RAD = math.radians(HEAD_TUBE_ANGLE)
HTT_POINT = (
    HTB_POINT[0] + HEAD_TUBE_LENGTH * math.cos(HT_ANGLE_RAD),
    0,
    HTB_POINT[2] + HEAD_TUBE_LENGTH * math.sin(HT_ANGLE_RAD)
)

RA_X_POS = -CHAIN_STAY_LENGTH_EFFECTIVE * math.cos(math.radians(10))
RA_Z_POS = WHEEL_RADIUS
RA_POINT = (RA_X_POS, 0, RA_Z_POS)

# --- Build the bicycle ---
# 1. Bottom Bracket Shell
bb_shell = (cq.Workplane("XY")
    .circle(BB_SHELL_OD / 2)
    .extrude(BB_SHELL_WIDTH)
    .translate((0, -BB_SHELL_WIDTH / 2, 0))
)

# 2. Seat Tube - using loft instead of sweep
seat_tube = (cq.Workplane("XY")
    .transformed(offset=(BB_POINT[0], BB_POINT[2]))
    .circle(TUBE_OD / 2)
    .workplane(offset=SEAT_TUBE_LENGTH_EFFECTIVE)
    .transformed(offset=(STT_POINT[0] - BB_POINT[0], STT_POINT[2] - BB_POINT[2]))
    .circle(TUBE_OD / 2)
    .loft()
)

# 3. Head Tube
head_tube_length = math.sqrt((HTT_POINT[0] - HTB_POINT[0])**2 + (HTT_POINT[2] - HTB_POINT[2])**2)
head_tube_center = ((HTB_POINT[0] + HTT_POINT[0])/2, 0, (HTB_POINT[2] + HTT_POINT[2])/2)
head_tube = (cq.Workplane("XY")
    .circle(HEAD_TUBE_OD / 2)
    .extrude(head_tube_length)
    .translate((head_tube_center[0], 0, head_tube_center[2] - head_tube_length/2))
    .rotate((head_tube_center[0], 0, head_tube_center[2]), (0, 1, 0), HEAD_TUBE_ANGLE)
)

# 4. Down Tube
down_tube_length = math.sqrt((HTB_POINT[0] - BB_POINT[0])**2 + (HTB_POINT[2] - BB_POINT[2])**2)
down_tube_center = ((HTB_POINT[0] + BB_POINT[0])/2, 0, (HTB_POINT[2] + BB_POINT[2])/2)
down_tube_angle = math.degrees(math.atan2(HTB_POINT[2] - BB_POINT[2], HTB_POINT[0] - BB_POINT[0]))
down_tube = (cq.Workplane("XY")
    .circle(TUBE_OD / 2)
    .extrude(down_tube_length)
    .translate((down_tube_center[0], 0, down_tube_center[2] - down_tube_length/2))
    .rotate((down_tube_center[0], 0, down_tube_center[2]), (0, 1, 0), down_tube_angle)
)

# 5. Top Tube
top_tube_length = math.sqrt((HTT_POINT[0] - STT_POINT[0])**2 + (HTT_POINT[2] - STT_POINT[2])**2)
top_tube_center = ((HTT_POINT[0] + STT_POINT[0])/2, 0, (HTT_POINT[2] + STT_POINT[2])/2)
top_tube_angle = math.degrees(math.atan2(HTT_POINT[2] - STT_POINT[2], HTT_POINT[0] - STT_POINT[0]))
top_tube = (cq.Workplane("XY")
    .circle(TUBE_OD / 2)
    .extrude(top_tube_length)
    .translate((top_tube_center[0], 0, top_tube_center[2] - top_tube_length/2))
    .rotate((top_tube_center[0], 0, top_tube_center[2]), (0, 1, 0), top_tube_angle)
)

# 6. Chain Stays
chain_stay_length = math.sqrt((RA_POINT[0] - BB_POINT[0])**2 + (RA_POINT[2] - BB_POINT[2])**2)
chain_stay_center = ((RA_POINT[0] + BB_POINT[0])/2, 0, (RA_POINT[2] + BB_POINT[2])/2)
chain_stay_angle = math.degrees(math.atan2(RA_POINT[2] - BB_POINT[2], RA_POINT[0] - BB_POINT[0]))
chain_stay_offset = 40

chain_stay_left = (cq.Workplane("XY")
    .circle(TUBE_OD / 2)
    .extrude(chain_stay_length)
    .translate((chain_stay_center[0], chain_stay_offset, chain_stay_center[2] - chain_stay_length/2))
    .rotate((chain_stay_center[0], chain_stay_offset, chain_stay_center[2]), (0, 1, 0), chain_stay_angle)
)

chain_stay_right = (cq.Workplane("XY")
    .circle(TUBE_OD / 2)
    .extrude(chain_stay_length)
    .translate((chain_stay_center[0], -chain_stay_offset, chain_stay_center[2] - chain_stay_length/2))
    .rotate((chain_stay_center[0], -chain_stay_offset, chain_stay_center[2]), (0, 1, 0), chain_stay_angle)
)

# 7. Seat Stays
seat_stay_length = math.sqrt((RA_POINT[0] - STT_POINT[0])**2 + (RA_POINT[2] - STT_POINT[2])**2)
seat_stay_center = ((RA_POINT[0] + STT_POINT[0])/2, 0, (RA_POINT[2] + STT_POINT[2])/2)
seat_stay_angle = math.degrees(math.atan2(RA_POINT[2] - STT_POINT[2], RA_POINT[0] - STT_POINT[0]))

seat_stay_left = (cq.Workplane("XY")
    .circle(TUBE_OD / 2)
    .extrude(seat_stay_length)
    .translate((seat_stay_center[0], chain_stay_offset, seat_stay_center[2] - seat_stay_length/2))
    .rotate((seat_stay_center[0], chain_stay_offset, seat_stay_center[2]), (0, 1, 0), seat_stay_angle)
)

seat_stay_right = (cq.Workplane("XY")
    .circle(TUBE_OD / 2)
    .extrude(seat_stay_length)
    .translate((seat_stay_center[0], -chain_stay_offset, seat_stay_center[2] - seat_stay_length/2))
    .rotate((seat_stay_center[0], -chain_stay_offset, seat_stay_center[2]), (0, 1, 0), seat_stay_angle)
)

# 8. Wheels (simplified)
def create_wheel():
    rim = (cq.Workplane("XY")
        .circle(WHEEL_RADIUS)
        .circle(WHEEL_RADIUS - RIM_HEIGHT)
        .extrude(RIM_WIDTH)
    )
    hub = (cq.Workplane("XY")
        .circle(HUB_DIAMETER / 2)
        .extrude(HUB_WIDTH)
        .translate((0, 0, -HUB_WIDTH/2 + RIM_WIDTH/2))
    )
    return rim.union(hub)

rear_wheel = create_wheel().translate((RA_POINT[0], 0, RA_POINT[2]))
front_axle_x = HTB_POINT[0] + 40
front_wheel = create_wheel().translate((front_axle_x, 0, WHEEL_RADIUS))

# 9. Seat Post and Saddle
seat_post = (cq.Workplane("XY")
    .circle(SEAT_POST_DIAMETER / 2)
    .extrude(SEAT_POST_LENGTH)
    .translate((STT_POINT[0], 0, STT_POINT[2]))
    .rotate((STT_POINT[0], 0, STT_POINT[2]), (0, 1, 0), SEAT_TUBE_ANGLE)
)

saddle_pos_x = STT_POINT[0] + SEAT_POST_LENGTH * math.cos(ST_ANGLE_RAD)
saddle_pos_z = STT_POINT[2] + SEAT_POST_LENGTH * math.sin(ST_ANGLE_RAD)

saddle = (cq.Workplane("XY")
    .box(SADDLE_LENGTH, SADDLE_WIDTH, SADDLE_HEIGHT)
    .translate((saddle_pos_x, 0, saddle_pos_z))
    .edges("|Z").fillet(FILLET_RADIUS)
)

# 10. Handlebar (simplified)
handlebar = (cq.Workplane("YZ")
    .circle(HANDLEBAR_DIAMETER / 2)
    .extrude(HANDLEBAR_WIDTH)
    .translate((HTT_POINT[0], -HANDLEBAR_WIDTH/2, HTT_POINT[2] + 50))
)

# 11. Chainring
chainring = (cq.Workplane("YZ")
    .circle(CHAINRING_DIAMETER / 2)
    .extrude(CHAINRING_THICKNESS)
    .translate((0, -BB_SHELL_WIDTH/2 - CHAINRING_THICKNESS, 0))
)

# Combine all parts
result = bb_shell
result = result.add(seat_tube)
result = result.add(head_tube)
result = result.add(down_tube)
result = result.add(top_tube)
result = result.add(chain_stay_left)
result = result.add(chain_stay_right)
result = result.add(seat_stay_left)
result = result.add(seat_stay_right)
result = result.add(rear_wheel)
result = result.add(front_wheel)
result = result.add(seat_post)
result = result.add(saddle)
result = result.add(handlebar)
result = result.add(chainring)
