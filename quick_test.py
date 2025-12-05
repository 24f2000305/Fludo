import requests
import json

base = 'http://127.0.0.1:7860'
print('🧪 FLUDO CAD Studio - Quick Sanity Check')
print('='*60)

tests_passed = 0
tests_total = 0

# Test 1: Server Health
tests_total += 1
try:
    r = requests.get(base, timeout=5)
    if r.status_code == 200:
        print(f'✅ Test 1/5: Server Health - PASS ({r.status_code})')
        tests_passed += 1
    else:
        print(f'❌ Test 1/5: Server Health - FAIL ({r.status_code})')
except Exception as e:
    print(f'❌ Test 1/5: Server Health - FAIL ({e})')

# Test 2: Landing Page
tests_total += 1
try:
    r = requests.get(base, timeout=5)
    if 'FLUDO' in r.text and 'START BUILDING' in r.text:
        print(f'✅ Test 2/5: Landing Page - PASS')
        tests_passed += 1
    else:
        print(f'❌ Test 2/5: Landing Page - FAIL (Missing elements)')
except Exception as e:
    print(f'❌ Test 2/5: Landing Page - FAIL ({e})')

# Test 3: CAD Studio Interface
tests_total += 1
try:
    r = requests.get(f'{base}/cad_studio_v2.html', timeout=5)
    if 'FLUDO STUDIO' in r.text and 'monaco-editor' in r.text:
        print(f'✅ Test 3/5: CAD Studio Interface - PASS')
        tests_passed += 1
    else:
        print(f'❌ Test 3/5: CAD Studio Interface - FAIL (Missing elements)')
except Exception as e:
    print(f'❌ Test 3/5: CAD Studio Interface - FAIL ({e})')

# Test 4: Code Execution
tests_total += 1
try:
    code = 'import cadquery as cq\nresult = cq.Workplane("XY").box(50, 40, 30)'
    r = requests.post(f'{base}/api/cad/execute', json={'script': code}, timeout=30)
    data = r.json()
    if data.get('success') and 'url' in data:
        print(f'✅ Test 4/5: Code Execution - PASS (Model URL: {data["url"]})')
        tests_passed += 1
    else:
        error_msg = data.get('error', 'Unknown error')[:50]
        print(f'❌ Test 4/5: Code Execution - FAIL ({error_msg})')
except Exception as e:
    print(f'❌ Test 4/5: Code Execution - FAIL ({str(e)[:50]}')

# Test 5: Code Validation
tests_total += 1
try:
    valid_code = 'import cadquery as cq\nresult = cq.Workplane("XY").box(50, 40, 30)'
    r = requests.post(f'{base}/api/cad/validate', json={'code': valid_code}, timeout=10)
    data = r.json()
    if data.get('valid', False):
        print(f'✅ Test 5/5: Code Validation - PASS')
        tests_passed += 1
    else:
        print(f'❌ Test 5/5: Code Validation - FAIL (Valid code marked invalid)')
except Exception as e:
    print(f'❌ Test 5/5: Code Validation - FAIL ({str(e)[:50]})')

print('='*60)
print(f'Results: {tests_passed}/{tests_total} tests passed ({(tests_passed/tests_total)*100:.0f}%)')

if tests_passed == tests_total:
    print('🎉 ALL CORE FEATURES WORKING!')
elif tests_passed >= 4:
    print('⚠️  Most features working, minor issues detected')
else:
    print('❌ Critical issues detected')
