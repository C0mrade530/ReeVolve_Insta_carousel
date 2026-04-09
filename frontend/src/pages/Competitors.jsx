import React, { useState, useEffect } from 'react'
import {
  Flame, Search, Zap, Sparkles, Copy, Check, ChevronRight,
  Loader2, TrendingUp, Target, MessageSquare, Eye, RefreshCw,
  ChevronLeft, Download, Plus, X, Instagram, Heart, MessageCircle,
  Users, ExternalLink, Trash2, Send, Clock, Play, Video
} from 'lucide-react'
import api from '../api/client'
import { useAccount } from '../contexts/AccountContext'

// ═══════════════════════════════════════════════════════════════════
// ENGAGEMENT BADGE
// ═══════════════════════════════════════════════════════════════════
function EngagementBadge({ level }) {
  const config = {
    high: { color: 'text-green-400 bg-green-500/10 border-green-500/20', label: 'Высокий' },
    medium: { color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20', label: 'Средний' },
    low: { color: 'text-gray-400 bg-gray-500/10 border-gray-500/20', label: 'Низкий' },
  }
  const c = config[level] || config.medium
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] border ${c.color}`}>
      <TrendingUp size={10} />
      {c.label}
    </span>
  )
}

// ═══════════════════════════════════════════════════════════════════
// SCRAPED POST CARD
// ═══════════════════════════════════════════════════════════════════
function PostCard({ post, index }) {
  const [expanded, setExpanded] = useState(false)
  const caption = post.caption || ''
  const isLong = caption.length > 150

  return (
    <div className="bg-brand-dark rounded-lg p-3 border border-brand-border/30">
      <div className="flex items-start gap-3">
        <div className="text-xs text-gray-500 w-5 text-right flex-shrink-0 pt-0.5">
          #{index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1.5">
            <span className="flex items-center gap-1 text-xs text-pink-400">
              <Heart size={10} /> {post.likes?.toLocaleString()}
            </span>
            <span className="flex items-center gap-1 text-xs text-blue-400">
              <MessageCircle size={10} /> {post.comments?.toLocaleString()}
            </span>
            {post.is_carousel && (
              <span className="text-[10px] text-purple-400 bg-purple-500/10 px-1.5 py-0.5 rounded">
                Карусель ({post.carousel_count} фото)
              </span>
            )}
            {post.url && (
              <a
                href={post.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-gray-500 hover:text-brand-orange ml-auto flex items-center gap-0.5"
              >
                <ExternalLink size={9} /> Открыть
              </a>
            )}
          </div>
          <p className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">
            {expanded || !isLong ? caption : caption.slice(0, 150) + '...'}
          </p>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-[10px] text-brand-orange mt-1"
            >
              {expanded ? 'Свернуть' : 'Показать всё'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// VIRAL TOPIC CARD
// ═══════════════════════════════════════════════════════════════════
function ViralTopicCard({ topic, index, onRewrite, rewriting }) {
  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-4 hover:border-brand-orange/30 transition-colors">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-brand-orange/10 text-brand-orange flex items-center justify-center flex-shrink-0 font-bold text-sm">
          {index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <h4 className="text-white font-medium text-sm truncate">
              {topic.hook_idea || topic.original_theme}
            </h4>
            <EngagementBadge level={topic.estimated_engagement} />
          </div>

          <p className="text-xs text-gray-400 mb-2 leading-relaxed">
            {topic.original_theme}
          </p>

          <div className="flex items-start gap-4 mb-3">
            <div className="flex-1">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Почему вирусно</div>
              <p className="text-xs text-gray-300">{topic.why_viral}</p>
            </div>
            <div className="flex-1">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Направление рерайта</div>
              <p className="text-xs text-gray-300">{topic.rewrite_angle}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] text-gray-500 px-2 py-0.5 rounded bg-brand-dark border border-brand-border/30">
              {topic.format || 'carousel'}
            </span>
            <button
              onClick={() => onRewrite(topic)}
              disabled={rewriting}
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-brand-orange hover:bg-orange-600 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
            >
              {rewriting ? (
                <>
                  <Loader2 size={12} className="animate-spin" />
                  Генерация...
                </>
              ) : (
                <>
                  <Zap size={12} />
                  Создать карусель
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// SLIDE PREVIEW
// ═══════════════════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════════════════
// COMPETITOR PUBLISH BAR — publish/schedule generated carousel
// ═══════════════════════════════════════════════════════════════════
function CompetitorPublishBar({ carouselId, accountId, accountUsername }) {
  const [publishing, setPublishing] = useState(false)
  const [result, setResult] = useState(null)

  const handlePublish = async () => {
    setPublishing(true)
    setResult(null)
    try {
      const res = await api.post(`/carousels/${carouselId}/publish-now`, {
        account_id: accountId,
      })
      setResult({ success: true, ...res.data })
    } catch (err) {
      setResult({ error: err.response?.data?.detail || 'Ошибка публикации' })
    } finally {
      setPublishing(false)
    }
  }

  return (
    <div className="mt-3">
      {result?.success ? (
        <div className="p-3 rounded-lg bg-green-900/20 border border-green-500/30">
          <p className="text-green-400 text-sm flex items-center gap-2">
            <Check size={14} />
            {result.message}
          </p>
          {result.url && (
            <a href={result.url} target="_blank" rel="noopener noreferrer"
              className="text-brand-orange text-xs hover:underline flex items-center gap-1 mt-1">
              <ExternalLink size={12} /> Открыть в Instagram
            </a>
          )}
        </div>
      ) : result?.error ? (
        <div className="p-3 rounded-lg bg-red-900/20 border border-red-500/30 mb-2">
          <p className="text-red-400 text-xs">{result.error}</p>
        </div>
      ) : null}
      {!result?.success && (
        <div className="flex gap-2">
          <button
            onClick={handlePublish}
            disabled={publishing}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-xs transition-colors disabled:opacity-40"
          >
            {publishing ? (
              <><Loader2 size={12} className="animate-spin" /> Публикация...</>
            ) : (
              <><Send size={12} /> Опубликовать в @{accountUsername}</>
            )}
          </button>
        </div>
      )}
    </div>
  )
}

function MiniSlidePreview({ slides, caption }) {
  const [current, setCurrent] = useState(0)
  const [copied, setCopied] = useState(false)

  if (!slides || slides.length === 0) return null
  const slide = slides[current]

  const handleCopy = () => {
    if (caption) {
      navigator.clipboard.writeText(caption)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="mt-4 bg-brand-darker rounded-xl p-4 border border-brand-border/50">
      <div className="flex gap-4">
        <div className="flex-shrink-0 relative group">
          <img
            src={slide.image_path}
            alt={`Слайд ${current + 1}`}
            className="w-[270px] h-[337px] object-cover rounded-lg border border-brand-border shadow-xl"
          />
          <div className="absolute inset-0 flex items-center justify-between px-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => setCurrent(Math.max(0, current - 1))}
              disabled={current === 0}
              className="bg-black/60 text-white rounded-full p-1.5 disabled:opacity-0"
            >
              <ChevronLeft size={16} />
            </button>
            <button
              onClick={() => setCurrent(Math.min(slides.length - 1, current + 1))}
              disabled={current === slides.length - 1}
              className="bg-black/60 text-white rounded-full p-1.5 disabled:opacity-0"
            >
              <ChevronRight size={16} />
            </button>
          </div>
          <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/70 text-white text-[10px] px-2 py-0.5 rounded-full">
            {current + 1} / {slides.length}
          </div>
        </div>

        <div className="flex-1 min-w-0 flex flex-col">
          <div className="text-xs text-gray-500 mb-1">Слайд {current + 1}</div>
          <div className="text-white font-medium text-sm mb-1">{slide.text_overlay}</div>
          {slide.body && (
            <div className="text-xs text-gray-400 mb-3 leading-relaxed">{slide.body}</div>
          )}
          {caption && (
            <div className="mt-auto">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-gray-500">Подпись к посту</span>
                <button onClick={handleCopy} className="text-[10px] text-brand-orange flex items-center gap-1">
                  {copied ? <Check size={10} /> : <Copy size={10} />}
                  {copied ? 'Скопировано' : 'Копировать'}
                </button>
              </div>
              <div className="bg-brand-dark rounded-lg p-2.5 text-xs text-gray-300 max-h-28 overflow-y-auto whitespace-pre-wrap border border-brand-border/30">
                {caption}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex gap-1.5 mt-3 overflow-x-auto pb-1">
        {slides.map((s, i) => (
          <button
            key={i}
            onClick={() => setCurrent(i)}
            className={`flex-shrink-0 rounded overflow-hidden border-2 transition-all ${
              i === current ? 'border-brand-orange scale-105' : 'border-transparent opacity-40 hover:opacity-70'
            }`}
          >
            <img src={s.image_path} alt="" className="w-12 h-15 object-cover" />
          </button>
        ))}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// REEL CARD — shows a scraped viral reel
// ═══════════════════════════════════════════════════════════════════
function ReelCard({ reel, index }) {
  const [expanded, setExpanded] = useState(false)
  const caption = reel.caption || ''
  const isLong = caption.length > 120

  return (
    <div className="bg-brand-dark rounded-lg p-3 border border-brand-border/30">
      <div className="flex items-start gap-3">
        <div className="text-xs text-gray-500 w-5 text-right flex-shrink-0 pt-0.5">
          #{index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1.5">
            <span className="flex items-center gap-1 text-xs text-purple-400">
              <Play size={10} /> {(reel.views || 0).toLocaleString()} просм.
            </span>
            <span className="flex items-center gap-1 text-xs text-pink-400">
              <Heart size={10} /> {(reel.likes || 0).toLocaleString()}
            </span>
            <span className="flex items-center gap-1 text-xs text-blue-400">
              <MessageCircle size={10} /> {(reel.comments || 0).toLocaleString()}
            </span>
            {reel.duration_sec > 0 && (
              <span className="text-[10px] text-gray-500">{reel.duration_sec}сек</span>
            )}
            {reel.url && (
              <a
                href={reel.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] text-gray-500 hover:text-brand-orange ml-auto flex items-center gap-0.5"
              >
                <ExternalLink size={9} /> Открыть
              </a>
            )}
          </div>
          <p className="text-xs text-gray-300 leading-relaxed whitespace-pre-wrap">
            {expanded || !isLong ? caption : caption.slice(0, 120) + '...'}
          </p>
          {isLong && (
            <button onClick={() => setExpanded(!expanded)} className="text-[10px] text-brand-orange mt-1">
              {expanded ? 'Свернуть' : 'Показать всё'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// REEL IDEA CARD — carousel idea generated from viral reel
// ═══════════════════════════════════════════════════════════════════
function ReelIdeaCard({ idea, index, onGenerate, generating }) {
  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-4 hover:border-purple-500/30 transition-colors">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center flex-shrink-0 font-bold text-sm">
          {index + 1}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <h4 className="text-white font-medium text-sm truncate">
              {idea.hook_for_first_slide || idea.original_reel_theme}
            </h4>
            <EngagementBadge level={idea.estimated_engagement} />
          </div>

          <p className="text-xs text-gray-400 mb-2">
            <Video size={10} className="inline mr-1 text-purple-400" />
            Из Reels: {idea.original_reel_theme}
          </p>

          <div className="flex items-start gap-4 mb-3">
            <div className="flex-1">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Почему залетело</div>
              <p className="text-xs text-gray-300">{idea.why_viral}</p>
            </div>
            <div className="flex-1">
              <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5">Адаптация в карусель</div>
              <p className="text-xs text-gray-300">{idea.carousel_adaptation}</p>
            </div>
          </div>

          {idea.content_angle && (
            <p className="text-xs text-brand-orange/70 mb-3">Угол: {idea.content_angle}</p>
          )}

          <button
            onClick={() => onGenerate(idea)}
            disabled={generating}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-700 hover:to-pink-600 text-white text-xs font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            {generating ? (
              <><Loader2 size={12} className="animate-spin" /> Генерация...</>
            ) : (
              <><Zap size={12} /> Создать карусель из Reels</>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// COMPETITOR INFO CARD
// ═══════════════════════════════════════════════════════════════════
function CompetitorInfoCard({ info }) {
  if (!info) return null
  return (
    <div className="bg-brand-dark rounded-lg p-3 border border-brand-border/30 mb-3 flex items-center gap-3">
      {info.profile_pic_url && (
        <img src={info.profile_pic_url} alt="" className="w-10 h-10 rounded-full border border-brand-border" />
      )}
      <div className="flex-1 min-w-0">
        <div className="text-sm text-white font-medium">@{info.username}</div>
        {info.full_name && <div className="text-[10px] text-gray-400">{info.full_name}</div>}
      </div>
      <div className="flex gap-4 text-center">
        <div>
          <div className="text-sm text-white font-medium">{(info.followers || 0).toLocaleString()}</div>
          <div className="text-[9px] text-gray-500">подписчиков</div>
        </div>
        <div>
          <div className="text-sm text-white font-medium">{(info.media_count || 0).toLocaleString()}</div>
          <div className="text-[9px] text-gray-500">постов</div>
        </div>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════
// MAIN COMPETITORS PAGE
// ═══════════════════════════════════════════════════════════════════
export default function Competitors() {
  const { selectedAccount } = useAccount()
  const [tab, setTab] = useState('scrape')  // scrape | reels | paste | ideas
  const [competitors, setCompetitors] = useState([])
  const [newCompetitor, setNewCompetitor] = useState('')
  const [addingCompetitor, setAddingCompetitor] = useState(false)

  // Scrape state
  const [selectedCompetitor, setSelectedCompetitor] = useState('')
  const [scraping, setScraping] = useState(false)
  const [scrapeResult, setScrapeResult] = useState(null)

  // Paste state
  const [postsText, setPostsText] = useState('')
  const [competitorUsername, setCompetitorUsername] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysis, setAnalysis] = useState(null)

  // Reels state
  const [scrapingReels, setScrapingReels] = useState(false)
  const [reelsResult, setReelsResult] = useState(null)
  const [generatingFromReel, setGeneratingFromReel] = useState(null)

  // Ideas state
  const [generatingIdeas, setGeneratingIdeas] = useState(false)
  const [viralIdeas, setViralIdeas] = useState(null)

  // Shared
  const [rewritingTopic, setRewritingTopic] = useState(null)
  const [generatedCarousel, setGeneratedCarousel] = useState(null)
  const [fontStyle] = useState('modern_clean')
  const [colorScheme, setColorScheme] = useState('dark_luxury')

  const authorName = selectedAccount?.username || 'Эксперт'
  const authorCity = selectedAccount?.city || ''
  const authorNiche = selectedAccount?.niche || ''

  // Load saved competitors
  useEffect(() => {
    loadCompetitors()
  }, [])

  const loadCompetitors = async () => {
    try {
      const res = await api.get('/competitors/list')
      setCompetitors(res.data || [])
    } catch {
      // table may not exist
    }
  }

  // ─── Add competitor ───
  const handleAddCompetitor = async () => {
    if (!newCompetitor.trim()) return
    setAddingCompetitor(true)
    try {
      await api.post('/competitors/add', { username: newCompetitor.replace('@', '') })
      setNewCompetitor('')
      await loadCompetitors()
    } catch (err) {
      alert(err.response?.data?.detail || 'Ошибка')
    } finally {
      setAddingCompetitor(false)
    }
  }

  const handleRemoveCompetitor = async (id) => {
    try {
      await api.delete(`/competitors/${id}`)
      await loadCompetitors()
    } catch {}
  }

  // ─── Auto-scrape ───
  const handleScrape = async () => {
    if (!selectedCompetitor) return
    setScraping(true)
    setScrapeResult(null)
    setGeneratedCarousel(null)

    try {
      const res = await api.post('/competitors/scrape', {
        competitor_username: selectedCompetitor,
        post_count: 30,
        top_n: 10,
        carousels_only: false,
        account_id: selectedAccount?.id || null,
      })
      setScrapeResult(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Ошибка парсинга. Проверьте что аккаунт Instagram подключён.')
    } finally {
      setScraping(false)
    }
  }

  // ─── Manual analyze ───
  const handleAnalyze = async () => {
    if (!postsText.trim()) return
    setAnalyzing(true)
    setAnalysis(null)
    setGeneratedCarousel(null)

    try {
      const res = await api.post('/competitors/analyze', {
        posts_text: postsText,
        competitor_username: competitorUsername || null,
      })
      setAnalysis(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Ошибка анализа')
    } finally {
      setAnalyzing(false)
    }
  }

  // ─── Scrape Reels ───
  const handleScrapeReels = async () => {
    if (!selectedCompetitor) return
    setScrapingReels(true)
    setReelsResult(null)
    setGeneratedCarousel(null)

    try {
      const res = await api.post('/competitors/scrape-reels', {
        competitor_username: selectedCompetitor,
        reel_count: 30,
        top_n: 10,
        account_id: selectedAccount?.id || null,
      })
      setReelsResult(res.data)
    } catch (err) {
      // handled by global toast
    } finally {
      setScrapingReels(false)
    }
  }

  // ─── Generate carousel from reel idea ───
  const handleReelToCarousel = async (idea) => {
    setGeneratingFromReel(idea.original_reel_theme)
    setGeneratedCarousel(null)

    try {
      const res = await api.post('/competitors/reel-to-carousel', {
        reel_theme: idea.original_reel_theme,
        why_viral: idea.why_viral,
        carousel_adaptation: idea.carousel_adaptation,
        hook: idea.hook_for_first_slide || '',
        name: authorName,
        city: authorCity,
        niche: authorNiche,
        font_style: fontStyle,
        color_scheme: colorScheme,
        generate_slides: true,
      })
      setGeneratedCarousel(res.data)
    } catch (err) {
      // handled by global toast
    } finally {
      setGeneratingFromReel(null)
    }
  }

  // ─── Generate ideas ───
  const handleGenerateIdeas = async () => {
    setGeneratingIdeas(true)
    setViralIdeas(null)
    setGeneratedCarousel(null)

    try {
      const res = await api.post('/competitors/viral-ideas', {
        niche: authorNiche,
        city: authorCity,
        count: 5,
      })
      setViralIdeas(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Ошибка')
    } finally {
      setGeneratingIdeas(false)
    }
  }

  // ─── Rewrite ───
  const handleRewrite = async (topic) => {
    setRewritingTopic(topic.original_theme)
    setGeneratedCarousel(null)

    try {
      const res = await api.post('/competitors/rewrite', {
        original_theme: topic.original_theme,
        why_viral: topic.why_viral,
        rewrite_angle: topic.rewrite_angle,
        name: authorName,
        city: authorCity,
        niche: authorNiche,
        font_style: fontStyle,
        color_scheme: colorScheme,
        generate_slides: true,
      })
      setGeneratedCarousel(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || 'Ошибка рерайта')
    } finally {
      setRewritingTopic(null)
    }
  }

  // Current results
  const topics =
    tab === 'scrape' ? (scrapeResult?.viral_topics || []) :
    tab === 'paste' ? (analysis?.viral_topics || []) :
    (viralIdeas?.viral_topics || [])

  const insights =
    tab === 'scrape' ? scrapeResult?.niche_insights :
    tab === 'paste' ? analysis?.niche_insights :
    viralIdeas?.niche_insights

  // Reels carousel ideas
  const reelIdeas = reelsResult?.carousel_ideas || []
  const reelsInsights = reelsResult?.reels_insights

  const isLoading = scraping || analyzing || generatingIdeas || scrapingReels

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Flame size={24} className="text-brand-orange" />
            Конкуренты и вирусный контент
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Парси топовые посты конкурентов, находи виральные темы и создавай уникальный контент
          </p>
        </div>
      </div>

      {/* Competitor accounts bar */}
      <div className="bg-brand-card border border-brand-border rounded-xl p-4 mb-5">
        <div className="flex items-center gap-2 mb-3">
          <Instagram size={14} className="text-brand-orange" />
          <span className="text-sm font-medium text-white">Аккаунты конкурентов</span>
          <span className="text-[10px] text-gray-500 ml-auto">{competitors.length} добавлено</span>
        </div>

        <div className="flex items-center gap-2 mb-3">
          <input
            type="text"
            value={newCompetitor}
            onChange={(e) => setNewCompetitor(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAddCompetitor()}
            placeholder="@username конкурента"
            className="flex-1 bg-brand-dark border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange"
          />
          <button
            onClick={handleAddCompetitor}
            disabled={addingCompetitor || !newCompetitor.trim()}
            className="bg-brand-orange hover:bg-orange-600 text-white px-3 py-2 rounded-lg text-sm transition-colors disabled:opacity-50 flex items-center gap-1.5"
          >
            <Plus size={14} />
            Добавить
          </button>
        </div>

        {competitors.length > 0 && (
          <div className="flex gap-2 flex-wrap">
            {competitors.map((c) => (
              <div
                key={c.id || c.username}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-all ${
                  selectedCompetitor === c.username
                    ? 'border-brand-orange bg-brand-orange/10 text-brand-orange'
                    : 'border-brand-border/30 text-gray-400 hover:border-brand-border hover:text-white'
                }`}
                onClick={() => setSelectedCompetitor(c.username)}
              >
                <Instagram size={12} />
                <span className="text-sm">@{c.username}</span>
                {c.followers && (
                  <span className="text-[10px] text-gray-500">{(c.followers / 1000).toFixed(0)}K</span>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); handleRemoveCompetitor(c.id) }}
                  className="text-gray-500 hover:text-red-400 ml-1"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-brand-darker p-1 rounded-lg w-fit">
        <button
          onClick={() => { setTab('scrape'); setGeneratedCarousel(null) }}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
            tab === 'scrape' ? 'bg-brand-orange text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          <Instagram size={16} />
          Авто-парсинг
        </button>
        <button
          onClick={() => { setTab('reels'); setGeneratedCarousel(null) }}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
            tab === 'reels' ? 'bg-purple-600 text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          <Play size={16} />
          Reels
        </button>
        <button
          onClick={() => { setTab('paste'); setGeneratedCarousel(null) }}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
            tab === 'paste' ? 'bg-brand-orange text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          <Search size={16} />
          Вставить текст
        </button>
        <button
          onClick={() => { setTab('ideas'); setGeneratedCarousel(null) }}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
            tab === 'ideas' ? 'bg-brand-orange text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          <Sparkles size={16} />
          Генератор идей
        </button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* ─── LEFT PANEL ─── */}
        <div className="col-span-5">
          <div className="bg-brand-card border border-brand-border rounded-xl p-5 sticky top-6">

            {/* TAB: Auto-scrape */}
            {tab === 'scrape' && (
              <>
                <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                  <Instagram size={14} className="text-brand-orange" />
                  Автоматический парсинг
                </h3>
                <p className="text-xs text-gray-500 mb-4">
                  Выберите конкурента из списка выше. Система сама зайдёт в его Instagram,
                  спарсит 30 последних постов, найдёт самые залайканные и предложит рерайт.
                </p>

                {!selectedCompetitor && (
                  <div className="text-center py-8 text-gray-500">
                    <Users size={24} className="mx-auto mb-2 opacity-30" />
                    <p className="text-xs">Выберите конкурента из списка выше</p>
                  </div>
                )}

                {selectedCompetitor && (
                  <>
                    <div className="bg-brand-dark rounded-lg p-3 mb-3 border border-brand-border/30">
                      <div className="flex items-center gap-2 mb-2">
                        <Instagram size={14} className="text-pink-400" />
                        <span className="text-sm text-white font-medium">@{selectedCompetitor}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-gray-500">Парсим: </span>
                          <span className="text-white">30 постов</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Топ: </span>
                          <span className="text-white">10 по вовлечённости</span>
                        </div>
                      </div>
                    </div>

                    {!selectedAccount && (
                      <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 mb-3 text-xs text-yellow-400">
                        Для парсинга нужен подключённый Instagram аккаунт. Добавьте аккаунт в разделе "Аккаунты" и выберите его в шапке.
                      </div>
                    )}

                    <button
                      onClick={handleScrape}
                      disabled={scraping || !selectedAccount}
                      className="w-full bg-gradient-to-r from-purple-600 to-pink-500 hover:from-purple-700 hover:to-pink-600 text-white font-medium py-2.5 rounded-lg transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      {scraping ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          Парсю @{selectedCompetitor}...
                        </>
                      ) : (
                        <>
                          <Zap size={16} />
                          Спарсить и найти вирусные посты
                        </>
                      )}
                    </button>
                  </>
                )}

                {/* Scraped posts list */}
                {scrapeResult?.posts && scrapeResult.posts.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-brand-border/30">
                    <div className="text-xs text-gray-500 mb-2">
                      Топ-{scrapeResult.posts.length} постов по вовлечённости:
                    </div>
                    <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                      {scrapeResult.posts.map((post, i) => (
                        <PostCard key={post.media_id || i} post={post} index={i} />
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* TAB: Reels analysis */}
            {tab === 'reels' && (
              <>
                <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                  <Play size={14} className="text-purple-400" />
                  Анализ залетевших Reels
                </h3>
                <p className="text-xs text-gray-500 mb-4">
                  Парсим Reels конкурента, находим самые просматриваемые и генерируем каруселей на основе тем,
                  которые уже залетели в видео.
                </p>

                {!selectedCompetitor && (
                  <div className="text-center py-8 text-gray-500">
                    <Users size={24} className="mx-auto mb-2 opacity-30" />
                    <p className="text-xs">Выберите конкурента из списка выше</p>
                  </div>
                )}

                {selectedCompetitor && (
                  <>
                    <div className="bg-brand-dark rounded-lg p-3 mb-3 border border-purple-500/20">
                      <div className="flex items-center gap-2 mb-2">
                        <Play size={14} className="text-purple-400" />
                        <span className="text-sm text-white font-medium">Reels @{selectedCompetitor}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-gray-500">Парсим: </span>
                          <span className="text-white">30 Reels</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Топ: </span>
                          <span className="text-white">10 по просмотрам</span>
                        </div>
                      </div>
                    </div>

                    {!selectedAccount && (
                      <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3 mb-3 text-xs text-yellow-400">
                        Для парсинга нужен подключённый Instagram аккаунт.
                      </div>
                    )}

                    <button
                      onClick={handleScrapeReels}
                      disabled={scrapingReels || !selectedAccount}
                      className="w-full bg-gradient-to-r from-purple-600 to-violet-500 hover:from-purple-700 hover:to-violet-600 text-white font-medium py-2.5 rounded-lg transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      {scrapingReels ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          Парсю Reels @{selectedCompetitor}...
                        </>
                      ) : (
                        <>
                          <Play size={16} />
                          Спарсить залетевшие Reels
                        </>
                      )}
                    </button>
                  </>
                )}

                {/* Scraped reels list */}
                {reelsResult?.reels && reelsResult.reels.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-brand-border/30">
                    <div className="text-xs text-gray-500 mb-2">
                      Топ-{reelsResult.reels.length} Reels по просмотрам:
                    </div>
                    <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
                      {reelsResult.reels.map((reel, i) => (
                        <ReelCard key={reel.media_id || i} reel={reel} index={i} />
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {/* TAB: Manual paste */}
            {tab === 'paste' && (
              <>
                <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                  <Target size={14} className="text-brand-orange" />
                  Вставь посты конкурента
                </h3>
                <p className="text-xs text-gray-500 mb-3">
                  Скопируй текст 3-10 постов конкурента из Instagram. Разделяй посты пустой строкой или ---.
                </p>

                <div className="mb-3">
                  <label className="block text-[10px] text-gray-500 mb-1">Аккаунт конкурента</label>
                  <input
                    type="text"
                    value={competitorUsername}
                    onChange={(e) => setCompetitorUsername(e.target.value)}
                    placeholder="@username"
                    className="w-full bg-brand-dark border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange"
                  />
                </div>

                <textarea
                  value={postsText}
                  onChange={(e) => setPostsText(e.target.value)}
                  placeholder={"Вставьте текст постов конкурента...\n\n---\n\nРазделяйте посты тройным дефисом"}
                  rows={10}
                  className="w-full bg-brand-dark border border-brand-border rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-brand-orange resize-none mb-3"
                />

                <div className="text-[10px] text-gray-500 mb-3">{postsText.length} / 15000</div>

                <button
                  onClick={handleAnalyze}
                  disabled={analyzing || !postsText.trim()}
                  className="w-full bg-brand-orange hover:bg-orange-600 text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {analyzing ? (
                    <><Loader2 size={16} className="animate-spin" /> Анализирую...</>
                  ) : (
                    <><Eye size={16} /> Найти виральные темы</>
                  )}
                </button>
              </>
            )}

            {/* TAB: AI Ideas */}
            {tab === 'ideas' && (
              <>
                <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                  <Sparkles size={14} className="text-brand-orange" />
                  Генерация виральных идей
                </h3>
                <p className="text-xs text-gray-500 mb-4">
                  AI проанализирует тренды в нише "{authorNiche}" и предложит 5 тем для виральных каруселей.
                </p>

                <div className="bg-brand-dark rounded-lg p-3 mb-4 border border-brand-border/30">
                  <div className="text-[10px] text-gray-500 mb-2">Параметры</div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div><span className="text-gray-500">Ниша: </span><span className="text-white">{authorNiche}</span></div>
                    <div><span className="text-gray-500">Город: </span><span className="text-white">{authorCity}</span></div>
                  </div>
                </div>

                <button
                  onClick={handleGenerateIdeas}
                  disabled={generatingIdeas}
                  className="w-full bg-gradient-to-r from-brand-orange to-pink-500 hover:from-orange-600 hover:to-pink-600 text-white font-medium py-2.5 rounded-lg transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {generatingIdeas ? (
                    <><Loader2 size={16} className="animate-spin" /> Генерирую идеи...</>
                  ) : (
                    <><Zap size={16} /> Сгенерировать виральные темы</>
                  )}
                </button>
              </>
            )}

            {/* Design settings */}
            <div className="mt-4 pt-4 border-t border-brand-border/30">
              <div className="text-[10px] text-gray-500 mb-2">Стиль каруселей</div>
              <div className="flex gap-1.5 flex-wrap">
                {[
                  { id: 'dark_luxury', name: 'Тёмный' },
                  { id: 'light_clean', name: 'Светлый' },
                  { id: 'gradient_warm', name: 'Тёплый' },
                  { id: 'neon_dark', name: 'Неон' },
                  { id: 'corporate', name: 'Корп.' },
                ].map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setColorScheme(t.id)}
                    className={`px-2 py-1 rounded text-[10px] border transition-all ${
                      colorScheme === t.id
                        ? 'border-brand-orange text-brand-orange bg-brand-orange/10'
                        : 'border-brand-border/30 text-gray-500 hover:text-gray-300'
                    }`}
                  >
                    {t.name}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ─── RIGHT PANEL — Results ─── */}
        <div className="col-span-7">
          {/* Competitor info */}
          {tab === 'scrape' && scrapeResult?.competitor && (
            <CompetitorInfoCard info={scrapeResult.competitor} />
          )}
          {tab === 'reels' && reelsResult?.competitor && (
            <CompetitorInfoCard info={reelsResult.competitor} />
          )}

          {/* Reels insights */}
          {tab === 'reels' && reelsInsights && (
            <div className="bg-gradient-to-r from-purple-500/5 to-violet-500/5 border border-purple-500/20 rounded-xl p-4 mb-4">
              <div className="flex items-center gap-2 mb-1">
                <Play size={14} className="text-purple-400" />
                <span className="text-xs font-medium text-purple-400">Инсайты из Reels</span>
              </div>
              <p className="text-sm text-gray-300">{reelsInsights}</p>
              {reelsResult?.trending_formats?.length > 0 && (
                <div className="flex gap-1.5 mt-2">
                  {reelsResult.trending_formats.map((f, i) => (
                    <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20">
                      {f}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Reel carousel ideas */}
          {tab === 'reels' && reelIdeas.length > 0 && (
            <div className="space-y-3 mb-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white flex items-center gap-2">
                  <Video size={14} className="text-purple-400" />
                  Идеи каруселей из Reels ({reelIdeas.length})
                </h3>
              </div>
              {reelIdeas.map((idea, i) => (
                <ReelIdeaCard
                  key={i}
                  idea={idea}
                  index={i}
                  onGenerate={handleReelToCarousel}
                  generating={generatingFromReel === idea.original_reel_theme}
                />
              ))}
            </div>
          )}

          {/* Insights */}
          {insights && tab !== 'reels' && (
            <div className="bg-gradient-to-r from-brand-orange/5 to-pink-500/5 border border-brand-orange/20 rounded-xl p-4 mb-4">
              <div className="flex items-center gap-2 mb-1">
                <MessageSquare size={14} className="text-brand-orange" />
                <span className="text-xs font-medium text-brand-orange">Инсайты по нише</span>
              </div>
              <p className="text-sm text-gray-300">{insights}</p>
            </div>
          )}

          {/* Viral topics */}
          {topics.length > 0 && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white">
                  Виральные темы ({topics.length})
                </h3>
              </div>
              {topics.map((topic, i) => (
                <ViralTopicCard
                  key={i}
                  topic={topic}
                  index={i}
                  onRewrite={handleRewrite}
                  rewriting={rewritingTopic === topic.original_theme}
                />
              ))}
            </div>
          )}

          {/* Empty state */}
          {!isLoading && topics.length === 0 && (tab !== 'reels' || reelIdeas.length === 0) && (
            <div className="text-center py-20">
              <Flame size={48} className="mx-auto mb-4 text-gray-700" />
              <p className="text-gray-500">
                {tab === 'scrape' ? 'Выберите конкурента и нажмите "Спарсить"' :
                 tab === 'reels' ? 'Выберите конкурента и спарсьте его Reels' :
                 tab === 'paste' ? 'Вставьте посты конкурента' :
                 'Нажмите "Сгенерировать"'}
              </p>
            </div>
          )}

          {/* Loading */}
          {isLoading && (
            <div className="text-center py-20">
              <Loader2 size={32} className="mx-auto mb-4 text-brand-orange animate-spin" />
              <p className="text-gray-400">
                {scraping ? `Парсю @${selectedCompetitor}...` :
                 scrapingReels ? `Парсю Reels @${selectedCompetitor}...` :
                 analyzing ? 'Анализирую посты...' : 'Генерирую идеи...'}
              </p>
              <p className="text-xs text-gray-600 mt-1">
                {scraping || scrapingReels ? 'Заходим в Instagram, парсим контент, анализируем AI — 30-60 сек' : '10-20 секунд'}
              </p>
            </div>
          )}

          {/* Generated carousel */}
          {generatedCarousel?.slides && (
            <div className="mt-6">
              <div className="flex items-center gap-2 mb-2">
                <Check size={16} className="text-green-400" />
                <span className="text-green-400 text-sm font-medium">{generatedCarousel.message}</span>
                <span className="text-[10px] bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded-full">Рерайт</span>
              </div>
              <MiniSlidePreview slides={generatedCarousel.slides} caption={generatedCarousel.caption} />
              {/* Publish from competitors */}
              {generatedCarousel.carousel_id && selectedAccount && (
                <CompetitorPublishBar
                  carouselId={generatedCarousel.carousel_id}
                  accountId={selectedAccount.id}
                  accountUsername={selectedAccount.username}
                />
              )}
              {!selectedAccount && generatedCarousel.carousel_id && (
                <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-yellow-900/10 border border-yellow-500/20">
                  <Instagram size={14} className="text-yellow-400" />
                  <span className="text-xs text-yellow-400">
                    Выберите аккаунт в шапке, чтобы опубликовать
                  </span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
