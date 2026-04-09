import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  Sparkles,
  Palette,
  BarChart3,
  Flame,
  Zap,
  Calendar,
  Fingerprint,
} from 'lucide-react'

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Дашборд' },
  { path: '/brand', icon: Fingerprint, label: 'Распаковка' },
  { path: '/accounts', icon: Users, label: 'Аккаунты' },
  { path: '/week-generator', icon: Zap, label: 'Автонеделя' },
  { path: '/calendar', icon: Calendar, label: 'Календарь' },
  { path: '/generator', icon: Sparkles, label: 'Генератор' },
  { path: '/competitors', icon: Flame, label: 'Конкуренты' },
  { path: '/templates', icon: Palette, label: 'Шаблоны' },
  { path: '/analytics', icon: BarChart3, label: 'Статистика' },
]

export default function Sidebar() {
  return (
    <aside className="w-64 bg-brand-darker border-r border-brand-border flex flex-col">
      <div className="p-5 border-b border-brand-border">
        <h1 className="text-xl font-bold text-white">
          Real<span className="text-brand-orange">Post</span> Pro
        </h1>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(({ path, icon: Icon, label }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-brand-orange/10 text-brand-orange'
                  : 'text-gray-400 hover:text-white hover:bg-white/5'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-brand-border text-xs text-gray-500">
        v0.3.0
      </div>
    </aside>
  )
}
