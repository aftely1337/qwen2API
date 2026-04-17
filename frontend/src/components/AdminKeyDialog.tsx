import { useState } from "react"
import { KeyRound, Loader2, ShieldCheck } from "lucide-react"
import { Button } from "./ui/button"
import { toast } from "sonner"
import { API_BASE } from "../lib/api"
import {
  clearStoredAdminKey,
  DEFAULT_ADMIN_KEY,
  getStoredAdminKey,
  normalizeAdminKeyInput,
  setStoredAdminKey,
  verifyAdminKeyCandidate,
} from "../lib/auth"

type AdminKeyDialogProps = {
  triggerLabel?: string
  resetLabel?: string
}

function maskAdminKey(value: string) {
  if (value.length <= 8) {
    return value
  }
  return `${value.slice(0, 4)}...${value.slice(-4)}`
}

export default function AdminKeyDialog({
  triggerLabel = "管理 Key",
  resetLabel = "恢复默认 admin",
}: AdminKeyDialogProps) {
  const [open, setOpen] = useState(false)
  const [adminKeyInput, setAdminKeyInput] = useState("")
  const [isSaving, setIsSaving] = useState(false)

  const storedKey = getStoredAdminKey()
  const activeKeyText = storedKey ? `当前使用：自定义 ${maskAdminKey(storedKey)}` : `当前使用：默认 ${DEFAULT_ADMIN_KEY}`

  const openDialog = () => {
    setAdminKeyInput(storedKey || "")
    setOpen(true)
  }

  const closeDialog = () => {
    if (isSaving) {
      return
    }
    setOpen(false)
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const result = await verifyAdminKeyCandidate(adminKeyInput, API_BASE)
      if (!result.ok) {
        toast.error(result.error)
        return
      }

      const normalized = setStoredAdminKey(result.key)
      toast.success(`管理台 Key 已保存：${maskAdminKey(normalized)}`)
      setOpen(false)
      window.setTimeout(() => window.location.reload(), 250)
    } finally {
      setIsSaving(false)
    }
  }

  const handleReset = () => {
    clearStoredAdminKey()
    setAdminKeyInput("")
    toast.success(`已恢复默认 ${DEFAULT_ADMIN_KEY}`)
    setOpen(false)
    window.setTimeout(() => window.location.reload(), 250)
  }

  return (
    <>
      <div className="fixed right-4 bottom-4 z-[60]">
        <Button
          variant="secondary"
          className="shadow-xl border border-border/60 bg-card/95 backdrop-blur"
          onClick={openDialog}
        >
          <KeyRound className="mr-2 h-4 w-4" />
          {triggerLabel}
        </Button>
      </div>

      {open && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 px-4" onClick={closeDialog}>
          <div
            className="w-full max-w-lg rounded-2xl border bg-card text-card-foreground shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="border-b px-6 py-5">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-primary" />
                <h3 className="text-lg font-semibold">管理台 Key</h3>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{activeKeyText}</p>
            </div>

            <div className="space-y-4 px-6 py-5">
              <div className="space-y-2">
                <label className="text-sm font-medium">请输入管理台 Key</label>
                <input
                  type="password"
                  value={adminKeyInput}
                  onChange={(event) => setAdminKeyInput(event.target.value)}
                  placeholder="admin 或 sk-qwen-..."
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>

              <div className="rounded-lg border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                <p>这里只接受管理台 Key：默认是 admin，也可以填你自己生成的 sk-qwen-...。</p>
                <p className="mt-1">支持直接粘贴 {`Bearer admin`}，系统会自动去掉 Bearer 前缀。不要填上游 token 或 cookie。</p>
              </div>

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <Button variant="ghost" onClick={handleReset} disabled={isSaving}>
                  {resetLabel}
                </Button>

                <div className="flex gap-2">
                  <Button variant="outline" onClick={closeDialog} disabled={isSaving}>
                    取消
                  </Button>
                  <Button onClick={handleSave} disabled={isSaving || !normalizeAdminKeyInput(adminKeyInput)}>
                    {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                    {isSaving ? "校验中..." : "校验并保存"}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
