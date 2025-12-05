"""Test edge selection validation for fillet/chamfer."""
from app.cad_engine import validate_cadquery_compatibility

# Test 1: Fillet without edge selection (BAD)
bad_fillet = """
import cadquery as cq

result = (cq.Workplane("XY")
    .box(10, 10, 10)
    .fillet(2)
)
"""

print("Test 1: Fillet without edge selection (should fail)")
is_valid, errors = validate_cadquery_compatibility(bad_fillet)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

# Test 2: Fillet with edge selection (GOOD)
good_fillet = """
import cadquery as cq

result = (cq.Workplane("XY")
    .box(10, 10, 10)
    .edges("|Z")
    .fillet(2)
)
"""

print("Test 2: Fillet with edge selection (should pass)")
is_valid, errors = validate_cadquery_compatibility(good_fillet)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

# Test 3: Chamfer without edge selection (BAD)
bad_chamfer = """
import cadquery as cq

result = (cq.Workplane("XY")
    .box(20, 20, 5)
    .chamfer(1)
)
"""

print("Test 3: Chamfer without edge selection (should fail)")
is_valid, errors = validate_cadquery_compatibility(bad_chamfer)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

# Test 4: Chamfer with edge selection (GOOD)
good_chamfer = """
import cadquery as cq

result = (cq.Workplane("XY")
    .box(20, 20, 5)
    .edges(">Z")
    .chamfer(1)
)
"""

print("Test 4: Chamfer with edge selection (should pass)")
is_valid, errors = validate_cadquery_compatibility(good_chamfer)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

# Test 5: Multi-line with edges on previous line (GOOD)
good_multiline = """
import cadquery as cq

result = (cq.Workplane("XY")
    .box(30, 30, 10)
    .edges("|Z")
    .fillet(2)
)
"""

print("Test 5: Multi-line with edges on previous line (should pass)")
is_valid, errors = validate_cadquery_compatibility(good_multiline)
print(f"Valid: {is_valid}")
for error in errors:
    print(f"  - {error}")
print()

print("✅ Edge selection validation tests complete!")
