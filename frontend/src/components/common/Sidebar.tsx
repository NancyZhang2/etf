import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/', label: '首页', icon: '📊' },
  { to: '/etf', label: 'ETF', icon: '📈' },
  { to: '/strategy', label: '策略', icon: '⚙' },
  { to: '/signals', label: '信号', icon: '🔔' },
  { to: '/research', label: '研报', icon: '📄' },
]

function NavItem({ to, label, icon }: { to: string; label: string; icon: string }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
          isActive
            ? 'bg-primary/10 text-primary font-medium'
            : 'text-gray-600 hover:bg-gray-100'
        }`
      }
    >
      <span className="text-lg">{icon}</span>
      <span>{label}</span>
    </NavLink>
  )
}

export default function Sidebar() {
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-56 fixed h-full bg-white border-r border-gray-200 z-30">
        <div className="px-6 py-5 border-b border-gray-100">
          <h1 className="text-lg font-bold text-gray-900">ETF量化投研</h1>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}
        </nav>
      </aside>

      {/* Mobile bottom tab bar */}
      <nav className="lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-30 flex">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center py-2 text-xs transition-colors ${
                isActive ? 'text-primary' : 'text-gray-500'
              }`
            }
          >
            <span className="text-base">{item.icon}</span>
            <span className="mt-0.5">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </>
  )
}
