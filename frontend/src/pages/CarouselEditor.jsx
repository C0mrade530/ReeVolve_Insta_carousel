import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ChevronLeft, ChevronRight, Save, RefreshCw, ArrowUp, ArrowDown,
  Trash2, Type, Image, Loader2, Check, X, Copy, Eye, Undo2,
  GripVertical, Pencil, Sparkles, ArrowLeft, Clock, Send, Instagram,
} from 'lucide-react'
import api from '../api/client'
import { useAccount } from '../contexts/AccountContext'
import MusicPicker from '../components/MusicPicker'

/* ─── Slide Editor Panel ─── */
function SlideEditor({ slide, index, total, onUpdate, onRegenerate, onMoveUp, onMoveDown, onDelete, regenerating }) {
  const [editTitle, setEditTitle] = useState(slide.text_overlay || '')
  const [editBody, setEditBody] = useState(slide.body || '')
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    setEditTitle(slide.text_overlay || '')
    setEditBody(slide.body || '')
    setDirty(false)
  }, [slide])

  const handleTitleChange = (val) => {
    setEditTitle(val)
    setDirty(true)
  }

  const handleBodyChange = (val) => {
    setEditBody(val)
    setDirty(true)
  }

  const handleSaveText = () => {
    onUpdate(index, { text_overlay: editTitle, body: editBody })
    setDirty(false)
  }

  const isFirst = index === 0
  const isLast = index === total - 1

  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <GripVertical size={14} className="text-gray-600" />
          <span className="text-sm font-medium text-white">
            Слайд {index + 1}
            {isFirst && <span className="text-xs text-brand-orange ml-2">обложка</span>}
            {isLast && <span className="text-xs text-purple-400 ml-2">CTA</span>}
          </span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onMoveUp(index)}
            disabled={isFirst}
            className="p-1.5 text-gray-500 hover:text-white disabled:opacity-20 transition-colors"
            title="Переместить вверх"
          >
            <ArrowUp size={14} />
          </button>
          <button
            onClick={() => onMoveDown(index)}
            disabled={isLast}
            className="p-1.5 text-gray-500 hover:text-white disabled:opacity-20 transition-colors"
            title="Переместить вниз"
          >
            <ArrowDown size={14} />
          </button>
          {total > 2 && !isFirst && !isLast && (
            <button
              onClick={() => onDelete(index)}
              className="p-1.5 text-gray-500 hover:text-red-400 transition-colors"
              title="Удалить слайд"
            >
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {/* Title */}
      <div className="mb-3">
        <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
          Заголовок
        </label>
        <input
          type="text"
          value={editTitle}
          onChange={(e) => handleTitleChange(e.target.value)}
          className="w-full bg-brand-dark border border-brand-border rounded-lg px-3 py-2
                     text-white text-sm focus:outline-none focus:border-brand-orange transition-colors"
          placeholder="Заголовок слайда"
        />
      </div>

      {/* Body */}
      <div className="mb-3">
        <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
          Текст
        </label>
        <textarea
          value={editBody}
          onChange={(e) => handleBodyChange(e.target.value)}
          rows={3}
          className="w-full bg-brand-dark border border-brand-border rounded-lg px-3 py-2
                     text-white text-sm focus:outline-none focus:border-brand-orange transition-colors resize-none"
          placeholder="Основной текст слайда"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        {dirty && (
          <button
            onClick={handleSaveText}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-orange hover:bg-orange-600
                       text-white text-xs font-medium rounded-lg transition-colors"
          >
            <Check size={12} />
            Применить текст
          </button>
        )}
        <button
          onClick={() => onRegenerate(index)}
          disabled={regenerating}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-brand-border
                     text-gray-400 hover:text-white hover:border-brand-orange/40
                     text-xs rounded-lg transition-colors disabled:opacity-40"
        >
          {regenerating ? (
            <Loader2 size={12} className="animate-spin" />
          ) : (
            <Sparkles size={12} />
          )}
          Перегенерировать слайд
        </button>
      </div>
    </div>
  )
}

/* ─── Caption Editor ─── */
function CaptionEditor({ caption, hashtags, onChange }) {
  const [editCaption, setEditCaption] = useState(caption || '')
  const [editHashtags, setEditHashtags] = useState(hashtags || '')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setEditCaption(caption || '')
    setEditHashtags(hashtags || '')
  }, [caption, hashtags])

  const handleCopy = () => {
    navigator.clipboard.writeText(editCaption + '\n\n' + editHashtags)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleBlur = () => {
    if (editCaption !== caption || editHashtags !== hashtags) {
      onChange({ caption: editCaption, hashtags: editHashtags })
    }
  }

  return (
    <div className="bg-brand-card border border-brand-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-white flex items-center gap-2">
          <Pencil size={14} className="text-brand-orange" />
          Подпись к посту
        </h3>
        <button
          onClick={handleCopy}
          className="text-xs text-brand-orange hover:text-orange-400 flex items-center gap-1 transition-colors"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Скопировано' : 'Копировать'}
        </button>
      </div>

      <textarea
        value={editCaption}
        onChange={(e) => setEditCaption(e.target.value)}
        onBlur={handleBlur}
        rows={5}
        className="w-full bg-brand-dark border border-brand-border rounded-lg px-3 py-2.5
                   text-white text-sm focus:outline-none focus:border-brand-orange transition-colors resize-none mb-3"
        placeholder="Подпись к посту..."
      />

      <div>
        <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
          Хэштеги
        </label>
        <input
          type="text"
          value={editHashtags}
          onChange={(e) => setEditHashtags(e.target.value)}
          onBlur={handleBlur}
          className="w-full bg-brand-dark border border-brand-border rounded-lg px-3 py-2
                     text-brand-orange/80 text-sm focus:outline-none focus:border-brand-orange transition-colors"
          placeholder="#эксперт #контент"
        />
      </div>
    </div>
  )
}

/* ─── Slide Preview (large) ─── */
function SlideViewer({ slides, currentIndex, onSelect }) {
  if (!slides || slides.length === 0) return null

  const slide = slides[currentIndex]

  return (
    <div>
      {/* Main image */}
      <div className="relative group rounded-xl overflow-hidden bg-brand-darker border border-brand-border">
        <img
          src={slide.image_path}
          alt={`Слайд ${currentIndex + 1}`}
          className="w-full aspect-[4/5] object-cover"
        />
        {/* Navigation arrows */}
        <div className="absolute inset-0 flex items-center justify-between px-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => onSelect(Math.max(0, currentIndex - 1))}
            disabled={currentIndex === 0}
            className="bg-black/60 backdrop-blur-sm text-white rounded-full p-2.5 disabled:opacity-0 hover:bg-black/80 transition-all"
          >
            <ChevronLeft size={22} />
          </button>
          <button
            onClick={() => onSelect(Math.min(slides.length - 1, currentIndex + 1))}
            disabled={currentIndex === slides.length - 1}
            className="bg-black/60 backdrop-blur-sm text-white rounded-full p-2.5 disabled:opacity-0 hover:bg-black/80 transition-all"
          >
            <ChevronRight size={22} />
          </button>
        </div>
        {/* Slide counter */}
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 bg-black/70 backdrop-blur-sm text-white text-xs px-3 py-1.5 rounded-full">
          {currentIndex + 1} / {slides.length}
        </div>
      </div>

      {/* Thumbnail strip */}
      <div className="flex gap-2 mt-3 overflow-x-auto pb-1">
        {slides.map((s, i) => (
          <button
            key={i}
            onClick={() => onSelect(i)}
            className={`flex-shrink-0 rounded-lg overflow-hidden border-2 transition-all relative ${
              i === currentIndex
                ? 'border-brand-orange shadow-lg shadow-brand-orange/20 scale-105'
                : 'border-transparent opacity-50 hover:opacity-80'
            }`}
          >
            <img
              src={s.image_path}
              alt={`Thumb ${i + 1}`}
              className="w-14 h-[70px] object-cover"
            />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-[10px] font-bold text-white drop-shadow-lg">{i + 1}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

/* ─── Main Carousel Editor ─── */
export default function CarouselEditor() {
  const { carouselId } = useParams()
  const navigate = useNavigate()
  const { selectedAccount } = useAccount()

  const [carousel, setCarousel] = useState(null)
  const [slides, setSlides] = useState([])
  const [caption, setCaption] = useState('')
  const [hashtags, setHashtags] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [currentSlide, setCurrentSlide] = useState(0)
  const [regeneratingSlide, setRegeneratingSlide] = useState(null)
  const [publishing, setPublishing] = useState(false)
  const [publishResult, setPublishResult] = useState(null)
  const [hasChanges, setHasChanges] = useState(false)
  const [musicQuery, setMusicQuery] = useState(null)

  // Load carousel
  useEffect(() => {
    if (!carouselId) return
    setLoading(true)
    api.get(`/carousels/${carouselId}`)
      .then((r) => {
        setCarousel(r.data)
        setSlides(r.data.slides || [])
        setCaption(r.data.caption || '')
        setHashtags(r.data.hashtags || '')
      })
      .catch(() => navigate('/'))
      .finally(() => setLoading(false))
  }, [carouselId])

  // Save to backend
  const handleSave = useCallback(async () => {
    if (!carouselId) return
    setSaving(true)
    setSaved(false)
    try {
      await api.patch(`/carousels/${carouselId}`, {
        slides,
        caption,
        hashtags,
      })
      setSaved(true)
      setHasChanges(false)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      alert('Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }, [carouselId, slides, caption, hashtags])

  // Update slide text (doesn't regenerate image yet)
  const handleUpdateSlide = (index, updates) => {
    const newSlides = [...slides]
    newSlides[index] = { ...newSlides[index], ...updates }
    setSlides(newSlides)
    setHasChanges(true)
  }

  // Regenerate single slide image
  const handleRegenerateSlide = async (index) => {
    if (!carouselId) return
    setRegeneratingSlide(index)
    try {
      // First save current text changes
      const slide = slides[index]
      const res = await api.post(`/carousels/${carouselId}/regenerate-slide/${index + 1}`, {
        title: slide.text_overlay || '',
        body: slide.body || '',
      })

      if (res.data.image_path) {
        const newSlides = [...slides]
        newSlides[index] = {
          ...newSlides[index],
          image_path: res.data.image_path + '?t=' + Date.now(), // cache bust
        }
        setSlides(newSlides)
        setHasChanges(true)
      }
    } catch (e) {
      alert(e.response?.data?.detail || 'Ошибка перегенерации слайда')
    } finally {
      setRegeneratingSlide(null)
    }
  }

  // Move slide up/down
  const handleMoveUp = (index) => {
    if (index <= 0) return
    const newSlides = [...slides]
    ;[newSlides[index - 1], newSlides[index]] = [newSlides[index], newSlides[index - 1]]
    // Update slide_number
    newSlides.forEach((s, i) => (s.slide_number = i + 1))
    setSlides(newSlides)
    setCurrentSlide(index - 1)
    setHasChanges(true)
  }

  const handleMoveDown = (index) => {
    if (index >= slides.length - 1) return
    const newSlides = [...slides]
    ;[newSlides[index], newSlides[index + 1]] = [newSlides[index + 1], newSlides[index]]
    newSlides.forEach((s, i) => (s.slide_number = i + 1))
    setSlides(newSlides)
    setCurrentSlide(index + 1)
    setHasChanges(true)
  }

  // Delete slide
  const handleDeleteSlide = (index) => {
    if (slides.length <= 2) return
    const newSlides = slides.filter((_, i) => i !== index)
    newSlides.forEach((s, i) => (s.slide_number = i + 1))
    setSlides(newSlides)
    if (currentSlide >= newSlides.length) {
      setCurrentSlide(newSlides.length - 1)
    }
    setHasChanges(true)
  }

  // Caption change
  const handleCaptionChange = ({ caption: c, hashtags: h }) => {
    setCaption(c)
    setHashtags(h)
    setHasChanges(true)
  }

  // Publish
  const handlePublish = async () => {
    if (!selectedAccount || !carouselId) return
    // Save first if there are changes
    if (hasChanges) await handleSave()

    setPublishing(true)
    setPublishResult(null)
    try {
      const payload = { account_id: selectedAccount.id }
      if (musicQuery) {
        payload.music_query = musicQuery
      }
      const res = await api.post(`/carousels/${carouselId}/publish-now`, payload)
      setPublishResult({ success: true, ...res.data })
    } catch (e) {
      setPublishResult({ error: e.response?.data?.detail || 'Ошибка публикации' })
    } finally {
      setPublishing(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={32} className="text-brand-orange animate-spin" />
      </div>
    )
  }

  if (!carousel) {
    return (
      <div className="text-center py-20 text-gray-400">
        Карусель не найдена
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-2 text-gray-400 hover:text-white transition-colors"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            <h2 className="text-xl font-bold text-white">Редактор карусели</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {slides.length} слайдов · {carousel.type === 'topic' ? 'Тематическая' : 'Объект'}
              {carousel.status && (
                <span className={`ml-2 ${
                  carousel.status === 'published' ? 'text-green-400' :
                  carousel.status === 'scheduled' ? 'text-brand-orange' :
                  'text-gray-400'
                }`}>
                  · {carousel.status === 'published' ? 'Опубликована' :
                     carousel.status === 'scheduled' ? 'Запланирована' :
                     'Готова'}
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {hasChanges && (
            <span className="text-xs text-yellow-400 flex items-center gap-1">
              <Pencil size={10} />
              Есть изменения
            </span>
          )}

          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              saved
                ? 'bg-green-600 text-white'
                : hasChanges
                  ? 'bg-brand-orange hover:bg-orange-600 text-white'
                  : 'bg-brand-card border border-brand-border text-gray-500'
            } disabled:opacity-50`}
          >
            {saving ? (
              <Loader2 size={14} className="animate-spin" />
            ) : saved ? (
              <Check size={14} />
            ) : (
              <Save size={14} />
            )}
            {saving ? 'Сохранение...' : saved ? 'Сохранено!' : 'Сохранить'}
          </button>

          {carousel.status !== 'published' && (
            <button
              onClick={handlePublish}
              disabled={publishing || !selectedAccount}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700
                         text-white rounded-lg text-sm font-medium transition-colors disabled:opacity-40"
            >
              {publishing ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Send size={14} />
              )}
              Опубликовать
            </button>
          )}
        </div>
      </div>

      {/* Music picker — show before publish */}
      {carousel.status !== 'published' && selectedAccount && (
        <MusicPicker
          selectedMusic={musicQuery}
          onSelect={setMusicQuery}
        />
      )}

      {/* Publish result */}
      {publishResult && (
        <div className={`border rounded-lg px-4 py-3 text-sm ${
          publishResult.error
            ? 'bg-red-500/10 border-red-500/30 text-red-400'
            : 'bg-green-500/10 border-green-500/30 text-green-400'
        }`}>
          {publishResult.error || publishResult.message}
          {publishResult.url && (
            <a
              href={publishResult.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-3 text-brand-orange hover:underline"
            >
              Открыть в Instagram →
            </a>
          )}
        </div>
      )}

      {/* No account warning */}
      {!selectedAccount && carousel.status !== 'published' && (
        <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg bg-yellow-900/10 border border-yellow-500/20">
          <Instagram size={14} className="text-yellow-400" />
          <span className="text-xs text-yellow-400">
            Выберите Instagram аккаунт в шапке, чтобы публиковать
          </span>
        </div>
      )}

      {/* Horizontal slide strip */}
      <div className="bg-brand-card border border-brand-border rounded-xl p-3">
        <div className="flex items-center gap-3 overflow-x-auto pb-1 scrollbar-thin">
          {slides.map((slide, idx) => (
            <button
              key={idx}
              onClick={() => setCurrentSlide(idx)}
              className={`flex-shrink-0 rounded-lg overflow-hidden border-2 transition-all ${
                idx === currentSlide
                  ? 'border-brand-orange shadow-lg shadow-brand-orange/20 scale-105'
                  : 'border-brand-border hover:border-gray-500'
              }`}
            >
              <img
                src={slide.image_path}
                alt={`Слайд ${idx + 1}`}
                className="w-[72px] h-[90px] object-cover"
              />
              <div className="text-center py-0.5 bg-brand-dark">
                <span className={`text-[10px] ${idx === currentSlide ? 'text-brand-orange' : 'text-gray-500'}`}>
                  {idx + 1}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Main editor layout: preview left, editor right */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Large slide preview */}
        <div className="space-y-4">
          <SlideViewer
            slides={slides}
            currentIndex={currentSlide}
            onSelect={setCurrentSlide}
          />
        </div>

        {/* Right: Slide Editor + Caption */}
        <div className="space-y-4 max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
          <div className="relative">
            <div className="absolute -left-2 top-0 bottom-0 w-1 bg-brand-orange rounded-full" />
            <SlideEditor
              slide={slides[currentSlide]}
              index={currentSlide}
              total={slides.length}
              onUpdate={handleUpdateSlide}
              onRegenerate={handleRegenerateSlide}
              onMoveUp={handleMoveUp}
              onMoveDown={handleMoveDown}
              onDelete={handleDeleteSlide}
              regenerating={regeneratingSlide === currentSlide}
            />
          </div>

          {/* Caption Editor */}
          <CaptionEditor
            caption={caption}
            hashtags={hashtags}
            onChange={handleCaptionChange}
          />
        </div>
      </div>
    </div>
  )
}
