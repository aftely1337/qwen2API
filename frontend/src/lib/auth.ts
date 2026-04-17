const STORAGE_KEY = "qwen2api_key"

export const DEFAULT_ADMIN_KEY = "admin"

type VerifyAdminKeyResult =
  | { ok: true; key: string }
  | { ok: false; error: string }

export function normalizeAdminKeyInput(rawValue: string): string {
  return rawValue.trim().replace(/^Bearer\s+/i, "").trim()
}

export function getStoredAdminKey(): string | null {
  if (typeof window === "undefined") {
    return null
  }

  const normalized = normalizeAdminKeyInput(window.localStorage.getItem(STORAGE_KEY) || "")
  return normalized || null
}

export function getEffectiveAdminKey(): string {
  return getStoredAdminKey() || DEFAULT_ADMIN_KEY
}

export function hasCustomAdminKey(): boolean {
  return getStoredAdminKey() !== null
}

export function setStoredAdminKey(value: string): string {
  const normalized = normalizeAdminKeyInput(value)

  if (typeof window !== "undefined") {
    if (normalized) {
      window.localStorage.setItem(STORAGE_KEY, normalized)
    } else {
      window.localStorage.removeItem(STORAGE_KEY)
    }
  }

  return normalized
}

export function clearStoredAdminKey() {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(STORAGE_KEY)
  }
}

export function getAuthHeader(keyOverride?: string) {
  const key = normalizeAdminKeyInput(keyOverride ?? getEffectiveAdminKey()) || DEFAULT_ADMIN_KEY
  return { Authorization: `Bearer ${key}` }
}

export async function verifyAdminKeyCandidate(candidate: string, apiBase: string): Promise<VerifyAdminKeyResult> {
  const normalized = normalizeAdminKeyInput(candidate)
  if (!normalized) {
    return { ok: false, error: "请输入管理台 Key" }
  }

  try {
    const res = await fetch(`${apiBase}/api/admin/settings`, {
      headers: getAuthHeader(normalized),
    })

    if (res.ok) {
      return { ok: true, key: normalized }
    }

    if (res.status === 401 || res.status === 403) {
      return { ok: false, error: "管理台 Key 无效，请填写 admin 或 sk-qwen-..." }
    }

    return { ok: false, error: `管理台 Key 校验失败（HTTP ${res.status}）` }
  } catch {
    return { ok: false, error: "无法连接后端，暂时无法校验管理台 Key" }
  }
}
