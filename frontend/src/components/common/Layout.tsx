import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      {/* Desktop sidebar */}
      <Sidebar />

      {/* Main content */}
      <main className="flex-1 pb-20 lg:pb-0 lg:ml-56">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
