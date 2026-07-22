// 统一 API 基础地址 — 同时适用于 Web 和 APK
// 硬编码避免 Vite tree-shaking 掉常量
export function apiFetch(path, options = {}) {
  return fetch(`http://43.139.179.58${path}`, options)
}
