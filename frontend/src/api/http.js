import axios from 'axios'
export const http = axios.create({ baseURL: '/api', timeout: 10000 })
http.interceptors.response.use(response => {
  const payload = response.data
  if (payload && payload.success === true && Object.prototype.hasOwnProperty.call(payload, 'data')) {
    response.data = payload.data
  }
  return response
})
// 联调默认使用 FastAPI；需要离线演示时显式设置 VITE_USE_MOCK=true。
export const useMock = import.meta.env.VITE_USE_MOCK === 'true'
