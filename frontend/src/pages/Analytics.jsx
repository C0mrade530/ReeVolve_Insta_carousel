import React, { useState, useEffect, useCallback } from 'react'
import {
  BarChart3,
  Heart,
  MessageCircle,
  Bookmark,
  Eye,
  TrendingUp,
  RefreshCw,
  ExternalLink,
  Trophy,
  Users,
  ArrowUpRight,
  ArrowDownRight,
  ImageIcon,
  Share2,
} from 'lucide-react'
import api from '../api/client'

/* ─── Helpers ─── */
function formatNum(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const hrs = Math.floor(diff / 3600000)
  if (hrs < 1) return 'только что'
  if (hrs < 24) return `${hrs}ч назад`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}д назад`
  return new Date(dateStr).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

/* ─── Summary Cards ─── */
function SummaryCards({ summary }) {
  if (!summary) return null

  const cards = [
    {
      icon: Heart,
      label: 'Лайков',
      value: formatNum(summary.total_likes),
      sub: `~${summary.avg_likes} / пост`,
      color: 'text-red-400 bg-red-400/10',
    },
    {
      icon: MessageCircle,
      label: 'Комментариев',
      value: formatNum(summary.total_comments),
      sub: `~${summary.avg_comments} / пост`,
      color: 'text-blue-400 bg-blue-400/10',
    },
    {
      icon: Bookmark,
      label: 'Сохранений',
      value: formatNum(summary.total_saves),
      sub: `${summary.total_posts} постов`,
      color: 'text-yellow-400 bg-yellow-400/10',
    },
    {
      icon: TrendingUp,
      label: 'Engagement Rate',
      value: `${summary.avg_engagement_rate}%`,
      sub: summary.total_reach > 0 ? `охват ${formatNum(summary.total_reach)}` : 'нет данных охвата',
      color: 'text-green-400 bg-green-400/10',
    },
  ]

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((c) => (
        <div key={c.label} className="bg-brand-card border border-brand-border rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${c.color}`}>
              <c.icon size={18} />
            </div>
            <span className="text-sm text-gray-400">{c.label}</span>
          </div>
          <div className="text-3xl font-bold text-white">{c.value}</div>
          <div className="text-xs text-gray-500 mt-1">{c.sub}</div>
        </div>
      ))}
    </div>
  )
}

/* ─── Best Post Badge ─── */
function BestPost({ post }) {
  if (!post) return null

  return (
    <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/20 rounded-xl p-4 flex items-center gap-4">
      <div className="w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center flex-shrink-0">
        <Trophy size={20} className="text-yellow-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text-yellow-400">Лучший пост</div>
        <div className="text-xs text-gray-400 mt-0.5">
          {post.likes} лайков · {post.comments} комментов
          {post.published_at && ` · ${timeAgo(post.published_at)}`}
        </div>
      </div>
    </div>
  )
}

/* ─── Sort Selector ─── */
function SortSelector({ value, onChange }) {
  const options = [
    { id: 'published_at', label: 'По дате' },
    { id: 'likes', label: 'По лайкам' },
    { id: 'comments', label: 'По комментам' },
    { id: 'engagement_rate', label: 'По ER' },
    { id: 'reach', label: 'По охвату' },
  ]

  return (
    <div className="flex items-center gap-1.5 bg-brand-card border border-brand-border rounded-lg p-1">
      {options.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
            value === o.id
              ? 'bg-brand-orange text-white'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/* ─── Post Row ─── */
function PostRow({ post }) {
  const instagramUrl = post.media_code
    ? `https://www.instagram.com/p/${post.media_code}/`
    : null

  return (
    <div className="flex items-center gap-4 py-3 px-4 rounded-xl bg-white/[0.02] hover:bg-white/[0.04] transition-colors">
      {/* Thumbnail */}
      {post.first_slide_image ? (
        <img
          src={post.first_slide_image}
          alt=""
          className="w-14 h-14 rounded-lg object-cover flex-shrink-0"
        />
      ) : (
        <div className="w-14 h-14 rounded-lg bg-brand-orange/10 flex items-center justify-center flex-shrink-0">
          <ImageIcon size={20} className="text-brand-orange" />
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="text-sm text-white truncate">
          {post.title || post.caption_preview || 'Карусель'}
        </div>
        <div className="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
          <span>@{post.account}</span>
          <span>·</span>
          <span>{timeAgo(post.published_at)}</span>
          {instagramUrl && (
            <a
              href={instagramUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand-orange hover:underline flex items-center gap-0.5"
            >
              <ExternalLink size={10} />
              <span>IG</span>
            </a>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-5 flex-shrink-0">
        <div className="text-center min-w-[50px]">
          <div className="flex items-center justify-center gap-1 text-red-400 text-sm font-medium">
            <Heart size={14} />
            {formatNum(post.likes)}
          </div>
          <div className="text-[10px] text-gray-600">лайков</div>
        </div>

        <div className="text-center min-w-[50px]">
          <div className="flex items-center justify-center gap-1 text-blue-400 text-sm font-medium">
            <MessageCircle size={14} />
            {formatNum(post.comments)}
          </div>
          <div className="text-[10px] text-gray-600">коммент.</div>
        </div>

        <div className="text-center min-w-[50px]">
          <div className="flex items-center justify-center gap-1 text-yellow-400 text-sm font-medium">
            <Bookmark size={14} />
            {formatNum(post.saves)}
          </div>
          <div className="text-[10px] text-gray-600">сохран.</div>
        </div>

        {post.reach > 0 && (
          <div className="text-center min-w-[50px]">
            <div className="flex items-center justify-center gap-1 text-purple-400 text-sm font-medium">
              <Eye size={14} />
              {formatNum(post.reach)}
            </div>
            <div className="text-[10px] text-gray-600">охват</div>
          </div>
        )}

        <div className="text-center min-w-[50px]">
          <div className={`text-sm font-bold ${
            post.engagement_rate >= 5
              ? 'text-green-400'
              : post.engagement_rate >= 2
              ? 'text-yellow-400'
              : 'text-gray-400'
          }`}>
            {post.engagement_rate > 0 ? `${post.engagement_rate}%` : '—'}
          </div>
          <div className="text-[10px] text-gray-600">ER</div>
        </div>
      </div>
    </div>
  )
}

/* ─── Empty State ─── */
function EmptyState({ onRefresh, refreshing }) {
  return (
    <div className="text-center py-16">
      <BarChart3 size={56} className="mx-auto mb-4 text-gray-600" />
      <h3 className="text-lg font-medium text-white mb-2">Нет данных статистики</h3>
      <p className="text-sm text-gray-500 mb-6 max-w-md mx-auto">
        Статистика появится после публикации каруселей в Instagram.
        Нажмите «Обновить», чтобы загрузить метрики опубликованных постов.
      </p>
      <button
        onClick={onRefresh}
        disabled={refreshing}
        className="inline-flex items-center gap-2 bg-brand-orange hover:bg-brand-orange/90
                   text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors
                   disabled:opacity-50"
      >
        <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
        {refreshing ? 'Загрузка...' : 'Обновить статистику'}
      </button>
    </div>
  )
}

/* ─── Main Analytics Page ─── */
export default function Analytics() {
  const [posts, setPosts] = useState([])
  const [summary, setSummary] = useState(null)
  const [sortBy, setSortBy] = useState('published_at')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshResult, setRefreshResult] = useState(null)

  const fetchStats = useCallback(
    (sort) => {
      setLoading(true)
      api
        .get('/analytics/stats', { params: { sort: sort || sortBy, limit: 30 } })
        .then((r) => {
          setPosts(r.data.posts || [])
          setSummary(r.data.summary || null)
        })
        .catch(() => {})
        .finally(() => setLoading(false))
    },
    [sortBy]
  )

  useEffect(() => {
    fetchStats(sortBy)
  }, [sortBy])

  const handleRefresh = async () => {
    setRefreshing(true)
    setRefreshResult(null)
    try {
      const r = await api.post('/analytics/stats/refresh')
      setRefreshResult(r.data)
      // Reload stats after refresh
      fetchStats(sortBy)
    } catch (e) {
      setRefreshResult({ message: 'Ошибка обновления', error: true })
    } finally {
      setRefreshing(false)
    }
  }

  const handleSortChange = (newSort) => {
    setSortBy(newSort)
  }

  if (loading && posts.length === 0) {
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
          <h2 className="text-2xl font-bold text-white">Статистика постов</h2>
          <p className="text-sm text-gray-500 mt-1">
            Лайки, комментарии, охваты, engagement rate
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 bg-brand-card border border-brand-border
                     hover:border-brand-orange/40 text-white px-4 py-2.5 rounded-lg
                     text-sm font-medium transition-all disabled:opacity-50"
        >
          <RefreshCw size={16} className={refreshing ? 'animate-spin' : ''} />
          {refreshing ? 'Обновление...' : 'Обновить из IG'}
        </button>
      </div>

      {/* Refresh result toast */}
      {refreshResult && (
        <div
          className={`border rounded-lg px-4 py-3 text-sm flex items-center justify-between ${
            refreshResult.error
              ? 'bg-red-500/10 border-red-500/30 text-red-400'
              : 'bg-green-500/10 border-green-500/30 text-green-400'
          }`}
        >
          <span>{refreshResult.message}</span>
          {refreshResult.fetched !== undefined && (
            <span className="text-xs text-gray-500">
              Загружено: {refreshResult.fetched} · Ошибок: {refreshResult.failed}
            </span>
          )}
          <button
            onClick={() => setRefreshResult(null)}
            className="text-gray-500 hover:text-white ml-3"
          >
            ✕
          </button>
        </div>
      )}

      {posts.length === 0 ? (
        <EmptyState onRefresh={handleRefresh} refreshing={refreshing} />
      ) : (
        <>
          {/* Summary Cards */}
          <SummaryCards summary={summary} />

          {/* Best Post */}
          <BestPost post={summary?.best_post} />

          {/* Sort + Post List */}
          <div className="bg-brand-card border border-brand-border rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <BarChart3 size={18} className="text-brand-orange" />
                Все посты ({posts.length})
              </h3>
              <SortSelector value={sortBy} onChange={handleSortChange} />
            </div>

            <div className="space-y-2">
              {posts.map((post) => (
                <PostRow key={post.id} post={post} />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
