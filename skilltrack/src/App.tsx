import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { HOME, useAuth } from './context/AuthContext'
import type { Role } from './context/AuthContext'
import AdminDashboard from './pages/AdminDashboard'
import DomainsPage from './pages/DomainsPage'
import ExamDashboard from './pages/ExamDashboard'
import InvigilatorDashboard from './pages/InvigilatorDashboard'
import Login from './pages/Login'
import OwnerDashboard from './pages/OwnerDashboard'
import SyllabusPage from './pages/SyllabusPage'
import QuestionPaperPage from './pages/QuestionPaperPage'
import Register from './pages/Register'
import Verify from './pages/Verify'
import StudentDashboard from './pages/StudentDashboard'
import CredentialsPage from './pages/CredentialsPage'
import SkillAnalysisPage from './pages/SkillAnalysisPage'

function RequireRole({ roles }: { roles: Role[] }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="p-6 text-sm text-slate-500">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  if (!roles.includes(user.role)) return <Navigate to={HOME[user.role]} replace />
  return <Outlet />
}

function Home() {
  const { user, loading } = useAuth()
  if (loading) return null
  return <Navigate to={user ? HOME[user.role] : '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/verify/:code" element={<Verify />} />
      <Route element={<Layout />}>
        <Route element={<RequireRole roles={['student']} />}>
          <Route path="/student" element={<StudentDashboard />} />
        </Route>
        <Route element={<RequireRole roles={['student']} />}>
          <Route path="/student/domains" element={<DomainsPage />} />
        </Route>
        <Route element={<RequireRole roles={['student']} />}>
          <Route path="/student/credentials" element={<CredentialsPage />} />
        </Route>
        <Route element={<RequireRole roles={['student']} />}>
          <Route path="/student/skill-analysis" element={<SkillAnalysisPage />} />
        </Route>
        <Route element={<RequireRole roles={['student']} />}>
          <Route path="/exam" element={<ExamDashboard />} />
        </Route>
        <Route element={<RequireRole roles={['invigilator', 'admin']} />}>
          <Route path="/invigilator" element={<InvigilatorDashboard />} />
        </Route>
        <Route element={<RequireRole roles={['owner']} />}>
          <Route path="/owner" element={<OwnerDashboard />} />
          <Route path="/owner/syllabus" element={<SyllabusPage />} />
          <Route path="/owner/questions" element={<QuestionPaperPage />} />
        </Route>
        <Route element={<RequireRole roles={['admin']} />}>
          <Route path="/admin" element={<AdminDashboard />} />
        </Route>
      </Route>
      <Route path="*" element={<Home />} />
    </Routes>
  )
}
