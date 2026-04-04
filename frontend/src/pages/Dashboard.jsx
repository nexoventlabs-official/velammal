import { useState, useEffect } from 'react'
import {
  Users, CheckCircle2, XCircle, TrendingUp, Award, BarChart3,
  ArrowDown, ArrowUp, BookOpen, Target,
} from 'lucide-react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, RadarChart, Radar, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis,
} from 'recharts'
import { getDashboardStats, getResults } from '../api'

const COLORS = ['#6366f1', '#f43f5e', '#10b981', '#f59e0b', '#3b82f6', '#8b5cf6']

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [results, setResults] = useState([])
  const [filters, setFilters] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => { fetchData() }, [filters])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [statsRes, resultsRes] = await Promise.all([getDashboardStats(filters), getResults(filters)])
      setStats(statsRes.data.stats)
      setResults(resultsRes.data.results)
    } catch (err) { console.error('Dashboard fetch error:', err) }
    setLoading(false)
  }

  const statCards = stats ? [
    { label: 'Total Results', value: stats.total_students, icon: Users, textColor: 'text-indigo-600', bg: 'bg-indigo-50' },
    { label: 'Passed', value: stats.total_passed, icon: CheckCircle2, textColor: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Failed', value: stats.total_failed, icon: XCircle, textColor: 'text-rose-600', bg: 'bg-rose-50' },
    { label: 'Pass %', value: `${stats.pass_percentage}%`, icon: TrendingUp, textColor: 'text-amber-600', bg: 'bg-amber-50' },
    { label: 'Average', value: stats.average_marks, icon: BarChart3, textColor: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Highest', value: stats.highest_marks, icon: Award, textColor: 'text-purple-600', bg: 'bg-purple-50' },
  ] : []

  const pieData = stats ? [
    { name: 'Passed', value: stats.total_passed },
    { name: 'Failed', value: stats.total_failed },
  ] : []

  const sectionData = stats ? Object.entries(stats.section_wise || {}).map(([key, val]) => ({
    name: key, passed: val.passed, failed: val.failed, avg: val.avg_marks, pass_pct: val.pass_pct,
  })) : []

  const subjectData = stats ? Object.entries(stats.subject_wise || {}).map(([key, val]) => ({
    name: key.length > 20 ? key.slice(0, 20) + '...' : key,
    fullName: key,
    total: val.total, passed: val.passed, failed: val.failed,
    avg: val.avg_marks, pass_pct: val.pass_pct, highest: val.highest, lowest: val.lowest,
  })) : []

  // CO averages across all results
  const coData = (() => {
    if (!results.length) return []
    const cos = ['CO1', 'CO2', 'CO3', 'CO4', 'CO5']
    return cos.map((co) => {
      const vals = results.map((r) => parseInt(r[co]) || 0).filter((v) => v > 0)
      return { co, avg: vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : 0 }
    }).filter((d) => d.avg > 0)
  })()

  // Top performers
  const topPerformers = [...results]
    .sort((a, b) => (parseInt(b.MarksObtained) || 0) - (parseInt(a.MarksObtained) || 0))
    .slice(0, 10)

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
        <p className="text-slate-500 mt-1">Overview of exam results, subjects, and course outcomes</p>
      </div>

      {/* Filter Bar */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-6 flex flex-wrap gap-3">
        <input className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="Section" value={filters.section || ''} onChange={(e) => setFilters({ ...filters, section: e.target.value || undefined })} />
        <select className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          value={filters.academic_year || ''} onChange={(e) => setFilters({ ...filters, academic_year: e.target.value || undefined })}>
          <option value="">All Years</option>
          <option value="1st Year">1st Year</option><option value="2nd Year">2nd Year</option>
          <option value="3rd Year">3rd Year</option><option value="4th Year">4th Year</option>
        </select>
        <input className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          placeholder="Subject Code" value={filters.subject_code || ''} onChange={(e) => setFilters({ ...filters, subject_code: e.target.value || undefined })} />
        <button onClick={fetchData} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors">Apply</button>
        <button onClick={() => setFilters({})} className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-200 transition-colors">Clear</button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600" />
        </div>
      ) : !stats || stats.total_students === 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center">
          <BarChart3 className="mx-auto text-slate-300 mb-4" size={48} />
          <h3 className="text-lg font-semibold text-slate-600">No Data Available</h3>
          <p className="text-slate-400 mt-2">Start scanning exam sheets to see dashboard statistics.</p>
        </div>
      ) : (
        <>
          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4 mb-8">
            {statCards.map((card) => (
              <div key={card.label} className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 hover:shadow-md transition-shadow">
                <div className={`w-10 h-10 ${card.bg} rounded-lg flex items-center justify-center mb-3`}>
                  <card.icon size={20} className={card.textColor} />
                </div>
                <p className="text-2xl font-bold text-slate-800">{card.value}</p>
                <p className="text-xs text-slate-500 mt-1">{card.label}</p>
              </div>
            ))}
          </div>

          {/* Charts Row 1: Pie + Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h3 className="text-sm font-semibold text-slate-700 mb-4">Pass vs Fail</h3>
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}>
                    <Cell fill="#10b981" /><Cell fill="#f43f5e" />
                  </Pie>
                  <Legend /><Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h3 className="text-sm font-semibold text-slate-700 mb-4">Section-wise Results</h3>
              {sectionData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={sectionData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} />
                    <Tooltip /><Legend />
                    <Bar dataKey="passed" fill="#10b981" name="Passed" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="failed" fill="#f43f5e" name="Failed" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <p className="text-slate-400 text-sm text-center py-16">No section data</p>}
            </div>
          </div>

          {/* Charts Row 2: Subject-wise + CO Radar */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* Subject-wise Performance */}
            {subjectData.length > 0 && (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <BookOpen size={16} className="text-indigo-500" />
                  <h3 className="text-sm font-semibold text-slate-700">Subject-wise Average Marks</h3>
                </div>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={subjectData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                    <YAxis dataKey="name" type="category" width={130} tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(val, name) => [val, name === 'avg' ? 'Avg Marks' : name]}
                      labelFormatter={(label) => subjectData.find(s => s.name === label)?.fullName || label} />
                    <Bar dataKey="avg" fill="#6366f1" name="Avg Marks" radius={[0, 4, 4, 0]} barSize={20} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* CO Radar Chart */}
            {coData.length > 0 && (
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Target size={16} className="text-purple-500" />
                  <h3 className="text-sm font-semibold text-slate-700">Course Outcome Performance (Avg)</h3>
                </div>
                <ResponsiveContainer width="100%" height={280}>
                  <RadarChart data={coData}>
                    <PolarGrid stroke="#e2e8f0" />
                    <PolarAngleAxis dataKey="co" tick={{ fontSize: 12, fill: '#6b7280' }} />
                    <PolarRadiusAxis angle={90} domain={[0, 'auto']} tick={{ fontSize: 10 }} />
                    <Radar dataKey="avg" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.3} name="Avg CO Marks" />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Subject Cards */}
          {subjectData.length > 0 && (
            <div className="mb-8">
              <h3 className="text-sm font-semibold text-slate-700 mb-4">Subject Breakdown</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {subjectData.map((s, i) => (
                  <div key={i} className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 hover:shadow-md transition-shadow">
                    <p className="text-sm font-semibold text-slate-800 truncate" title={s.fullName}>{s.fullName}</p>
                    <div className="mt-3 grid grid-cols-3 gap-3 text-center">
                      <div>
                        <p className="text-lg font-bold text-indigo-600">{s.total}</p>
                        <p className="text-[10px] text-slate-400">Students</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-emerald-600">{s.pass_pct}%</p>
                        <p className="text-[10px] text-slate-400">Pass Rate</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-blue-600">{s.avg}</p>
                        <p className="text-[10px] text-slate-400">Average</p>
                      </div>
                    </div>
                    <div className="mt-3 w-full bg-slate-100 rounded-full h-2">
                      <div className="bg-emerald-500 h-2 rounded-full transition-all" style={{ width: `${s.pass_pct}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Top Performers Table */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="p-6 border-b border-slate-200 flex items-center gap-2">
              <Award size={16} className="text-amber-500" />
              <h3 className="text-sm font-semibold text-slate-700">Top Performers</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    {['#', 'Reg No', 'Name', 'Section', 'Subject', 'Pattern', 'Part A', 'Part B&C', 'Total', 'Status'].map((h) => (
                      <th key={h} className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {topPerformers.map((r, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-4 py-3">
                        {i < 3 ? (
                          <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                            i === 0 ? 'bg-amber-400' : i === 1 ? 'bg-slate-400' : 'bg-amber-600'
                          }`}>{i + 1}</span>
                        ) : <span className="text-slate-400 text-xs">{i + 1}</span>}
                      </td>
                      <td className="px-4 py-3 font-medium text-indigo-600">{r.RegisterNumber}</td>
                      <td className="px-4 py-3 text-slate-700 font-medium">{r.StudentName}</td>
                      <td className="px-4 py-3 text-slate-600">{r.Section}</td>
                      <td className="px-4 py-3 text-slate-600">{r.SubjectName} <span className="text-slate-400">({r.SubjectCode})</span></td>
                      <td className="px-4 py-3"><span className="px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded text-xs font-medium">{r.ExamPattern}</span></td>
                      <td className="px-4 py-3 text-slate-700">{r.PartATotal}</td>
                      <td className="px-4 py-3 text-slate-700">{r.PartBCTotal}</td>
                      <td className="px-4 py-3 font-bold text-slate-800">{r.MarksObtained}<span className="text-slate-400 font-normal text-xs">/100</span></td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${
                          String(r.Status).toUpperCase() === 'PASS' ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'
                        }`}>
                          {String(r.Status).toUpperCase() === 'PASS' ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
                          {r.Status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {topPerformers.length === 0 && (
                    <tr><td colSpan={10} className="px-4 py-8 text-center text-slate-400">No results found</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
