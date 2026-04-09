import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { supabase } from './api/client'
import { onApiError } from './api/client'
import { AccountProvider } from './contexts/AccountContext'
import { ToastProvider, useToast } from './contexts/ToastContext'

import Layout from './components/Layout/Layout'
import Dashboard from './pages/Dashboard'
import Accounts from './pages/Accounts'
import ContentPlan from './pages/ContentPlan'
import Generator from './pages/Generator'
import WeekGenerator from './pages/WeekGenerator'
import Calendar from './pages/Calendar'
import Competitors from './pages/Competitors'
import Parser from './pages/Parser'
import Templates from './pages/Templates'
import Analytics from './pages/Analytics'
import CarouselEditor from './pages/CarouselEditor'
import BrandProfile from './pages/BrandProfile'
import Login from './pages/Login'

// ── Error Boundary ──
class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info)
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-brand-dark flex items-center justify-center p-8">
          <div className="bg-brand-card border border-red-500/30 rounded-2xl p-8 max-w-lg text-center">
            <div className="text-4xl mb-4">💥</div>
            <h2 className="text-xl font-bold text-white mb-2">Что-то пошло не так</h2>
            <p className="text-gray-400 text-sm mb-6">{this.state.error?.message || 'Неизвестная ошибка'}</p>
            <button
              onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload() }}
              className="px-6 py-2.5 bg-brand-orange text-white rounded-xl font-medium hover:bg-orange-600 transition-colors"
            >
              Перезагрузить
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

// ── API Error Listener (inside ToastProvider) ──
function ApiErrorListener() {
  const toast = useToast()
  useEffect(() => {
    const ERROR_MAP = {
      401: 'Сессия истекла. Войдите заново',
      403: 'Нет доступа',
      404: 'Не найдено',
      429: 'Слишком много запросов. Подождите минуту',
      500: 'Ошибка сервера',
      502: 'Сервер недоступен',
      503: 'Сервер перегружен',
    }
    return onApiError(({ message, status }) => {
      const mapped = ERROR_MAP[status]
      if (status === 401) return // handled by auth flow
      toast.error(mapped || message)
    })
  }, [toast])
  return null
}

export default function App() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => setSession(session)
    )

    return () => subscription.unsubscribe()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-brand-dark flex items-center justify-center">
        <div className="text-brand-orange text-xl">Загрузка...</div>
      </div>
    )
  }

  if (!session) {
    return (
      <ToastProvider>
        <Login />
      </ToastProvider>
    )
  }

  return (
    <ErrorBoundary>
      <ToastProvider>
        <ApiErrorListener />
        <AccountProvider>
          <BrowserRouter>
            <Layout user={session.user}>
              <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/accounts" element={<Accounts />} />
              <Route path="/content" element={<ContentPlan />} />
              <Route path="/generator" element={<Generator />} />
              <Route path="/week-generator" element={<WeekGenerator />} />
              <Route path="/calendar" element={<Calendar />} />
              <Route path="/competitors" element={<Competitors />} />
              <Route path="/parser" element={<Parser />} />
              <Route path="/templates" element={<Templates />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/brand" element={<BrandProfile />} />
              <Route path="/editor/:carouselId" element={<CarouselEditor />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </Layout>
          </BrowserRouter>
        </AccountProvider>
      </ToastProvider>
    </ErrorBoundary>
  )
}
