import React, { useState, useEffect } from 'react'
import {
  Plus, Settings, Trash2, CheckCircle, XCircle, Users,
  Loader2, AlertTriangle, Shield, Wifi, X, RefreshCw,
  Clock, ThumbsUp,
} from 'lucide-react'
import api from '../api/client'
import { useAccount } from '../contexts/AccountContext'

function AccountCard({ account, onDelete, onVerify, onConfirmChallenge, verifying, confirming }) {
  const needsConfirm = !account.is_active

  return (
    <div className={`bg-brand-card border rounded-xl p-5 ${
      needsConfirm ? 'border-yellow-500/40' : 'border-brand-border'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-white">@{account.username}</span>
          {account.is_active ? (
            <CheckCircle size={16} className="text-green-400" />
          ) : (
            <Clock size={16} className="text-yellow-400" />
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => onVerify(account.id)}
            disabled={verifying}
            className="text-gray-400 hover:text-brand-orange transition-colors"
            title="Проверить сессию"
          >
            {verifying ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          </button>
          <button
            onClick={() => onDelete(account.id)}
            className="text-gray-400 hover:text-red-400 transition-colors"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {/* Challenge confirmation banner */}
      {needsConfirm && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg px-3 py-2.5 mb-3">
          <p className="text-yellow-400 text-xs mb-2">
            Откройте Instagram, нажмите «Это я», потом нажмите кнопку ниже:
          </p>
          <button
            onClick={() => onConfirmChallenge(account.id)}
            disabled={confirming}
            className="w-full bg-yellow-500/20 hover:bg-yellow-500/30 text-yellow-300
                       py-2 rounded-lg text-sm font-semibold transition-colors
                       flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {confirming ? (
              <>
                <Loader2 size={14} className="animate-spin" />
                Активация...
              </>
            ) : (
              <>
                <ThumbsUp size={14} />
                Я подтвердил в Instagram
              </>
            )}
          </button>
        </div>
      )}

      {/* Session expiry warning */}
      {account.session_expires_at && (() => {
        const expiresAt = new Date(account.session_expires_at)
        const now = new Date()
        const daysLeft = Math.ceil((expiresAt - now) / (1000 * 60 * 60 * 24))
        if (daysLeft < 0) {
          return (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 mb-3">
              <p className="text-red-400 text-xs flex items-center gap-1.5">
                <AlertTriangle size={12} />
                Сессия истекла. Перелогиньтесь.
              </p>
            </div>
          )
        }
        if (daysLeft <= 3) {
          return (
            <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg px-3 py-2 mb-3">
              <p className="text-orange-400 text-xs flex items-center gap-1.5">
                <AlertTriangle size={12} />
                Сессия истекает через {daysLeft} дн. Рекомендуем перелогиниться.
              </p>
            </div>
          )
        }
        return null
      })()}

      <div className="space-y-1.5 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-400">Публикаций/день</span>
          <span className="text-gray-200">{account.daily_post_limit}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Расписание</span>
          <span className="text-gray-200">{account.posting_schedule?.join(', ')}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Ниша</span>
          <span className="text-gray-200">{account.niche}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-400">Город</span>
          <span className="text-gray-200">{account.city}</span>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-brand-border flex gap-2">
        <span className="text-xs px-2 py-1 rounded bg-brand-orange/10 text-brand-orange">
          {account.cta_keyword}
        </span>
        {account.last_published_at && (
          <span className="text-xs text-gray-500 flex items-center gap-1 ml-auto">
            Посл. пост: {new Date(account.last_published_at).toLocaleDateString('ru-RU')}
          </span>
        )}
      </div>
    </div>
  )
}

function AddAccountModal({ isOpen, onClose, onSuccess }) {
  const [form, setForm] = useState({
    username: '',
    password: '',
    proxy: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Reset on open
  useEffect(() => {
    if (isOpen) {
      setError(null)
      setLoading(false)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (loading) return // prevent double-submit

    setLoading(true)
    setError(null)

    try {
      const res = await api.post('/accounts', form)
      // Check if challenge was returned (account saved but needs confirm)
      if (res.data?.login_status === 'challenge_required') {
        onSuccess() // refresh account list to show the confirm button
        onClose()
        return
      }
      onSuccess()
      onClose()
    } catch (err) {
      const status = err.response?.status
      let detail = err.response?.data?.detail || ''
      // Pydantic 422 returns array of validation errors — extract message
      if (Array.isArray(detail)) {
        detail = detail.map(e => e.msg || JSON.stringify(e)).join('; ')
      } else if (typeof detail === 'object') {
        detail = detail.msg || JSON.stringify(detail)
      }

      if (status === 429) {
        // IP blocked or rate limited
        setError({
          type: 'ip_blocked',
          message: detail || 'IP заблокирован Instagram. Добавьте прокси или подождите.',
        })
      } else if (status === 403) {
        setError({
          type: 'challenge',
          message: detail || 'Instagram требует подтверждение. Откройте приложение Instagram.',
        })
      } else if (status === 401) {
        setError({
          type: 'password',
          message: detail || 'Неверный пароль.',
        })
      } else {
        setError({
          type: 'error',
          message: detail || 'Не удалось подключить аккаунт',
        })
      }
    } finally {
      setLoading(false)
    }
  }

  const errorColors = {
    ip_blocked: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
    challenge: 'bg-blue-500/10 border-blue-500/30 text-blue-400',
    password: 'bg-red-500/10 border-red-500/30 text-red-400',
    error: 'bg-red-500/10 border-red-500/30 text-red-400',
  }

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-brand-card border border-brand-border rounded-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">Добавить аккаунт</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className={`border rounded-lg px-4 py-3 mb-4 text-sm ${errorColors[error.type]}`}>
            <div className="flex items-start gap-2">
              <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
              <div>
                <p>{error.message}</p>
                {error.type === 'ip_blocked' && (
                  <p className="text-xs opacity-70 mt-1">
                    Укажите прокси в поле ниже (формат: http://user:pass@ip:port).
                    Мобильные прокси работают лучше всего.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <input
              type="text"
              placeholder="Instagram username"
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className="w-full bg-brand-dark border border-brand-border rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-brand-orange"
              required
              disabled={loading}
            />
          </div>
          <div>
            <input
              type="password"
              placeholder="Instagram password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="w-full bg-brand-dark border border-brand-border rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-brand-orange"
              required
              disabled={loading}
            />
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Shield size={12} className="text-brand-orange" />
              <label className="text-[10px] text-gray-500 uppercase tracking-wider">
                Прокси (SOCKS5 адрес)
              </label>
            </div>
            <input
              type="text"
              placeholder="user:pass@host:port"
              value={form.proxy}
              onChange={(e) => setForm({ ...form, proxy: e.target.value })}
              className={`w-full bg-brand-dark border rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-brand-orange ${
                error?.type === 'ip_blocked'
                  ? 'border-yellow-500/50 bg-yellow-500/5'
                  : 'border-brand-border'
              }`}
              disabled={loading}
            />
            <p className="text-[10px] text-gray-600 mt-1">
              Мобильный прокси защищает от блокировки IP
            </p>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="flex-1 border border-brand-border text-gray-300 py-2.5 rounded-lg hover:bg-white/5 transition-colors text-sm disabled:opacity-50"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-brand-orange hover:bg-orange-600 text-white py-2.5 rounded-lg transition-colors text-sm font-semibold disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  Подключение...
                </>
              ) : (
                'Подключить'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Accounts() {
  const [accounts, setAccounts] = useState([])
  const [showAdd, setShowAdd] = useState(false)
  const [verifyingId, setVerifyingId] = useState(null)
  const [confirmingId, setConfirmingId] = useState(null)
  const { refreshAccounts } = useAccount()

  const fetchAccounts = () => {
    api.get('/accounts').then((r) => setAccounts(r.data)).catch(() => {})
    refreshAccounts() // Also refresh global context (Header selector)
  }

  useEffect(() => { fetchAccounts() }, [])

  const handleDelete = async (id) => {
    if (!confirm('Удалить аккаунт?')) return
    await api.delete(`/accounts/${id}`)
    fetchAccounts()
  }

  const handleVerify = async (id) => {
    setVerifyingId(id)
    try {
      const res = await api.post(`/accounts/${id}/verify`)
      const msg = res.data.status === 'active'
        ? 'Сессия активна!'
        : 'Сессия истекла. Нужна переавторизация.'
      alert(msg)
      fetchAccounts()
    } catch {
      alert('Ошибка проверки')
    } finally {
      setVerifyingId(null)
    }
  }

  const handleConfirmChallenge = async (id) => {
    setConfirmingId(id)
    try {
      const res = await api.post(`/accounts/${id}/confirm-challenge`)
      alert(res.data.message || 'Аккаунт активирован!')
      fetchAccounts()
    } catch {
      alert('Ошибка активации. Попробуйте ещё раз.')
    } finally {
      setConfirmingId(null)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-white">Аккаунты</h2>
        <button
          onClick={() => setShowAdd(true)}
          className="flex items-center gap-2 bg-brand-orange hover:bg-orange-600 text-white px-4 py-2 rounded-lg transition-colors text-sm font-semibold"
        >
          <Plus size={16} />
          Добавить
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="text-center py-16 text-gray-500">
          <Users size={48} className="mx-auto mb-4 opacity-30" />
          <p>Нет добавленных аккаунтов</p>
          <p className="text-sm mt-1">Добавьте Instagram-аккаунт для начала работы</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {accounts.map((acc) => (
            <AccountCard
              key={acc.id}
              account={acc}
              onDelete={handleDelete}
              onVerify={handleVerify}
              onConfirmChallenge={handleConfirmChallenge}
              verifying={verifyingId === acc.id}
              confirming={confirmingId === acc.id}
            />
          ))}
        </div>
      )}

      <AddAccountModal
        isOpen={showAdd}
        onClose={() => setShowAdd(false)}
        onSuccess={fetchAccounts}
      />
    </div>
  )
}
