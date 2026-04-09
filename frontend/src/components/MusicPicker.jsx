import React, { useState } from 'react'
import { Music, X, Check, Sparkles } from 'lucide-react'

/**
 * MusicPicker — select music for carousel publishing.
 * Instead of searching Instagram API (which requires active session),
 * user types track name. Music is found at publish time.
 *
 * Props:
 *   selectedMusic: string|null — currently selected track query
 *   onSelect: (query|null) => void — callback when track selected/cleared
 */

const POPULAR_TRACKS = [
  // --- Existing ---
  { query: 'The xx - Intro', label: 'The xx — Intro' },
  { query: 'Ludovico Einaudi - Nuvole Bianche', label: 'Einaudi — Nuvole Bianche' },
  { query: 'Hans Zimmer - Time', label: 'Hans Zimmer — Time' },
  { query: 'Imagine Dragons - Believer', label: 'Imagine Dragons — Believer' },
  { query: 'Kino - Gruppa Krovi', label: 'Кино — Группа крови' },
  { query: 'Miyagi - Minor', label: 'Miyagi — Minor' },
  { query: 'Billie Eilish - Lovely', label: 'Billie Eilish — Lovely' },
  { query: 'Arctic Monkeys - Do I Wanna Know', label: 'Arctic Monkeys — Do I Wanna Know' },
  { query: 'JONY - Allergy', label: 'JONY — Аллергия' },
  { query: 'Rauf Faik - Childhood', label: 'Rauf & Faik — Детство' },
  { query: 'Lana Del Rey - Summertime Sadness', label: 'Lana Del Rey — Summertime' },
  { query: 'Post Malone - Sunflower', label: 'Post Malone — Sunflower' },
  // --- From Instagram saved ---
  { query: 'Gregory Alan Isakov - Sweet Heat Lightning', label: 'Gregory Alan Isakov — Sweet Heat Lightning' },
  { query: 'Knockin On Heavens Door - Conner Coffin', label: "Knockin' On Heaven's Door — Conner Coffin" },
  { query: 'Giulio Cercato - Beautiful', label: 'Giulio Cercato — Beautiful' },
  { query: 'Morunas - Spring is Coming', label: 'Morunas — Spring is Coming' },
  { query: 'Kaan Simseker - Deep Force', label: 'Kaan Simseker — Deep Force' },
  { query: 'I Know What You Want x Madison Calley', label: 'I Know What You Want x Madison Calley' },
  { query: 'Hippie Sabotage - Devil Eyes', label: 'Hippie Sabotage — Devil Eyes' },
  { query: 'Gibran Alcocer - Idea 10', label: 'Gibran Alcocer — Idea 10' },
  { query: 'Runaway feat Pusha T', label: 'Runaway (feat. Pusha T)' },
  { query: 'Luke Willies - everything works out in the end', label: 'Luke Willies — everything works out in the end' },
  { query: 'flora cash - You re Somebody Else', label: "flora cash — You're Somebody Else" },
  { query: 'David Kushner - Daylight', label: 'David Kushner — Daylight' },
  { query: 'Richy Mitch and the Coal Miners - Evergreen', label: 'Richy Mitch & the Coal Miners — Evergreen' },
  { query: 'SHAMO - Chegeri', label: 'SHAMO — Чегери' },
  { query: 'Piano Peace - Save Me', label: 'Piano Peace — Save Me' },
  { query: 'NEU SONG - are you ready', label: 'NEU SONG — are you ready?' },
  { query: 'Interstellar Main Theme Piano', label: 'Interstellar — Main Theme Piano' },
]

export default function MusicPicker({ selectedMusic, onSelect }) {
  const [open, setOpen] = useState(false)
  const [custom, setCustom] = useState('')

  const handleSelectPreset = (query) => {
    onSelect(query)
    setOpen(false)
  }

  const handleCustomSubmit = () => {
    const q = custom.trim()
    if (q) {
      onSelect(q)
      setOpen(false)
      setCustom('')
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleCustomSubmit()
    }
  }

  // Compact view
  if (!open) {
    return (
      <div className="flex items-center gap-2">
        {selectedMusic ? (
          <div className="flex items-center gap-2 bg-purple-500/10 border border-purple-500/30 rounded-lg px-3 py-2 flex-1">
            <Music size={14} className="text-purple-400 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm text-purple-300 truncate font-medium">
                {selectedMusic}
              </div>
              <div className="text-[10px] text-purple-400/60">
                Будет найдена при публикации
              </div>
            </div>
            <button
              onClick={() => onSelect(null)}
              className="text-purple-400/50 hover:text-purple-300 flex-shrink-0"
            >
              <X size={14} />
            </button>
            <button
              onClick={() => setOpen(true)}
              className="text-purple-400/50 hover:text-purple-300 text-xs flex-shrink-0"
            >
              Изменить
            </button>
          </div>
        ) : (
          <button
            onClick={() => setOpen(true)}
            className="flex items-center gap-2 px-3 py-2 border border-brand-border/50 rounded-lg
                       text-gray-400 hover:text-purple-400 hover:border-purple-500/30 transition-colors
                       text-sm"
          >
            <Music size={14} />
            Добавить музыку
          </button>
        )}
      </div>
    )
  }

  // Expanded picker
  return (
    <div className="bg-brand-darker border border-purple-500/30 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-purple-400">
          <Music size={16} />
          <span className="text-sm font-medium">Выбрать музыку</span>
        </div>
        <button
          onClick={() => setOpen(false)}
          className="text-gray-500 hover:text-white transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* Custom input */}
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Введите: Исполнитель - Название трека"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={handleKeyDown}
          className="flex-1 bg-brand-dark border border-brand-border rounded-lg px-3 py-2
                     text-white text-sm focus:outline-none focus:border-purple-500/50"
          autoFocus
        />
        <button
          onClick={handleCustomSubmit}
          disabled={!custom.trim()}
          className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm
                     font-medium transition-colors disabled:opacity-40 flex items-center gap-1"
        >
          <Check size={14} />
          Выбрать
        </button>
      </div>

      {/* Popular tracks */}
      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <Sparkles size={12} className="text-purple-400/60" />
          <span className="text-[11px] text-gray-500">Популярные треки</span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {POPULAR_TRACKS.map((track) => {
            const isSelected = selectedMusic === track.query
            return (
              <button
                key={track.query}
                onClick={() => handleSelectPreset(track.query)}
                className={`px-2.5 py-1.5 rounded-lg text-xs transition-all border ${
                  isSelected
                    ? 'bg-purple-500/20 border-purple-500/40 text-purple-300'
                    : 'bg-brand-dark/50 border-brand-border/30 text-gray-400 hover:text-purple-300 hover:border-purple-500/30'
                }`}
              >
                {track.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Info */}
      <p className="text-[11px] text-gray-600 text-center">
        Музыка будет найдена и добавлена автоматически при публикации карусели
      </p>
    </div>
  )
}
