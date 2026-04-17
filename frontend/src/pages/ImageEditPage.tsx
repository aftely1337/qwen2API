import { useEffect, useMemo, useState } from "react"
import { Download, Image as ImageIcon, RefreshCw, Wand2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "../components/ui/button"
import { getAuthHeader } from "../lib/auth"
import { API_BASE } from "../lib/api"

type EditedImage = {
  url: string
  revised_prompt: string
}

function useObjectUrl(file: File | null) {
  const objectUrl = useMemo(() => {
    if (!file) return ""
    return URL.createObjectURL(file)
  }, [file])

  useEffect(() => {
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [objectUrl])

  return objectUrl
}

export default function ImageEditPage() {
  const [prompt, setPrompt] = useState("")
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [maskFile, setMaskFile] = useState<File | null>(null)
  const [n, setN] = useState(1)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<EditedImage[]>([])
  const [error, setError] = useState("")

  const imagePreview = useObjectUrl(imageFile)
  const maskPreview = useObjectUrl(maskFile)

  const handleEdit = async () => {
    if (!imageFile) {
      toast.error("请先上传要编辑的图片")
      return
    }
    if (!prompt.trim()) {
      toast.error("请先填写编辑提示词")
      return
    }

    setLoading(true)
    setError("")

    try {
      const formData = new FormData()
      formData.append("image", imageFile)
      if (maskFile) {
        formData.append("mask", maskFile)
      }
      formData.append("prompt", prompt.trim())
      formData.append("n", String(n))
      formData.append("model", "dall-e-3")

      const res = await fetch(`${API_BASE}/v1/images/edits`, {
        method: "POST",
        headers: getAuthHeader(),
        body: formData,
      })

      const data = await res.json()
      if (!res.ok) {
        const detail = data?.detail || data?.error || `HTTP ${res.status}`
        throw new Error(String(detail))
      }

      const images: EditedImage[] = (data.data || []).map((item: any) => ({
        url: item.url,
        revised_prompt: item.revised_prompt || prompt.trim(),
      }))

      if (!images.length) {
        throw new Error("未返回编辑后的图片")
      }

      setResults(images)
      toast.success(`成功生成 ${images.length} 张编辑结果`)
    } catch (err: any) {
      const message = err?.message || "图像编辑失败"
      setError(message)
      toast.error(`图像编辑失败: ${message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleDownload = (url: string, index: number) => {
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `qwen_image_edit_${Date.now()}_${index}.png`
    anchor.target = "_blank"
    anchor.rel = "noopener noreferrer"
    anchor.click()
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">图像编辑</h2>
        <p className="text-muted-foreground">
          上传一张原图并输入编辑要求，调用 <code>/v1/images/edits</code> 生成修改结果。
        </p>
      </div>

      <div className="rounded-xl border bg-card p-6 shadow-sm space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <label className="text-sm font-medium">原始图片</label>
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setImageFile(event.target.files?.[0] || null)}
              className="block w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground">
              支持 png / jpg / webp 等常见格式。图像编辑默认继承原图比例。
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">遮罩图（可选）</label>
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setMaskFile(event.target.files?.[0] || null)}
              className="block w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground">当前后端可接收 mask，但主流程仍以原图为主。</p>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">编辑提示词</label>
          <textarea
            rows={4}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="例如：把背景改成雪山日落，人物保持不变，写实风格"
            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            disabled={loading}
          />
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">生成数量</label>
            <div className="flex gap-2">
              {[1, 2, 4].map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setN(value)}
                  disabled={loading}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-all ${
                    n === value
                      ? "bg-primary text-primary-foreground border-primary shadow-sm"
                      : "bg-background border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
                  }`}
                >
                  {value} 张
                </button>
              ))}
            </div>
          </div>

          <Button onClick={handleEdit} disabled={loading || !imageFile || !prompt.trim()} className="ml-auto gap-2">
            {loading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Wand2 className="h-4 w-4" />}
            {loading ? "编辑中..." : "开始编辑"}
          </Button>
        </div>

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {error}
          </div>
        )}
      </div>

      {(imagePreview || maskPreview) && (
        <div className="grid gap-4 md:grid-cols-2">
          {imagePreview && (
            <div className="rounded-xl border bg-card p-4 shadow-sm space-y-3">
              <div className="text-sm font-medium">原图预览</div>
              <img src={imagePreview} alt="原图预览" className="w-full rounded-lg border bg-muted/20 object-contain" />
            </div>
          )}
          {maskPreview && (
            <div className="rounded-xl border bg-card p-4 shadow-sm space-y-3">
              <div className="text-sm font-medium">Mask 预览</div>
              <img src={maskPreview} alt="遮罩预览" className="w-full rounded-lg border bg-muted/20 object-contain" />
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="rounded-xl border bg-card p-12 shadow-sm">
          <div className="flex flex-col items-center gap-4 text-muted-foreground">
            <div className="relative">
              <ImageIcon className="h-16 w-16 text-muted-foreground/20" />
              <RefreshCw className="absolute -bottom-1 -right-1 h-6 w-6 animate-spin text-primary" />
            </div>
            <div className="text-center">
              <p className="font-medium">正在生成编辑结果...</p>
              <p className="mt-1 text-sm text-muted-foreground/70">通常需要 10-30 秒，请耐心等待。</p>
            </div>
          </div>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">编辑结果 ({results.length} 张)</h3>
            <Button variant="ghost" size="sm" onClick={() => setResults([])}>
              清空
            </Button>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {results.map((item, index) => (
              <div key={`${item.url}-${index}`} className="group overflow-hidden rounded-xl border bg-card shadow-sm">
                <div className="relative bg-muted/30">
                  <img src={item.url} alt={item.revised_prompt} className="w-full object-contain" loading="lazy" />
                  <div className="absolute inset-0 flex items-center justify-center gap-3 bg-black/40 opacity-0 transition-opacity group-hover:opacity-100">
                    <Button size="sm" variant="secondary" onClick={() => handleDownload(item.url, index)} className="gap-1.5">
                      <Download className="h-3.5 w-3.5" /> 下载
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => window.open(item.url, "_blank")}>
                      新窗口打开
                    </Button>
                  </div>
                </div>
                <div className="space-y-1 p-3">
                  <div className="truncate text-xs text-muted-foreground">{item.revised_prompt}</div>
                  <div className="truncate font-mono text-xs text-muted-foreground">{item.url}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!loading && results.length === 0 && (
        <div className="rounded-xl border bg-card/50 p-12 shadow-sm">
          <div className="flex flex-col items-center gap-4 text-muted-foreground">
            <ImageIcon className="h-16 w-16 text-muted-foreground/20" />
            <div className="text-center">
              <p className="font-medium">还没有图像编辑结果</p>
              <p className="mt-1 text-sm text-muted-foreground/70">上传原图并填写提示词后，点击“开始编辑”。</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
