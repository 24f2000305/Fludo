"""
Comprehensive Feature Testing for FLUDO CAD Studio
Tests each feature 3 times to ensure robustness and reliability
"""

import requests
import json
import time
from typing import Dict, Any, List

BASE_URL = "http://127.0.0.1:7860"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class FeatureTester:
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []
        
    def print_header(self, text: str):
        print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{text.center(80)}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")
    
    def print_test(self, test_name: str, attempt: int):
        print(f"{Colors.BLUE}🧪 Testing: {Colors.BOLD}{test_name}{Colors.RESET} (Attempt {attempt}/3)")
    
    def print_success(self, message: str):
        print(f"{Colors.GREEN}✅ PASS: {message}{Colors.RESET}")
        
    def print_failure(self, message: str):
        print(f"{Colors.RED}❌ FAIL: {message}{Colors.RESET}")
        
    def print_warning(self, message: str):
        print(f"{Colors.YELLOW}⚠️  WARNING: {message}{Colors.RESET}")
    
    def test_feature(self, feature_name: str, test_func, attempts=3):
        """Run a test function multiple times"""
        self.print_header(f"Testing: {feature_name}")
        
        success_count = 0
        failures = []
        
        for i in range(1, attempts + 1):
            self.total_tests += 1
            self.print_test(feature_name, i)
            
            try:
                result = test_func()
                if result['success']:
                    self.passed_tests += 1
                    success_count += 1
                    self.print_success(result.get('message', 'Test passed'))
                else:
                    self.failed_tests += 1
                    failures.append(result.get('error', 'Unknown error'))
                    self.print_failure(result.get('error', 'Test failed'))
                    
            except Exception as e:
                self.failed_tests += 1
                failures.append(str(e))
                self.print_failure(f"Exception: {str(e)}")
            
            time.sleep(1)  # Delay between attempts
        
        # Summary for this feature
        print(f"\n{Colors.BOLD}Feature Summary: {Colors.RESET}")
        print(f"  Success Rate: {success_count}/{attempts} ({(success_count/attempts)*100:.1f}%)")
        
        if failures:
            print(f"  Failures: {len(failures)}")
            for idx, failure in enumerate(failures, 1):
                print(f"    {idx}. {failure}")
        
        self.test_results.append({
            'feature': feature_name,
            'attempts': attempts,
            'successes': success_count,
            'failures': len(failures),
            'failure_details': failures
        })
        
        return success_count == attempts

# ============================================================================
# TEST FUNCTIONS
# ============================================================================

def test_server_health():
    """Test if server is running and responding"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        return {
            'success': response.status_code == 200,
            'message': f'Server responding (Status: {response.status_code})'
        }
    except Exception as e:
        return {'success': False, 'error': f'Server not responding: {str(e)}'}

def test_landing_page():
    """Test landing page loads correctly"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        content = response.text
        
        # Check for key elements
        checks = [
            ('FLUDO' in content, 'FLUDO branding present'),
            ('START BUILDING' in content, 'CTA button present'),
            ('theme-toggle-landing' in content, 'Dark mode toggle present'),
            ('Engineering Excellence' in content, 'Gallery section present'),
            ('Meet The Dreamers' in content, 'Team section present')
        ]
        
        failed_checks = [check[1] for check in checks if not check[0]]
        
        if failed_checks:
            return {'success': False, 'error': f'Missing elements: {", ".join(failed_checks)}'}
        
        return {'success': True, 'message': 'All landing page elements present'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_cad_studio_loads():
    """Test CAD Studio interface loads"""
    try:
        response = requests.get(f"{BASE_URL}/cad_studio_v2.html", timeout=5)
        content = response.text
        
        checks = [
            ('FLUDO STUDIO' in content, 'Studio branding'),
            ('monaco-editor' in content, 'Monaco editor'),
            ('Execute' in content, 'Execute button'),
            ('theme-toggle' in content, 'Theme toggle'),
            ('editor-container' in content, 'Editor container')
        ]
        
        failed_checks = [check[1] for check in checks if not check[0]]
        
        if failed_checks:
            return {'success': False, 'error': f'Missing: {", ".join(failed_checks)}'}
        
        return {'success': True, 'message': 'CAD Studio loaded successfully'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_code_execution():
    """Test code execution endpoint"""
    try:
        test_code = '''import cadquery as cq

result = (cq.Workplane("XY")
    .box(50, 40, 30)
    .edges("|Z")
    .fillet(2)
)'''
        
        response = requests.post(
            f"{BASE_URL}/api/cad/execute",
            json={'code': test_code},
            timeout=30
        )
        
        data = response.json()
        
        if 'error' in data:
            return {'success': False, 'error': data['error']}
        
        if 'obj_data' not in data or 'stl_data' not in data:
            return {'success': False, 'error': 'Missing model data in response'}
        
        return {'success': True, 'message': 'Code executed and model generated'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_ai_generation():
    """Test AI code generation endpoint"""
    try:
        prompts = [
            "Create a simple box 50x40x30mm with rounded edges",
            "Make a cylinder with diameter 20mm and height 50mm",
            "Design a rectangular bracket with mounting holes"
        ]
        
        # Test with first prompt
        prompt = prompts[0]
        
        response = requests.post(
            f"{BASE_URL}/api/cad/generate",
            json={'prompt': prompt},
            timeout=60
        )
        
        data = response.json()
        
        if 'error' in data:
            return {'success': False, 'error': data['error']}
        
        if 'code' not in data:
            return {'success': False, 'error': 'No code generated'}
        
        code = data['code']
        
        # Validate generated code
        if 'import cadquery as cq' not in code:
            return {'success': False, 'error': 'Generated code missing CadQuery import'}
        
        if 'result =' not in code:
            return {'success': False, 'error': 'Generated code missing result assignment'}
        
        return {'success': True, 'message': f'AI generated valid code ({len(code)} chars)'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_ai_chat():
    """Test AI chat/modify endpoint"""
    try:
        current_code = '''import cadquery as cq

result = cq.Workplane("XY").box(50, 40, 30)'''
        
        response = requests.post(
            f"{BASE_URL}/api/cad/chat",
            json={
                'message': 'Add rounded edges with 2mm fillet',
                'current_code': current_code
            },
            timeout=60
        )
        
        data = response.json()
        
        if 'error' in data:
            return {'success': False, 'error': data['error']}
        
        if 'code' not in data:
            return {'success': False, 'error': 'No modified code returned'}
        
        modified_code = data['code']
        
        if 'fillet' not in modified_code:
            return {'success': False, 'error': 'AI did not add fillet to code'}
        
        return {'success': True, 'message': 'AI successfully modified code'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_code_validation():
    """Test code validation endpoint"""
    try:
        valid_code = '''import cadquery as cq

result = cq.Workplane("XY").box(50, 40, 30)'''
        
        invalid_code = '''import cadquery as cq

# Missing result assignment
cq.Workplane("XY").box(50, 40, 30)'''
        
        # Test valid code
        response = requests.post(
            f"{BASE_URL}/api/cad/validate",
            json={'code': valid_code},
            timeout=10
        )
        
        data = response.json()
        
        if not data.get('valid', False):
            return {'success': False, 'error': 'Valid code marked as invalid'}
        
        # Test invalid code
        response = requests.post(
            f"{BASE_URL}/api/cad/validate",
            json={'code': invalid_code},
            timeout=10
        )
        
        data = response.json()
        
        if data.get('valid', True):
            return {'success': False, 'error': 'Invalid code marked as valid'}
        
        return {'success': True, 'message': 'Validation correctly identifies valid/invalid code'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_export_formats():
    """Test model export in different formats"""
    try:
        test_code = '''import cadquery as cq

result = cq.Workplane("XY").box(50, 40, 30)'''
        
        # First execute code to get model
        exec_response = requests.post(
            f"{BASE_URL}/api/cad/execute",
            json={'code': test_code},
            timeout=30
        )
        
        if exec_response.status_code != 200:
            return {'success': False, 'error': 'Failed to execute code for export test'}
        
        # Test STEP export
        export_response = requests.post(
            f"{BASE_URL}/api/cad/export/step",
            json={'code': test_code},
            timeout=30
        )
        
        if export_response.status_code != 200:
            return {'success': False, 'error': 'STEP export failed'}
        
        if len(export_response.content) < 100:
            return {'success': False, 'error': 'STEP file too small (likely empty)'}
        
        return {'success': True, 'message': f'Export successful (STEP: {len(export_response.content)} bytes)'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_undo_redo():
    """Test undo/redo functionality"""
    try:
        # Save a history state
        save_response = requests.post(
            f"{BASE_URL}/api/cad/save_history",
            json={
                'code': 'import cadquery as cq\n\nresult = cq.Workplane("XY").box(10, 10, 10)',
                'description': 'Test state'
            },
            timeout=10
        )
        
        if save_response.status_code != 200:
            return {'success': False, 'error': 'Failed to save history'}
        
        # Test undo
        undo_response = requests.post(
            f"{BASE_URL}/api/cad/undo",
            json={},
            timeout=10
        )
        
        if undo_response.status_code != 200:
            return {'success': False, 'error': 'Undo request failed'}
        
        # Test redo
        redo_response = requests.post(
            f"{BASE_URL}/api/cad/redo",
            json={},
            timeout=10
        )
        
        if redo_response.status_code != 200:
            return {'success': False, 'error': 'Redo request failed'}
        
        return {'success': True, 'message': 'Undo/Redo endpoints responding correctly'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def test_measurement_extraction():
    """Test measurement extraction from code"""
    try:
        test_code = '''import cadquery as cq

# Box dimensions
width = 50
height = 40
depth = 30

result = cq.Workplane("XY").box(width, height, depth)'''
        
        response = requests.post(
            f"{BASE_URL}/api/cad/extract_measurements",
            json={'code': test_code},
            timeout=10
        )
        
        data = response.json()
        
        if 'measurements' not in data:
            return {'success': False, 'error': 'No measurements extracted'}
        
        measurements = data['measurements']
        
        if len(measurements) < 3:
            return {'success': False, 'error': f'Expected 3+ measurements, got {len(measurements)}'}
        
        return {'success': True, 'message': f'Extracted {len(measurements)} measurements'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    tester = FeatureTester()
    
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("╔═══════════════════════════════════════════════════════════════════════════════╗")
    print("║                                                                               ║")
    print("║                    FLUDO CAD STUDIO - COMPREHENSIVE TEST SUITE               ║")
    print("║                                                                               ║")
    print("║                   Testing all features 3x for reliability                    ║")
    print("║                                                                               ║")
    print("╚═══════════════════════════════════════════════════════════════════════════════╝")
    print(Colors.RESET)
    
    # Run all tests
    tests = [
        ("Server Health Check", test_server_health),
        ("Landing Page Loading", test_landing_page),
        ("CAD Studio Interface", test_cad_studio_loads),
        ("Code Execution Engine", test_code_execution),
        ("AI Code Generation", test_ai_generation),
        ("AI Chat/Modification", test_ai_chat),
        ("Code Validation", test_code_validation),
        ("Model Export (STEP)", test_export_formats),
        ("Undo/Redo System", test_undo_redo),
        ("Measurement Extraction", test_measurement_extraction),
    ]
    
    start_time = time.time()
    
    for test_name, test_func in tests:
        tester.test_feature(test_name, test_func, attempts=3)
        time.sleep(2)  # Delay between different features
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Final Report
    tester.print_header("FINAL TEST REPORT")
    
    print(f"{Colors.BOLD}Overall Statistics:{Colors.RESET}")
    print(f"  Total Tests Run: {tester.total_tests}")
    print(f"  Passed: {Colors.GREEN}{tester.passed_tests}{Colors.RESET}")
    print(f"  Failed: {Colors.RED}{tester.failed_tests}{Colors.RESET}")
    print(f"  Success Rate: {Colors.BOLD}{(tester.passed_tests/tester.total_tests)*100:.1f}%{Colors.RESET}")
    print(f"  Duration: {duration:.1f} seconds")
    
    print(f"\n{Colors.BOLD}Feature-by-Feature Results:{Colors.RESET}\n")
    
    for result in tester.test_results:
        status_icon = "✅" if result['successes'] == result['attempts'] else "⚠️" if result['successes'] > 0 else "❌"
        status_color = Colors.GREEN if result['successes'] == result['attempts'] else Colors.YELLOW if result['successes'] > 0 else Colors.RED
        
        print(f"{status_icon} {Colors.BOLD}{result['feature']}{Colors.RESET}")
        print(f"   {status_color}{result['successes']}/{result['attempts']} successful{Colors.RESET}")
        
        if result['failures'] > 0:
            print(f"   {Colors.RED}Failed: {result['failures']}{Colors.RESET}")
            for failure in result['failure_details']:
                print(f"      • {failure[:100]}...")
        print()
    
    # Recommendation
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
    
    if tester.failed_tests == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}")
        print("🎉 ALL TESTS PASSED! System is READY FOR DEPLOYMENT! 🎉")
        print(Colors.RESET)
    elif tester.failed_tests <= 3:
        print(f"{Colors.YELLOW}{Colors.BOLD}")
        print("⚠️  MINOR ISSUES DETECTED - Review failures before deployment")
        print(Colors.RESET)
    else:
        print(f"{Colors.RED}{Colors.BOLD}")
        print("❌ CRITICAL ISSUES DETECTED - DO NOT DEPLOY YET")
        print(Colors.RESET)
    
    print(f"{Colors.BOLD}{'='*80}{Colors.RESET}\n")

if __name__ == "__main__":
    main()
