// Simple event bus for cross-component notifications
const listeners = {}

export function on(event, fn) {
  (listeners[event] = listeners[event] || []).push(fn)
  return () => off(event, fn)
}

export function off(event, fn) {
  if (!listeners[event]) return
  listeners[event] = listeners[event].filter(f => f !== fn)
}

export function emit(event, ...args) {
  (listeners[event] || []).forEach(fn => fn(...args))
}
