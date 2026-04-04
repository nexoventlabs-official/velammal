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

# Column headers — 100 marks, question-wise + CO columns
BASE_HEADERS = [
    "S.No", "Register Number", "Student Name", "Section",
    "Academic Year", "Year/Batch", "Department",
    "Subject Name", "Subject Code", "Exam Pattern",
    "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10",
    "Part A (/20)",
    "Q11", "Q12", "Q13", "Q14", "Q15", "Q16",
    "Part B&C (/80)",
    "Grand Total (/100)", "Pass Marks", "Status",
    "CO1", "CO2", "CO3", "CO4", "CO5",
]

# Prefix used to identify subject banner rows inside dept+year+section sheets
SUBJECT_BANNER_PREFIX = "\u25b6 "

# ── Formatting colors ──
HEADER_BG  = {"red": 0.16, "green": 0.22, "blue": 0.43}
HEADER_FG  = {"red": 1, "green": 1, "blue": 1}
PASS_BG    = {"red": 0.85, "green": 0.95, "blue": 0.87}
FAIL_BG    = {"red": 0.97, "green": 0.85, "blue": 0.85}
BANNER_BG  = {"red": 0.91, "green": 0.85, "blue": 1.0}
BANNER_FG  = {"red": 0.20, "green": 0.10, "blue": 0.50}


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

def _style_banner(ws, row_number, col_count):
    """Style a subject banner row with purple background."""
    try:
        sid = _get_sheet_id(ws)
        ws.spreadsheet.batch_update({"requests": [
            {"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": row_number - 1, "endRowIndex": row_number,
                           "startColumnIndex": 0, "endColumnIndex": col_count},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": BANNER_BG,
                    "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": BANNER_FG},
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }}
        ]})
    except Exception as e:
        print(f"Warning: banner style failed: {e}")

def _build_client(creds_filename):
    """Build gspread client. Tries: 1) env var JSON/base64, 2) file on disk."""
    import base64
    
    # Method 1: Try loading from env var (for Render deployment)
    creds_json_env = settings.RESULTS_CREDENTIALS_JSON
    if creds_json_env:
        print("Attempting to load credentials from RESULTS_CREDENTIALS_JSON env var...")
        try:
            creds_str = creds_json_env.strip()
            creds_dict = None
            
            # Try base64 decode first
            try:
                padding = 4 - len(creds_str) % 4
                if padding != 4:
                    creds_str += '=' * padding
                decoded = base64.b64decode(creds_str).decode('utf-8')
                creds_dict = json.loads(decoded)
                print("✓ Decoded base64 credentials from env var")
            except:
                # Try raw JSON
                try:
                    creds_dict = json.loads(creds_json_env)
                    print("✓ Parsed raw JSON credentials from env var")
                except:
                    pass
            
            if creds_dict:
                creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
                client = gspread.authorize(creds)
                print(f"✓ Google Sheets client authorized from env var")
                return client
        except Exception as e:
            print(f"Failed to load from env var: {e}")
    
    # Method 2: Try loading from file (for local development)
    creds_path = os.path.join(BACKEND_DIR, creds_filename)
    print(f"Looking for credentials file at: {creds_path}")
    if os.path.exists(creds_path):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, SCOPES)
            client = gspread.authorize(creds)
            print(f"✓ Google Sheets client authorized from file")
            return client
        except Exception as e:
            print(f"ERROR authorizing from file: {e}")
    else:
        print(f"Credentials file not found: {creds_path}")
    
    print("ERROR: Could not load Google Sheets credentials from env var or file")
    return None


class GoogleSheetsService:
    def __init__(self):
        self.results_client = None
        self.results_db = None
        self.spreadsheet = None
        self._connect()

    def _connect(self):
        self.results_client = _build_client(settings.RESULTS_CREDENTIALS_FILE)
        if self.results_client and settings.RESULTS_DB_SHEET_ID:
            try:
                self.spreadsheet = self.results_client.open_by_key(settings.RESULTS_DB_SHEET_ID)
                print(f"Connected to spreadsheet: {self.spreadsheet.title}")
                
                # Get or create All Results sheet
                try:
                    self.results_db = self.spreadsheet.worksheet("All Results")
                except gspread.exceptions.WorksheetNotFound:
                    self.results_db = self.spreadsheet.add_worksheet(title="All Results", rows=500, cols=20)
                    print("Created 'All Results' worksheet")
                
                # Ensure headers exist
                self._ensure_headers(self.results_db)
                print(f"Results DB ready: '{self.results_db.title}'")
            except Exception as e:
                print(f"ERROR connecting to Results DB: {e}")
                import traceback
                traceback.print_exc()

    def _ensure_headers(self, ws):
        """Ensure worksheet has proper headers."""
        try:
            existing = ws.row_values(1)
            if not existing or len(existing) < 5:
                ws.update('A1', [BASE_HEADERS])
                _style_header(ws, len(BASE_HEADERS))
                print(f"Headers written to '{ws.title}'")
        except Exception as e:
            print(f"Error ensuring headers: {e}")

    # ─── Save results ───

    def _get_row_count(self, ws) -> int:
        """Get current number of data rows (excluding header)."""
        try:
            return max(0, len(ws.get_all_values()) - 1)
        except Exception:
            return 0

    def _result_row(self, r: ExamResult, sno: int = 0) -> list:
        """Build a flat row with question-wise marks, CO marks."""
        co_marks = getattr(r, 'co_marks', {}) or {}

        # Parse section_marks_json for question-wise data
        try:
            section_data = json.loads(r.section_marks_json) if r.section_marks_json else {}
        except Exception:
            section_data = {}

        part_a = section_data.get('part_a', {})
        part_bc = section_data.get('part_bc', {})

        # Q1-Q10 individual marks
        q_a = [str(part_a.get(f'Q{i}', '')) for i in range(1, 11)]

        # Q11-Q16 totals (sum sub-parts per question)
        q_bc = []
        for q in range(11, 17):
            total = 0
            for sub in ['a', 'b']:
                for col in ['i', 'ii', 'iii']:
                    total += int(part_bc.get(f'Q{q}{sub}_{col}', 0) or 0)
            q_bc.append(str(total))

        return [
            str(sno) if sno else "",
            r.register_number,
            r.student_name,
            r.section,
            r.academic_year,
            getattr(r, 'year', ''),
            getattr(r, 'branch', ''),
            r.subject_name,
            r.subject_code,
            getattr(r, 'exam_pattern', ''),
            *q_a,                       # Q1-Q10
            str(r.part_a_total),
            *q_bc,                      # Q11-Q16 totals
            str(r.part_bc_total),
            str(r.marks_obtained),
            str(r.pass_marks),
            r.status,
            str(co_marks.get('CO1', '')),
            str(co_marks.get('CO2', '')),
            str(co_marks.get('CO3', '')),
            str(co_marks.get('CO4', '')),
            str(co_marks.get('CO5', '')),
        ]

    def save_result(self, result: ExamResult) -> bool:
        """Save result to All Results sheet."""
        if not self.results_db:
            print("ERROR: results_db not connected")
            return False
        try:
            self._ensure_headers(self.results_db)
            
            sno = self._get_row_count(self.results_db) + 1
            row = self._result_row(result, sno)
            self.results_db.append_row(row, value_input_option='USER_ENTERED')
            row_num = len(self.results_db.get_all_values())
            _style_row(self.results_db, row_num, len(row), result.status)
            print(f"Saved to All Results: {result.register_number} - {result.marks_obtained}")
            return True
        except Exception as e:
            print(f"Error saving result: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save_result_to_worksheet(self, sheet_name: str, result: ExamResult) -> bool:
        """Save result to a dept+year+section worksheet with subject grouping.
        Each subject gets a banner row; student rows are placed under the
        correct subject group."""
        if not self.spreadsheet:
            print("ERROR: spreadsheet not connected")
            return False
        try:
            try:
                ws = self.spreadsheet.worksheet(sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                ws = self.spreadsheet.add_worksheet(title=sheet_name, rows=500, cols=len(BASE_HEADERS) + 2)
                ws.update('A1', [BASE_HEADERS])
                _style_header(ws, len(BASE_HEADERS))

            all_values = ws.get_all_values()
            col_count = len(BASE_HEADERS)
            subject_code = result.subject_code
            exam_pattern = getattr(result, 'exam_pattern', '')

            # ── Find existing subject group ──
            banner_idx = None   # 0-based row index of subject banner
            group_end = None    # 0-based row index of last data row in group

            for i, row in enumerate(all_values):
                cell0 = str(row[0]) if row else ""
                if cell0.startswith(SUBJECT_BANNER_PREFIX) and subject_code in cell0:
                    banner_idx = i
                    group_end = i
                elif banner_idx is not None and cell0.startswith(SUBJECT_BANNER_PREFIX):
                    break  # hit next subject banner
                elif banner_idx is not None:
                    if any(str(c).strip() for c in row):
                        group_end = i

            if banner_idx is not None:
                # Subject exists → insert after last data row
                sno = group_end - banner_idx  # rows between banner and end = data count
                row_data = self._result_row(result, sno)
                insert_pos = group_end + 2  # 1-indexed, after last data row
                ws.insert_row(row_data, insert_pos, value_input_option='USER_ENTERED')
                _style_row(ws, insert_pos, col_count, result.status)
                print(f"Inserted under subject '{subject_code}' at row {insert_pos}")
            else:
                # New subject → append section at bottom
                current_rows = len(all_values)

                # Empty separator row (skip if sheet only has the header)
                if current_rows > 1:
                    ws.append_row([''] * col_count, value_input_option='USER_ENTERED')

                # Subject banner row
                banner_text = f"{SUBJECT_BANNER_PREFIX}{subject_code} - {result.subject_name}"
                if exam_pattern:
                    banner_text += f" | {exam_pattern}"
                banner_row = [banner_text] + [''] * (col_count - 1)
                ws.append_row(banner_row, value_input_option='USER_ENTERED')
                banner_row_num = len(ws.get_all_values())
                _style_banner(ws, banner_row_num, col_count)

                # Data row
                row_data = self._result_row(result, 1)
                ws.append_row(row_data, value_input_option='USER_ENTERED')
                data_row_num = len(ws.get_all_values())
                _style_row(ws, data_row_num, col_count, result.status)
                print(f"Created subject group '{subject_code}' in '{sheet_name}'")

            return True
        except Exception as e:
            print(f"Error saving to {sheet_name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ─── Read results ───

    @staticmethod
    def _normalize(row: Dict) -> Dict:
        """Map Google Sheet header names to consistent API keys."""
        return {
            "SNo": row.get("S.No", ""),
            "RegisterNumber": str(row.get("Register Number", "")),
            "StudentName": str(row.get("Student Name", "")),
            "Section": str(row.get("Section", "")),
            "AcademicYear": str(row.get("Academic Year", "")),
            "Year": str(row.get("Year/Batch", "")),
            "Branch": str(row.get("Department", "")),
            "SubjectName": str(row.get("Subject Name", "")),
            "SubjectCode": str(row.get("Subject Code", "")),
            "ExamPattern": str(row.get("Exam Pattern", "")),
            "Q1": row.get("Q1", ""), "Q2": row.get("Q2", ""),
            "Q3": row.get("Q3", ""), "Q4": row.get("Q4", ""),
            "Q5": row.get("Q5", ""), "Q6": row.get("Q6", ""),
            "Q7": row.get("Q7", ""), "Q8": row.get("Q8", ""),
            "Q9": row.get("Q9", ""), "Q10": row.get("Q10", ""),
            "PartATotal": row.get("Part A (/20)", 0),
            "Q11": row.get("Q11", ""), "Q12": row.get("Q12", ""),
            "Q13": row.get("Q13", ""), "Q14": row.get("Q14", ""),
            "Q15": row.get("Q15", ""), "Q16": row.get("Q16", ""),
            "PartBCTotal": row.get("Part B&C (/80)", 0),
            "MarksObtained": row.get("Grand Total (/100)", 0),
            "TotalMarks": 100,
            "PassMarks": row.get("Pass Marks", 40),
            "Status": str(row.get("Status", "")),
            "CO1": row.get("CO1", ""), "CO2": row.get("CO2", ""),
            "CO3": row.get("CO3", ""), "CO4": row.get("CO4", ""),
            "CO5": row.get("CO5", ""),
        }

    def get_all_results(self) -> List[Dict]:
        if not self.results_db:
            return []
        try:
            raw = self.results_db.get_all_records()
            return [self._normalize(r) for r in raw]
        except Exception as e:
            print(f"Error fetching results: {e}")
            return []

    def get_results_by_filter(self, section=None, academic_year=None, subject_code=None) -> List[Dict]:
        results = self.get_all_results()
        filtered = []
        for r in results:
            if section and r["Section"].upper() != section.upper(): continue
            if academic_year and r["AcademicYear"].upper() != academic_year.upper(): continue
            if subject_code and r["SubjectCode"].upper() != subject_code.upper(): continue
            filtered.append(r)
        return filtered

    def get_dashboard_stats(self, section=None, academic_year=None, subject_code=None) -> Dict:
        results = self.get_results_by_filter(section, academic_year, subject_code)
        if not results:
            return {"total_students": 0, "total_passed": 0, "total_failed": 0,
                    "pass_percentage": 0.0, "average_marks": 0.0,
                    "highest_marks": 0, "lowest_marks": 0,
                    "section_wise": {}, "year_wise": {}, "subject_wise": {}}

        marks_list, passed, failed = [], 0, 0
        section_wise, year_wise, subject_wise = {}, {}, {}

        for r in results:
            m = int(r.get("MarksObtained", 0) or 0)
            marks_list.append(m)
            st = str(r.get("Status", "")).upper()
            passed += 1 if st == "PASS" else 0
            failed += 1 if st == "FAIL" else 0

            for bucket, key in [
                (section_wise, r.get("Section", "?")),
                (year_wise, r.get("AcademicYear", "?")),
                (subject_wise, f"{r.get('SubjectCode','')} - {r.get('SubjectName','')}"),
            ]:
                bucket.setdefault(key, {"total": 0, "passed": 0, "failed": 0, "marks": []})
                bucket[key]["total"] += 1
                bucket[key]["passed"] += 1 if st == "PASS" else 0
                bucket[key]["failed"] += 1 if st == "FAIL" else 0
                bucket[key]["marks"].append(m)

        def _summarize(bucket):
            for k, v in bucket.items():
                ml = v.pop("marks", [])
                v["avg_marks"] = round(sum(ml) / len(ml), 2) if ml else 0
                v["highest"] = max(ml) if ml else 0
                v["lowest"] = min(ml) if ml else 0
                v["pass_pct"] = round((v["passed"] / v["total"]) * 100, 1) if v["total"] else 0

        _summarize(section_wise)
        _summarize(year_wise)
        _summarize(subject_wise)

        t = len(results)
        return {
            "total_students": t, "total_passed": passed, "total_failed": failed,
            "pass_percentage": round((passed / t) * 100, 2) if t else 0,
            "average_marks": round(sum(marks_list) / len(marks_list), 2) if marks_list else 0,
            "highest_marks": max(marks_list) if marks_list else 0,
            "lowest_marks": min(marks_list) if marks_list else 0,
            "section_wise": section_wise,
            "year_wise": year_wise,
            "subject_wise": subject_wise,
        }

    # ─── Worksheet management ───

    def _get_registry(self):
        if not self.spreadsheet: return None
        try:
            try: 
                return self.spreadsheet.worksheet("_registry")
            except gspread.exceptions.WorksheetNotFound:
                ws = self.spreadsheet.add_worksheet(title="_registry", rows=200, cols=10)
                headers = ["SheetName", "SubjectName", "SubjectCode", "TotalMarks", "PassMarks", "ExamType", "Section", "AcademicYear", "Branch", "CreatedAt"]
                ws.update('A1', [headers])
                _style_header(ws, 10)
                return ws
        except Exception as e:
            print(f"Error getting registry: {e}")
            return None

    def get_or_create_session_worksheet(self, config: dict) -> Dict:
        """Get or create a worksheet based on Department + Year + Section.
        One sheet per dept+year+section combo; different subjects go as rows."""
        if not self.spreadsheet:
            print("ERROR: Spreadsheet not connected for session worksheet")
            return {"success": False, "sheet_name": None, "message": "Results DB not connected"}
        try:
            import datetime
            section = config.get("section", "")
            branch = config.get("branch", "")       # department
            year = config.get("year", "")            # batch year
            academic_year = config.get("academic_year", "")

            # Sheet name: Department - Year - Section
            name = f"{branch} - {year} - {section}"
            if len(name) > 95:
                name = name[:95]
            name = name.replace("/", "-").replace("\\", "-")

            existing_titles = [w.title for w in self.spreadsheet.worksheets()]
            if name in existing_titles:
                print(f"Sheet '{name}' already exists, reusing")
                return {"success": True, "sheet_name": name, "message": "Sheet already exists"}

            # Create new worksheet with headers
            ws = self.spreadsheet.add_worksheet(title=name, rows=500, cols=len(BASE_HEADERS) + 2)
            ws.update('A1', [BASE_HEADERS])
            _style_header(ws, len(BASE_HEADERS))
            print(f"Created session worksheet: '{name}'")

            # Register in _registry
            reg = self._get_registry()
            if reg:
                reg.append_row([
                    name, "", "", "100", str(config.get("pass_marks", 40)),
                    "Model Exam", section, academic_year, branch,
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                ], value_input_option='USER_ENTERED')
            return {"success": True, "sheet_name": name, "message": f"Sheet '{name}' created"}
        except Exception as e:
            print(f"Error creating session worksheet: {e}")
            return {"success": False, "sheet_name": None, "message": str(e)}

    def create_results_worksheet(self, subject_name, subject_code, total_marks, section="", academic_year="", branch="") -> Dict:
        if not self.spreadsheet:
            return {"success": False, "message": "Results DB not connected"}
        try:
            import datetime
            # Sheet name based on department + year + section
            name = f"{branch} - {academic_year} - {section}" if branch else f"{subject_code} - {subject_name}"
            name = name.replace("/", "-").replace("\\", "-")
            if name in [w.title for w in self.spreadsheet.worksheets()]:
                return {"success": True, "message": f"'{name}' already exists", "sheet_name": name,
                        "subject_name": subject_name, "subject_code": subject_code,
                        "total_marks": 100, "pass_marks": 40, "exam_type": "Model Exam"}
            ws = self.spreadsheet.add_worksheet(title=name, rows=500, cols=len(BASE_HEADERS) + 2)
            ws.update('A1', [BASE_HEADERS])
            _style_header(ws, len(BASE_HEADERS))
            reg = self._get_registry()
            if reg:
                reg.append_row([name, subject_name, subject_code, "100", "40",
                                 "Model Exam", section, academic_year, branch,
                                 datetime.datetime.now().strftime("%Y-%m-%d %H:%M")], value_input_option='USER_ENTERED')
            return {"success": True, "message": f"'{name}' created", "sheet_name": name,
                    "subject_name": subject_name, "subject_code": subject_code,
                    "total_marks": 100, "pass_marks": 40, "exam_type": "Model Exam"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def list_results_worksheets(self) -> List[Dict]:
        if not self.spreadsheet: return []
        try:
            all_sheets = [w.title for w in self.spreadsheet.worksheets()]
            reg_data = {}
            reg = self._get_registry()
            if reg:
                for r in reg.get_all_records():
                    reg_data[str(r.get("SheetName", ""))] = {
                        "subject_name": str(r.get("SubjectName", "")),
                        "subject_code": str(r.get("SubjectCode", "")),
                        "total_marks": int(r.get("TotalMarks", 0) or 0),
                        "pass_marks": int(r.get("PassMarks", 0) or 0),
                        "exam_type": str(r.get("ExamType", "")),
                        "section": str(r.get("Section", "")),
                        "academic_year": str(r.get("AcademicYear", "")),
                        "branch": str(r.get("Branch", "")),
                        "created_at": str(r.get("CreatedAt", "")),
                    }
            return [
                {"sheet_name": n, **reg_data.get(n, {
                    "subject_name": "", "subject_code": "", "total_marks": 0,
                    "pass_marks": 0, "exam_type": "", "section": "", "academic_year": "",
                    "branch": "", "created_at": ""
                })}
                for n in all_sheets if n not in ("_registry", "All Results", "Sheet1")
            ]
        except Exception as e:
            print(f"Error listing worksheets: {e}"); return []

    def get_sheet_results(self, sheet_name: str) -> List[Dict]:
        """Get all data rows from a specific sheet (skip banner rows)."""
        if not self.spreadsheet: return []
        try:
            ws = self.spreadsheet.worksheet(sheet_name)
            raw = ws.get_all_records()
            # Filter out subject banner rows
            return [r for r in raw if not str(r.get("S.No", "")).startswith(SUBJECT_BANNER_PREFIX)]
        except Exception as e:
            print(f"Error reading sheet {sheet_name}: {e}"); return []

    def get_sheet_stats(self, sheet_name: str) -> Dict:
        """Get pass/fail stats for a specific sheet."""
        rows = self.get_sheet_results(sheet_name)
        if not rows:
            return {"total": 0, "passed": 0, "failed": 0, "pass_pct": 0, "avg": 0, "highest": 0, "lowest": 0}
        total, passed, failed = 0, 0, 0
        marks = []
        for r in rows:
            st = str(r.get("Status", "")).upper()
            if st not in ("PASS", "FAIL"): continue
            total += 1
            if st == "PASS": passed += 1
            else: failed += 1
            for key in ["Grand Total (/100)", "Grand Total"]:
                val = r.get(key)
                if val is not None:
                    try: marks.append(int(val)); break
                    except: pass
        return {
            "total": total, "passed": passed, "failed": failed,
            "pass_pct": round((passed / total) * 100, 1) if total else 0,
            "avg": round(sum(marks) / len(marks), 1) if marks else 0,
            "highest": max(marks) if marks else 0,
            "lowest": min(marks) if marks else 0,
        }

    def restyle_all_sheets(self) -> Dict:
        styled, errors = 0, []
        if self.results_client and settings.RESULTS_DB_SHEET_ID:
            try:
                sp = self.results_client.open_by_key(settings.RESULTS_DB_SHEET_ID)
                reqs = []
                for ws in sp.worksheets():
                    try:
                        sid = _get_sheet_id(ws)
                        vals = ws.get_all_values()
                        if not vals: continue
                        cc = len(vals[0]) if vals[0] else len(BASE_HEADERS)
                        reqs.extend(_build_header_fmt(sid, cc))
                        # Status column index in BASE_HEADERS
                        status_idx = next((j for j, h in enumerate(BASE_HEADERS) if h == "Status"), 30)
                        for ri in range(1, len(vals)):
                            st = vals[ri][status_idx] if len(vals[ri]) > status_idx else ""
                            if st.upper() in ("PASS", "FAIL"):
                                reqs.append(_build_row_color(sid, ri, cc, st))
                        styled += 1
                    except Exception as e: errors.append(f"'{ws.title}': {e}")
                if reqs: sp.batch_update({"requests": reqs})
            except Exception as e: errors.append(f"Results DB: {e}")
        return {"success": True, "styled_sheets": styled, "errors": errors}


sheets_service = GoogleSheetsService()
