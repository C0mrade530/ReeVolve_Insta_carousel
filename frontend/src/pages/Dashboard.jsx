import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Users,
  ImageIcon,
  Clock,
  CheckCircle,
  Zap,
  Sparkles,
  Calendar,
  TrendingUp,
  AlertCircle,
  Wifi,
  WifiOff,
  ChevronRight,
  BarChart3,
} from 'lucide-react'
import api from '../api/client'

/* ─── helpers ─── */
function relativeDay(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diff = Math.round((target - today) / 86400000)
  if (diff === 0) return 'Сегодня'
  if (diff === 1) return 'Завтра'
  if (diff === -1) return 'Вчера'
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function timeAgo(dateStr) {
  if (!dateStr) return 'никогда'
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins} мин назад`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}ч назад`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}д назад`
  return new Date(dateStr).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

/* ─── StatCard ─── */
function StatCard({ icon: Icon, label, value, sub, color, onClick }) {
  return (
    <div
      onClick={onClick}
      className={`bg-brand-card border border-brand-border rounded-xl p-5 transition-all ${
        onClick ? 'cursor-pointer hover:border-brand-orange/40 hover:shadow-lg hover:shadow-brand-orange/5' : ''
      }`}
    >
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={18} />
        </div>
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <div className="text-3xl font-bold text-white">{value}</div>
      {sub && <div className="text-xs text-gray-500 mt-1">{sub}</div>}
    </div>
  )
}

/* ─── QuickActions ─── */
function QuickActions() {
  const navigate = useNavigate()
  const actions = [
    {
      icon: Zap,
      label: 'Автонеделя',
      desc: 'Сгенерировать неделю контента',
      path: '/week-generator',
      color: 'text-yellow-400 bg-yellow-400/10',
    },
    {
      icon: Sparkles,
      label: 'Генератор',
      desc: 'Создать одну карусель',
      path: '/generator',
      color: 'text-purple-400 bg-purple-400/10',
    },
    {
      icon: Calendar,
      label: 'Календарь',
      desc: 'Посмотреть расписание',
      path: '/calendar',
      color: 'text-blue-400 bg-blue-400/10',
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {actions.map((a) => (
        <button
          key={a.path}
          onClick={() => navigate(a.path)}
          className="flex items-center gap-3 bg-brand-card border border-brand-border rounded-xl p-4
                     hover:border-brand-orange/40 transition-all text-left group"
        >
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${a.color}`}>
            <a.icon size={20} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-white group-hover:text-brand-orange transition-colors">
              {a.label}
            </div>
            <div className="text-xs text-gray-500">{a.desc}</div>
          </div>
          <ChevronRight size={16} className="text-gray-600 group-hover:text-brand-orange transition-colors" />
        </button>
      ))}
    </div>
  )
}

/* ─── UpcomingPosts ─── */
function UpcomingPosts({ items }) {
  const navigate = useNavigate()

  if (!items || items.length === 0) {
    return (
      <div className="bg-brand-card border border-brand-border rounded-xl p-5">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <Clock size={18} className="text-yellow-400" />
          Ближайшие публикации
        </h3>
        <div className="text-center py-6">
          <Clock size={32} className="text-gray-600 mx-auto mb-2" />
          <p className="text-gray-500 text-sm">Нет запланированных постов</p>
          <button
            onClick={() => navigate('/week-generator')}
            className="mt-3 text-sm text-brand-orange hover:underline"
          >
            Сгенерировать неделю →
          </button>
        </div>
      </div>
    )
  }

  // Group by day
  const grouped = {}
  items.forEach((item) => {
    const day = relativeDay(item.scheduled_time)
    if (!grouped[day]) grouped[day] = []
    grouped[day].push(item)
  })

  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-5">
      <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
        <Clock size={18} className="text-yellow-400" />
        Ближайшие публикации
      </h3>
      <div className="space-y-4">
        {Object.entries(grouped).map(([day, posts]) => (
          <div key={day}>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
              {day}
            </div>
            <div className="space-y-2">
              {posts.map((p) => (
                <div
                  key={p.id}
                  className="flex items-center justify-between py-2 px-3 rounded-lg
                             bg-white/[0.02] hover:bg-white/[0.05] transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-brand-orange font-mono w-12">
                      {formatTime(p.scheduled_time)}
                    </span>
                    <span className="text-sm text-gray-300">@{p.username || '?'}</span>
                  </div>
                  <span className="text-xs text-gray-600">
                    #{p.carousel_id?.slice(0, 6)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ─── RecentPublished ─── */
function RecentPublished({ items }) {
  if (!items || items.length === 0) {
    return (
      <div className="bg-brand-card border border-brand-border rounded-xl p-5">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <CheckCircle size={18} className="text-green-400" />
          Недавние публикации
        </h3>
        <div className="text-center py-6">
          <ImageIcon size={32} className="text-gray-600 mx-auto mb-2" />
          <p className="text-gray-500 text-sm">Пока нет публикаций</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-5">
      <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
        <CheckCircle size={18} className="text-green-400" />
        Недавние публикации
      </h3>
      <div className="space-y-3">
        {items.map((item) => (
          <div
            key={item.carousel_id}
            className="flex items-center gap-3 py-2 px-3 rounded-lg
                       bg-white/[0.02] hover:bg-white/[0.05] transition-colors"
          >
            {item.first_slide_image ? (
              <img
                src={item.first_slide_image}
                alt=""
                className="w-10 h-10 rounded-lg object-cover flex-shrink-0"
              />
            ) : (
              <div className="w-10 h-10 rounded-lg bg-brand-orange/10 flex items-center justify-center flex-shrink-0">
                <ImageIcon size={16} className="text-brand-orange" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="text-sm text-white truncate">
                {item.title || item.caption_preview || 'Карусель'}
              </div>
              <div className="text-xs text-gray-500">{timeAgo(item.published_at)}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ─── AccountStatus ─── */
function AccountStatus({ accounts }) {
  const navigate = useNavigate()

  if (!accounts || accounts.length === 0) {
    return (
      <div className="bg-brand-card border border-brand-border rounded-xl p-5">
        <h3 className="text-base font-semibold text-white mb-4 flex items-center gap-2">
          <Users size={18} className="text-blue-400" />
          Аккаунты
        </h3>
        <div className="text-center py-6">
          <Users size={32} className="text-gray-600 mx-auto mb-2" />
          <p className="text-gray-500 text-sm">Нет подключённых аккаунтов</p>
          <button
            onClick={() => navigate('/accounts')}
            className="mt-3 text-sm text-brand-orange hover:underline"
          >
            Подключить аккаунт →
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-white flex items-center gap-2">
          <Users size={18} className="text-blue-400" />
          Аккаунты
        </h3>
        <button
          onClick={() => navigate('/accounts')}
          className="text-xs text-gray-500 hover:text-brand-orange transition-colors"
        >
          Управление →
        </button>
      </div>
      <div className="space-y-2">
        {accounts.map((acc) => (
          <div
            key={acc.id}
            className="flex items-center justify-between py-2.5 px-3 rounded-lg
                       bg-white/[0.02]"
          >
            <div className="flex items-center gap-3">
              {acc.is_active ? (
                <Wifi size={14} className="text-green-400" />
              ) : (
                <WifiOff size={14} className="text-red-400" />
              )}
              <span className="text-sm text-white">@{acc.username}</span>
            </div>
            <div className="flex items-center gap-3">
              {acc.has_proxy && (
                <span className="text-[10px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">
                  proxy
                </span>
              )}
              <span className="text-xs text-gray-500">
                {acc.last_published_at ? timeAgo(acc.last_published_at) : 'нет постов'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ─── Main Dashboard ─── */
export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    api
      .get('/analytics/dashboard')
      .then((r) => setStats(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-brand-orange border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Дашборд</h2>
          <p className="text-sm text-gray-500 mt-1">
            Обзор вашего контента и аккаунтов
          </p>
        </div>
        <button
          onClick={() => navigate('/week-generator')}
          className="flex items-center gap-2 bg-brand-orange hover:bg-brand-orange/90
                     text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
        >
          <Zap size={16} />
          Сгенерировать неделю
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={Users}
          label="Аккаунтов"
          value={stats?.active_accounts ?? 0}
          sub={stats?.accounts_count > 0 ? `из ${stats.accounts_count} всего` : null}
          color="bg-blue-500/10 text-blue-400"
          onClick={() => navigate('/accounts')}
        />
        <StatCard
          icon={CheckCircle}
          label="Сегодня"
          value={stats?.published_today ?? 0}
          sub={stats?.published_week ? `${stats.published_week} за неделю` : null}
          color="bg-green-500/10 text-green-400"
        />
        <StatCard
          icon={Clock}
          label="В очереди"
          value={stats?.scheduled ?? 0}
          sub={stats?.ready ? `${stats.ready} готовых` : null}
          color="bg-yellow-500/10 text-yellow-400"
          onClick={() => navigate('/calendar')}
        />
        <StatCard
          icon={TrendingUp}
          label="Всего опубликовано"
          value={stats?.published_total ?? 0}
          sub={stats?.total_carousels ? `из ${stats.total_carousels} каруселей` : null}
          color="bg-brand-orange/10 text-brand-orange"
        />
      </div>

      {/* Quick Actions */}
      <QuickActions />

      {/* Two columns: upcoming + recent */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <UpcomingPosts items={stats?.upcoming} />
        <RecentPublished items={stats?.recent_published} />
      </div>

      {/* Accounts */}
      <AccountStatus accounts={stats?.accounts} />
    </div>
  )
}
