import cadquery as cq
from app.cad_engine import CADEngine

# Test the recovery system
engine = CADEngine()

# This script has a fillet that will likely fail
test_script = """import cadquery as cq

# Complex gear with problematic fillet
result = (cq.Workplane("XY")
    .rect(80, 60)
    .extrude(5)
    .faces(">Z").workplane()
    .rect(60, 40, forConstruction=True)
    .vertices()
    .hole(6)
    .edges("|Z").fillet(50)  # This will fail - radius too large!
)
"""

print("Testing script with problematic fillet...")
print("=" * 60)

result = engine.execute_script(test_script)

print(f"\nSuccess: {result['success']}")
print(f"Warnings: {result.get('warnings', [])}")

if result['success']:
    print("\n✅ Model rendered successfully!")
    print(f"Type: {result['type']}")
    if result.get('warnings'):
        print("\nWarnings issued:")
        for warning in result['warnings']:
            print(f"  - {warning}")
    if result.get('original_script'):
        print("\n📝 Script was automatically modified to render")
else:
    print(f"\n❌ Failed: {result['error']}")
