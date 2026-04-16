import { useState, useRef, useEffect } from "react"
import { Image as ImageIcon, Upload, Eraser, Undo, RefreshCw, Download, Wand2 } from "lucide-react"
import { Button } from "../components/ui/button"
import { toast } from "sonner"
import { getAuthHeader } from "../lib/auth"
import { API_BASE } from "../lib/api"

export default function ImageEditPage() {
  const [prompt, setPrompt] = useState("")
  const [loading, setLoading] = useState(false)
  const [resultImage, setResultImage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [imageFile, setImageFile] = useState<File | null>(null)
  const [brushSize, setBrushSize] = useState(20)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [isDrawing, setIsDrawing] = useState(false)

  // Load image to canvas
  useEffect(() => {
    if (!imageFile || !canvasRef.current) return
    const url = URL.createObjectURL(imageFile)
    const img = new Image()
    img.onload = () => {
      const canvas = canvasRef.current!
      const ctx = canvas.getContext("2d")
      if (!ctx) return
      // Set canvas size to match image
      canvas.width = img.width
      canvas.height = img.height
      // Draw image
      ctx.globalCompositeOperation = "source-over"
      ctx.drawImage(img, 0, 0)
      URL.revokeObjectURL(url)
    }
    img.src = url
  }, [imageFile])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (!file.type.startsWith("image/")) {
        toast.error("请上传图片文件")
        return
      }
      setImageFile(file)
      setResultImage(null)
      setError(null)
    }
  }

  // Drawing mask (erasing to transparent)
  const startDrawing = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDrawing(true)
    draw(e)
  }

  const stopDrawing = () => {
    setIsDrawing(false)
    const ctx = canvasRef.current?.getContext("2d")
    if (ctx) ctx.beginPath() // reset path
  }

  const draw = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const rect = canvas.getBoundingClientRect()
    // Calculate scale because CSS size might differ from canvas actual size
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    const x = (e.clientX - rect.left) * scaleX
    const y = (e.clientY - rect.top) * scaleY

    ctx.lineWidth = brushSize * scaleX
    ctx.lineCap = "round"
    ctx.globalCompositeOperation = "destination-out" // Make drawn area transparent
    ctx.lineTo(x, y)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(x, y)
  }

  const handleReset = () => {
    // Re-trigger useEffect by re-setting the same file
    if (imageFile) {
      setImageFile(new File([imageFile], imageFile.name, { type: imageFile.type }))
    }
  }

  const handleGenerate = async () => {
    if (!prompt.trim() || !imageFile || !canvasRef.current) {
      toast.error("请填写提示词并上传图片")
      return
    }
    setLoading(true)
    setError(null)

    try {
      // Get masked image as blob
      const blob = await new Promise<Blob | null>(resolve => 
        canvasRef.current!.toBlob(resolve, "image/png")
      )
      
      if (!blob) throw new Error("无法生成遮罩图片")

      const formData = new FormData()
      formData.append("image", blob, "image.png")
      formData.append("prompt", prompt.trim())
      formData.append("n", "1")
      formData.append("size", "1024x1024") // Standard size for OpenAI API
      formData.append("model", "dall-e-3") // Fallback to current default

      const res = await fetch(`${API_BASE}/v1/images/edits`, {
        method: "POST",
        headers: {
          ...getAuthHeader()
          // Do NOT set Content-Type, fetch will set it with boundary for FormData
        },
        body: formData,
      })

      const data = await res.json()
      if (!res.ok) {
        const detail = data?.detail || data?.error || `HTTP ${res.status}`
        throw new Error(String(detail))
      }

      if (data.data && data.data.length > 0) {
        setResultImage(data.data[0].url)
        toast.success("成功生成编辑图片")
      } else {
        throw new Error("未返回图片，请重试")
      }
    } catch (err: any) {
      const msg = err.message || "网络错误"
      setError(msg)
      toast.error(`生成失败: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">AI 图像编辑 (图生图)</h2>
        <p className="text-muted-foreground">上传原图并涂抹需要修改的区域，然后输入提示词让 AI 重新绘制。</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 左侧：编辑区 */}
        <div className="rounded-xl border bg-card shadow-sm p-6 space-y-4 flex flex-col">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">1. 上传与涂抹遮罩</label>
            <div className="flex items-center gap-2">
              {imageFile && (
                <Button variant="outline" size="sm" onClick={handleReset} className="h-8 text-xs gap-1">
                  <Undo className="h-3.5 w-3.5" /> 还原
                </Button>
              )}
              <Button variant="secondary" size="sm" className="h-8 text-xs relative overflow-hidden gap-1">
                <Upload className="h-3.5 w-3.5" /> 上传图片
                <input 
                  type="file" 
                  accept="image/png, image/jpeg, image/webp" 
                  className="absolute inset-0 opacity-0 cursor-pointer"
                  onChange={handleFileChange}
                />
              </Button>
            </div>
          </div>

          <div className="flex-1 min-h-[300px] border-2 border-dashed rounded-lg bg-muted/30 flex items-center justify-center relative overflow-hidden">
            {!imageFile ? (
              <div className="text-center text-muted-foreground">
                <ImageIcon className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p className="text-sm">点击右上角上传图片</p>
                <p className="text-xs opacity-70">支持 PNG, JPG, WebP</p>
              </div>
            ) : (
              <canvas
                ref={canvasRef}
                className="max-w-full max-h-[500px] object-contain cursor-crosshair checkerboard-bg"
                onMouseDown={startDrawing}
                onMouseMove={draw}
                onMouseUp={stopDrawing}
                onMouseLeave={stopDrawing}
              />
            )}
          </div>

          {imageFile && (
            <div className="flex items-center gap-4 text-sm">
              <Eraser className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground whitespace-nowrap">橡皮擦大小:</span>
              <input
                type="range"
                min="5"
                max="100"
                value={brushSize}
                onChange={e => setBrushSize(parseInt(e.target.value))}
                className="flex-1"
              />
              <span className="w-8 text-right font-mono">{brushSize}px</span>
            </div>
          )}
        </div>

        {/* 右侧：生成设置与结果 */}
        <div className="space-y-6 flex flex-col">
          <div className="rounded-xl border bg-card shadow-sm p-6 space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">2. 编辑提示词 (Prompt)</label>
              <textarea
                rows={4}
                value={prompt}
                onChange={e => setPrompt(e.target.value)}
                placeholder="描述你希望在涂抹区域生成什么，例如：将原本的猫换成一只可爱的赛博朋克机器狗"
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm resize-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                disabled={loading || !imageFile}
                onKeyDown={e => {
                  if (e.key === "Enter" && e.ctrlKey) handleGenerate()
                }}
              />
            </div>

            <Button
              onClick={handleGenerate}
              disabled={loading || !prompt.trim() || !imageFile}
              className="w-full h-10 gap-2"
            >
              {loading
                ? <><RefreshCw className="h-4 w-4 animate-spin" /> 生成中...</>
                : <><Wand2 className="h-4 w-4" /> 开始编辑</>
              }
            </Button>

            {error && (
              <div className="rounded-md bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 text-sm mt-4">
                {error}
              </div>
            )}
          </div>

          <div className="rounded-xl border bg-card shadow-sm p-6 flex-1 flex flex-col">
            <label className="text-sm font-medium mb-4 block">3. 编辑结果</label>
            <div className="flex-1 border rounded-lg bg-muted/30 flex items-center justify-center relative overflow-hidden group">
              {!resultImage && !loading && (
                <div className="text-center text-muted-foreground">
                  <ImageIcon className="h-12 w-12 mx-auto mb-2 opacity-20" />
                  <p className="text-sm">结果将显示在这里</p>
                </div>
              )}
              {loading && (
                <div className="text-center text-muted-foreground">
                  <RefreshCw className="h-8 w-8 mx-auto mb-2 animate-spin text-primary" />
                  <p className="text-sm">AI 正在努力重绘中...</p>
                </div>
              )}
              {resultImage && !loading && (
                <>
                  <img src={resultImage} alt="Edited Result" className="max-w-full max-h-[400px] object-contain" />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        const a = document.createElement("a")
                        a.href = resultImage
                        a.download = `edited_${Date.now()}.png`
                        a.click()
                      }}
                      className="gap-1.5"
                    >
                      <Download className="h-3.5 w-3.5" /> 下载图片
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => window.open(resultImage, "_blank")}
                    >
                      在新窗口打开
                    </Button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        .checkerboard-bg {
          background-image: 
            linear-gradient(45deg, #ccc 25%, transparent 25%),
            linear-gradient(-45deg, #ccc 25%, transparent 25%),
            linear-gradient(45deg, transparent 75%, #ccc 75%),
            linear-gradient(-45deg, transparent 75%, #ccc 75%);
          background-size: 20px 20px;
          background-position: 0 0, 0 10px, 10px -10px, -10px 0px;
        }
      `}</style>
    </div>
  )
}
