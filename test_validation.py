"""Test CadQuery compatibility validation."""
from app.cad_engine import validate_cadquery_compatibility

# Test 1: Bad code with StringSelector (deprecated)
bad_code_1 = """
import cadquery as cq

result = (cq.Workplane("XY")
    .box(10, 10, 10)
    .edges(cq.selectors.StringSelector(">Z"))
    .fillet(2)
)
"""

print("Test 1: Bad code with StringSelector")
is_valid, errors = validate_cadquery_compatibility(bad_code_1)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

# Test 2: Good code with string selector
good_code_1 = """
import cadquery as cq

result = (cq.Workplane("XY")
    .box(10, 10, 10)
    .edges(">Z")
    .fillet(2)
)
"""

print("Test 2: Good code with string selector")
is_valid, errors = validate_cadquery_compatibility(good_code_1)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

# Test 3: Code with math but no import
bad_code_2 = """
import cadquery as cq

radius = 20
angle = math.pi / 4

result = (cq.Workplane("XY")
    .circle(radius)
    .extrude(10)
)
"""

print("Test 3: Code with math but no import")
is_valid, errors = validate_cadquery_compatibility(bad_code_2)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

# Test 4: Code with math and import
good_code_2 = """
import cadquery as cq
import math

radius = 20
angle = math.pi / 4

result = (cq.Workplane("XY")
    .circle(radius)
    .extrude(10)
)
"""

print("Test 4: Code with math and import")
is_valid, errors = validate_cadquery_compatibility(good_code_2)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

# Test 5: Code with large fillet
warning_code = """
import cadquery as cq

result = (cq.Workplane("XY")
    .box(10, 10, 10)
    .edges("|Z")
    .fillet(50)
)
"""

print("Test 5: Code with large fillet (should warn)")
is_valid, errors = validate_cadquery_compatibility(warning_code)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

print("✅ Validation tests complete!")
