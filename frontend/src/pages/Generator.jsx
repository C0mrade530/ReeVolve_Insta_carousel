import React, { useState, useEffect, useRef } from 'react'
import {
  Sparkles, Building2, ChevronLeft, ChevronRight, Copy,
  Clock, Send, Palette, Type, Star, RefreshCw, Check, Download, Loader2,
  Upload, User, Camera, Wand2, ImageIcon, X, Instagram, Zap, Pencil, Magnet,
  Link, Search, MapPin, Home, DollarSign, Trash2
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import api, { supabase } from '../api/client'
import { useAccount } from '../contexts/AccountContext'
import MusicPicker from '../components/MusicPicker'

// Design template loaded from user settings (default fallback)
const DEFAULT_TEMPLATE_ID = 'expert'

// ═══════════════════════════════════════════════════════════════════
// EXPERT PHOTO UPLOAD COMPONENT
// ═══════════════════════════════════════════════════════════════════
function ExpertPhotoUpload({ accountId }) {
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [status, setStatus] = useState(null)
  const fileRef = useRef(null)

  // Check current status on mount
  useEffect(() => {
    if (!accountId) return
    api.get(`/expert-template/status?user_id=${accountId}`)
      .then(r => setStatus(r.data))
      .catch(() => {})
  }, [accountId])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('user_id', accountId)
      form.append('remove_bg', 'true')
      await api.post('/expert-template/upload-photo', form)

      // Auto-generate template after upload
      setGenerating(true)
      await api.post('/expert-template/generate', {
        user_id: accountId,
        accent_color: '#d4a853',
      })

      // Refresh status
      const r = await api.get(`/expert-template/status?user_id=${accountId}`)
      setStatus(r.data)
    } catch (err) {
      console.error('Upload failed:', err)
    } finally {
      setUploading(false)
      setGenerating(false)
    }
  }

  const hasTemplate = status?.has_template

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={() => fileRef.current?.click()}
        disabled={uploading || generating}
        className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border-2 transition-all text-sm ${
          hasTemplate
            ? 'border-green-500/40 bg-green-500/10 text-green-400'
            : 'border-brand-orange/40 bg-brand-orange/10 text-brand-orange hover:bg-brand-orange/20'
        }`}
      >
        {uploading || generating ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            {generating ? 'Генерация фона...' : 'Загрузка...'}
          </>
        ) : hasTemplate ? (
          <>
            <Check size={16} />
            Фото загружено
          </>
        ) : (
          <>
            <Camera size={16} />
            Загрузить фото эксперта
          </>
        )}
      </button>
      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={handleUpload}
        className="hidden"
      />
      {hasTemplate && (
        <button
          onClick={() => fileRef.current?.click()}
          className="text-xs text-gray-500 hover:text-gray-300 transition"
        >
          Заменить
        </button>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// QUALITY SCORE BADGE
// ═══════════════════════════════════════════════════════════════════
function QualityBadge({ score, rounds }) {
  if (!score) return null

  const color =
    score >= 8 ? 'text-green-400 border-green-500/30 bg-green-500/10' :
    score >= 7 ? 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10' :
    'text-red-400 border-red-500/30 bg-red-500/10'

  const label =
    score >= 8 ? 'Отличный контент' :
    score >= 7 ? 'Хороший контент' :
    'Базовый контент'

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border text-sm ${color}`}>
      <Star size={14} />
      <span className="font-medium">{score}/10</span>
      <span className="text-xs opacity-70">{label}</span>
      {rounds > 1 && (
        <span className="text-xs opacity-50">{rounds} итер.</span>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// SLIDE PREVIEW
// ═══════════════════════════════════════════════════════════════════
function SlidePreview({ slides, caption, hashtags }) {
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
    <div className="mt-6">
      <h3 className="text-lg font-semibold text-white mb-4">
        Превью карусели ({slides.length} слайдов)
      </h3>

      <div className="flex gap-6">
        {/* Main slide */}
        <div className="flex-shrink-0 relative group">
          <img
            src={slide.image_path}
            alt={`Слайд ${current + 1}`}
            className="w-[324px] h-[405px] object-cover rounded-xl border border-brand-border shadow-2xl"
          />
          {/* Navigation arrows */}
          <div className="absolute inset-0 flex items-center justify-between px-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={() => setCurrent(Math.max(0, current - 1))}
              disabled={current === 0}
              className="bg-black/60 backdrop-blur-sm text-white rounded-full p-2 disabled:opacity-0 hover:bg-black/80 transition-all"
            >
              <ChevronLeft size={20} />
            </button>
            <button
              onClick={() => setCurrent(Math.min(slides.length - 1, current + 1))}
              disabled={current === slides.length - 1}
              className="bg-black/60 backdrop-blur-sm text-white rounded-full p-2 disabled:opacity-0 hover:bg-black/80 transition-all"
            >
              <ChevronRight size={20} />
            </button>
          </div>
          {/* Slide counter */}
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 bg-black/70 backdrop-blur-sm text-white text-xs px-3 py-1 rounded-full">
            {current + 1} / {slides.length}
          </div>
        </div>

        {/* Slide info */}
        <div className="flex-1 min-w-0 flex flex-col">
          <div className="text-xs text-gray-500 mb-1 uppercase tracking-wider">
            Слайд {current + 1} из {slides.length}
          </div>
          <div className="text-white font-semibold text-lg mb-2">{slide.text_overlay}</div>
          {slide.body && (
            <div className="text-sm text-gray-400 mb-4 leading-relaxed">{slide.body}</div>
          )}

          {/* Caption */}
          {caption && (
            <div className="mt-auto">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-500 uppercase tracking-wider">Подпись к посту</span>
                <button
                  onClick={handleCopy}
                  className="text-xs text-brand-orange hover:text-orange-400 flex items-center gap-1 transition-colors"
                >
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                  {copied ? 'Скопировано' : 'Копировать'}
                </button>
              </div>
              <div className="bg-brand-darker rounded-lg p-3 text-sm text-gray-300 max-h-36 overflow-y-auto whitespace-pre-wrap border border-brand-border/50">
                {caption}
              </div>
            </div>
          )}

          {hashtags && (
            <div className="mt-2 text-xs text-brand-orange/80">{hashtags}</div>
          )}
        </div>
      </div>

      {/* Thumbnail strip */}
      <div className="flex gap-2 mt-4 overflow-x-auto pb-2">
        {slides.map((s, i) => (
          <button
            key={i}
            onClick={() => setCurrent(i)}
            className={`flex-shrink-0 rounded-lg overflow-hidden border-2 transition-all ${
              i === current
                ? 'border-brand-orange shadow-lg shadow-brand-orange/20 scale-105'
                : 'border-transparent opacity-50 hover:opacity-80'
            }`}
          >
            <img
              src={s.image_path}
              alt={`Thumb ${i + 1}`}
              className="w-16 h-20 object-cover"
            />
          </button>
        ))}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// GENERATION STEP INDICATOR
// ═══════════════════════════════════════════════════════════════════
const TOPIC_STEPS = [
  { key: 'topic', label: 'Тема и стратегия', icon: '🧠' },
  { key: 'slides', label: 'Слайды и описание', icon: '✍️' },
  { key: 'evaluate', label: 'Проверка виральности', icon: '🔍' },
  { key: 'refine', label: 'Улучшение', icon: '✨' },
  { key: 'slides_render', label: 'Рисую слайды', icon: '🎨' },
]

const PROPERTY_STEPS = [
  { key: 'fetch_listing', label: 'Загрузка объявления', icon: '🏠' },
  { key: 'generate_text', label: 'Тексты слайдов', icon: '✍️' },
  { key: 'evaluate', label: 'Проверка качества', icon: '🔍' },
  { key: 'refine', label: 'Улучшение', icon: '✨' },
  { key: 'slides_render', label: 'Рисую слайды с фото', icon: '🎨' },
]

function GenerationProgress({ step, currentStep, totalSteps, mode = 'topic' }) {
  const PIPELINE_STEPS = mode === 'property' ? PROPERTY_STEPS : TOPIC_STEPS

  // Determine current index from step name
  const currentIdx = PIPELINE_STEPS.findIndex(s => s.key === step)
  const activeIdx = currentIdx >= 0 ? currentIdx : 0

  return (
    <div className="mt-4">
      <div className="flex items-center gap-2 flex-wrap">
        {PIPELINE_STEPS.map((s, i) => (
          <div key={s.key} className="flex items-center gap-2">
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs transition-all ${
              i === activeIdx
                ? 'bg-brand-orange/20 text-brand-orange border border-brand-orange/30'
                : i < activeIdx
                  ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                  : 'bg-brand-darker text-gray-600 border border-brand-border/30'
            }`}>
              {i < activeIdx ? <Check size={12} /> :
               i === activeIdx ? <Loader2 size={12} className="animate-spin" /> :
               <span className="text-[10px]">{s.icon}</span>}
              <span>{s.label}</span>
            </div>
            {i < PIPELINE_STEPS.length - 1 && (
              <div className={`w-4 h-[1px] ${i < activeIdx ? 'bg-green-500/40' : 'bg-brand-border/30'}`} />
            )}
          </div>
        ))}
      </div>
      {/* Progress bar */}
      {totalSteps > 0 && (
        <div className="mt-3 w-full bg-brand-darker rounded-full h-1.5 overflow-hidden">
          <div
            className="bg-brand-orange h-full rounded-full transition-all duration-500"
            style={{ width: `${Math.round((currentStep / totalSteps) * 100)}%` }}
          />
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════
// BACKGROUND UPLOAD SECTION (подложка для каруселей)
// ═══════════════════════════════════════════════════════════════════
function ExpertTemplateSection() {
  const [status, setStatus] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [cacheBust, setCacheBust] = useState(Date.now())
  const fileInputRef = useRef(null)

  useEffect(() => {
    loadStatus()
  }, [])

  const loadStatus = async () => {
    try {
      const res = await api.get('/expert-template/status')
      setStatus(res.data)
    } catch {
      // Not logged in or endpoint not ready
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await api.post('/expert-template/upload-photo', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setCacheBust(Date.now())
      await loadStatus()
    } catch (err) {
      alert(err.response?.data?.detail || 'Ошибка загрузки')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-5 mb-6">
      <h4 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
        <ImageIcon size={14} className="text-brand-orange" />
        Подложка для каруселей
        {status?.has_template && (
          <span className="text-[10px] bg-green-500/20 text-green-400 px-2 py-0.5 rounded-full">Загружена</span>
        )}
      </h4>
      <p className="text-xs text-gray-500 mb-4">
        Загрузите готовую подложку (1080×1350). Текст, никнейм, счётчик страниц будут наложены поверх.
      </p>

      <div className="flex gap-4 items-center">
        {/* Upload area / preview */}
        <div
          onClick={() => fileInputRef.current?.click()}
          className={`w-32 h-40 rounded-xl border-2 border-dashed cursor-pointer transition-all flex items-center justify-center overflow-hidden bg-brand-dark group ${
            status?.has_template
              ? 'border-green-500/30 hover:border-green-500/60'
              : 'border-brand-border hover:border-brand-orange'
          }`}
        >
          {status?.template_url ? (
            <img
              src={`${status.template_url}?t=${cacheBust}`}
              alt="Подложка"
              className="w-full h-full object-cover group-hover:opacity-70 transition-opacity"
            />
          ) : (
            <div className="flex flex-col items-center gap-2 text-gray-500 group-hover:text-brand-orange transition-colors">
              <Upload size={24} />
              <span className="text-xs text-center px-2">Загрузить подложку</span>
            </div>
          )}
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={handleUpload}
          className="hidden"
        />

        <div className="flex flex-col gap-2">
          {uploading && (
            <span className="text-sm text-brand-orange flex items-center gap-2">
              <Loader2 size={14} className="animate-spin" /> Загрузка...
            </span>
          )}
          {status?.has_template && !uploading && (
            <>
              <span className="text-sm text-green-400 flex items-center gap-2">
                <Check size={14} /> Подложка готова
              </span>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-xs text-gray-500 hover:text-brand-orange transition-colors flex items-center gap-1"
              >
                <RefreshCw size={12} />
                Заменить
              </button>
            </>
          )}
          {!status?.has_template && !uploading && (
            <span className="text-xs text-gray-500">
              Рекомендуемый размер: 1080×1350 px (4:5)
            </span>
          )}
        </div>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════
// MAIN GENERATOR PAGE
// ═══════════════════════════════════════════════════════════════════
export default function Generator() {
  const navigate = useNavigate()
  const { selectedAccount, accounts } = useAccount()
  const [tab, setTab] = useState('topic')
  const [topic, setTopic] = useState('')
  const [name, setName] = useState('Эксперт')
  const [city, setCity] = useState('')
  const [niche, setNiche] = useState('')
  const [fontStyle, setFontStyle] = useState('luxury')
  const [colorScheme, setColorScheme] = useState('expert')
  const [accentColor, setAccentColor] = useState(null)
  const [ctaFinal, setCtaFinal] = useState(() => localStorage.getItem('rp_cta_final') || '')
  const [leadMagnet, setLeadMagnet] = useState(() => localStorage.getItem('rp_lead_magnet') || '')
  const [generating, setGenerating] = useState(false)
  const [generationStep, setGenerationStep] = useState('')
  const [result, setResult] = useState(null)

  // Property tab state
  const [cianUrl, setCianUrl] = useState('')
  const [parsingUrl, setParsingUrl] = useState(false)
  const [selectedListing, setSelectedListing] = useState(null)
  const [listings, setListings] = useState([])
  const [loadingListings, setLoadingListings] = useState(false)
  const [listingFilter, setListingFilter] = useState({ rooms: '', min_price: '', max_price: '' })
  const [showManualForm, setShowManualForm] = useState(false)
  const [manualForm, setManualForm] = useState({
    title: '', price: '', rooms: '', area_total: '', address: '', district: '',
    metro_station: '', complex_name: '', description: '', source_url: '',
  })
  const generatingRef = useRef(false) // debounce guard

  // Publish & schedule state
  const [publishing, setPublishing] = useState(false)
  const [publishResult, setPublishResult] = useState(null)
  const [showSchedule, setShowSchedule] = useState(false)
  const [musicQuery, setMusicQuery] = useState(null)
  const [scheduleDate, setScheduleDate] = useState('')
  const [scheduleTime, setScheduleTime] = useState('10:00')
  const [scheduling, setScheduling] = useState(false)

  // Auto-fill from selected Instagram account
  useEffect(() => {
    if (selectedAccount) {
      setName(selectedAccount.username || 'Эксперт')
      setCity(selectedAccount.city || '')
      setNiche(selectedAccount.niche || '')
    }
  }, [selectedAccount])

  // Load design settings on mount
  useEffect(() => {
    api.get('/design-settings').then(r => {
      if (r.data?.template_id) {
        setColorScheme(r.data.template_id)
        setFontStyle(r.data.font_pairing || 'luxury')
        setAccentColor(r.data.accent_color || null)
      }
    }).catch(() => {})
  }, [])

  // Persist CTA fields to localStorage (дублируются из карусели в карусель)
  useEffect(() => { localStorage.setItem('rp_cta_final', ctaFinal) }, [ctaFinal])
  useEffect(() => { localStorage.setItem('rp_lead_magnet', leadMagnet) }, [leadMagnet])

  // Load saved listings on mount
  useEffect(() => {
    loadListings()
  }, [])

  const loadListings = async () => {
    setLoadingListings(true)
    try {
      const params = new URLSearchParams()
      if (listingFilter.rooms) params.set('rooms', listingFilter.rooms)
      if (listingFilter.min_price) params.set('min_price', listingFilter.min_price)
      if (listingFilter.max_price) params.set('max_price', listingFilter.max_price)
      params.set('limit', '20')
      const res = await api.get(`/listings?${params}`)
      setListings(res.data || [])
    } catch {
      // ignore
    } finally {
      setLoadingListings(false)
    }
  }

  const handleParseCian = async () => {
    if (!cianUrl || !cianUrl.includes('cian.ru')) return
    setParsingUrl(true)
    try {
      const res = await api.post(`/listings/parse-url?url=${encodeURIComponent(cianUrl)}`)
      const listing = res.data?.listing
      if (listing) {
        setSelectedListing(listing)
        setCianUrl('')
        loadListings() // refresh list
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Ошибка парсинга CIAN')
    } finally {
      setParsingUrl(false)
    }
  }

  const handleManualSubmit = async () => {
    if (!manualForm.title || !manualForm.price) return
    try {
      const res = await api.post('/listings/manual', {
        ...manualForm,
        price: parseInt(manualForm.price) || 0,
        rooms: manualForm.rooms ? parseInt(manualForm.rooms) : null,
        area_total: manualForm.area_total ? parseFloat(manualForm.area_total) : null,
        source_url: manualForm.source_url || `manual-${Date.now()}`,
      })
      const listing = res.data?.listing
      if (listing) {
        setSelectedListing(listing)
        setShowManualForm(false)
        setManualForm({ title: '', price: '', rooms: '', area_total: '', address: '', district: '', metro_station: '', complex_name: '', description: '', source_url: '' })
        loadListings()
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Ошибка сохранения')
    }
  }

  const handleDeleteListing = async (e, listingId) => {
    e.stopPropagation()
    if (!confirm('Удалить объявление?')) return
    try {
      await api.delete(`/listings/${listingId}`)
      if (selectedListing?.id === listingId) setSelectedListing(null)
      loadListings()
    } catch {
      // ignore
    }
  }

  const [progressStep, setProgressStep] = useState('')
  const [progressCurrent, setProgressCurrent] = useState(0)
  const [progressTotal, setProgressTotal] = useState(0)

  const _streamSSE = async (url, body) => {
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token
    if (!token) throw new Error('Не авторизован. Перезайдите в аккаунт.')
    const baseUrl = api.defaults.baseURL || ''

    const response = await fetch(`${baseUrl}${url}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `HTTP ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const jsonStr = line.slice(6).trim()
        if (!jsonStr) continue

        try {
          const event = JSON.parse(jsonStr)

          if (event.event === 'progress') {
            setProgressStep(event.step)
            setProgressCurrent(event.current)
            setProgressTotal(event.total)
            setGenerationStep(event.label)
          } else if (event.event === 'result') {
            setResult(event)
          } else if (event.event === 'error') {
            setResult({ error: event.error })
          }
        } catch {
          // skip malformed JSON
        }
      }
    }
  }

  const handleGenerate = async () => {
    // Debounce: prevent double-click
    if (generatingRef.current) return
    generatingRef.current = true

    setGenerating(true)
    setResult(null)
    setPublishResult(null)
    setProgressCurrent(0)

    if (tab === 'topic') {
      setProgressStep('topic')
      setProgressTotal(5)
      setGenerationStep('Придумываю тему...')

      const body = {
        topic: topic || null,
        name,
        city,
        niche,
        font_style: fontStyle,
        color_scheme: colorScheme,
        accent_color: accentColor,
        cta_final: ctaFinal,
        lead_magnet: leadMagnet,
      }

      try {
        await _streamSSE('/carousels/generate/topic/stream', body)
      } catch (err) {
        try {
          const res = await api.post('/carousels/generate/topic', body)
          setResult(res.data)
        } catch (fallbackErr) {
          setResult({ error: fallbackErr.response?.data?.detail || err.message || 'Ошибка генерации' })
        }
      }
    } else if (tab === 'property') {
      if (!selectedListing) {
        setResult({ error: 'Выберите объявление из списка или загрузите с CIAN' })
        setGenerating(false)
        generatingRef.current = false
        return
      }

      setProgressStep('fetch_listing')
      setProgressTotal(6)
      setGenerationStep('Загружаю объявление...')

      const body = {
        listing_id: selectedListing.id,
        font_style: 'luxury',
        cta_final: ctaFinal,
        lead_magnet: leadMagnet,
      }

      try {
        await _streamSSE('/carousels/generate/property/stream', body)
      } catch (err) {
        try {
          const res = await api.post('/carousels/generate/property', body)
          setResult(res.data)
        } catch (fallbackErr) {
          setResult({ error: fallbackErr.response?.data?.detail || err.message || 'Ошибка генерации' })
        }
      }
    }

    setGenerating(false)
    setGenerationStep('')
    setProgressStep('')
    generatingRef.current = false
  }

  const handlePublishNow = async () => {
    if (!selectedAccount) {
      setPublishResult({ error: 'Выберите Instagram аккаунт в шапке страницы' })
      return
    }
    if (!result?.carousel_id) return

    setPublishing(true)
    setPublishResult(null)
    try {
      const payload = { account_id: selectedAccount.id }
      if (musicQuery) {
        payload.music_query = musicQuery
      }
      const res = await api.post(`/carousels/${result.carousel_id}/publish-now`, payload)
      setPublishResult({ success: true, ...res.data })
    } catch (err) {
      const detail = err.response?.data?.detail || 'Ошибка публикации'
      setPublishResult({ error: detail })
    } finally {
      setPublishing(false)
    }
  }

  const handleSchedule = async () => {
    if (!selectedAccount) {
      setPublishResult({ error: 'Выберите Instagram аккаунт в шапке страницы' })
      return
    }
    if (!result?.carousel_id || !scheduleDate || !scheduleTime) return

    setScheduling(true)
    setPublishResult(null)
    try {
      const scheduledAt = `${scheduleDate}T${scheduleTime}:00`
      const res = await api.post(`/carousels/${result.carousel_id}/schedule`, {
        scheduled_at: scheduledAt,
        account_id: selectedAccount.id,
      })
      setPublishResult({ success: true, scheduled: true, ...res.data })
      setShowSchedule(false)
    } catch (err) {
      setPublishResult({ error: err.response?.data?.detail || 'Ошибка планирования' })
    } finally {
      setScheduling(false)
    }
  }

  // Default schedule date = tomorrow
  useEffect(() => {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    setScheduleDate(tomorrow.toISOString().split('T')[0])
  }, [])

  return (
    <div>
      <h2 className="text-2xl font-bold text-white mb-6">Генератор каруселей</h2>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-brand-darker p-1 rounded-lg w-fit">
        <button
          onClick={() => { setTab('topic'); setResult(null) }}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
            tab === 'topic' ? 'bg-brand-orange text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          <Sparkles size={16} />
          Тематическая
        </button>
        <button
          onClick={() => { setTab('property'); setResult(null) }}
          className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm transition-colors ${
            tab === 'property' ? 'bg-brand-orange text-white' : 'text-gray-400 hover:text-white'
          }`}
        >
          <Building2 size={16} />
          Объект
        </button>
      </div>

      <div className="bg-brand-card border border-brand-border rounded-xl p-6">

        {tab === 'topic' ? (
          <>
            {/* Topic input */}
            <div className="mb-5">
              <label className="block text-sm text-gray-400 mb-1">
                Тема (пусто = AI сам придумает виральную тему)
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="w-full bg-brand-dark border border-brand-border rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-brand-orange transition-colors"
                placeholder="Например: 5 ошибок, которые совершают новички"
              />
            </div>

            {/* Account auto-fill indicator */}
            {selectedAccount && (
              <div className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg bg-brand-orange/5 border border-brand-orange/20">
                <Instagram size={14} className="text-brand-orange" />
                <span className="text-xs text-brand-orange">
                  Данные из аккаунта @{selectedAccount.username}
                </span>
                <span className="text-[10px] text-gray-500 ml-auto">
                  Можно изменить вручную
                </span>
              </div>
            )}

            {/* Quick settings row */}
            <div className="grid grid-cols-3 gap-4 mb-5">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Имя автора</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-brand-dark border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Город</label>
                <input
                  type="text"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full bg-brand-dark border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Ниша</label>
                <input
                  type="text"
                  value={niche}
                  onChange={(e) => setNiche(e.target.value)}
                  className="w-full bg-brand-dark border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange"
                />
              </div>
            </div>

            {/* ─── Expert Template ─── */}
            <ExpertTemplateSection />

            {/* ─── Последний слайд (дублируется из карусели в карусель) ─── */}
            <div className="mt-5 p-4 bg-brand-dark border border-brand-border rounded-xl">
              <div className="flex items-center gap-2 mb-3">
                <Magnet size={16} className="text-brand-orange" />
                <span className="text-sm font-medium text-white">Последний слайд</span>
                <span className="text-[10px] text-gray-500 ml-auto">Сохраняется между генерациями</span>
              </div>

              {/* Поле 1 — Призыв подписаться */}
              <div className="mb-3">
                <label className="block text-xs text-gray-500 mb-1">Призыв подписаться</label>
                <textarea
                  value={ctaFinal}
                  onChange={(e) => setCtaFinal(e.target.value)}
                  rows={2}
                  className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange transition-colors resize-none"
                  placeholder="Поделись с друзьями и подписывайся&#10;Здесь очень интересно!"
                />
              </div>

              {/* Поле 2 — Лид-магнит */}
              <div>
                <label className="block text-xs text-gray-500 mb-1">Лид-магнит</label>
                <textarea
                  value={leadMagnet}
                  onChange={(e) => setLeadMagnet(e.target.value)}
                  rows={3}
                  className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange transition-colors resize-none"
                  placeholder='Напиши "СТАРТ" — получишь бесплатный чек-лист для начинающих!'
                />
              </div>
            </div>
          </>
        ) : (
          <>
            {/* ─── CIAN URL Parser ─── */}
            <div className="mb-5">
              <label className="block text-sm text-gray-400 mb-1 flex items-center gap-1.5">
                <Link size={14} className="text-brand-orange" />
                Ссылка с CIAN
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={cianUrl}
                  onChange={(e) => setCianUrl(e.target.value)}
                  className="flex-1 bg-brand-dark border border-brand-border rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-brand-orange transition-colors"
                  placeholder="https://www.cian.ru/sale/flat/..."
                />
                <button
                  onClick={handleParseCian}
                  disabled={parsingUrl || !cianUrl}
                  className="flex items-center gap-2 px-5 py-2.5 bg-brand-orange hover:bg-orange-600 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-40"
                >
                  {parsingUrl ? (
                    <><Loader2 size={14} className="animate-spin" /> Загрузка...</>
                  ) : (
                    <><Search size={14} /> Загрузить</>
                  )}
                </button>
              </div>
              <div className="flex items-center gap-3 mt-1">
                <p className="text-xs text-gray-600">Вставь ссылку на объявление — фотографии, цена, описание загрузятся автоматически</p>
                <button
                  onClick={() => setShowManualForm(!showManualForm)}
                  className="text-xs text-brand-orange hover:text-orange-400 transition-colors whitespace-nowrap"
                >
                  {showManualForm ? 'Скрыть' : 'Или ввести вручную'}
                </button>
              </div>
            </div>

            {/* ─── Manual Form ─── */}
            {showManualForm && (
              <div className="mb-5 p-4 bg-brand-dark border border-brand-border rounded-xl">
                <h4 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                  <Pencil size={14} className="text-brand-orange" />
                  Ручной ввод объявления
                </h4>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Название *</label>
                    <input type="text" value={manualForm.title} onChange={e => setManualForm(f => ({ ...f, title: e.target.value }))}
                      placeholder="Название объекта или услуги" className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Цена (₽) *</label>
                    <input type="number" value={manualForm.price} onChange={e => setManualForm(f => ({ ...f, price: e.target.value }))}
                      placeholder="15000000" className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Комнаты</label>
                    <select value={manualForm.rooms} onChange={e => setManualForm(f => ({ ...f, rooms: e.target.value }))}
                      className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange">
                      <option value="">—</option><option value="0">Студия</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4+</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Площадь (м²)</label>
                    <input type="number" step="0.1" value={manualForm.area_total} onChange={e => setManualForm(f => ({ ...f, area_total: e.target.value }))}
                      placeholder="65.5" className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">ЖК / Комплекс</label>
                    <input type="text" value={manualForm.complex_name} onChange={e => setManualForm(f => ({ ...f, complex_name: e.target.value }))}
                      placeholder="ЖК Символ" className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Район</label>
                    <input type="text" value={manualForm.district} onChange={e => setManualForm(f => ({ ...f, district: e.target.value }))}
                      placeholder="Лефортово" className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Метро</label>
                    <input type="text" value={manualForm.metro_station} onChange={e => setManualForm(f => ({ ...f, metro_station: e.target.value }))}
                      placeholder="Авиамоторная" className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Адрес</label>
                    <input type="text" value={manualForm.address} onChange={e => setManualForm(f => ({ ...f, address: e.target.value }))}
                      placeholder="ул. Золоторожский вал, 11" className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange" />
                  </div>
                </div>
                <div className="mb-3">
                  <label className="block text-xs text-gray-500 mb-1">Описание</label>
                  <textarea value={manualForm.description} onChange={e => setManualForm(f => ({ ...f, description: e.target.value }))}
                    rows={3} placeholder="Подробное описание для генерации контента..."
                    className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange resize-none" />
                </div>
                <button onClick={handleManualSubmit} disabled={!manualForm.title || !manualForm.price}
                  className="flex items-center gap-2 px-5 py-2 bg-brand-orange hover:bg-orange-600 text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-40">
                  <Check size={14} /> Сохранить объявление
                </button>
              </div>
            )}

            {/* ─── Selected Listing Preview ─── */}
            {selectedListing && (
              <div className="mb-5 p-4 bg-brand-dark border border-green-500/30 rounded-xl">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <Check size={16} className="text-green-400" />
                    <span className="text-sm font-medium text-green-400">Объявление выбрано</span>
                  </div>
                  <button onClick={() => setSelectedListing(null)} className="text-gray-500 hover:text-red-400 transition-colors">
                    <X size={16} />
                  </button>
                </div>
                <div className="flex gap-4">
                  {/* Listing photos thumbnails */}
                  {selectedListing.photos?.length > 0 && (
                    <div className="flex gap-1.5 flex-shrink-0">
                      {selectedListing.photos.slice(0, 3).map((photo, i) => (
                        <img key={i} src={photo} alt="" className="w-16 h-20 object-cover rounded-lg border border-brand-border" />
                      ))}
                      {selectedListing.photos.length > 3 && (
                        <div className="w-16 h-20 rounded-lg border border-brand-border bg-brand-darker flex items-center justify-center text-xs text-gray-500">
                          +{selectedListing.photos.length - 3}
                        </div>
                      )}
                    </div>
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="text-white font-medium text-sm truncate">{selectedListing.title || selectedListing.complex_name || 'Объект'}</div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                      {selectedListing.rooms && <span className="flex items-center gap-1"><Home size={11} />{selectedListing.rooms}-комн.</span>}
                      {selectedListing.area_total && <span>{selectedListing.area_total} м²</span>}
                      {selectedListing.district && <span className="flex items-center gap-1"><MapPin size={11} />{selectedListing.district}</span>}
                    </div>
                    {selectedListing.price && (
                      <div className="mt-1 text-brand-orange font-semibold text-sm flex items-center gap-1">
                        <DollarSign size={13} />
                        {Number(selectedListing.price).toLocaleString('ru-RU')} ₽
                      </div>
                    )}
                  </div>
                </div>

                {/* ─── Slide Structure Preview ─── */}
                <div className="mt-3 pt-3 border-t border-brand-border/30">
                  <div className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Структура карусели (6 слайдов)</div>
                  <div className="flex gap-1.5 overflow-x-auto pb-1">
                    {[
                      { n: 1, label: 'Хук', color: 'bg-brand-orange/20 text-brand-orange border-brand-orange/30' },
                      { n: 2, label: 'Антитезис', color: 'bg-purple-500/15 text-purple-400 border-purple-500/30' },
                      { n: 3, label: 'Локация', color: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
                      { n: 4, label: 'Район', color: 'bg-teal-500/15 text-teal-400 border-teal-500/30' },
                      { n: 5, label: 'Особенности', color: 'bg-green-500/15 text-green-400 border-green-500/30' },
                      { n: 6, label: 'Условия+CTA', color: 'bg-red-500/15 text-red-400 border-red-500/30' },
                    ].map(s => (
                      <div key={s.n} className={`flex-shrink-0 px-2.5 py-1 rounded-md border text-[10px] font-medium ${s.color}`}>
                        {s.n}. {s.label}
                      </div>
                    ))}
                  </div>
                  <div className="text-[10px] text-gray-600 mt-1.5">
                    {selectedListing.photos?.length || 0} фото — {selectedListing.photos?.length >= 5
                      ? 'каждый слайд с уникальным фото'
                      : `некоторые фото будут кадрированы по-разному`}
                  </div>
                </div>
              </div>
            )}

            {/* ─── Listings Browser ─── */}
            <div className="mb-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-gray-400 flex items-center gap-1.5">
                  <Building2 size={14} />
                  Сохранённые объявления
                </span>
                <button onClick={loadListings} disabled={loadingListings} className="text-xs text-gray-500 hover:text-brand-orange transition-colors flex items-center gap-1">
                  <RefreshCw size={11} className={loadingListings ? 'animate-spin' : ''} />
                  Обновить
                </button>
              </div>

              {/* Filters row */}
              <div className="flex gap-2 mb-3">
                <select
                  value={listingFilter.rooms}
                  onChange={(e) => setListingFilter(f => ({ ...f, rooms: e.target.value }))}
                  className="bg-brand-dark border border-brand-border rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-brand-orange"
                >
                  <option value="">Комнаты</option>
                  <option value="1">1-комн</option>
                  <option value="2">2-комн</option>
                  <option value="3">3-комн</option>
                  <option value="4">4+</option>
                </select>
                <input
                  type="number"
                  placeholder="Цена от"
                  value={listingFilter.min_price}
                  onChange={(e) => setListingFilter(f => ({ ...f, min_price: e.target.value }))}
                  className="w-28 bg-brand-dark border border-brand-border rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-brand-orange"
                />
                <input
                  type="number"
                  placeholder="Цена до"
                  value={listingFilter.max_price}
                  onChange={(e) => setListingFilter(f => ({ ...f, max_price: e.target.value }))}
                  className="w-28 bg-brand-dark border border-brand-border rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-brand-orange"
                />
                <button onClick={loadListings} className="px-3 py-1.5 bg-brand-orange/10 text-brand-orange text-xs rounded-lg hover:bg-brand-orange/20 transition-colors">
                  Найти
                </button>
              </div>

              {/* Listings grid */}
              {listings.length > 0 ? (
                <div className="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto pr-1">
                  {listings.map(l => (
                    <button
                      key={l.id}
                      onClick={() => setSelectedListing(l)}
                      className={`text-left p-3 rounded-lg border transition-all ${
                        selectedListing?.id === l.id
                          ? 'border-brand-orange bg-brand-orange/10'
                          : 'border-brand-border bg-brand-darker hover:border-brand-orange/40'
                      }`}
                    >
                      <div className="flex gap-2">
                        {l.photos?.[0] && (
                          <img src={l.photos[0]} alt="" className="w-12 h-15 object-cover rounded-md flex-shrink-0" />
                        )}
                        <div className="min-w-0">
                          <div className="text-white text-xs font-medium truncate">{l.complex_name || l.title || 'Объект'}</div>
                          <div className="text-[10px] text-gray-500 mt-0.5">
                            {l.rooms && `${l.rooms}-комн • `}{l.area_total && `${l.area_total} м² • `}{l.district || ''}
                          </div>
                          {l.price && (
                            <div className="text-xs text-brand-orange font-medium mt-0.5">
                              {Number(l.price).toLocaleString('ru-RU')} ₽
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center justify-between mt-1">
                        {l.carousel_generated && (
                          <span className="text-[9px] bg-green-500/10 text-green-400 px-1.5 py-0.5 rounded inline-block">Карусель создана</span>
                        )}
                        <button onClick={(e) => handleDeleteListing(e, l.id)}
                          className="ml-auto text-gray-600 hover:text-red-400 transition-colors p-0.5" title="Удалить">
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-gray-600 text-xs">
                  {loadingListings ? 'Загрузка...' : 'Нет сохранённых объявлений. Загрузите с CIAN выше.'}
                </div>
              )}
            </div>

            {/* ─── Lead Magnet (shared) ─── */}
            <div className="p-4 bg-brand-dark border border-brand-border rounded-xl">
              <div className="flex items-center gap-2 mb-3">
                <Magnet size={16} className="text-brand-orange" />
                <span className="text-sm font-medium text-white">Последний слайд</span>
                <span className="text-[10px] text-gray-500 ml-auto">Сохраняется между генерациями</span>
              </div>
              <div className="mb-3">
                <label className="block text-xs text-gray-500 mb-1">Призыв к действию</label>
                <textarea
                  value={ctaFinal}
                  onChange={(e) => setCtaFinal(e.target.value)}
                  rows={2}
                  className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange transition-colors resize-none"
                  placeholder="Напиши + в комментариях для подробностей"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Лид-магнит</label>
                <textarea
                  value={leadMagnet}
                  onChange={(e) => setLeadMagnet(e.target.value)}
                  rows={3}
                  className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange transition-colors resize-none"
                  placeholder='Напиши "ХОЧУ" — получишь бесплатную консультацию!'
                />
              </div>
            </div>
          </>
        )}

        {/* Generate button */}
        <button
          onClick={handleGenerate}
          disabled={generating || (tab === 'property' && !selectedListing)}
          className="mt-5 bg-brand-orange hover:bg-orange-600 text-white font-semibold py-3 px-8 rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
        >
          {generating ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              Генерация...
            </>
          ) : tab === 'property' ? (
            <>
              <Building2 size={18} />
              Сгенерировать карусель
            </>
          ) : (
            <>
              <Sparkles size={18} />
              Сгенерировать
            </>
          )}
        </button>

        {generating && (
          <GenerationProgress
            step={progressStep}
            currentStep={progressCurrent}
            totalSteps={progressTotal}
            mode={tab}
          />
        )}

        {/* Error */}
        {result?.error && (
          <div className="mt-4 p-4 rounded-lg bg-red-900/20 border border-red-500/30">
            <p className="text-red-400 text-sm">{result.error}</p>
          </div>
        )}

        {/* Quality badge + Slide Preview */}
        {result?.slides && result.slides.length > 0 && (
          <>
            <div className="mt-4 flex items-center gap-4">
              <QualityBadge score={result.quality_score} rounds={result.generation_rounds} />
              {result.message && (
                <span className="text-green-400 text-sm flex items-center gap-1">
                  <Check size={14} />
                  {result.message}
                </span>
              )}
            </div>

            <SlidePreview
              slides={result.slides}
              caption={result.caption}
              hashtags={result.hashtags}
            />

            {/* Publish result */}
            {publishResult?.success && (
              <div className="mt-4 p-4 rounded-lg bg-green-900/20 border border-green-500/30">
                {publishResult.scheduled ? (
                  <p className="text-green-400 text-sm flex items-center gap-2">
                    <Clock size={16} />
                    {publishResult.message}
                  </p>
                ) : (
                  <div>
                    <p className="text-green-400 text-sm flex items-center gap-2 mb-2">
                      <Check size={16} />
                      {publishResult.message}
                    </p>
                    {publishResult.url && (
                      <a
                        href={publishResult.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-brand-orange text-sm hover:underline flex items-center gap-1"
                      >
                        <Instagram size={14} />
                        Открыть в Instagram
                      </a>
                    )}
                  </div>
                )}
              </div>
            )}
            {publishResult?.error && (
              <div className="mt-4 p-4 rounded-lg bg-red-900/20 border border-red-500/30">
                <p className="text-red-400 text-sm">{publishResult.error}</p>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-3 mt-6 pt-4 border-t border-brand-border flex-wrap">
              <button
                onClick={() => navigate(`/editor/${result.carousel_id}`)}
                className="flex items-center gap-2 px-4 py-2 bg-brand-orange/10 border border-brand-orange/30 text-brand-orange rounded-lg hover:bg-brand-orange/20 text-sm transition-colors font-medium"
              >
                <Pencil size={14} />
                Редактировать
              </button>

              <button
                onClick={handleGenerate}
                className="flex items-center gap-2 px-4 py-2 border border-brand-border text-gray-300 rounded-lg hover:bg-white/5 text-sm transition-colors"
              >
                <RefreshCw size={14} />
                Перегенерировать
              </button>

              {/* Schedule button */}
              <button
                onClick={() => setShowSchedule(!showSchedule)}
                disabled={!selectedAccount || publishResult?.success}
                className={`flex items-center gap-2 px-4 py-2 border text-sm rounded-lg transition-colors ${
                  showSchedule
                    ? 'border-brand-orange text-brand-orange bg-brand-orange/10'
                    : 'border-brand-border text-gray-300 hover:bg-white/5'
                } disabled:opacity-40`}
              >
                <Clock size={14} />
                Запланировать
              </button>

              {/* Publish NOW button */}
              <button
                onClick={handlePublishNow}
                disabled={publishing || !selectedAccount || publishResult?.success}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm transition-colors disabled:opacity-40"
              >
                {publishing ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Публикация...
                  </>
                ) : (
                  <>
                    <Send size={14} />
                    Опубликовать сейчас
                  </>
                )}
              </button>

              <button className="flex items-center gap-2 px-4 py-2 border border-brand-border text-gray-300 rounded-lg hover:bg-white/5 text-sm transition-colors ml-auto">
                <Download size={14} />
                Скачать слайды
              </button>
            </div>

            {/* Music picker */}
            {selectedAccount && !publishResult?.success && (
              <div className="mt-3">
                <MusicPicker
                  selectedMusic={musicQuery}
                  onSelect={setMusicQuery}
                />
              </div>
            )}

            {/* No account warning */}
            {!selectedAccount && (
              <div className="mt-3 flex items-center gap-2 px-3 py-2 rounded-lg bg-yellow-900/10 border border-yellow-500/20">
                <Instagram size={14} className="text-yellow-400" />
                <span className="text-xs text-yellow-400">
                  Выберите Instagram аккаунт в шапке, чтобы публиковать
                </span>
              </div>
            )}

            {/* Schedule picker */}
            {showSchedule && selectedAccount && (
              <div className="mt-4 p-4 rounded-lg bg-brand-darker border border-brand-border">
                <h4 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
                  <Clock size={14} className="text-brand-orange" />
                  Запланировать публикацию в @{selectedAccount.username}
                </h4>
                <div className="flex gap-3 items-end">
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Дата</label>
                    <input
                      type="date"
                      value={scheduleDate}
                      onChange={(e) => setScheduleDate(e.target.value)}
                      className="bg-brand-dark border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-500 mb-1">Время (МСК)</label>
                    <input
                      type="time"
                      value={scheduleTime}
                      onChange={(e) => setScheduleTime(e.target.value)}
                      className="bg-brand-dark border border-brand-border rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-brand-orange"
                    />
                  </div>
                  <button
                    onClick={handleSchedule}
                    disabled={scheduling || !scheduleDate}
                    className="bg-brand-orange hover:bg-orange-600 text-white font-medium py-2 px-5 rounded-lg text-sm transition-colors disabled:opacity-40 flex items-center gap-2"
                  >
                    {scheduling ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        Планирование...
                      </>
                    ) : (
                      <>
                        <Clock size={14} />
                        Запланировать
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
