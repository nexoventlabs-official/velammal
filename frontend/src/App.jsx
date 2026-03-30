import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import ScanExam from './pages/ScanExam'
import Results from './pages/Results'
import Sessions from './pages/Sessions'
import ManageSheets from './pages/ManageStudents'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="scan" element={<ScanExam />} />
        <Route path="results" element={<Results />} />
        <Route path="manage" element={<ManageSheets />} />
        <Route path="sessions" element={<Sessions />} />
      </Route>
    </Routes>
  )
}
