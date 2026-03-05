import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-gray-500">
      <div className="text-6xl font-bold text-gray-200 mb-4">404</div>
      <p className="text-sm mb-4">页面不存在</p>
      <Link to="/" className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary/90">
        返回首页
      </Link>
    </div>
  )
}
