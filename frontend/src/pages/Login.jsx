import React, { useState } from 'react'
import { supabase } from '../api/client'

export default function Login() {
  const [mode, setMode] = useState('login') // 'login' | 'signup' | 'reset'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  const switchMode = (newMode) => {
    setMode(newMode)
    setError('')
    setSuccess('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)

    try {
      if (mode === 'reset') {
        const { error } = await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset-password`,
        })
        if (error) throw error
        setSuccess('Ссылка для сброса пароля отправлена на вашу почту')
      } else if (mode === 'signup') {
        const { error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { name } },
        })
        if (error) throw error
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        })
        if (error) throw error
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const title = mode === 'signup' ? 'Регистрация' : mode === 'reset' ? 'Сброс пароля' : 'Вход'
  const buttonText = mode === 'signup' ? 'Зарегистрироваться' : mode === 'reset' ? 'Отправить ссылку' : 'Войти'

  return (
    <div className="min-h-screen bg-brand-dark flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-white">
            Real<span className="text-brand-orange">Post</span> Pro
          </h1>
          <p className="text-gray-400 mt-2">
            AI-генерация и автопубликация каруселей для экспертов
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-brand-card border border-brand-border rounded-xl p-6 space-y-4"
        >
          <h2 className="text-xl font-semibold text-white">{title}</h2>

          {error && (
            <div className="bg-red-900/30 border border-red-500/50 rounded-lg p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          {success && (
            <div className="bg-green-900/30 border border-green-500/50 rounded-lg p-3 text-green-400 text-sm">
              {success}
            </div>
          )}

          {mode === 'signup' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Имя</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-brand-dark border border-brand-border rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-brand-orange"
                placeholder="Ваше имя"
              />
            </div>
          )}

          <div>
            <label className="block text-sm text-gray-400 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-brand-dark border border-brand-border rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-brand-orange"
              placeholder="email@example.com"
              required
            />
          </div>

          {mode !== 'reset' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Пароль</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-brand-dark border border-brand-border rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-brand-orange"
                placeholder="••••••••"
                required
                minLength={6}
              />
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-brand-orange hover:bg-orange-600 text-white font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-50"
          >
            {loading ? 'Загрузка...' : buttonText}
          </button>

          {mode === 'login' && (
            <button
              type="button"
              onClick={() => switchMode('reset')}
              className="w-full text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              Забыли пароль?
            </button>
          )}

          <p className="text-center text-sm text-gray-400">
            {mode === 'signup' ? (
              <>Уже есть аккаунт?{' '}
                <button type="button" onClick={() => switchMode('login')} className="text-brand-orange hover:underline">
                  Войти
                </button>
              </>
            ) : mode === 'reset' ? (
              <>Вспомнили пароль?{' '}
                <button type="button" onClick={() => switchMode('login')} className="text-brand-orange hover:underline">
                  Войти
                </button>
              </>
            ) : (
              <>Нет аккаунта?{' '}
                <button type="button" onClick={() => switchMode('signup')} className="text-brand-orange hover:underline">
                  Зарегистрироваться
                </button>
              </>
            )}
          </p>
        </form>
      </div>
    </div>
  )
}
