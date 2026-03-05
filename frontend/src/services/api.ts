import axios from 'axios'
import type { ApiResponse } from '@/types/api'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// Response interceptor: unwrap {code, data, message} envelope
api.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse<unknown>
    if (body.code !== 0) {
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return body.data as never
  },
  (error) => {
    const msg = error.response?.data?.message || error.message || '网络错误'
    return Promise.reject(new Error(msg))
  },
)

export default api
