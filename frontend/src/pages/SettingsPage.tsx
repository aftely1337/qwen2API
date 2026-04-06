import { useState, useEffect } from "react"
import { Settings2, RefreshCw } from "lucide-react"
import { Button } from "../components/ui/button"

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>(null)

  const fetchSettings = () => {
    fetch("http://localhost:8080/api/admin/settings", { headers: { Authorization: "Bearer admin" } })
      .then(res => res.json())
      .then(data => setSettings(data))
  }

  useEffect(() => {
    fetchSettings()
  }, [])

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">系统设置</h2>
          <p className="text-muted-foreground">查看当前网关的运行时配置与路由映射。</p>
        </div>
        <Button variant="outline" onClick={fetchSettings}>
          <RefreshCw className="mr-2 h-4 w-4" /> 刷新配置
        </Button>
      </div>

      <div className="grid gap-6">
        {/* Core Settings */}
        <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
          <div className="flex flex-col space-y-1.5 p-6 border-b bg-muted/30">
            <div className="flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-primary" />
              <h3 className="font-semibold leading-none tracking-tight">核心并发参数</h3>
            </div>
            <p className="text-sm text-muted-foreground">运行时并发槽位与排队阈值（需要在后端 config.json 中修改后重启生效）。</p>
          </div>
          <div className="p-6 space-y-4">
            <div className="flex justify-between items-center py-2 border-b">
              <div className="space-y-1">
                <span className="text-sm font-medium">当前系统版本</span>
              </div>
              <span className="font-mono text-sm">{settings?.version || "..."}</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b">
              <div className="space-y-1">
                <span className="text-sm font-medium">单账号最大并发 (max_inflight)</span>
                <p className="text-xs text-muted-foreground">控制每个上游账号同时处理的请求数量，避免被封禁。</p>
              </div>
              <span className="font-mono text-sm bg-secondary px-2 py-1 rounded">{settings?.max_inflight_per_account || 2}</span>
            </div>
          </div>
        </div>

        {/* Model Mapping */}
        <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
          <div className="flex flex-col space-y-1.5 p-6 border-b bg-muted/30">
            <h3 className="font-semibold leading-none tracking-tight">自动模型映射规则 (Model Aliases)</h3>
            <p className="text-sm text-muted-foreground">下游传入的模型名称将被网关自动路由至以下千问实际模型。</p>
          </div>
          <div className="p-0">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 border-b text-muted-foreground text-left">
                <tr>
                  <th className="h-10 px-6 font-medium w-1/2">客户端请求模型</th>
                  <th className="h-10 px-6 font-medium w-1/2">实际映射目标</th>
                </tr>
              </thead>
              <tbody>
                {settings?.model_aliases ? Object.entries(settings.model_aliases).map(([alias, target]: [string, any]) => (
                  <tr key={alias} className="border-b last:border-0 hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-3 font-mono text-xs text-primary">{alias}</td>
                    <td className="px-6 py-3 font-mono text-xs text-muted-foreground">{target}</td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={2} className="px-6 py-8 text-center text-muted-foreground">加载中...</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}
