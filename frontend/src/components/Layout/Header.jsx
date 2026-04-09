import React, { useState, useRef, useEffect } from 'react'
import { LogOut, ChevronDown, Instagram, User, Globe } from 'lucide-react'
import { supabase } from '../../api/client'
import { useAccount } from '../../contexts/AccountContext'

export default function Header({ user }) {
  const { accounts, selectedAccount, selectAccount } = useAccount()
  const [open, setOpen] = useState(false)
  const dropRef = useRef(null)

  const handleLogout = async () => {
    await supabase.auth.signOut()
  }

  // Close dropdown on click outside
  useEffect(() => {
    const handler = (e) => {
      if (dropRef.current && !dropRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <header className="h-14 bg-brand-darker border-b border-brand-border flex items-center justify-between px-6">
      {/* Account selector */}
      <div className="relative" ref={dropRef}>
        {accounts.length > 0 ? (
          <>
            <button
              onClick={() => setOpen(!open)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-brand-border/50 hover:border-brand-orange/50 transition-colors bg-brand-dark/50"
            >
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                <Instagram size={12} className="text-white" />
              </div>
              <div className="text-left">
                <div className="text-sm text-white font-medium leading-tight">
                  @{selectedAccount?.username || 'Выберите аккаунт'}
                </div>
                {selectedAccount?.city && (
                  <div className="text-[10px] text-gray-500 leading-tight flex items-center gap-0.5">
                    <Globe size={8} />
                    {selectedAccount.city}
                    {selectedAccount.niche && ` · ${selectedAccount.niche}`}
                  </div>
                )}
              </div>
              <ChevronDown size={14} className={`text-gray-400 transition-transform ${open ? 'rotate-180' : ''}`} />
            </button>

            {open && (
              <div className="absolute top-full left-0 mt-1 w-64 bg-brand-card border border-brand-border rounded-xl shadow-2xl shadow-black/40 z-50 overflow-hidden">
                <div className="px-3 py-2 border-b border-brand-border/50">
                  <span className="text-[10px] text-gray-500 uppercase tracking-wider">Аккаунты Instagram</span>
                </div>
                {accounts.map((acc) => (
                  <button
                    key={acc.id}
                    onClick={() => { selectAccount(acc); setOpen(false) }}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 transition-colors ${
                      selectedAccount?.id === acc.id ? 'bg-brand-orange/10' : ''
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                      selectedAccount?.id === acc.id
                        ? 'bg-gradient-to-br from-brand-orange to-pink-500'
                        : 'bg-brand-darker'
                    }`}>
                      <Instagram size={14} className="text-white" />
                    </div>
                    <div className="text-left flex-1 min-w-0">
                      <div className={`text-sm font-medium truncate ${
                        selectedAccount?.id === acc.id ? 'text-brand-orange' : 'text-white'
                      }`}>
                        @{acc.username}
                      </div>
                      <div className="text-[10px] text-gray-500 truncate">
                        {acc.city || 'Город не указан'}
                        {acc.niche && ` · ${acc.niche}`}
                      </div>
                    </div>
                    {selectedAccount?.id === acc.id && (
                      <div className="w-2 h-2 rounded-full bg-brand-orange" />
                    )}
                  </button>
                ))}
                {/* Option to deselect (manual mode) */}
                <button
                  onClick={() => { selectAccount(null); setOpen(false) }}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 hover:bg-white/5 transition-colors border-t border-brand-border/30 ${
                    !selectedAccount ? 'bg-brand-orange/10' : ''
                  }`}
                >
                  <div className="w-8 h-8 rounded-full bg-brand-darker flex items-center justify-center">
                    <User size={14} className="text-gray-400" />
                  </div>
                  <div className="text-left">
                    <div className={`text-sm ${!selectedAccount ? 'text-brand-orange' : 'text-gray-400'}`}>
                      Ручной режим
                    </div>
                    <div className="text-[10px] text-gray-500">Без привязки к аккаунту</div>
                  </div>
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="text-xs text-gray-500 flex items-center gap-1.5">
            <User size={14} />
            Нет подключённых аккаунтов
          </div>
        )}
      </div>

      {/* User info */}
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-400">
          {user?.email}
        </span>
        <button
          onClick={handleLogout}
          className="text-gray-400 hover:text-white transition-colors"
          title="Выйти"
        >
          <LogOut size={18} />
        </button>
      </div>
    </header>
  )
}
