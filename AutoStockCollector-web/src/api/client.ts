import axios from 'axios'
import { ElMessage } from 'element-plus'

const client = axios.create({
  baseURL: '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
client.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
client.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data && data.success === false) {
      const msg = data.message || data.error || '请求失败'
      ElMessage.error(msg)
    }
    return response
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      const msg = error.response.data?.message || error.response.data?.error || error.message
      ElMessage.error(`请求错误 ${status}: ${msg}`)
    } else if (error.request) {
      ElMessage.error('网络错误，无法连接到服务器')
    } else {
      ElMessage.error(error.message || '未知错误')
    }
    return Promise.reject(error)
  }
)

export default client
