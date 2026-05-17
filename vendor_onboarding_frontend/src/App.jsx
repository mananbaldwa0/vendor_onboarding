import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Form from './pages/Form'
import Status from './pages/Status'
import AdminLogin from './pages/admin/AdminLogin'
import Dashboard from './pages/admin/Dashboard'

function PrivateRoute({ children }) {
  return localStorage.getItem('token') ? children : <Navigate to="/" replace />
}

function AdminRoute({ children }) {
  return localStorage.getItem('adminToken') ? children : <Navigate to="/admin" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/form" element={<PrivateRoute><Form /></PrivateRoute>} />
      <Route path="/status" element={<PrivateRoute><Status /></PrivateRoute>} />
      <Route path="/admin" element={<AdminLogin />} />
      <Route path="/admin/dashboard" element={<AdminRoute><Dashboard /></AdminRoute>} />
    </Routes>
  )
}
