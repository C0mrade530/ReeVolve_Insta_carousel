import React from 'react'
import Sidebar from './Sidebar'
import Header from './Header'

export default function Layout({ children, user }) {
  return (
    <div className="min-h-screen bg-brand-dark flex">
      <Sidebar />
      <div className="flex-1 flex flex-col min-h-screen">
        <Header user={user} />
        <main className="flex-1 p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
