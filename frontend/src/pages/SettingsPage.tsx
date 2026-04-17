import { useEffect, useState } from "react"
import { Code, KeyRound, Loader2, RefreshCw, ServerCrash, Settings2 } from "lucide-react"
import { Button } from "../components/ui/button"
import { toast } from "sonner"
import {
  clearStoredAdminKey,
  DEFAULT_ADMIN_KEY,
  getAuthHeader,
  getStoredAdminKey,
  normalizeAdminKeyInput,
  setStoredAdminKey,
  verifyAdminKeyCandidate,
} from "../lib/auth"
import { API_BASE } from "../lib/api"

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>(null)
  const [adminKey, setAdminKey] = useState("")
  const [isSavingAdminKey, setIsSavingAdminKey] = useState(false)
  const [maxInflight, setMaxInflight] = useState(4)
  const [autoRefillTarget, setAutoRefillTarget] = useState(3)
  const [modelAliases, setModelAliases] = useState("")

  const loadAdminKey = () => {
    setAdminKey(getStoredAdminKey() || "")
  }

  const fetchSettings = () => {
    fetch(`${API_BASE}/api/admin/settings`, { headers: getAuthHeader() })
      .then((res) => {
        if (!res.ok) throw new Error("Unauthorized")
        return res.json()
      })
      .then((data) => {
        setSettings(data)
        setMaxInflight(data.max_inflight_per_account || 4)
        setAutoRefillTarget(Math.max(0, Number(data.auto_refill_target_min_accounts ?? 3)))
        setModelAliases(JSON.stringify(data.model_aliases || {}, null, 2))
      })
      .catch(() => toast.error("配置获取失败，请检查右下角的管理 Key"))
  }

  useEffect(() => {
    loadAdminKey()
    fetchSettings()
  }, [])

  const handleSaveAdminKey = async () => {
    setIsSavingAdminKey(true)
    try {
      const result = await verifyAdminKeyCandidate(adminKey, API_BASE)
      if (!result.ok) {
        toast.error(result.error)
        return
      }

      setStoredAdminKey(result.key)
      setAdminKey(result.key)
      toast.success("管理台 Key 已保存")
      fetchSettings()
    } finally {
      setIsSavingAdminKey(false)
    }
  }

  const handleClearAdminKey = () => {
    clearStoredAdminKey()
    setAdminKey("")
    toast.success(`已恢复默认 ${DEFAULT_ADMIN_KEY}`)
    fetchSettings()
  }

  const handleSaveConcurrency = () => {
    fetch(`${API_BASE}/api/admin/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ max_inflight_per_account: Number(maxInflight) }),
    }).then((res) => {
      if (res.ok) {
        toast.success("并发配置已保存")
        fetchSettings()
      } else {
        toast.error("保存失败")
      }
    })
  }

  const handleSaveAutoRefillTarget = () => {
    fetch(`${API_BASE}/api/admin/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify({ auto_refill_target_min_accounts: Math.max(0, Number(autoRefillTarget) || 0) }),
    }).then((res) => {
      if (res.ok) {
        toast.success("自动补号目标已保存")
        fetchSettings()
      } else {
        toast.error("保存失败")
      }
    })
  }

  const handleSaveAliases = () => {
    try {
      const parsed = JSON.parse(modelAliases)
      fetch(`${API_BASE}/api/admin/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...getAuthHeader() },
        body: JSON.stringify({ model_aliases: parsed }),
      }).then((res) => {
        if (res.ok) {
          toast.success("模型映射规则已更新")
          fetchSettings()
        } else {
          toast.error("保存失败")
        }
      })
    } catch {
      toast.error("JSON 格式错误，请检查语法")
    }
  }

  const baseUrl = API_BASE || `http://${window.location.hostname}:7860`
  const currentKeyLabel = adminKey ? `当前本地保存：${normalizeAdminKeyInput(adminKey)}` : `当前使用默认 ${DEFAULT_ADMIN_KEY}`

  const curlExample = `# OpenAI 流式对话
curl ${baseUrl}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "model": "qwen3.6-plus",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'

# Anthropic 格式（Claude Code / SDK）
curl ${baseUrl}/anthropic/v1/messages \\
  -H "Content-Type: application/json" \\
  -H "x-api-key: YOUR_API_KEY" \\
  -H "anthropic-version: 2023-06-01" \\
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "你好"}]
  }'

# Gemini 格式
curl ${baseUrl}/v1beta/models/qwen3.6-plus:generateContent \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "contents": [{"parts": [{"text": "你好"}]}]
  }'

# 图片生成（标准 OpenAI Images 接口，推荐）
curl ${baseUrl}/v1/images/generations \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "model": "dall-e-3",
    "prompt": "一只赛博朋克风格的猫，霓虹灯背景，超写实",
    "n": 1,
    "size": "1024x1024",
    "response_format": "url"
  }'

# 图片生成（Chat 意图识别自动路由，返回内容中附带图片链接）
curl ${baseUrl}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "model": "qwen3.6-plus",
    "stream": false,
    "messages": [{"role": "user", "content": "帮我生成一张星空下的雪山图片，写实风格"}]
  }'

# 视频生成（仍为预留链路，先不要作为稳定能力依赖）
curl ${baseUrl}/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_API_KEY" \\
  -d '{
    "model": "qwen3.6-plus",
    "stream": false,
    "messages": [{"role": "user", "content": "生成视频：海浪拍打礁石，慢动作"}]
  }'`

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">系统设置</h2>
          <p className="text-muted-foreground">管理控制台认证与网关运行时配置。</p>
        </div>
        <Button variant="outline" onClick={() => { fetchSettings(); toast.success("配置已刷新") }}>
          <RefreshCw className="mr-2 h-4 w-4" /> 刷新配置
        </Button>
      </div>

      <div className="grid gap-6">
        <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
          <div className="flex flex-col space-y-1.5 border-b bg-muted/30 p-6">
            <div className="flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-primary" />
              <h3 className="font-semibold leading-none tracking-tight">当前管理台 Key</h3>
            </div>
            <p className="text-sm text-muted-foreground">这里只接受管理台 Key：默认是 admin，也可以填你自己生成的 sk-qwen-...。不要填上游 token 或 cookie。</p>
            <p className="text-xs text-muted-foreground">{currentKeyLabel}</p>
          </div>
          <div className="space-y-3 p-6">
            <input
              type="password"
              value={adminKey}
              onChange={(event) => setAdminKey(event.target.value)}
              placeholder="admin 或 sk-qwen-..."
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            <p className="text-xs text-muted-foreground">支持直接粘贴 Bearer admin，系统会自动去掉 Bearer 前缀。</p>
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleSaveAdminKey} disabled={isSavingAdminKey || !normalizeAdminKeyInput(adminKey)}>
                {isSavingAdminKey ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                {isSavingAdminKey ? "校验中..." : "校验并保存"}
              </Button>
              <Button variant="ghost" onClick={handleClearAdminKey}>
                恢复默认 admin
              </Button>
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
          <div className="flex flex-col space-y-1.5 border-b bg-muted/30 p-6">
            <div className="flex items-center gap-2">
              <ServerCrash className="h-5 w-5 text-primary" />
              <h3 className="font-semibold leading-none tracking-tight">连接信息</h3>
            </div>
          </div>
          <div className="p-6">
            <div className="space-y-1">
              <label className="text-sm font-medium">API 基础地址 (Base URL)</label>
              <input type="text" readOnly value={baseUrl} className="flex h-10 w-full rounded-md border border-input bg-muted px-3 py-2 text-sm font-mono text-muted-foreground" />
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
          <div className="flex flex-col space-y-1.5 border-b bg-muted/30 p-6">
            <div className="flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-primary" />
              <h3 className="font-semibold leading-none tracking-tight">核心并发参数</h3>
            </div>
            <p className="text-sm text-muted-foreground">运行时并发槽位与排队阈值（需要在后端 config.json 中修改后重启生效）。</p>
          </div>
          <div className="space-y-4 p-6">
            <div className="flex items-center justify-between border-b py-2">
              <div className="space-y-1">
                <span className="text-sm font-medium">当前系统版本</span>
              </div>
              <span className="font-mono text-sm">{settings?.version || "..."}</span>
            </div>
            <div className="flex items-center justify-between border-b py-2">
              <div className="space-y-1">
                <span className="text-sm font-medium">单账号最大并发 (max_inflight)</span>
                <p className="text-xs text-muted-foreground">控制每个上游账号同时处理的请求数量，避免被封禁。</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={maxInflight}
                  onChange={(event) => setMaxInflight(Number(event.target.value))}
                  className="flex h-8 w-20 rounded-md border border-input bg-background px-3 py-1 text-center text-sm"
                />
                <Button size="sm" onClick={handleSaveConcurrency}>保存</Button>
              </div>
            </div>
            <div className="flex items-center justify-between py-2">
              <div className="space-y-1">
                <span className="text-sm font-medium">自动补号目标健康账号数</span>
                <p className="text-xs text-muted-foreground">后台会尽量把健康账号维持到这个数量。设置为 0 表示关闭自动补号。</p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="0"
                  max="50"
                  value={autoRefillTarget}
                  onChange={(event) => setAutoRefillTarget(Math.max(0, Number(event.target.value) || 0))}
                  className="flex h-8 w-20 rounded-md border border-input bg-background px-3 py-1 text-center text-sm"
                />
                <Button size="sm" onClick={handleSaveAutoRefillTarget}>保存</Button>
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
          <div className="flex flex-col space-y-1.5 border-b bg-muted/30 p-6">
            <h3 className="font-semibold leading-none tracking-tight">自动模型映射规则 (Model Aliases)</h3>
            <p className="text-sm text-muted-foreground">下游传入的模型名称将被网关自动路由至以下千问实际模型。请使用标准 JSON 格式编辑。</p>
          </div>
          <div className="p-6">
            <textarea
              rows={8}
              value={modelAliases}
              onChange={(event) => setModelAliases(event.target.value)}
              className="flex min-h-[160px] w-full rounded-md border border-input bg-slate-950 px-3 py-2 text-sm font-mono text-slate-300"
            />
            <div className="mt-4 flex justify-end">
              <Button onClick={handleSaveAliases}>保存映射</Button>
            </div>
          </div>
        </div>

        <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
          <div className="flex flex-col space-y-1.5 border-b bg-muted/30 p-6">
            <div className="flex items-center gap-2">
              <Code className="h-5 w-5 text-primary" />
              <h3 className="font-semibold leading-none tracking-tight">使用示例</h3>
            </div>
          </div>
          <div className="p-6">
            <div className="overflow-x-auto whitespace-pre rounded-lg bg-slate-950 p-4 text-sm font-mono text-slate-300">
              {curlExample}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
