import React, { useState, useEffect, useRef } from 'react'
import {
  Palette, Type, Layout, Maximize2, ImageIcon, Sticker, Info,
  Layers, ChevronLeft, ChevronRight, Check, Upload, Loader2,
  Wand2, Save, Sparkles, X
} from 'lucide-react'
import api from '../api/client'
import { useToast } from '../contexts/ToastContext'
import { useAccount } from '../contexts/AccountContext'
import { useNavigate } from 'react-router-dom'

// ═══════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════

const TABS = [
  { id: 'templates', icon: Layers, label: 'Шаблоны' },
  { id: 'background', icon: Palette, label: 'Фон' },
  { id: 'typography', icon: Type, label: 'Типограф.' },
  { id: 'layout', icon: Layout, label: 'Макет' },
  { id: 'size', icon: Maximize2, label: 'Размер' },
  { id: 'photo', icon: ImageIcon, label: 'Фото' },
  { id: 'stickers', icon: Sticker, label: 'Стикеры' },
  { id: 'info', icon: Info, label: 'Инфо' },
]

const SIZE_PRESETS = [
  { w: 1080, h: 1350, label: '4:5', desc: 'Instagram' },
  { w: 1080, h: 1080, label: '1:1', desc: 'Квадрат' },
  { w: 1080, h: 1920, label: '9:16', desc: 'Stories' },
]

const FONT_PAIRINGS = [
  { id: 'luxury', name: 'Люкс' },
  { id: 'modern_clean', name: 'Современный' },
  { id: 'elegant_serif', name: 'Элегантный' },
  { id: 'bold_impact', name: 'Жирный' },
  { id: 'minimal_light', name: 'Минимализм' },
  { id: 'business_pro', name: 'Бизнес' },
  { id: 'editorial', name: 'Редакторский' },
  { id: 'gothic', name: 'Готика' },
]

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════

export default function Templates() {
  const toast = useToast()
  const navigate = useNavigate()
  const { selectedAccount } = useAccount()

  const [activeTab, setActiveTab] = useState('templates')
  const [templates, setTemplates] = useState([])
  const [stickers, setStickers] = useState([])
  const [carousels, setCarousels] = useState([])
  const [selectedCarousel, setSelectedCarousel] = useState(null)
  const [selectedSlideIdx, setSelectedSlideIdx] = useState(0)
  const [saving, setSaving] = useState(false)
  const [loading, setLoading] = useState(true)

  // Design settings state
  const [settings, setSettings] = useState({
    template_id: 'expert',
    bg_type: 'template',
    bg_color: '#0a0a0a',
    bg_gradient_start: '#0a0a0a',
    bg_gradient_end: '#1a1a2e',
    font_pairing: 'luxury',
    title_size: 62,
    body_size: 36,
    text_color: '#ffffff',
    accent_color: '#d4a853',
    text_position: 'bottom',
    image_position: 'top',
    avatar_placement: 'middle',
    canvas_width: 1080,
    canvas_height: 1350,
    photo_type: 'expert',
  })

  // Load data on mount
  useEffect(() => {
    Promise.all([
      api.get('/design-settings').catch(() => ({ data: {} })),
      api.get('/design-settings/templates').catch(() => ({ data: [] })),
      api.get('/design-settings/stickers').catch(() => ({ data: [] })),
      api.get('/carousels?status=ready&limit=20').catch(() => ({ data: [] })),
    ]).then(([settingsRes, templatesRes, stickersRes, carouselsRes]) => {
      if (settingsRes.data && settingsRes.data.template_id) {
        setSettings(prev => ({ ...prev, ...settingsRes.data }))
      }
      setTemplates(templatesRes.data || [])
      setStickers(stickersRes.data || [])
      const carouselList = Array.isArray(carouselsRes.data) ? carouselsRes.data : []
      setCarousels(carouselList)
      if (carouselList.length > 0) {
        setSelectedCarousel(carouselList[0])
      }
      setLoading(false)
    })
  }, [])

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.put('/design-settings', settings)
      toast.success('Настройки дизайна сохранены')
    } catch (err) {
      toast.error('Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  const slides = selectedCarousel?.slides || []
  const currentSlide = slides[selectedSlideIdx]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="animate-spin text-brand-orange" size={32} />
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden">
      {/* ── MAIN CONTENT AREA ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-brand-border">
          <div>
            <h1 className="text-xl font-bold text-white">Дизайн слайдов</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Настройте внешний вид ваших каруселей
            </p>
          </div>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-orange text-white rounded-xl font-medium hover:bg-orange-600 transition-colors disabled:opacity-50"
          >
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Сохранить
          </button>
        </div>

        {/* Slide Preview Area */}
        <div className="flex-1 flex items-center justify-center p-6 bg-brand-darker overflow-hidden">
          {currentSlide ? (
            <div className="relative">
              <img
                src={currentSlide.image_path}
                alt={`Слайд ${selectedSlideIdx + 1}`}
                className="max-h-[65vh] rounded-xl shadow-2xl"
                style={{ aspectRatio: `${settings.canvas_width}/${settings.canvas_height}` }}
              />
            </div>
          ) : (
            <div className="text-center text-gray-600">
              <Layers size={48} className="mx-auto mb-3 opacity-30" />
              <p>Выберите карусель для редактирования</p>
            </div>
          )}
        </div>

        {/* Horizontal Slide Strip */}
        <div className="border-t border-brand-border bg-brand-dark">
          <div className="flex items-center gap-3 px-4 py-3 overflow-x-auto scrollbar-thin">
            {slides.map((slide, idx) => (
              <button
                key={idx}
                onClick={() => setSelectedSlideIdx(idx)}
                className={`flex-shrink-0 rounded-lg overflow-hidden border-2 transition-all ${
                  idx === selectedSlideIdx
                    ? 'border-brand-orange shadow-lg shadow-brand-orange/20 scale-105'
                    : 'border-brand-border hover:border-gray-500'
                }`}
              >
                <img
                  src={slide.image_path}
                  alt={`Слайд ${idx + 1}`}
                  className="w-[80px] h-[100px] object-cover"
                />
              </button>
            ))}
            {slides.length === 0 && carousels.length > 0 && (
              <p className="text-xs text-gray-600 px-2">Выберите карусель ниже</p>
            )}
          </div>

          {/* Carousel Selector */}
          {carousels.length > 1 && (
            <div className="flex items-center gap-2 px-4 pb-3 overflow-x-auto">
              {carousels.map((c, idx) => (
                <button
                  key={c.id}
                  onClick={() => { setSelectedCarousel(c); setSelectedSlideIdx(0) }}
                  className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-xs transition-colors ${
                    selectedCarousel?.id === c.id
                      ? 'bg-brand-orange/20 text-brand-orange border border-brand-orange/40'
                      : 'bg-brand-card text-gray-400 border border-brand-border hover:text-white'
                  }`}
                >
                  {(c.slides?.[0]?.text_overlay || `Карусель ${idx + 1}`).slice(0, 30)}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── RIGHT SIDEBAR — SETTINGS TABS ── */}
      <div className="w-[320px] flex-shrink-0 border-l border-brand-border bg-brand-dark flex">
        {/* Tab Icons */}
        <div className="w-[72px] flex-shrink-0 border-r border-brand-border bg-brand-darker flex flex-col pt-2">
          {TABS.map(tab => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex flex-col items-center gap-1 py-3 px-1 transition-colors ${
                  active
                    ? 'text-brand-orange bg-brand-orange/10'
                    : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                <Icon size={20} />
                <span className="text-[10px] leading-tight">{tab.label}</span>
              </button>
            )
          })}
        </div>

        {/* Tab Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === 'templates' && (
            <TemplatesTab
              templates={templates}
              selected={settings.template_id}
              onSelect={(id) => updateSetting('template_id', id)}
            />
          )}
          {activeTab === 'background' && (
            <BackgroundTab settings={settings} onChange={updateSetting} />
          )}
          {activeTab === 'typography' && (
            <TypographyTab settings={settings} onChange={updateSetting} />
          )}
          {activeTab === 'layout' && (
            <LayoutTab settings={settings} onChange={updateSetting} />
          )}
          {activeTab === 'size' && (
            <SizeTab settings={settings} onChange={updateSetting} />
          )}
          {activeTab === 'photo' && (
            <PhotoTab settings={settings} onChange={updateSetting} />
          )}
          {activeTab === 'stickers' && (
            <StickersTab stickers={stickers} />
          )}
          {activeTab === 'info' && (
            <InfoTab slide={currentSlide} carousel={selectedCarousel} />
          )}
        </div>
      </div>
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════
// TAB PANELS
// ═══════════════════════════════════════════════════════════════

function TemplatesTab({ templates, selected, onSelect }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-white mb-3">Встроенные шаблоны</h3>
      <p className="text-xs text-gray-500 mb-4">
        Выберите готовый шаблон оформления для ваших слайдов.
      </p>
      <div className="grid grid-cols-2 gap-2">
        {templates.map(t => (
          <button
            key={t.id}
            onClick={() => onSelect(t.id)}
            className={`relative rounded-xl overflow-hidden border-2 transition-all text-left ${
              selected === t.id
                ? 'border-brand-orange shadow-lg shadow-brand-orange/20'
                : 'border-brand-border hover:border-gray-500'
            }`}
          >
            {/* Color preview */}
            <div
              className="h-20 flex items-end p-2"
              style={{ backgroundColor: t.bg }}
            >
              <div className="flex flex-col gap-0.5">
                <span
                  className="text-[11px] font-bold leading-tight"
                  style={{ color: t.text }}
                >
                  СОЗДАВАЙ
                </span>
                <span
                  className="text-[9px] px-1 rounded"
                  style={{
                    backgroundColor: t.accent,
                    color: t.bg,
                  }}
                >
                  {t.name}
                </span>
              </div>
            </div>
            <div className="px-2 py-1.5 bg-brand-card">
              <span className="text-[11px] text-gray-300">{t.name}</span>
            </div>
            {selected === t.id && (
              <div className="absolute top-1.5 right-1.5 w-5 h-5 bg-brand-orange rounded-full flex items-center justify-center">
                <Check size={12} className="text-white" />
              </div>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}


function BackgroundTab({ settings, onChange }) {
  const fileRef = useRef(null)
  const [uploading, setUploading] = useState(false)

  const bgOptions = [
    { value: 'template', label: 'Из шаблона' },
    { value: 'ai', label: 'AI генерация' },
    { value: 'upload', label: 'Загрузить' },
    { value: 'solid', label: 'Цвет' },
    { value: 'gradient', label: 'Градиент' },
  ]

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await api.post('/design-settings/upload-bg', form)
      onChange('bg_upload_path', res.data.path)
      onChange('bg_type', 'upload')
    } catch (err) {
      console.error(err)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white">Фон</h3>

      <div className="space-y-2">
        {bgOptions.map(opt => (
          <button
            key={opt.value}
            onClick={() => onChange('bg_type', opt.value)}
            className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-colors ${
              settings.bg_type === opt.value
                ? 'bg-brand-orange/15 text-brand-orange border border-brand-orange/40'
                : 'bg-brand-card text-gray-400 border border-brand-border hover:text-white'
            }`}
          >
            {opt.value === 'ai' && <Sparkles size={14} className="inline mr-2" />}
            {opt.label}
          </button>
        ))}
      </div>

      {settings.bg_type === 'solid' && (
        <div className="space-y-2">
          <label className="text-xs text-gray-500">Цвет фона</label>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={settings.bg_color}
              onChange={(e) => onChange('bg_color', e.target.value)}
              className="w-10 h-10 rounded-lg border border-brand-border cursor-pointer"
            />
            <input
              type="text"
              value={settings.bg_color}
              onChange={(e) => onChange('bg_color', e.target.value)}
              className="flex-1 bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-sm text-white"
            />
          </div>
        </div>
      )}

      {settings.bg_type === 'gradient' && (
        <div className="space-y-2">
          <label className="text-xs text-gray-500">Градиент</label>
          <div className="flex gap-2">
            <div className="flex-1">
              <input
                type="color"
                value={settings.bg_gradient_start || '#0a0a0a'}
                onChange={(e) => onChange('bg_gradient_start', e.target.value)}
                className="w-full h-8 rounded border border-brand-border cursor-pointer"
              />
              <span className="text-[10px] text-gray-600">Начало</span>
            </div>
            <div className="flex-1">
              <input
                type="color"
                value={settings.bg_gradient_end || '#1a1a2e'}
                onChange={(e) => onChange('bg_gradient_end', e.target.value)}
                className="w-full h-8 rounded border border-brand-border cursor-pointer"
              />
              <span className="text-[10px] text-gray-600">Конец</span>
            </div>
          </div>
        </div>
      )}

      {settings.bg_type === 'upload' && (
        <div>
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-brand-border rounded-xl text-sm text-gray-400 hover:border-brand-orange hover:text-brand-orange transition-colors"
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            {uploading ? 'Загрузка...' : 'Загрузить изображение'}
          </button>
          <input ref={fileRef} type="file" accept="image/*" onChange={handleUpload} className="hidden" />
          {settings.bg_upload_path && (
            <p className="text-xs text-green-400 mt-2">Фон загружен</p>
          )}
        </div>
      )}
    </div>
  )
}


function TypographyTab({ settings, onChange }) {
  return (
    <div className="space-y-5">
      <h3 className="text-sm font-semibold text-white">Типографика</h3>

      {/* Font family */}
      <div>
        <label className="text-xs text-gray-500 mb-1.5 block">Шрифт</label>
        <div className="grid grid-cols-2 gap-1.5">
          {FONT_PAIRINGS.map(fp => (
            <button
              key={fp.id}
              onClick={() => onChange('font_pairing', fp.id)}
              className={`px-2.5 py-2 rounded-lg text-xs transition-colors ${
                settings.font_pairing === fp.id
                  ? 'bg-brand-orange/15 text-brand-orange border border-brand-orange/40'
                  : 'bg-brand-card text-gray-400 border border-brand-border hover:text-white'
              }`}
            >
              {fp.name}
            </button>
          ))}
        </div>
      </div>

      {/* Title size */}
      <div>
        <label className="text-xs text-gray-500 mb-1.5 flex justify-between">
          <span>Размер заголовка</span>
          <span className="text-gray-600">{settings.title_size}px</span>
        </label>
        <input
          type="range" min={32} max={80} value={settings.title_size}
          onChange={(e) => onChange('title_size', parseInt(e.target.value))}
          className="w-full accent-brand-orange"
        />
      </div>

      {/* Body size */}
      <div>
        <label className="text-xs text-gray-500 mb-1.5 flex justify-between">
          <span>Размер текста</span>
          <span className="text-gray-600">{settings.body_size}px</span>
        </label>
        <input
          type="range" min={20} max={48} value={settings.body_size}
          onChange={(e) => onChange('body_size', parseInt(e.target.value))}
          className="w-full accent-brand-orange"
        />
      </div>

      {/* Text color */}
      <div>
        <label className="text-xs text-gray-500 mb-1.5 block">Цвет текста</label>
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={settings.text_color}
            onChange={(e) => onChange('text_color', e.target.value)}
            className="w-8 h-8 rounded border border-brand-border cursor-pointer"
          />
          <input
            type="text" value={settings.text_color}
            onChange={(e) => onChange('text_color', e.target.value)}
            className="flex-1 bg-brand-card border border-brand-border rounded-lg px-3 py-1.5 text-xs text-white"
          />
        </div>
      </div>

      {/* Accent color — PROMINENT */}
      <div className="p-3 rounded-xl bg-brand-orange/5 border border-brand-orange/20">
        <label className="text-xs text-brand-orange font-medium mb-2 block">Акцентный цвет</label>
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={settings.accent_color}
            onChange={(e) => onChange('accent_color', e.target.value)}
            className="w-10 h-10 rounded-lg border border-brand-orange/40 cursor-pointer"
          />
          <div className="flex-1">
            <input
              type="text" value={settings.accent_color}
              onChange={(e) => onChange('accent_color', e.target.value)}
              className="w-full bg-brand-card border border-brand-border rounded-lg px-3 py-1.5 text-xs text-white"
            />
            <p className="text-[10px] text-gray-600 mt-1">Выделенные слова в заголовках</p>
          </div>
        </div>
        {/* Preview of accent */}
        <div className="mt-2 px-3 py-1.5 rounded-lg" style={{ backgroundColor: settings.accent_color }}>
          <span className="text-xs font-bold" style={{ color: settings.text_color }}>ПРИМЕР *АКЦЕНТА*</span>
        </div>
      </div>
    </div>
  )
}


function LayoutTab({ settings, onChange }) {
  const positions = [
    { value: 'top', label: 'Сверху' },
    { value: 'center', label: 'Центр' },
    { value: 'bottom', label: 'Снизу' },
  ]

  const imagePositions = [
    { value: 'top', label: 'Сверху' },
    { value: 'center', label: 'Центр' },
    { value: 'full', label: 'На весь' },
  ]

  const avatarOptions = [
    { value: 'top', label: 'Сверху' },
    { value: 'middle', label: 'Середина' },
    { value: 'bottom', label: 'Снизу' },
    { value: 'none', label: 'Нет' },
  ]

  return (
    <div className="space-y-5">
      <h3 className="text-sm font-semibold text-white">Макет</h3>

      <div>
        <label className="text-xs text-gray-500 mb-2 block">Позиция текста</label>
        <div className="flex gap-1.5">
          {positions.map(p => (
            <button
              key={p.value}
              onClick={() => onChange('text_position', p.value)}
              className={`flex-1 py-2 rounded-lg text-xs text-center transition-colors ${
                settings.text_position === p.value
                  ? 'bg-brand-orange/15 text-brand-orange border border-brand-orange/40'
                  : 'bg-brand-card text-gray-400 border border-brand-border'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-gray-500 mb-2 block">Позиция изображения</label>
        <div className="flex gap-1.5">
          {imagePositions.map(p => (
            <button
              key={p.value}
              onClick={() => onChange('image_position', p.value)}
              className={`flex-1 py-2 rounded-lg text-xs text-center transition-colors ${
                settings.image_position === p.value
                  ? 'bg-brand-orange/15 text-brand-orange border border-brand-orange/40'
                  : 'bg-brand-card text-gray-400 border border-brand-border'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-gray-500 mb-2 block">Аватар</label>
        <div className="grid grid-cols-2 gap-1.5">
          {avatarOptions.map(p => (
            <button
              key={p.value}
              onClick={() => onChange('avatar_placement', p.value)}
              className={`py-2 rounded-lg text-xs text-center transition-colors ${
                settings.avatar_placement === p.value
                  ? 'bg-brand-orange/15 text-brand-orange border border-brand-orange/40'
                  : 'bg-brand-card text-gray-400 border border-brand-border'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}


function SizeTab({ settings, onChange }) {
  const currentPreset = SIZE_PRESETS.find(
    p => p.w === settings.canvas_width && p.h === settings.canvas_height
  )

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white">Размер</h3>

      <div className="space-y-2">
        {SIZE_PRESETS.map(preset => (
          <button
            key={preset.label}
            onClick={() => {
              onChange('canvas_width', preset.w)
              onChange('canvas_height', preset.h)
            }}
            className={`w-full flex items-center justify-between px-4 py-3 rounded-xl border transition-colors ${
              currentPreset?.label === preset.label
                ? 'bg-brand-orange/15 text-brand-orange border-brand-orange/40'
                : 'bg-brand-card text-gray-400 border-brand-border hover:text-white'
            }`}
          >
            <div>
              <span className="text-sm font-medium">{preset.label}</span>
              <span className="text-xs text-gray-600 ml-2">{preset.desc}</span>
            </div>
            <span className="text-xs text-gray-600">{preset.w}x{preset.h}</span>
          </button>
        ))}
      </div>
    </div>
  )
}


function PhotoTab({ settings, onChange }) {
  const photoOptions = [
    { value: 'expert', label: 'Фото эксперта', desc: 'Загруженное фото на подложке' },
    { value: 'ai', label: 'AI генерация', desc: 'NanoBanana генерирует фон по теме' },
    { value: 'upload', label: 'Загрузить', desc: 'Свой фон для всех слайдов' },
    { value: 'none', label: 'Без фото', desc: 'Только цвет/градиент' },
  ]

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white">Фото</h3>
      <div className="space-y-2">
        {photoOptions.map(opt => (
          <button
            key={opt.value}
            onClick={() => onChange('photo_type', opt.value)}
            className={`w-full text-left px-4 py-3 rounded-xl border transition-colors ${
              settings.photo_type === opt.value
                ? 'bg-brand-orange/15 text-brand-orange border-brand-orange/40'
                : 'bg-brand-card text-gray-400 border-brand-border hover:text-white'
            }`}
          >
            <div className="text-sm font-medium">{opt.label}</div>
            <div className="text-xs text-gray-600 mt-0.5">{opt.desc}</div>
          </button>
        ))}
      </div>
    </div>
  )
}


function StickersTab({ stickers }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white">Стикеры</h3>
      <p className="text-xs text-gray-500">Нажмите на стикер чтобы добавить на слайд.</p>

      {stickers.length === 0 ? (
        <div className="text-center py-8 text-gray-600">
          <Sticker size={32} className="mx-auto mb-2 opacity-30" />
          <p className="text-xs">Стикеры пока не загружены</p>
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-2">
          {stickers.map(s => (
            <button
              key={s.id}
              className="aspect-square rounded-lg bg-brand-card border border-brand-border hover:border-brand-orange transition-colors p-1.5 flex items-center justify-center"
              title={s.name}
            >
              <img src={s.path} alt={s.name} className="w-full h-full object-contain" />
            </button>
          ))}
        </div>
      )}
    </div>
  )
}


function InfoTab({ slide, carousel }) {
  if (!slide) {
    return (
      <div className="text-center py-8 text-gray-600">
        <Info size={32} className="mx-auto mb-2 opacity-30" />
        <p className="text-xs">Выберите слайд</p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white">Информация</h3>

      <div>
        <label className="text-xs text-gray-500 mb-1 block">Заголовок</label>
        <div className="bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-sm text-white">
          {slide.text_overlay || '-'}
        </div>
      </div>

      <div>
        <label className="text-xs text-gray-500 mb-1 block">Текст</label>
        <div className="bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-sm text-gray-300 min-h-[60px]">
          {slide.body || '-'}
        </div>
      </div>

      {carousel?.caption && (
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Описание</label>
          <div className="bg-brand-card border border-brand-border rounded-lg px-3 py-2 text-xs text-gray-400 max-h-40 overflow-y-auto">
            {carousel.caption}
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 text-xs text-gray-600">
        <span>Слайд {slide.slide_number}</span>
        {carousel?.generation_params?.color_scheme && (
          <span className="px-1.5 py-0.5 bg-brand-dark rounded text-gray-500">
            {carousel.generation_params.color_scheme}
          </span>
        )}
      </div>
    </div>
  )
}
