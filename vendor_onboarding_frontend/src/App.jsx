import { Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Form from './pages/Form'
import Status from './pages/Status'

function PrivateRoute({ children }) {
  return localStorage.getItem('token') ? children : <Navigate to="/" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/form" element={<PrivateRoute><Form /></PrivateRoute>} />
      <Route path="/status" element={<PrivateRoute><Status /></PrivateRoute>} />
    </Routes>
  )
}
