import re
import os
import json
import base64
from typing import List
from app.config import settings

# ── Groq Vision API ──
GROQ_AVAILABLE = False
groq_client = None

try:
    from groq import Groq
    if settings.GROQ_API_KEY and settings.GROQ_API_KEY != "your_groq_api_key_here":
        groq_client = Groq(api_key=settings.GROQ_API_KEY)
        GROQ_AVAILABLE = True
        print("INFO: Groq Vision API initialized successfully.")
    else:
        print("WARNING: GROQ_API_KEY not set.")
except Exception as e:
    print(f"WARNING: Groq SDK not available: {e}")


def _image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _get_mime_type(image_path: str) -> str:
    ext = os.path.splitext(image_path)[1].lower()
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".bmp": "image/bmp", ".tiff": "image/tiff", ".tif": "image/tiff",
        ".webp": "image/webp",
    }.get(ext, "image/png")


def _build_groq_prompt(exam_format: dict, reg_prefix: str = "") -> str:
    fmt = exam_format
    part_a = fmt["part_a"]
    part_bc = fmt["part_bc"]
    co = fmt["course_outcomes"]

    reg_hint = ""
    if reg_prefix:
        reg_hint = f"""
REGISTRATION NUMBER FORMAT:
  The registration number starts with "{reg_prefix}" followed by exactly 3 digits (001-999).
  So the full registration number looks like: {reg_prefix}XXX (where XXX is a 3-digit number).
  FOCUS on reading the LAST 3 DIGITS accurately — the prefix "{reg_prefix}" is already known.
  Example: {reg_prefix}042, {reg_prefix}118, {reg_prefix}003
  Return the FULL registration number including the prefix.
"""

    qs = part_bc['questions_start']
    qe = part_bc['questions_end']

    prompt = f"""You are an expert OCR system for Indian university exam answer sheets (Velammal Institute of Technology).
The sheet has handwritten marks in RED/PINK ink. This is a **{fmt['exam_type']}** exam — max **{fmt['total_marks']} marks**.
{reg_hint}
=== STEP 1: READ WRITTEN TOTALS (GROUND TRUTH) ===
These are the MOST RELIABLE numbers on the sheet — read each digit very carefully:
  - "Total" row at bottom of PART A Marks column → "part_a_total_written"
  - Bottom of "Total Marks" column in Part B&C section → "part_bc_total_written"
  - Circled Grand Total (usually in red circle, shown as fraction X/{fmt['total_marks']}) → "grand_total_written"
  DIGIT TIPS: "17" has two digits (1 then 7). "11" has two vertical strokes. "57" vs "51" — check second digit.

=== STEP 2: PART A (Q1-Q{part_a['questions']}, each 0-{part_a['marks_each']}) ===
  - Each Part A question is worth max {part_a['marks_each']} marks.
  - Read the "Marks" column for each row Q1..Q{part_a['questions']}.
  - IMPORTANT: Most Part A marks are either {part_a['marks_each']} (full marks) or 0 (not attempted).
    A mark of 1 is possible but LESS COMMON. If you see what looks like "1", double-check:
    could it be "{part_a['marks_each']}" with the first digit partially hidden?
  - Empty cell / no writing = 0. Tick mark (✓) next to a number is NOT an extra digit.
  - VALIDATE: Sum of Q1..Q{part_a['questions']} MUST equal part_a_total_written.

=== STEP 3: PART B & C (Q{qs}-Q{qe}) — MOST CRITICAL SECTION ===

  STEP 3a: DETERMINE WHICH SUB-PART (a or b) EACH QUESTION USES
  Each question Q{qs}-Q{qe} has TWO rows on the sheet:
    - ROW 1 (top row for that question) is labeled "a" in the Sub column
    - ROW 2 (bottom row for that question) is labeled "b" in the Sub column
  Students answer ONLY ONE of a or b per question. The OTHER row is BLANK.

  FOR EACH QUESTION, look at both rows and determine which one has marks:
  - If marks are in ROW 1 (the "a" row) → that question's answer is "a"
  - If marks are in ROW 2 (the "b" row) → that question's answer is "b"
  Report this in "part_bc_answered": {{"Q{qs}": "a" or "b", "Q{qs+1}": "a" or "b", ...}}

  STEP 3b: READ THE MARKS
  - Only read marks from the row that has writing. The other row is all zeros.
  - Column "i" has the main mark. Columns "ii" and "iii" are usually 0.
  - Read the "Total Marks" column too — it shows the total for that question.
  - VALIDATE: Sum of all Part B&C marks MUST equal part_bc_total_written.

=== STEP 4: COURSE OUTCOMES (CO-1 to CO-{co['count']}) ===
  Table at bottom of sheet. It has 4 data columns LEFT to RIGHT:
    Column 1: PART A | Column 2: PART B | Column 3: PART C | Column 4: TOTAL
  
  READ ALL 4 COLUMNS for each CO row:
  - PART A = Column 1 (small numbers, typically 1-6)
  - PART B = Column 2 (medium numbers, typically 8-12)
  - PART C = Column 3 (may be EMPTY/0 for many rows — only some COs have Part C marks)
  - TOTAL = Column 4, the RIGHTMOST column (this is the sum written by examiner)
  
  CRITICAL: The PART C column is OFTEN EMPTY. If you see no writing in that cell, it is 0.
  The TOTAL column always has a value. Do NOT confuse an empty PART C with TOTAL.
  Read TOTAL from the LAST column on the right.

=== STEP 5: FINAL VALIDATION ===
  - Sum(Q1..Q{part_a['questions']}) == part_a_total_written
  - Sum(all Part B&C marks) == part_bc_total_written
  - part_a_total_written + part_bc_total_written == grand_total_written
  - For each CO: PART A + PART B + PART C should equal TOTAL

RETURN ONLY valid JSON (no markdown, no code fences, no explanation):
{{
  "registration_number": "<string or null>",
  "part_a_total_written": <int>,
  "part_bc_total_written": <int>,
  "grand_total_written": <int>,
  "part_a": {{"Q1": <int 0-{part_a['marks_each']}>, "Q2": <int>, ..., "Q{part_a['questions']}": <int>}},
  "part_bc_answered": {{"Q{qs}": "a", "Q{qs+1}": "a", ..., "Q{qe}": "b"}},
  "part_bc_totals": {{"Q{qs}": <int>, "Q{qs+1}": <int>, ..., "Q{qe}": <int>}},
  "part_bc": {{
    "Q{qs}a_i": <int>, "Q{qs}a_ii": <int>, "Q{qs}a_iii": <int>,
    "Q{qs}b_i": <int>, "Q{qs}b_ii": <int>, "Q{qs}b_iii": <int>,
    ... for Q{qs}-Q{qe}, each with a_i,a_ii,a_iii,b_i,b_ii,b_iii
  }},
  "course_outcomes": {{
    "{co['labels'][0]}": {{"PART A": <int>, "PART B": <int>, "PART C": <int>, "TOTAL": <int>}},
    ... for: {', '.join(co['labels'])}
  }},
  "confidence": <float 0.0-1.0>
}}

RULES:
- Empty/blank cell = 0.
- Registration number: "REGISTER NUMBER" field.{f' Prefix is "{reg_prefix}".' if reg_prefix else ''}
- Written totals are GROUND TRUTH — individual marks must sum to match.
- For Part B&C: fill "part_bc_answered" FIRST, then fill marks only in the answered sub-part.
- "part_bc_totals" = the "Total Marks" column value for each question Q{qs}-Q{qe}.
- For CO: read ALL 4 columns. PART C is often 0 (empty cell). TOTAL is the rightmost column.
- Return ONLY raw JSON.
"""
    return prompt


def _adjust_marks_to_target(marks: dict, target: int) -> dict:
    """Adjust marks dict so sum equals target. Spreads adjustment across
    non-zero keys first (for reduction) or existing-mark keys first (for increase)."""
    current_sum = sum(marks.values())
    diff = current_sum - target
    if diff == 0:
        return marks
    adjusted = dict(marks)
    if diff > 0:
        # Need to reduce — prefer reducing from largest values by 1 at a time
        remaining = diff
        while remaining > 0:
            # Sort by value desc, only consider keys with value > 0
            candidates = sorted([k for k in adjusted if adjusted[k] > 0],
                                key=lambda k: adjusted[k], reverse=True)
            if not candidates:
                break
            for key in candidates:
                if remaining <= 0:
                    break
                adjusted[key] -= 1
                remaining -= 1
    else:
        # Need to increase — prefer adding to keys that already have marks
        remaining = abs(diff)
        while remaining > 0:
            candidates = sorted([k for k in adjusted if adjusted[k] > 0],
                                key=lambda k: adjusted[k], reverse=False)
            if not candidates:
                # All zero — add to first key
                candidates = sorted(adjusted.keys())
            for key in candidates:
                if remaining <= 0:
                    break
                adjusted[key] += 1
                remaining -= 1
    return adjusted


def _fix_part_bc_subparts(part_bc: dict, q_start: int, q_end: int,
                          answered: dict = None) -> dict:
    """Fix sub-part placement using the 'part_bc_answered' hint from Groq.
    If answered dict says Q12='b', move any marks from a→b for that question.
    Also ensures only one sub-part has marks per question."""
    fixed = dict(part_bc)
    for q in range(q_start, q_end + 1):
        a_total = sum(int(fixed.get(f'Q{q}a_{c}', 0) or 0) for c in ['i', 'ii', 'iii'])
        b_total = sum(int(fixed.get(f'Q{q}b_{c}', 0) or 0) for c in ['i', 'ii', 'iii'])
        q_key = f'Q{q}'
        hint = (answered or {}).get(q_key, '').lower().strip()

        # Use the answered hint to fix misplaced marks
        if hint == 'b' and a_total > 0 and b_total == 0:
            # Groq said student answered "b" but marks are in "a" → move them
            for c in ['i', 'ii', 'iii']:
                fixed[f'Q{q}b_{c}'] = fixed.get(f'Q{q}a_{c}', 0)
                fixed[f'Q{q}a_{c}'] = 0
        elif hint == 'a' and b_total > 0 and a_total == 0:
            # Groq said student answered "a" but marks are in "b" → move them
            for c in ['i', 'ii', 'iii']:
                fixed[f'Q{q}a_{c}'] = fixed.get(f'Q{q}b_{c}', 0)
                fixed[f'Q{q}b_{c}'] = 0

        # Recalculate after potential move
        a_total = sum(int(fixed.get(f'Q{q}a_{c}', 0) or 0) for c in ['i', 'ii', 'iii'])
        b_total = sum(int(fixed.get(f'Q{q}b_{c}', 0) or 0) for c in ['i', 'ii', 'iii'])

        # If both still have marks, keep the higher one
        if a_total > 0 and b_total > 0:
            if b_total > a_total:
                for c in ['i', 'ii', 'iii']:
                    fixed[f'Q{q}a_{c}'] = 0
            else:
                for c in ['i', 'ii', 'iii']:
                    fixed[f'Q{q}b_{c}'] = 0
    return fixed


def _validate_and_fix(data: dict, exam_format: dict) -> dict:
    fmt = exam_format
    part_a_cfg = fmt["part_a"]
    part_bc_cfg = fmt["part_bc"]

    part_a_total_written = data.get("part_a_total_written")
    part_bc_total_written = data.get("part_bc_total_written")
    grand_total_written = data.get("grand_total_written")

    # Clamp Part A
    part_a = data.get("part_a", {})
    for key in list(part_a.keys()):
        part_a[key] = max(0, min(int(part_a.get(key, 0) or 0), part_a_cfg["marks_each"]))

    part_a_max = part_a_cfg["max_marks"]
    target_a = part_a_total_written if isinstance(part_a_total_written, (int, float)) and 0 <= int(part_a_total_written) <= part_a_max else min(sum(part_a.values()), part_a_max)
    target_a = int(target_a)
    part_a = _adjust_marks_to_target(part_a, target_a)
    for key in list(part_a.keys()):
        part_a[key] = max(0, min(part_a[key], part_a_cfg["marks_each"]))
    part_a_total = sum(part_a.values())

    # Clamp Part BC
    part_bc = data.get("part_bc", {})
    for key in list(part_bc.keys()):
        part_bc[key] = max(0, int(part_bc.get(key, 0) or 0))

    # Fix sub-parts using the answered hint from Groq
    answered = data.get("part_bc_answered", {})
    part_bc = _fix_part_bc_subparts(
        part_bc,
        part_bc_cfg["questions_start"],
        part_bc_cfg["questions_end"],
        answered=answered,
    )

    # Use per-question totals to fix individual question marks
    q_totals = data.get("part_bc_totals", {})
    for q in range(part_bc_cfg["questions_start"], part_bc_cfg["questions_end"] + 1):
        q_key = f'Q{q}'
        expected = int(q_totals.get(q_key, 0) or 0)
        if expected <= 0:
            continue
        # Sum current marks for this question (both a and b)
        current = sum(int(part_bc.get(f'Q{q}{sub}_{c}', 0) or 0)
                       for sub in ['a', 'b'] for c in ['i', 'ii', 'iii'])
        if current != expected and expected <= 16:
            # Find which sub-part has marks and fix the _i value
            for sub in ['a', 'b']:
                sub_total = sum(int(part_bc.get(f'Q{q}{sub}_{c}', 0) or 0) for c in ['i', 'ii', 'iii'])
                if sub_total > 0:
                    # Adjust the primary mark (i) to match expected total
                    ii_val = int(part_bc.get(f'Q{q}{sub}_ii', 0) or 0)
                    iii_val = int(part_bc.get(f'Q{q}{sub}_iii', 0) or 0)
                    new_i = expected - ii_val - iii_val
                    if new_i >= 0:
                        part_bc[f'Q{q}{sub}_i'] = new_i
                    break

    part_bc_max = part_bc_cfg["max_marks"]
    target_bc = part_bc_total_written if isinstance(part_bc_total_written, (int, float)) and 0 <= int(part_bc_total_written) <= part_bc_max else min(sum(part_bc.values()), part_bc_max)
    target_bc = int(target_bc)
    part_bc = _adjust_marks_to_target(part_bc, target_bc)
    for key in list(part_bc.keys()):
        part_bc[key] = max(0, part_bc[key])
    part_bc_total = sum(part_bc.values())

    # Grand total
    if isinstance(grand_total_written, (int, float)) and 0 <= int(grand_total_written) <= fmt["total_marks"]:
        grand_total = int(grand_total_written)
    else:
        grand_total = part_a_total + part_bc_total

    if grand_total != (part_a_total + part_bc_total):
        needed_bc = grand_total - part_a_total
        if 0 <= needed_bc <= part_bc_max:
            part_bc = _adjust_marks_to_target(part_bc, needed_bc)
            for key in list(part_bc.keys()):
                part_bc[key] = max(0, part_bc[key])
            part_bc_total = sum(part_bc.values())

    # Course Outcomes — detect column swap and always derive PART C
    # Groq often reads TOTAL into PART C column, then computes its own TOTAL.
    # Detection: if TOTAL == PA+PB+PC and PC > PA and PC > PB → column swap
    co = data.get("course_outcomes", {})
    for label in list(co.keys()):
        if isinstance(co[label], dict):
            for col in list(co[label].keys()):
                co[label][col] = max(0, int(co[label].get(col, 0) or 0))
            pa = co[label].get("PART A", 0)
            pb = co[label].get("PART B", 0)
            pc = co[label].get("PART C", 0)
            total = co[label].get("TOTAL", 0)

            # Detect column swap: Groq put TOTAL in PART C, then computed TOTAL=PA+PB+PC
            if total == pa + pb + pc and pc > pa and pc > pb:
                # pc is actually the real TOTAL; derive real PART C
                real_total = pc
                real_pc = max(0, real_total - pa - pb)
                co[label]["PART C"] = real_pc
                co[label]["TOTAL"] = real_total
            else:
                # No swap detected — derive PART C from TOTAL
                derived_pc = max(0, total - pa - pb)
                co[label]["PART C"] = derived_pc
                co[label]["TOTAL"] = pa + pb + derived_pc

    return {
        "registration_number": data.get("registration_number"),
        "part_a": part_a, "part_bc": part_bc, "course_outcomes": co,
        "part_a_total": part_a_total, "part_bc_total": part_bc_total,
        "grand_total": grand_total, "confidence": data.get("confidence", 0.85),
        "part_a_total_written": int(part_a_total_written) if isinstance(part_a_total_written, (int, float)) else None,
        "part_bc_total_written": int(part_bc_total_written) if isinstance(part_bc_total_written, (int, float)) else None,
        "grand_total_written": int(grand_total_written) if isinstance(grand_total_written, (int, float)) else None,
    }


class OCREngine:
    """OCR Engine using Groq Vision API only."""

    @staticmethod
    def process_exam_sheet(image_paths: List[str], exam_format: dict = None, reg_prefix: str = "") -> dict:
        if not GROQ_AVAILABLE or not exam_format:
            return OCREngine._empty_result(len(image_paths))
        return OCREngine._process_with_groq(image_paths, exam_format, reg_prefix)

    @staticmethod
    def _process_with_groq(image_paths: List[str], exam_format: dict, reg_prefix: str = "") -> dict:
        try:
            prompt = _build_groq_prompt(exam_format, reg_prefix)
            content = [{"type": "text", "text": prompt}]
            for path in image_paths:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{_get_mime_type(path)};base64,{_image_to_base64(path)}"},
                })

            response = groq_client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role": "user", "content": content}],
                temperature=0.1,
                max_tokens=4096,
            )

            raw_text = response.choices[0].message.content.strip()
            print(f"DEBUG Groq raw:\n{raw_text[:500]}")

            cleaned = raw_text
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)

            data = json.loads(cleaned)
            validated = _validate_and_fix(data, exam_format)

            # Fix registration number using known prefix
            raw_reg = str(validated.get("registration_number") or "").strip()
            if reg_prefix and raw_reg:
                digits_only = re.sub(r"[^0-9]", "", raw_reg)
                last3 = digits_only[-3:] if len(digits_only) >= 3 else digits_only.zfill(3)
                validated["registration_number"] = reg_prefix + last3
            elif reg_prefix and not raw_reg:
                validated["registration_number"] = None

            return {
                "registration_number": validated.get("registration_number"),
                "marks_obtained": validated.get("grand_total", 0),
                "part_a_marks": validated.get("part_a", {}),
                "part_bc_marks": validated.get("part_bc", {}),
                "course_outcomes": validated.get("course_outcomes", {}),
                "part_a_total": validated.get("part_a_total", 0),
                "part_bc_total": validated.get("part_bc_total", 0),
                "grand_total": validated.get("grand_total", 0),
                "confidence": validated.get("confidence", 0.85),
                "page_count": len(image_paths),
                "engine": "groq_vision",
                "written_totals": {
                    "part_a": validated.get("part_a_total_written"),
                    "part_bc": validated.get("part_bc_total_written"),
                    "grand": validated.get("grand_total_written"),
                },
            }
        except json.JSONDecodeError as e:
            print(f"ERROR: Groq returned invalid JSON: {e}")
            return OCREngine._empty_result(len(image_paths))
        except Exception as e:
            print(f"ERROR: Groq Vision failed: {e}")
            return OCREngine._empty_result(len(image_paths))

    @staticmethod
    def _empty_result(page_count: int) -> dict:
        return {
            "registration_number": None, "marks_obtained": 0,
            "part_a_marks": {}, "part_bc_marks": {}, "course_outcomes": {},
            "part_a_total": 0, "part_bc_total": 0, "grand_total": 0,
            "confidence": 0.0, "page_count": page_count, "engine": "none",
            "written_totals": {},
        }


ocr_engine = OCREngine()
