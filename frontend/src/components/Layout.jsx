import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  ScanLine,
  FileText,
  FolderOpen,
  GraduationCap,
  FileSpreadsheet,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/scan', icon: ScanLine, label: 'Scan Exam' },
  { to: '/results', icon: FileText, label: 'Results' },
  { to: '/manage', icon: FileSpreadsheet, label: 'Manage Sheets' },
  { to: '/sessions', icon: FolderOpen, label: 'Sessions' },
]

export default function Layout() {
  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 bg-gradient-to-b from-indigo-900 to-indigo-800 text-white flex flex-col shadow-xl">
        <div className="p-6 border-b border-indigo-700">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-500 rounded-lg flex items-center justify-center">
              <GraduationCap size={24} />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">ExamScan AI</h1>
              <p className="text-xs text-indigo-300">Grading System</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-white/15 text-white shadow-md'
                    : 'text-indigo-200 hover:bg-white/10 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-indigo-700">
          <div className="text-xs text-indigo-300 text-center">
            Admin Panel v1.0
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
