import { Outlet, Link } from "react-router-dom"
import { Activity, Map, Users, Calendar, Bus, Briefcase, FileText } from "lucide-react"

export function Layout() {
  return (
    <div className="flex h-screen w-full bg-slate-50 text-slate-900">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 text-slate-100 flex flex-col">
        <div className="p-4 font-bold text-xl border-b border-slate-800">
          GovPlanner
        </div>
        <nav className="flex-1 p-4 space-y-2">
          <NavItem to="/" icon={<Activity size={20} />} label="Overview" />
          <NavItem to="/population" icon={<Users size={20} />} label="Population" />
          <NavItem to="/events" icon={<Calendar size={20} />} label="Event Planning" />
          <NavItem to="/transport" icon={<Bus size={20} />} label="Transport" />
          <NavItem to="/facilities" icon={<Briefcase size={20} />} label="Facilities" />
          <NavItem to="/maps" icon={<Map size={20} />} label="Maps" />
          <NavItem to="/reports" icon={<FileText size={20} />} label="Reports" />
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6">
          <div className="font-medium text-lg">Gov Resource Planning Platform</div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-500">Live Data</span>
            <div className="h-8 w-8 rounded-full bg-slate-200"></div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

function NavItem({ to, icon, label }: { to: string, icon: React.ReactNode, label: string }) {
  return (
    <Link to={to} className="flex items-center gap-3 p-2 rounded hover:bg-slate-800 transition-colors">
      {icon}
      <span>{label}</span>
    </Link>
  )
}
