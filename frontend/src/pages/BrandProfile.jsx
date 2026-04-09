import React, { useState, useEffect, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import {
  Upload, FileText, Loader2, CheckCircle, AlertCircle,
  ChevronDown, ChevronUp, Pencil, Save, RefreshCw, Trash2,
  Target, Users, ShoppingBag, MessageSquare, Lightbulb, Fingerprint
} from 'lucide-react'
import api from '../api/client.js'
import { useToast } from '../contexts/ToastContext'

const ACCEPTED_TYPES = {
  'text/plain': ['.txt'],
  'text/markdown': ['.md'],
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
}

export default function BrandProfile() {
  const { addToast } = useToast()
  const [profiles, setProfiles] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [unpacking, setUnpacking] = useState(false)
  const [unpackProgress, setUnpackProgress] = useState(null)
  const [selectedProfile, setSelectedProfile] = useState(null)
  const [expandedSections, setExpandedSections] = useState({})
  const [editingSection, setEditingSection] = useState(null)
  const [editValue, setEditValue] = useState('')

  // Load profiles
  useEffect(() => {
    loadProfiles()
  }, [])

  const loadProfiles = async () => {
    try {
      const { data } = await api.get('/brand/profiles')
      setProfiles(data)
      if (data.length > 0 && !selectedProfile) {
        loadFullProfile(data[0].id)
      }
    } catch (e) {
      console.error('Failed to load profiles:', e)
    } finally {
      setLoading(false)
    }
  }

  const loadFullProfile = async (id) => {
    try {
      const { data } = await api.get(`/brand/profiles/${id}`)
      setSelectedProfile(data)
    } catch (e) {
      addToast('Ошибка загрузки профиля', 'error')
    }
  }

  // File upload
  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return
    setUploading(true)

    try {
      const formData = new FormData()
      acceptedFiles.forEach(f => formData.append('files', f))

      const { data } = await api.post('/brand/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      addToast(`Загружено ${data.files_processed} файлов (${(data.total_chars / 1000).toFixed(0)}K символов)`, 'success')

      // Auto-start unpacking
      await startUnpacking(data.id)
      await loadProfiles()
    } catch (e) {
      addToast('Ошибка загрузки файлов', 'error')
    } finally {
      setUploading(false)
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxFiles: 10,
    maxSize: 10 * 1024 * 1024,
  })

  // Unpacking via SSE
  const startUnpacking = async (profileId) => {
    setUnpacking(true)
    setUnpackProgress({ step: 'starting', current: 0, total: 3 })

    try {
      const { data: { session } } = await (await import('../api/client.js')).supabase.auth.getSession()
      const token = session?.access_token

      const response = await fetch(`/api/brand/unpack/${profileId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text = decoder.decode(value)
        const lines = text.split('\n').filter(l => l.startsWith('data: '))

        for (const line of lines) {
          try {
            const event = JSON.parse(line.slice(6))
            setUnpackProgress(event)

            if (event.step === 'done') {
              addToast('Распаковка личности завершена!', 'success')
              await loadProfiles()
              if (event.profile_id) {
                await loadFullProfile(event.profile_id)
              }
            } else if (event.step === 'error') {
              addToast(`Ошибка: ${event.error}`, 'error')
            }
          } catch (e) {
            // skip malformed events
          }
        }
      }
    } catch (e) {
      addToast('Ошибка распаковки', 'error')
    } finally {
      setUnpacking(false)
      setUnpackProgress(null)
    }
  }

  // Edit section
  const startEdit = (section, value) => {
    setEditingSection(section)
    setEditValue(typeof value === 'string' ? value : JSON.stringify(value, null, 2))
  }

  const saveEdit = async (section) => {
    if (!selectedProfile) return
    try {
      let parsed = editValue
      if (section !== 'positioning' && section !== 'niche') {
        parsed = JSON.parse(editValue)
      }
      await api.put(`/brand/profiles/${selectedProfile.id}`, { [section]: parsed })
      addToast('Сохранено', 'success')
      setEditingSection(null)
      await loadFullProfile(selectedProfile.id)
    } catch (e) {
      addToast('Ошибка сохранения. Проверьте формат JSON.', 'error')
    }
  }

  const deleteProfile = async (id) => {
    if (!confirm('Удалить профиль?')) return
    try {
      await api.delete(`/brand/profiles/${id}`)
      addToast('Профиль удалён', 'success')
      setSelectedProfile(null)
      await loadProfiles()
    } catch (e) {
      addToast('Ошибка удаления', 'error')
    }
  }

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-brand-orange" size={32} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Распаковка личности</h1>
        <p className="text-gray-400 mt-1">
          Загрузите файлы о себе, и AI создаст профиль вашего бренда для генерации контента
        </p>
      </div>

      {/* Upload zone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
          isDragActive
            ? 'border-brand-orange bg-brand-orange/5'
            : 'border-brand-border hover:border-brand-orange/50 hover:bg-white/[0.02]'
        }`}
      >
        <input {...getInputProps()} />
        {uploading || unpacking ? (
          <div className="space-y-3">
            <Loader2 className="animate-spin text-brand-orange mx-auto" size={40} />
            <p className="text-white font-medium">
              {uploading ? 'Загружаю файлы...' :
               unpackProgress?.step === 'analyzing' ? 'AI анализирует материалы...' :
               unpackProgress?.step === 'finalizing' ? 'Формирую профиль...' :
               'Обрабатываю...'}
            </p>
            {unpackProgress && (
              <div className="w-48 mx-auto bg-brand-border rounded-full h-2">
                <div
                  className="bg-brand-orange h-2 rounded-full transition-all duration-500"
                  style={{ width: `${((unpackProgress.current || 0) / (unpackProgress.total || 3)) * 100}%` }}
                />
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <Upload className="text-gray-400 mx-auto" size={40} />
            <div>
              <p className="text-white font-medium">Перетащите файлы сюда</p>
              <p className="text-gray-400 text-sm mt-1">
                или нажмите для выбора. Поддерживаются: MD, TXT, PDF, DOCX (до 10 файлов)
              </p>
            </div>
            <div className="text-xs text-gray-500 space-y-1">
              <p>Что загрузить: описание услуг, кейсы, отзывы клиентов, презентации,</p>
              <p>контент-план, скрипты продаж, ваше позиционирование, информация о нише</p>
            </div>
          </div>
        )}
      </div>

      {/* Profile list */}
      {profiles.length > 0 && (
        <div className="flex gap-3 flex-wrap">
          {profiles.map(p => (
            <button
              key={p.id}
              onClick={() => loadFullProfile(p.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all ${
                selectedProfile?.id === p.id
                  ? 'bg-brand-orange text-white'
                  : 'bg-brand-card text-gray-300 hover:bg-white/10'
              }`}
            >
              {p.status === 'ready' ? <CheckCircle size={14} /> :
               p.status === 'processing' ? <Loader2 size={14} className="animate-spin" /> :
               p.status === 'error' ? <AlertCircle size={14} /> :
               <FileText size={14} />}
              {p.niche || 'Новый профиль'}
            </button>
          ))}
        </div>
      )}

      {/* Profile details */}
      {selectedProfile && selectedProfile.status === 'ready' && (
        <div className="space-y-4">
          {/* Actions bar */}
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-white">
              Профиль: {selectedProfile.niche || 'Эксперт'}
            </h2>
            <div className="flex gap-2">
              <button
                onClick={() => startUnpacking(selectedProfile.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-card text-gray-300 rounded-lg hover:bg-white/10"
              >
                <RefreshCw size={14} /> Перегенерировать
              </button>
              <button
                onClick={() => deleteProfile(selectedProfile.id)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-red-900/30 text-red-400 rounded-lg hover:bg-red-900/50"
              >
                <Trash2 size={14} /> Удалить
              </button>
            </div>
          </div>

          {/* Positioning */}
          <ProfileSection
            title="Позиционирование"
            icon={<Target size={18} />}
            sectionKey="positioning"
            expanded={expandedSections.positioning !== false}
            onToggle={() => toggleSection('positioning')}
            editing={editingSection === 'positioning'}
            onStartEdit={() => startEdit('positioning', selectedProfile.positioning)}
            onSave={() => saveEdit('positioning')}
            onCancel={() => setEditingSection(null)}
            editValue={editValue}
            onEditChange={setEditValue}
          >
            <p className="text-gray-300 leading-relaxed">{selectedProfile.positioning}</p>
          </ProfileSection>

          {/* Target Audience */}
          <ProfileSection
            title="Целевая аудитория"
            icon={<Users size={18} />}
            sectionKey="target_audience"
            expanded={expandedSections.target_audience !== false}
            onToggle={() => toggleSection('target_audience')}
            editing={editingSection === 'target_audience'}
            onStartEdit={() => startEdit('target_audience', selectedProfile.target_audience)}
            onSave={() => saveEdit('target_audience')}
            onCancel={() => setEditingSection(null)}
            editValue={editValue}
            onEditChange={setEditValue}
          >
            <div className="space-y-3">
              {(selectedProfile.target_audience || []).map((persona, i) => (
                <div key={i} className="bg-black/20 rounded-lg p-3">
                  <p className="text-white font-medium text-sm">{persona.persona}</p>
                  {persona.pain_points?.length > 0 && (
                    <div className="mt-2">
                      <span className="text-xs text-brand-orange">Боли: </span>
                      <span className="text-xs text-gray-400">{persona.pain_points.join(' | ')}</span>
                    </div>
                  )}
                  {persona.desires?.length > 0 && (
                    <div className="mt-1">
                      <span className="text-xs text-green-400">Желания: </span>
                      <span className="text-xs text-gray-400">{persona.desires.join(' | ')}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </ProfileSection>

          {/* Services */}
          <ProfileSection
            title="Услуги / Продукты"
            icon={<ShoppingBag size={18} />}
            sectionKey="services"
            expanded={expandedSections.services !== false}
            onToggle={() => toggleSection('services')}
            editing={editingSection === 'services'}
            onStartEdit={() => startEdit('services', selectedProfile.services)}
            onSave={() => saveEdit('services')}
            onCancel={() => setEditingSection(null)}
            editValue={editValue}
            onEditChange={setEditValue}
          >
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(selectedProfile.services || []).map((svc, i) => (
                <div key={i} className="bg-black/20 rounded-lg p-3">
                  <p className="text-white font-medium text-sm">{svc.name}</p>
                  <p className="text-gray-400 text-xs mt-1">{svc.description}</p>
                  {svc.for_whom && (
                    <p className="text-brand-orange text-xs mt-1">Для: {svc.for_whom}</p>
                  )}
                </div>
              ))}
            </div>
          </ProfileSection>

          {/* Content Topics */}
          <ProfileSection
            title="Темы для контента"
            icon={<Lightbulb size={18} />}
            sectionKey="content_topics"
            expanded={expandedSections.content_topics !== false}
            onToggle={() => toggleSection('content_topics')}
            editing={editingSection === 'content_topics'}
            onStartEdit={() => startEdit('content_topics', selectedProfile.content_topics)}
            onSave={() => saveEdit('content_topics')}
            onCancel={() => setEditingSection(null)}
            editValue={editValue}
            onEditChange={setEditValue}
          >
            <div className="space-y-3">
              {(selectedProfile.content_topics || []).map((cat, i) => (
                <div key={i} className="bg-black/20 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <p className="text-white font-medium text-sm">{cat.category}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      cat.priority === 'high' ? 'bg-brand-orange/20 text-brand-orange' :
                      cat.priority === 'medium' ? 'bg-blue-500/20 text-blue-400' :
                      'bg-gray-600/20 text-gray-400'
                    }`}>
                      {cat.priority}
                    </span>
                  </div>
                  {cat.description && (
                    <p className="text-gray-400 text-xs mt-1">{cat.description}</p>
                  )}
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {(cat.topics || []).map((topic, j) => (
                      <span key={j} className="text-xs bg-white/5 text-gray-300 px-2 py-1 rounded">
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </ProfileSection>

          {/* Tone of Voice */}
          <ProfileSection
            title="Тон общения"
            icon={<MessageSquare size={18} />}
            sectionKey="tone_of_voice"
            expanded={expandedSections.tone_of_voice !== false}
            onToggle={() => toggleSection('tone_of_voice')}
            editing={editingSection === 'tone_of_voice'}
            onStartEdit={() => startEdit('tone_of_voice', selectedProfile.tone_of_voice)}
            onSave={() => saveEdit('tone_of_voice')}
            onCancel={() => setEditingSection(null)}
            editValue={editValue}
            onEditChange={setEditValue}
          >
            {selectedProfile.tone_of_voice && (
              <div className="space-y-3">
                <div className="flex gap-4">
                  <div className="bg-black/20 rounded-lg px-3 py-2">
                    <span className="text-xs text-gray-500">Стиль</span>
                    <p className="text-white text-sm">{selectedProfile.tone_of_voice.style}</p>
                  </div>
                  <div className="bg-black/20 rounded-lg px-3 py-2">
                    <span className="text-xs text-gray-500">Обращение</span>
                    <p className="text-white text-sm">на "{selectedProfile.tone_of_voice.addressing}"</p>
                  </div>
                </div>
                {selectedProfile.tone_of_voice.examples?.length > 0 && (
                  <div>
                    <span className="text-xs text-gray-500">Примеры фраз:</span>
                    <div className="mt-1 space-y-1">
                      {selectedProfile.tone_of_voice.examples.map((ex, i) => (
                        <p key={i} className="text-gray-300 text-sm italic">"{ex}"</p>
                      ))}
                    </div>
                  </div>
                )}
                {selectedProfile.tone_of_voice.banned_phrases?.length > 0 && (
                  <div>
                    <span className="text-xs text-red-400">Запрещённые фразы:</span>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {selectedProfile.tone_of_voice.banned_phrases.map((b, i) => (
                        <span key={i} className="text-xs bg-red-900/20 text-red-400 px-2 py-0.5 rounded">
                          {b}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </ProfileSection>

          {/* Unique Phrases */}
          {selectedProfile.unique_phrases?.length > 0 && (
            <ProfileSection
              title="Фирменные выражения"
              icon={<Fingerprint size={18} />}
              sectionKey="unique_phrases"
              expanded={expandedSections.unique_phrases !== false}
              onToggle={() => toggleSection('unique_phrases')}
              editing={editingSection === 'unique_phrases'}
              onStartEdit={() => startEdit('unique_phrases', selectedProfile.unique_phrases)}
              onSave={() => saveEdit('unique_phrases')}
              onCancel={() => setEditingSection(null)}
              editValue={editValue}
              onEditChange={setEditValue}
            >
              <div className="flex flex-wrap gap-2">
                {selectedProfile.unique_phrases.map((phrase, i) => (
                  <span key={i} className="text-sm bg-brand-orange/10 text-brand-orange px-3 py-1.5 rounded-lg">
                    "{phrase}"
                  </span>
                ))}
              </div>
            </ProfileSection>
          )}
        </div>
      )}

      {/* Empty state */}
      {profiles.length === 0 && !loading && (
        <div className="text-center py-12 bg-brand-card rounded-xl">
          <Fingerprint className="text-gray-600 mx-auto mb-3" size={48} />
          <h3 className="text-white font-medium">Нет профилей</h3>
          <p className="text-gray-400 text-sm mt-1">
            Загрузите файлы о себе и AI создаст ваш уникальный профиль бренда
          </p>
        </div>
      )}
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════════
// Reusable section component
// ═══════════════════════════════════════════════════════════════════

function ProfileSection({
  title, icon, sectionKey, expanded, onToggle,
  editing, onStartEdit, onSave, onCancel,
  editValue, onEditChange, children,
}) {
  return (
    <div className="bg-brand-card rounded-xl border border-brand-border overflow-hidden">
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-white/[0.02]"
        onClick={onToggle}
      >
        <div className="flex items-center gap-2 text-white">
          {icon}
          <span className="font-medium">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          {!editing && (
            <button
              onClick={(e) => { e.stopPropagation(); onStartEdit() }}
              className="p-1 text-gray-400 hover:text-white rounded"
            >
              <Pencil size={14} />
            </button>
          )}
          {expanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4">
          {editing ? (
            <div className="space-y-2">
              <textarea
                value={editValue}
                onChange={(e) => onEditChange(e.target.value)}
                className="w-full bg-black/30 text-gray-200 text-sm rounded-lg p-3 border border-brand-border focus:border-brand-orange focus:outline-none font-mono"
                rows={10}
              />
              <div className="flex gap-2">
                <button
                  onClick={onSave}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-brand-orange text-white rounded-lg hover:bg-brand-orange/80"
                >
                  <Save size={14} /> Сохранить
                </button>
                <button
                  onClick={onCancel}
                  className="px-3 py-1.5 text-sm text-gray-400 hover:text-white"
                >
                  Отмена
                </button>
              </div>
            </div>
          ) : (
            children
          )}
        </div>
      )}
    </div>
  )
}
