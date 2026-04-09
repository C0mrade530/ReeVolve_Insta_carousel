import React, { createContext, useContext, useState, useCallback, useRef } from 'react'

const ToastContext = createContext(null)

let toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timersRef = useRef({})

  const removeToast = useCallback((id) => {
    clearTimeout(timersRef.current[id])
    delete timersRef.current[id]
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++toastId
    setToasts(prev => [...prev.slice(-4), { id, message, type }]) // max 5 toasts
    if (duration > 0) {
      timersRef.current[id] = setTimeout(() => removeToast(id), duration)
    }
    return id
  }, [removeToast])

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      {/* Toast container */}
      <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none" style={{ maxWidth: '420px' }}>
        {toasts.map(t => (
          <ToastItem key={t.id} toast={t} onClose={() => removeToast(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

const TOAST_STYLES = {
  success: { bg: 'bg-green-500/15 border-green-500/40', icon: '✓', iconColor: 'text-green-400' },
  error: { bg: 'bg-red-500/15 border-red-500/40', icon: '✕', iconColor: 'text-red-400' },
  warning: { bg: 'bg-yellow-500/15 border-yellow-500/40', icon: '⚠', iconColor: 'text-yellow-400' },
  info: { bg: 'bg-blue-500/15 border-blue-500/40', icon: 'ℹ', iconColor: 'text-blue-400' },
}

function ToastItem({ toast, onClose }) {
  const style = TOAST_STYLES[toast.type] || TOAST_STYLES.info

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-md
        ${style.bg} text-white shadow-xl`}
      style={{ animation: 'slideIn 0.3s ease-out' }}
    >
      <span className={`text-lg flex-shrink-0 ${style.iconColor}`}>{style.icon}</span>
      <p className="text-sm flex-1 leading-snug">{toast.message}</p>
      <button
        onClick={onClose}
        className="text-gray-400 hover:text-white text-xs flex-shrink-0 mt-0.5"
      >
        ✕
      </button>
    </div>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')

  const { addToast, removeToast } = ctx
  return {
    success: (msg, dur) => addToast(msg, 'success', dur),
    error: (msg, dur) => addToast(msg, 'error', dur || 6000),
    warning: (msg, dur) => addToast(msg, 'warning', dur),
    info: (msg, dur) => addToast(msg, 'info', dur),
    remove: removeToast,
  }
}
