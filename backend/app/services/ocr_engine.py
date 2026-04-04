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

    prompt = f"""You are an expert OCR system for Indian university exam answer sheets (Velammal Institute of Technology style).
Analyze this exam sheet image very carefully. The sheet has handwritten marks in RED/PINK ink.

This is a **{fmt['exam_type']}** exam — maximum **{fmt['total_marks']} marks**.

CRITICAL INSTRUCTIONS — READ THESE CAREFULLY:
=============================================
{reg_hint}
STEP 1: READ THE WRITTEN TOTALS FIRST — these are GROUND TRUTH:
  - "Total" row at bottom of Part A Marks column → "part_a_total_written".
  - Last value in the "Total Marks" column of Part B&C (bottom row) → "part_bc_total_written".
  - Circled Grand Total (usually in red, often shown as X/{fmt['total_marks']}) → "grand_total_written".
  READ EACH DIGIT OF THESE TOTALS VERY CAREFULLY. Double-check: "17" vs "11" vs "7", "57" vs "51".

STEP 2: READ PART A MARKS (Q1 to Q{part_a['questions']}):
  - Each question: 0 to {part_a['marks_each']} marks max.
  - Empty cell = 0. Dash/line = 0.
  - IMPORTANT: A small tick mark (✓) next to a number is NOT an extra digit.
  - Common confusion: "1" vs "7", "0" vs "6". If the cell appears empty, use 0.
  - The SUM of Q1..Q{part_a['questions']} MUST equal part_a_total_written.

STEP 3: READ PART B & C MARKS (Q{part_bc['questions_start']} to Q{part_bc['questions_end']}):
  *** THIS IS THE MOST CRITICAL SECTION — PAY CLOSE ATTENTION ***

  SHEET LAYOUT for Part B&C:
  Each question (Q{part_bc['questions_start']}..Q{part_bc['questions_end']}) has TWO ROWS on the sheet:
    - Row labeled "a" → sub-part a (student attempted option a)
    - Row labeled "b" → sub-part b (student attempted option b)
  The "Sub" column on the sheet shows "a" or "b" for each row.

  IMPORTANT RULES FOR a vs b:
  - Students typically answer ONLY ONE of a or b per question (either a OR b, not both).
  - If the "a" row has marks written in it, put those marks in Q__a_i, Q__a_ii, Q__a_iii.
  - If the "b" row has marks written in it, put those marks in Q__b_i, Q__b_ii, Q__b_iii.
  - If a row is BLANK/EMPTY, ALL its fields (i, ii, iii) must be 0.
  - DO NOT default everything to sub-part "a". Carefully check WHICH ROW has the marks.
  - The "Total Marks" column on the RIGHT shows the total for that question (a+b combined).

  MARK COLUMNS:
  - "i" is the primary marks column (usually contains the main mark).
  - "ii" and "iii" are secondary — usually 0 unless the examiner split marks across columns.
  - Most often, only "i" has a non-zero value.

  DIGIT READING TIPS:
  - "11" (eleven) vs "1" vs "7" — look at stroke count.
  - "8" vs "3" — check if the top loop is closed.
  - "10" vs "16" vs "18" — check second digit carefully.
  - If a cell is empty or has no writing, it is 0.

  The SUM of all Part B&C marks MUST equal part_bc_total_written.

STEP 4: READ COURSE OUTCOMES (CO-1 to CO-{co['count']}):
  - Located at the bottom of the sheet in a separate table.
  - Columns: PART A, PART B, PART C, TOTAL.
  - Read each value carefully.

STEP 5: VALIDATE ALL TOTALS:
  - Sum(Q1..Q{part_a['questions']}) must == part_a_total_written
  - Sum(all Part B&C fields) must == part_bc_total_written
  - part_a_total_written + part_bc_total_written must == grand_total_written
  - If mismatches exist, TRUST the written totals and adjust individual marks.

RETURN ONLY A VALID JSON OBJECT (no markdown, no explanation, no code fences):

{{
  "registration_number": "<string or null>",
  "part_a_total_written": <integer>,
  "part_bc_total_written": <integer>,
  "grand_total_written": <integer>,
  "part_a": {{"Q1": <int 0-{part_a['marks_each']}>, "Q2": <int>, ..., "Q{part_a['questions']}": <int>}},
  "part_bc": {{
    "Q{part_bc['questions_start']}a_i": <int>, "Q{part_bc['questions_start']}a_ii": <int>, "Q{part_bc['questions_start']}a_iii": <int>,
    "Q{part_bc['questions_start']}b_i": <int>, "Q{part_bc['questions_start']}b_ii": <int>, "Q{part_bc['questions_start']}b_iii": <int>,
    ... for Q{part_bc['questions_start']} to Q{part_bc['questions_end']}, each with a_i, a_ii, a_iii, b_i, b_ii, b_iii
  }},
  "course_outcomes": {{
    "{co['labels'][0]}": {{"PART A": <int>, "PART B": <int>, "PART C": <int>, "TOTAL": <int>}},
    ... for: {', '.join(co['labels'])}
  }},
  "confidence": <float 0.0-1.0>
}}

FINAL RULES:
- Empty/blank/unreadable cell = 0.
- For Part B&C: if marks are in row "b", put them in b_i/b_ii/b_iii and set a_i/a_ii/a_iii = 0. Vice versa.
- Registration number: look for "REGISTER NUMBER" field.{f' Prefix is "{reg_prefix}".' if reg_prefix else ''}
- Written totals are GROUND TRUTH — individual marks must add up to match them.
- Return ONLY raw JSON. No markdown. No explanation. No code fences.
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


def _fix_part_bc_subparts(part_bc: dict, q_start: int, q_end: int) -> dict:
    """Ensure for each question only one sub-part (a or b) has marks.
    If both a and b have marks for the same question, keep the one with
    higher total and zero out the other."""
    fixed = dict(part_bc)
    for q in range(q_start, q_end + 1):
        a_total = sum(int(fixed.get(f'Q{q}a_{c}', 0) or 0) for c in ['i', 'ii', 'iii'])
        b_total = sum(int(fixed.get(f'Q{q}b_{c}', 0) or 0) for c in ['i', 'ii', 'iii'])
        # If both have marks, keep the higher one
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

    # Fix sub-parts: only one of a/b should have marks per question
    part_bc = _fix_part_bc_subparts(
        part_bc,
        part_bc_cfg["questions_start"],
        part_bc_cfg["questions_end"],
    )

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

    # Course Outcomes
    co = data.get("course_outcomes", {})
    for label in list(co.keys()):
        if isinstance(co[label], dict):
            for col in list(co[label].keys()):
                co[label][col] = max(0, int(co[label].get(col, 0) or 0))

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
