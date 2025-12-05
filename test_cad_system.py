#!/usr/bin/env python3
"""Test script for the CAD system"""

import os
from app.cad_engine import get_engine
from app.cad_agent import have_gemini, generate_cadquery_script, modify_cadquery_script

def test_engine():
    """Test CadQuery engine"""
    print("=" * 60)
    print("Testing CadQuery Engine")
    print("=" * 60)
    
    # Test 1: Simple box
    print("\n1. Testing simple box generation...")
    script = """import cadquery as cq
result = cq.Workplane("XY").box(50, 40, 30)
"""
    engine = get_engine()
    result = engine.execute_script(script)
    
    if result['success']:
        print("   ✓ Box generated successfully")
        print(f"   Type: {result['type']}")
        
        # Test STL export
        stl_data = engine.export_stl()
        print(f"   ✓ STL export: {len(stl_data)} bytes")
        
        # Test STEP export
        step_data = engine.export_step()
        print(f"   ✓ STEP export: {len(step_data)} bytes")
    else:
        print(f"   ✗ Error: {result['error']}")
    
    # Test 2: Complex part with holes and fillets
    print("\n2. Testing complex part with holes and fillets...")
    script = """import cadquery as cq

result = (cq.Workplane("XY")
    .rect(80, 60)
    .extrude(5)
    .faces(">Z").workplane()
    .rect(60, 40, forConstruction=True)
    .vertices()
    .hole(6)
    .edges("|Z").fillet(3)
)
"""
    result = engine.execute_script(script)
    
    if result['success']:
        print("   ✓ Complex part generated successfully")
        stl_data = engine.export_stl()
        print(f"   ✓ STL export: {len(stl_data)} bytes")
    else:
        print(f"   ✗ Error: {result['error']}")
    
    # Test 3: Cylinder with hole
    print("\n3. Testing cylinder with central hole...")
    script = """import cadquery as cq

result = (cq.Workplane("XY")
    .circle(25)
    .extrude(50)
    .faces(">Z").workplane()
    .hole(10)
)
"""
    result = engine.execute_script(script)
    
    if result['success']:
        print("   ✓ Cylinder generated successfully")
    else:
        print(f"   ✗ Error: {result['error']}")
    
    print("\n✓ Engine tests completed!")

def test_ai_agent():
    """Test AI agent (requires Gemini API key)"""
    print("\n" + "=" * 60)
    print("Testing AI Agent")
    print("=" * 60)
    
    if not have_gemini():
        print("\n⚠️  Gemini API key not configured")
        print("Set GEMINI_API_KEY environment variable to test AI features")
        return
    
    print("\n✓ Gemini API configured")
    print("\nSkipping AI tests to avoid API rate limits")
    print("Use the web interface to test AI generation")

def main():
    print("\n🔧 CAD System Test Suite\n")
    
    # Test engine
    test_engine()
    
    # Test AI agent
    test_ai_agent()
    
    print("\n" + "=" * 60)
    print("All Tests Completed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Set GEMINI_API_KEY environment variable")
    print("2. Start the server: uvicorn app.server:app --reload")
    print("3. Open http://localhost:8000 in your browser")
    print("4. Try generating CAD models with AI!")
    print()

if __name__ == "__main__":
    main()
