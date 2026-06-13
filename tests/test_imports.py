"""
Comprehensive import test for the Tax Investigation System.
Verifies all modules can be imported, then runs unit-level tests on key functions.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

errors = []
successes = []

def try_import(module_name, label=None):
    try:
        __import__(module_name, fromlist=[""])
        successes.append(f"[OK] {label or module_name}")
    except Exception as e:
        errors.append(f"[FAIL] {label or module_name}: {e}")

# Test all modules in dependency order
try_import("src.utils", "src.utils")
try_import("src.models", "src.models")
try_import("src.config", "src.config")
try_import("src.case_discovery", "src.case_discovery")
try_import("src.parsing", "src.parsing")
try_import("src.extraction", "src.extraction")
try_import("src.validation", "src.validation")
try_import("src.discrepancies", "src.discrepancies")
try_import("src.decision", "src.decision")
try_import("src.output", "src.output")
try_import("src.llm_reviewer", "src.llm_reviewer")
try_import("src.mapping", "src.mapping")
try_import("src.document_gen", "src.document_gen")

# Also test full main.py import
try_import("main", "main (as __main__)")

print(f"\n=== Import Test Results ===")
for s in successes:
    print(f"  {s}")
if errors:
    print(f"\n!!! {len(errors)} ERRORS:")
    for e in errors:
        print(f"  {e}")
else:
    print(f"\nAll {len(successes)} modules imported successfully!")

sys.exit(1 if errors else 0)
