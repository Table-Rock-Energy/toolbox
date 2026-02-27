import { useState, useEffect } from 'react'

export interface GhlConnection {
  id: string
  name: string
  locationId: string
  token: string // Stored in plaintext in stub mode (encrypted on backend in Phase 9)
  createdAt: string // ISO string
}

export default function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: T | ((prev: T) => T)) => void] {
  // Initialize state with lazy initializer
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key)
      return item ? JSON.parse(item) : initialValue
    } catch (error) {
      console.warn(`Error reading localStorage key "${key}":`, error)
      return initialValue
    }
  })

  // Sync state to localStorage whenever it changes
  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(storedValue))
    } catch (error) {
      console.warn(`Error writing to localStorage key "${key}":`, error)
    }
  }, [key, storedValue])

  // Return a wrapped version of setState that accepts both values and updater functions
  const setValue = (value: T | ((prev: T) => T)) => {
    try {
      // Allow value to be a function so we have same API as useState
      const valueToStore = value instanceof Function ? value(storedValue) : value
      setStoredValue(valueToStore)
    } catch (error) {
      console.warn(`Error setting localStorage key "${key}":`, error)
    }
  }

  return [storedValue, setValue]
}
