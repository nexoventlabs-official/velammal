import { useState, useEffect } from 'react'
import {
  FileText, Search, Download, ArrowUp, ArrowDown, Filter, X, User, BookOpen,
  CheckCircle2, XCircle, BarChart3, Award, ChevronRight,
} from 'lucide-react'
import { getResults, getStudentResults } from '../api'

export default function Results() {
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ section: '', branch: '', year: '', subject_code: '' })
  const [searchQuery, setSearchQuery] = useState('')

  // Student detail modal
  const [selectedStudent, setSelectedStudent] = useState(null)
  const [studentDetail, setStudentDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => { fetchResults() }, [])

  const fetchResults = async () => {
    setLoading(true)
    try {
      const clean = {}
      if (filters.section) clean.section = filters.section
      if (filters.subject_code) clean.subject_code = filters.subject_code
      const res = await getResults(clean)
      setResults(res.data.results || [])
    } catch (err) { console.error('Error fetching results:', err) }
    setLoading(false)
  }

  const filteredResults = results.filter((r) => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return (
      String(r.RegisterNumber || '').toLowerCase().includes(q) ||
      String(r.StudentName || '').toLowerCase().includes(q) ||
      String(r.SubjectName || '').toLowerCase().includes(q) ||
      String(r.SubjectCode || '').toLowerCase().includes(q)
    )
  })

  const openStudentDetail = async (regNo) => {
    setSelectedStudent(regNo)
    setDetailLoading(true)
    try {
      const res = await getStudentResults(regNo)
      setStudentDetail(res.data)
    } catch (err) { console.error(err); setStudentDetail(null) }
    setDetailLoading(false)
  }

  const exportCSV = () => {
    if (filteredResults.length === 0) return
    const headers = ['RegisterNumber','StudentName','Section','Branch','Year','SubjectName','SubjectCode','ExamPattern','PartATotal','PartBCTotal','MarksObtained','TotalMarks','Status','CO1','CO2','CO3','CO4','CO5']
    const csvRows = [headers.join(',')]
    filteredResults.forEach((r) => {
      csvRows.push(headers.map((h) => `"${String(r[h] || '').replace(/"/g, '""')}"`).join(','))
    })
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'exam_results.csv'; a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Exam Results</h1>
          <p className="text-slate-500 mt-1">Click any student row to view detailed marks breakdown</p>
        </div>
        <button onClick={exportCSV} disabled={filteredResults.length === 0}
          className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors disabled:opacity-50">
          <Download size={16} /> Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Filter size={16} className="text-slate-400" />
          <span className="text-sm font-medium text-slate-600">Filters</span>
        </div>
        <div className="flex flex-wrap gap-3">
          <input className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 w-36"
            placeholder="Section" value={filters.section} onChange={(e) => setFilters({ ...filters, section: e.target.value })} />
          <input className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 w-36"
            placeholder="Subject Code" value={filters.subject_code} onChange={(e) => setFilters({ ...filters, subject_code: e.target.value })} />
          <button onClick={fetchResults} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors">Apply</button>
          <button onClick={() => { setFilters({ section: '', branch: '', year: '', subject_code: '' }); setTimeout(fetchResults, 100) }}
            className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-200 transition-colors">Clear</button>
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input className="w-full pl-9 pr-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Search by name, reg no, subject..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
            </div>
          </div>
        </div>
      </div>

      {/* Results Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-4 border-b border-slate-200">
          <span className="text-sm font-medium text-slate-600">{filteredResults.length} result(s) found</span>
        </div>
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  {['Reg No','Name','Branch','Section','Subject','Pattern','Part A','Part B&C','Total','Status',''].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredResults.map((r, i) => (
                  <tr key={i} className="hover:bg-indigo-50/40 cursor-pointer transition-colors" onClick={() => openStudentDetail(r.RegisterNumber)}>
                    <td className="px-4 py-3 font-medium text-indigo-600">{r.RegisterNumber}</td>
                    <td className="px-4 py-3 text-slate-700 font-medium">{r.StudentName}</td>
                    <td className="px-4 py-3 text-slate-600 text-xs">{r.Branch}</td>
                    <td className="px-4 py-3 text-slate-600">{r.Section}</td>
                    <td className="px-4 py-3 text-slate-600">{r.SubjectName} <span className="text-slate-400">({r.SubjectCode})</span></td>
                    <td className="px-4 py-3"><span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded text-xs font-medium">{r.ExamPattern}</span></td>
                    <td className="px-4 py-3 text-slate-700 font-semibold">{r.PartATotal}</td>
                    <td className="px-4 py-3 text-slate-700 font-semibold">{r.PartBCTotal}</td>
                    <td className="px-4 py-3 font-bold text-slate-800">{r.MarksObtained}<span className="text-slate-400 font-normal">/100</span></td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${
                        String(r.Status).toUpperCase() === 'PASS' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
                      }`}>
                        {String(r.Status).toUpperCase() === 'PASS' ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
                        {r.Status}
                      </span>
                    </td>
                    <td className="px-4 py-3"><ChevronRight size={16} className="text-slate-300" /></td>
                  </tr>
                ))}
                {filteredResults.length === 0 && (
                  <tr><td colSpan={11} className="px-4 py-12 text-center">
                    <FileText className="mx-auto text-slate-300 mb-3" size={36} />
                    <p className="text-slate-400">No results found</p>
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ═══ Student Detail Modal ═══ */}
      {selectedStudent && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setSelectedStudent(null)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            {/* Modal Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-gradient-to-r from-indigo-50 to-slate-50 sticky top-0 z-10">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
                  <User size={20} className="text-indigo-600" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-800">Student Details</h3>
                  <p className="text-xs text-slate-500">{selectedStudent}</p>
                </div>
              </div>
              <button onClick={() => setSelectedStudent(null)} className="text-slate-400 hover:text-slate-600"><X size={20} /></button>
            </div>

            {detailLoading ? (
              <div className="flex items-center justify-center h-60">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600" />
              </div>
            ) : studentDetail ? (
              <div className="p-6 space-y-6">
                {/* Student Info */}
                {studentDetail.student?.StudentName && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500">Name</p>
                      <p className="font-semibold text-slate-800">{studentDetail.student.StudentName}</p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500">Department</p>
                      <p className="font-semibold text-slate-800 text-sm">{studentDetail.student.Branch}</p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500">Section</p>
                      <p className="font-semibold text-slate-800">{studentDetail.student.Section}</p>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3">
                      <p className="text-xs text-slate-500">Year</p>
                      <p className="font-semibold text-slate-800">{studentDetail.student.AcademicYear}</p>
                    </div>
                  </div>
                )}

                {/* Summary Cards */}
                {studentDetail.summary && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 text-center">
                      <BookOpen size={20} className="mx-auto text-indigo-500 mb-1" />
                      <p className="text-2xl font-bold text-indigo-700">{studentDetail.summary.total_subjects}</p>
                      <p className="text-xs text-indigo-500">Subjects</p>
                    </div>
                    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
                      <CheckCircle2 size={20} className="mx-auto text-emerald-500 mb-1" />
                      <p className="text-2xl font-bold text-emerald-700">{studentDetail.summary.passed}</p>
                      <p className="text-xs text-emerald-500">Passed</p>
                    </div>
                    <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-center">
                      <XCircle size={20} className="mx-auto text-rose-500 mb-1" />
                      <p className="text-2xl font-bold text-rose-700">{studentDetail.summary.failed}</p>
                      <p className="text-xs text-rose-500">Failed</p>
                    </div>
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center">
                      <Award size={20} className="mx-auto text-amber-500 mb-1" />
                      <p className="text-2xl font-bold text-amber-700">{studentDetail.summary.average_marks}</p>
                      <p className="text-xs text-amber-500">Average</p>
                    </div>
                  </div>
                )}

                {/* CO Averages */}
                {studentDetail.summary?.co_averages && Object.keys(studentDetail.summary.co_averages).length > 0 && (
                  <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
                    <h4 className="text-sm font-semibold text-purple-800 mb-3">Course Outcome Averages</h4>
                    <div className="flex gap-3 flex-wrap">
                      {Object.entries(studentDetail.summary.co_averages).map(([co, val]) => (
                        <div key={co} className="bg-white border border-purple-200 rounded-lg px-4 py-2 text-center min-w-[70px]">
                          <p className="text-xs text-purple-500 font-medium">{co}</p>
                          <p className="text-lg font-bold text-purple-700">{val}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Subject-wise Results */}
                <div>
                  <h4 className="text-sm font-semibold text-slate-700 mb-3">Subject-wise Marks Breakdown</h4>
                  <div className="space-y-4">
                    {(studentDetail.results || []).map((r, idx) => (
                      <div key={idx} className="border border-slate-200 rounded-xl overflow-hidden">
                        {/* Subject Header */}
                        <div className={`px-4 py-3 flex items-center justify-between ${
                          String(r.Status).toUpperCase() === 'PASS' ? 'bg-emerald-50 border-b border-emerald-200' : 'bg-rose-50 border-b border-rose-200'
                        }`}>
                          <div>
                            <span className="font-semibold text-slate-800">{r.SubjectName}</span>
                            <span className="text-slate-400 ml-2">({r.SubjectCode})</span>
                            <span className="ml-3 px-2 py-0.5 bg-white rounded text-xs font-medium text-indigo-600">{r.ExamPattern}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-lg font-bold text-slate-800">{r.MarksObtained}<span className="text-slate-400 text-sm font-normal">/100</span></span>
                            <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                              String(r.Status).toUpperCase() === 'PASS' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                            }`}>{r.Status}</span>
                          </div>
                        </div>

                        <div className="p-4 space-y-3">
                          {/* Part A - Q1 to Q10 */}
                          <div>
                            <p className="text-xs font-semibold text-slate-500 mb-2">PART A (Q1-Q10) — Total: <span className="text-indigo-600">{r.PartATotal}/20</span></p>
                            <div className="flex flex-wrap gap-2">
                              {[1,2,3,4,5,6,7,8,9,10].map((q) => (
                                <div key={q} className="bg-slate-50 border border-slate-200 rounded px-2.5 py-1 text-center min-w-[42px]">
                                  <p className="text-[10px] text-slate-400">Q{q}</p>
                                  <p className="text-sm font-semibold text-slate-700">{r[`Q${q}`] ?? '-'}</p>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* Part B&C - Q11 to Q16 */}
                          <div>
                            <p className="text-xs font-semibold text-slate-500 mb-2">PART B & C (Q11-Q16) — Total: <span className="text-indigo-600">{r.PartBCTotal}/80</span></p>
                            <div className="flex flex-wrap gap-2">
                              {[11,12,13,14,15,16].map((q) => (
                                <div key={q} className="bg-slate-50 border border-slate-200 rounded px-3 py-1.5 text-center min-w-[52px]">
                                  <p className="text-[10px] text-slate-400">Q{q}</p>
                                  <p className="text-sm font-semibold text-slate-700">{r[`Q${q}`] ?? '-'}</p>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* CO Marks */}
                          {(r.CO1 || r.CO2 || r.CO3 || r.CO4 || r.CO5) ? (
                            <div>
                              <p className="text-xs font-semibold text-slate-500 mb-2">Course Outcomes</p>
                              <div className="flex gap-2">
                                {['CO1','CO2','CO3','CO4','CO5'].map((co) => (
                                  r[co] ? (
                                    <div key={co} className="bg-purple-50 border border-purple-200 rounded px-3 py-1.5 text-center min-w-[52px]">
                                      <p className="text-[10px] text-purple-400">{co}</p>
                                      <p className="text-sm font-semibold text-purple-700">{r[co]}</p>
                                    </div>
                                  ) : null
                                ))}
                              </div>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-12 text-center">
                <FileText className="mx-auto text-slate-300 mb-3" size={36} />
                <p className="text-slate-400">No data found for this student</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
