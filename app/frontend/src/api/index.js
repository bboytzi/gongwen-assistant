import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// FastAPI 的 422 校验错误里 detail 是数组，直接丢给 ElMessage 显示不出内容
function formatError(error) {
  const detail = error.response?.data?.detail

  if (Array.isArray(detail)) {
    return detail
      .map(item => {
        const field = Array.isArray(item.loc) ? item.loc.filter(x => x !== 'body').join('.') : ''
        return field ? `${field}: ${item.msg}` : item.msg
      })
      .join('；')
  }
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') return detail.msg || JSON.stringify(detail)

  return error.message || '请求失败'
}

api.interceptors.response.use(
  response => response.data,
  error => {
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    } else if (status === 403 && typeof detail === 'string' && detail.includes('停用')) {
      // 账号被管理员停用，已签发的 token 立即失效
      localStorage.removeItem('token')
      router.push('/login')
    }

    const msg = formatError(error)
    ElMessage.error(msg)
    return Promise.reject(error)
  }
)

export default api
