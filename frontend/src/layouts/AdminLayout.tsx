import { Outlet, Link, useLocation } from "react-router-dom"
import { Activity, Key, Settings, LayoutDashboard, MessageSquare, Menu, X, Image, Wand2 } from "lucide-react"
import { useState } from "react"
import AdminKeyDialog from "../components/AdminKeyDialog"

export default function AdminLayout() {
  const loc = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)

  const navs = [
    { name: "运行状态", path: "/", icon: LayoutDashboard },
    { name: "账号管理", path: "/accounts", icon: Activity },
    { name: "API Key", path: "/tokens", icon: Key },
    { name: "接口测试", path: "/test", icon: MessageSquare },
    { name: "图片生成", path: "/images", icon: Image },
    { name: "图像编辑", path: "/images/edit", icon: Wand2 },
    { name: "系统设置", path: "/settings", icon: Settings },
  ]

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground transition-colors duration-300">
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm transition-opacity dark:bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border/40 bg-card/90 shadow-2xl shadow-black/5 backdrop-blur-xl transition-transform duration-300 dark:shadow-black/50 md:static md:bg-card/50 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-border/40 px-6">
          <div className="bg-gradient-to-br from-indigo-500 to-purple-500 bg-clip-text text-xl font-extrabold tracking-tight text-transparent">qwen2API</div>
          <button className="text-muted-foreground transition-colors hover:text-foreground md:hidden" onClick={() => setMobileOpen(false)}>
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-2 p-4">
          {navs.map((nav) => {
            const active = loc.pathname === nav.path
            return (
              <Link
                key={nav.path}
                to={nav.path}
                onClick={() => setMobileOpen(false)}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-300 ${
                  active
                    ? "bg-primary/10 text-primary ring-1 ring-primary/20 shadow-[inset_0_1px_0_0_rgba(0,0,0,0.05)] dark:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1)]"
                    : "text-muted-foreground hover:bg-black/5 hover:text-foreground dark:hover:bg-white/5"
                }`}
              >
                <nav.icon className={`h-4 w-4 ${active ? "drop-shadow-[0_0_8px_rgba(168,85,247,0.5)]" : ""}`} />
                {nav.name}
              </Link>
            )
          })}
        </nav>

        <div className="border-t border-border/40 p-4 text-xs text-muted-foreground">
          <div className="rounded-lg border bg-muted/20 p-3">
            <div className="font-medium text-foreground">管理 Key 快捷恢复</div>
            <div className="mt-1 leading-5">如果输错了管理台 Key，也可以在任意页面点右下角“管理 Key”，或者直接恢复默认 admin。</div>
          </div>
        </div>
      </aside>

      <main className="relative flex flex-1 flex-col overflow-hidden">
        <header className="z-10 flex h-16 items-center justify-between border-b border-border/40 bg-card/80 px-6 shadow-sm backdrop-blur-xl md:hidden">
          <div className="bg-gradient-to-br from-indigo-500 to-purple-500 bg-clip-text text-lg font-extrabold text-transparent">qwen2API</div>
          <button className="text-muted-foreground transition-colors hover:text-foreground" onClick={() => setMobileOpen(true)}>
            <Menu className="h-6 w-6" />
          </button>
        </header>

        <div className="z-0 flex-1 overflow-y-auto p-6 md:p-8">
          <div className="mx-auto max-w-6xl animate-fade-in-up">
            <Outlet />
          </div>
        </div>
      </main>

      <AdminKeyDialog triggerLabel="管理 Key" resetLabel="恢复默认 admin" />
    </div>
  )
}
