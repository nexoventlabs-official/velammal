"""
Google Sheets service — Results DB only.
Student data is now handled by MongoDB (student_db.py).
"""
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import List, Optional, Dict
from app.config import settings
from app.models import ExamResult, get_exam_format

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Base columns (before marks breakdown)
BASE_HEADERS = [
    "RegisterNumber", "StudentName", "Email", "Section", "AcademicYear",
    "SubjectName", "SubjectCode", "TotalMarks", "MarksObtained",
    "PassMarks", "Status", "PartATotal", "PartBCTotal",
]


def _build_marks_headers(total_marks: int) -> List[str]:
    """Build individual mark column headers based on exam format."""
    fmt = get_exam_format(total_marks)
    cols = []
    # Part A: Q1, Q2, ...
    for i in range(1, fmt["part_a"]["questions"] + 1):
        cols.append(f"Q{i}")
    # Part BC: Q6a_i, Q6a_ii, Q6a_iii, Q6b_i, ...
    for q in range(fmt["part_bc"]["questions_start"], fmt["part_bc"]["questions_end"] + 1):
        for sub in fmt["part_bc"]["sub_parts"]:
            for mc in fmt["part_bc"]["mark_columns"]:
                cols.append(f"Q{q}{sub}_{mc}")
    # Course Outcomes: CO-4_PARTA, CO-4_PARTB, ...
    for label in fmt["course_outcomes"]["labels"]:
        for c in fmt["course_outcomes"]["columns"]:
            cols.append(f"{label}_{c.replace(' ', '')}")
    return cols


def _build_full_headers(total_marks: int) -> List[str]:
    return BASE_HEADERS + _build_marks_headers(total_marks)

# ── Formatting colors ──
HEADER_BG = {"red": 0.16, "green": 0.22, "blue": 0.43}
HEADER_FG = {"red": 1, "green": 1, "blue": 1}
PASS_BG   = {"red": 0.85, "green": 0.95, "blue": 0.87}
FAIL_BG   = {"red": 0.97, "green": 0.85, "blue": 0.85}


def _get_sheet_id(worksheet) -> int:
    return worksheet._properties.get("sheetId", worksheet.id)

def _build_header_fmt(sheet_id: int, col_count: int) -> list:
    return [
        {"repeatCell": {
            "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": col_count},
            "cell": {"userEnteredFormat": {
                "backgroundColor": HEADER_BG,
                "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": HEADER_FG},
                "horizontalAlignment": "CENTER",
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
        }},
        {"updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount",
        }},
    ]

def _build_row_color(sheet_id: int, row_idx: int, col_count: int, status: str) -> dict:
    bg = PASS_BG if status.upper() == "PASS" else FAIL_BG
    return {"repeatCell": {
        "range": {"sheetId": sheet_id, "startRowIndex": row_idx, "endRowIndex": row_idx + 1, "startColumnIndex": 0, "endColumnIndex": col_count},
        "cell": {"userEnteredFormat": {"backgroundColor": bg}},
        "fields": "userEnteredFormat.backgroundColor",
    }}

def _style_header(ws, col_count):
    try:
        ws.spreadsheet.batch_update({"requests": _build_header_fmt(_get_sheet_id(ws), col_count)})
    except Exception as e:
        print(f"Warning: header style failed: {e}")

def _style_row(ws, row_number, col_count, status):
    try:
        ws.spreadsheet.batch_update({"requests": [_build_row_color(_get_sheet_id(ws), row_number - 1, col_count, status)]})
    except Exception as e:
        print(f"Warning: row style failed: {e}")

def _build_client(creds_filename):
    creds_path = os.path.join(BACKEND_DIR, creds_filename)
    if not os.path.exists(creds_path):
        print(f"WARNING: Credentials not found: {creds_path}")
        return None
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, SCOPES)
    return gspread.authorize(creds)


class GoogleSheetsService:
    def __init__(self):
        self.results_client = None
        self.results_db = None
        self._connect()

    def _connect(self):
        self.results_client = _build_client(settings.RESULTS_CREDENTIALS_FILE)
        if self.results_client and settings.RESULTS_DB_SHEET_ID:
            try:
                spreadsheet = self.results_client.open_by_key(settings.RESULTS_DB_SHEET_ID)
                # Get or create "All Results" as the main combined sheet
                try:
                    self.results_db = spreadsheet.worksheet("All Results")
                except gspread.exceptions.WorksheetNotFound:
                    try:
                        self.results_db = spreadsheet.worksheet("Sheet1")
                    except gspread.exceptions.WorksheetNotFound:
                        # Create it
                        self.results_db = spreadsheet.add_worksheet(title="All Results", rows=500, cols=20)

                existing = self.results_db.row_values(1)
                if not existing:
                    # Default to 60-mark headers for the main combined sheet
                    headers = _build_full_headers(60)
                    self.results_db.append_row(headers)
                _style_header(self.results_db, len(self.results_db.row_values(1) or BASE_HEADERS))
                print(f"Results DB connected: '{self.results_db.title}'")
            except Exception as e:
                print(f"WARNING: Could not open Results DB: {e}")

    # ─── Save results ───

    def _result_row(self, r: ExamResult) -> list:
        """Build a flat row with base columns + expanded section marks."""
        base = [
            r.register_number, r.student_name, r.email,
            r.section, r.academic_year,
            r.subject_name, r.subject_code,
            str(r.total_marks), str(r.marks_obtained),
            str(r.pass_marks), r.status,
            str(r.part_a_total), str(r.part_bc_total),
        ]
        # Parse section_marks_json and expand into columns
        try:
            sm = json.loads(r.section_marks_json) if r.section_marks_json else {}
        except (json.JSONDecodeError, TypeError):
            sm = {}

        fmt = get_exam_format(r.total_marks)
        part_a = sm.get("part_a", {})
        part_bc = sm.get("part_bc", {})
        co = sm.get("course_outcomes", {})

        marks_cols = []
        # Part A questions
        for i in range(1, fmt["part_a"]["questions"] + 1):
            marks_cols.append(str(part_a.get(f"Q{i}", 0)))
        # Part BC questions
        for q in range(fmt["part_bc"]["questions_start"], fmt["part_bc"]["questions_end"] + 1):
            for sub in fmt["part_bc"]["sub_parts"]:
                for mc in fmt["part_bc"]["mark_columns"]:
                    marks_cols.append(str(part_bc.get(f"Q{q}{sub}_{mc}", 0)))
        # Course Outcomes
        for label in fmt["course_outcomes"]["labels"]:
            co_data = co.get(label, {})
            for c in fmt["course_outcomes"]["columns"]:
                marks_cols.append(str(co_data.get(c, 0)))

        return base + marks_cols

    def save_result(self, result: ExamResult) -> bool:
        if not self.results_db:
            return False
        try:
            row = self._result_row(result)
            self.results_db.append_row(row)
            row_num = len(self.results_db.get_all_values())
            _style_row(self.results_db, row_num, len(row), result.status)
            return True
        except Exception as e:
            print(f"Error saving result: {e}")
            return False

    def save_result_to_worksheet(self, sheet_name: str, result: ExamResult) -> bool:
        if not self.results_client or not settings.RESULTS_DB_SHEET_ID:
            return False
        try:
            sp = self.results_client.open_by_key(settings.RESULTS_DB_SHEET_ID)
            ws = sp.worksheet(sheet_name)
            row = self._result_row(result)
            ws.append_row(row)
            row_num = len(ws.get_all_values())
            _style_row(ws, row_num, len(row), result.status)
            return True
        except Exception as e:
            print(f"Error saving to {sheet_name}: {e}")
            return False

    # ─── Read results ───

    def get_all_results(self) -> List[Dict]:
        if not self.results_db:
            return []
        try:
            return self.results_db.get_all_records()
        except Exception as e:
            print(f"Error fetching results: {e}")
            return []

    def get_results_by_filter(self, section=None, academic_year=None, subject_code=None) -> List[Dict]:
        results = self.get_all_results()
        filtered = []
        for r in results:
            if section and str(r.get("Section", "")).upper() != section.upper(): continue
            if academic_year and str(r.get("AcademicYear", "")).upper() != academic_year.upper(): continue
            if subject_code and str(r.get("SubjectCode", "")).upper() != subject_code.upper(): continue
            filtered.append(r)
        return filtered

    def get_dashboard_stats(self, section=None, academic_year=None, subject_code=None) -> Dict:
        results = self.get_results_by_filter(section, academic_year, subject_code)
        if not results:
            return {"total_students": 0, "total_passed": 0, "total_failed": 0, "pass_percentage": 0.0, "average_marks": 0.0, "highest_marks": 0, "lowest_marks": 0, "section_wise": {}, "year_wise": {}}
        marks_list, passed, failed = [], 0, 0
        section_wise, year_wise = {}, {}
        for r in results:
            m = int(r.get("MarksObtained", 0)); marks_list.append(m)
            st = str(r.get("Status", "")).upper()
            passed += 1 if st == "PASS" else 0; failed += 1 if st == "FAIL" else 0
            for bucket, key in [(section_wise, str(r.get("Section", "?"))), (year_wise, str(r.get("AcademicYear", "?")))]:
                bucket.setdefault(key, {"total": 0, "passed": 0, "failed": 0, "avg_marks": 0})
                bucket[key]["total"] += 1
                bucket[key]["passed"] += 1 if st == "PASS" else 0
                bucket[key]["failed"] += 1 if st == "FAIL" else 0
        for sec in section_wise:
            sm = [int(r.get("MarksObtained", 0)) for r in results if str(r.get("Section", "")) == sec]
            section_wise[sec]["avg_marks"] = round(sum(sm)/len(sm), 2) if sm else 0
        for yr in year_wise:
            ym = [int(r.get("MarksObtained", 0)) for r in results if str(r.get("AcademicYear", "")) == yr]
            year_wise[yr]["avg_marks"] = round(sum(ym)/len(ym), 2) if ym else 0
        t = len(results)
        return {"total_students": t, "total_passed": passed, "total_failed": failed,
                "pass_percentage": round((passed/t)*100, 2) if t else 0,
                "average_marks": round(sum(marks_list)/len(marks_list), 2) if marks_list else 0,
                "highest_marks": max(marks_list) if marks_list else 0,
                "lowest_marks": min(marks_list) if marks_list else 0,
                "section_wise": section_wise, "year_wise": year_wise}

    # ─── Worksheet management ───

    def _get_registry(self):
        if not self.results_client or not settings.RESULTS_DB_SHEET_ID: return None
        try:
            sp = self.results_client.open_by_key(settings.RESULTS_DB_SHEET_ID)
            try: return sp.worksheet("_registry")
            except gspread.exceptions.WorksheetNotFound:
                ws = sp.add_worksheet(title="_registry", rows=100, cols=6)
                ws.append_row(["SheetName", "SubjectName", "SubjectCode", "TotalMarks", "PassMarks", "ExamType"])
                _style_header(ws, 6)
                return ws
        except Exception: return None

    def create_results_worksheet(self, subject_name, subject_code, total_marks) -> Dict:
        if not self.results_client or not settings.RESULTS_DB_SHEET_ID:
            return {"success": False, "message": "Results DB not connected"}
        try:
            sp = self.results_client.open_by_key(settings.RESULTS_DB_SHEET_ID)
            name = f"{subject_code} - {subject_name} ({total_marks}m)"
            if name in [w.title for w in sp.worksheets()]:
                return {"success": False, "message": f"'{name}' already exists"}
            headers = _build_full_headers(total_marks)
            ws = sp.add_worksheet(title=name, rows=200, cols=len(headers) + 2)
            ws.append_row(headers)
            _style_header(ws, len(headers))
            exam_type = "Internal Assessment" if total_marks <= 60 else "Model Exam"
            pass_marks = 24 if total_marks <= 60 else 40
            reg = self._get_registry()
            if reg: reg.append_row([name, subject_name, subject_code, str(total_marks), str(pass_marks), exam_type])
            return {"success": True, "message": f"'{name}' created", "sheet_name": name,
                    "subject_name": subject_name, "subject_code": subject_code,
                    "total_marks": total_marks, "pass_marks": pass_marks, "exam_type": exam_type}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def list_results_worksheets(self) -> List[Dict]:
        if not self.results_client or not settings.RESULTS_DB_SHEET_ID: return []
        try:
            sp = self.results_client.open_by_key(settings.RESULTS_DB_SHEET_ID)
            all_sheets = [w.title for w in sp.worksheets()]
            reg_data = {}
            reg = self._get_registry()
            if reg:
                for r in reg.get_all_records():
                    reg_data[str(r.get("SheetName", ""))] = {
                        "subject_name": str(r.get("SubjectName", "")), "subject_code": str(r.get("SubjectCode", "")),
                        "total_marks": int(r.get("TotalMarks", 0) or 0), "pass_marks": int(r.get("PassMarks", 0) or 0),
                        "exam_type": str(r.get("ExamType", "")),
                    }
            return [{"sheet_name": n, **reg_data.get(n, {"subject_name": "", "subject_code": "", "total_marks": 0, "pass_marks": 0, "exam_type": ""})} for n in all_sheets if n != "_registry"]
        except Exception as e:
            print(f"Error listing worksheets: {e}"); return []

    def restyle_all_sheets(self) -> Dict:
        styled, errors = 0, []
        if self.results_client and settings.RESULTS_DB_SHEET_ID:
            try:
                sp = self.results_client.open_by_key(settings.RESULTS_DB_SHEET_ID)
                reqs = []
                for ws in sp.worksheets():
                    try:
                        sid = _get_sheet_id(ws)
                        if ws.title == "_registry":
                            reqs.extend(_build_header_fmt(sid, 6)); styled += 1; continue
                        vals = ws.get_all_values()
                        if not vals: continue
                        cc = len(vals[0]) if vals[0] else len(BASE_HEADERS)
                        reqs.extend(_build_header_fmt(sid, cc))
                        for ri in range(1, len(vals)):
                            st = vals[ri][10] if len(vals[ri]) > 10 else ""
                            if st.upper() in ("PASS", "FAIL"):
                                reqs.append(_build_row_color(sid, ri, cc, st))
                        styled += 1
                    except Exception as e: errors.append(f"'{ws.title}': {e}")
                if reqs: sp.batch_update({"requests": reqs})
            except Exception as e: errors.append(f"Results DB: {e}")
        return {"success": True, "styled_sheets": styled, "errors": errors}


sheets_service = GoogleSheetsService()
