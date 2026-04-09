import React, { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/client'

const AccountContext = createContext(null)

export function AccountProvider({ children }) {
  const [accounts, setAccounts] = useState([])
  const [selectedAccount, setSelectedAccount] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadAccounts = async () => {
    try {
      const res = await api.get('/accounts')
      const list = res.data || []
      setAccounts(list)

      // Auto-select or re-validate selected account
      const savedId = localStorage.getItem('selected_account_id')

      if (list.length > 0) {
        // Check if currently selected account still exists
        const currentStillExists = selectedAccount && list.find(a => a.id === selectedAccount.id)
        if (currentStillExists) {
          // Update with fresh data from server
          setSelectedAccount(currentStillExists)
        } else {
          // Selected account was deleted — pick saved or first
          const saved = savedId ? list.find(a => a.id === savedId) : null
          setSelectedAccount(saved || list[0])
        }
      } else {
        setSelectedAccount(null)
        localStorage.removeItem('selected_account_id')
      }
    } catch {
      // Not logged in
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAccounts()
  }, [])

  const selectAccount = (account) => {
    setSelectedAccount(account)
    if (account) {
      localStorage.setItem('selected_account_id', account.id)
    } else {
      localStorage.removeItem('selected_account_id')
    }
  }

  return (
    <AccountContext.Provider value={{
      accounts,
      selectedAccount,
      selectAccount,
      loading,
      refreshAccounts: loadAccounts,
    }}>
      {children}
    </AccountContext.Provider>
  )
}

export function useAccount() {
  const ctx = useContext(AccountContext)
  if (!ctx) throw new Error('useAccount must be used within AccountProvider')
  return ctx
}
