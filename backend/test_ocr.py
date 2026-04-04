"""Quick test: run OCR on a local exam sheet image and print results."""
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from app.models import FORMAT_100
from app.services.ocr_engine import ocr_engine

# Use the image path from command line, or default
image_path = sys.argv[1] if len(sys.argv) > 1 else "test_sheet.jpg"

if not os.path.exists(image_path):
    print(f"ERROR: Image not found: {image_path}")
    sys.exit(1)

print(f"Running OCR on: {image_path}")
print("=" * 60)

result = ocr_engine.process_exam_sheet(
    [image_path],
    exam_format=FORMAT_100,
    reg_prefix="113S2310603"[:8] if len("113S2310603") > 3 else ""
)

# Pretty print results
print("\n=== PART A ===")
pa = result.get("part_a_marks", {})
for q in sorted(pa.keys(), key=lambda x: int(x.replace("Q", ""))):
    print(f"  {q}: {pa[q]}")
print(f"  TOTAL: {result.get('part_a_total', '?')}")

print("\n=== PART B & C ===")
pbc = result.get("part_bc_marks", {})
for qn in range(11, 17):
    a_vals = {k: pbc.get(k, 0) for k in [f"Q{qn}a_i", f"Q{qn}a_ii", f"Q{qn}a_iii"]}
    b_vals = {k: pbc.get(k, 0) for k in [f"Q{qn}b_i", f"Q{qn}b_ii", f"Q{qn}b_iii"]}
    a_sum = sum(a_vals.values())
    b_sum = sum(b_vals.values())
    sub = "a" if a_sum > 0 else "b"
    val = a_sum if a_sum > 0 else b_sum
    print(f"  Q{qn}: sub={sub}, i={pbc.get(f'Q{qn}{sub}_i',0)}, ii={pbc.get(f'Q{qn}{sub}_ii',0)}, iii={pbc.get(f'Q{qn}{sub}_iii',0)}, total={val}")
print(f"  TOTAL: {result.get('part_bc_total', '?')}")

print("\n=== COURSE OUTCOMES ===")
co = result.get("course_outcomes", {})
for label in sorted(co.keys()):
    c = co[label]
    print(f"  {label}: PA={c.get('PART A',0)}, PB={c.get('PART B',0)}, PC={c.get('PART C',0)}, TOTAL={c.get('TOTAL',0)}")

print(f"\n=== SUMMARY ===")
print(f"  Registration: {result.get('registration_number')}")
print(f"  Grand Total: {result.get('grand_total')}")
print(f"  Written Totals: {result.get('written_totals')}")
print(f"  Confidence: {result.get('confidence')}")
print(f"  Engine: {result.get('engine')}")
