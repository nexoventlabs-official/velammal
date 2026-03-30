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

CRITICAL INSTRUCTIONS — READ THESE FIRST:
=============================================
{reg_hint}
STEP 1: FIRST read the WRITTEN TOTALS on the sheet. These are the most reliable numbers:
  - There is a "Total" row at the bottom of Part A — read that number as "part_a_total_written".
  - There is a "Total Marks" column on the right side of Part B&C — read the total at the bottom as "part_bc_total_written".
  - There is a Grand Total (circled, usually in red) — read that as "grand_total_written".
  - The Grand Total is often shown as X/{fmt['total_marks']} (e.g., 49/60 or 74/100).

STEP 2: THEN read individual question marks. Be very careful with handwritten digits:
  - "1" and "7" look similar — check context.
  - "0" and "6" look similar — if cell looks empty, it is 0.
  - An empty cell or a cell with just a dash/line = 0.
  - Part A: Each question max {part_a['marks_each']} marks. NO question can exceed {part_a['marks_each']}.
  - Part B&C "i Marks" column contains the main marks. "ii Marks" and "iii Marks" columns are often 0 unless the student attempted multiple parts.

STEP 3: VALIDATE — The sum of individual Part A marks MUST equal the written Part A total.
  If they don't match, TRUST the written total and adjust individual marks to match.
  Similarly, Part B&C individual marks must add up to the written Part B&C total.
  Grand total = Part A total + Part B&C total. This MUST match the written grand total.

NOW EXTRACT AND RETURN ONLY A VALID JSON OBJECT (no markdown, no explanation, no code fences):

{{
  "registration_number": "<string or null>",
  "part_a_total_written": <integer — the total written at bottom of Part A column>,
  "part_bc_total_written": <integer — the total written at bottom of Part B&C Total Marks column>,
  "grand_total_written": <integer — the circled grand total on the sheet>,
  "part_a": {{"Q1": <int 0-{part_a['marks_each']}>, "Q2": <int>, ..., "Q{part_a['questions']}": <int>}},
  "part_bc": {{
    "Q{part_bc['questions_start']}a_i": <int>, "Q{part_bc['questions_start']}a_ii": <int>, "Q{part_bc['questions_start']}a_iii": <int>,
    "Q{part_bc['questions_start']}b_i": <int>, "Q{part_bc['questions_start']}b_ii": <int>, "Q{part_bc['questions_start']}b_iii": <int>,
    ... continue for ALL questions Q{part_bc['questions_start']} to Q{part_bc['questions_end']}, sub-parts {', '.join(part_bc['sub_parts'])}, columns {', '.join(part_bc['mark_columns'])}
  }},
  "course_outcomes": {{
    "{co['labels'][0]}": {{"PART A": <int>, "PART B": <int>, "PART C": <int>, "TOTAL": <int>}},
    ... for all: {', '.join(co['labels'])}
  }},
  "confidence": <float 0.0-1.0>
}}

FINAL RULES:
- Empty/blank/unreadable cell = 0.
- Registration number: look for "Registration No." or "REGISTER NUMBER" field.{f' The prefix is "{reg_prefix}" — only the last 3 digits vary.' if reg_prefix else ''}
- The written totals (part_a_total_written, part_bc_total_written, grand_total_written) are GROUND TRUTH.
- Return ONLY the raw JSON. No markdown. No explanation. No code fences.
"""
    return prompt


def _adjust_marks_to_target(marks: dict, target: int) -> dict:
    current_sum = sum(marks.values())
    diff = current_sum - target
    if diff == 0:
        return marks
    adjusted = dict(marks)
    sorted_keys = sorted(adjusted.keys(), key=lambda k: adjusted[k], reverse=True)
    if diff > 0:
        remaining = diff
        for key in sorted_keys:
            if remaining <= 0: break
            can_reduce = min(adjusted[key], remaining)
            if can_reduce > 0:
                adjusted[key] -= can_reduce
                remaining -= can_reduce
    else:
        remaining = abs(diff)
        for key in sorted_keys:
            if remaining <= 0: break
            adjusted[key] += 1
            remaining -= 1
    return adjusted


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
