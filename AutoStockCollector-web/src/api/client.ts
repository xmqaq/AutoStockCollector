import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: '',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor — inject auth token
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor — handle 401 redirect
let _redirecting = false

client.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data && data.success === false && !(response.config as any).skipErrorMessage) {
      const msg = data.message || data.error || '请求失败'
      ElMessage.error(msg)
    }
    return response
  },
  (error) => {
    const skipToast = error.config && (error.config as any).skipErrorMessage
    if (error.response) {
      const status = error.response.status
      if (status === 401 && !_redirecting) {
        _redirecting = true
        localStorage.removeItem('auth_token')
        localStorage.removeItem('auth_user')
        window.location.href = '/login'
        return Promise.reject(error)
      }
      if (!skipToast) {
        const msg = error.response.data?.message || error.response.data?.error || error.message
        ElMessage.error(`请求错误 ${status}: ${msg}`)
      }
    } else if (error.request) {
      if (!skipToast) ElMessage.error('网络错误，无法连接到服务器')
    } else {
      if (!skipToast) ElMessage.error(error.message || '未知错误')
    }
    return Promise.reject(error)
  }
)

export default client
