import { http, useMock } from './http.js'
import { mockDashboard, mockVideo, mockVideos } from './mock.js'
export const getVideos = async () => {
  if (useMock) return mockVideos
  const rows = (await http.get('/videos')).data
  return rows.map(row => ({ ...row, video_name: row.video_name || row.filename, width: row.width, height: row.height }))
}
export const getVideo = async id => {
  if (useMock) return mockVideo(Number(id))
  const row = (await http.get(`/videos/${id}`)).data
  return { ...row, video_name: row.video_name || row.filename, stats: { persons: row.person_count || 0, behaviors: row.behavior_count || 0, anomalies: row.anomaly_count || 0, outfits: row.person_count || 0 } }
}
export const getDashboard = async () => {
  if (useMock) return mockDashboard
  const row = (await http.get('/dashboard')).data
  return { stats: { videos: row.video_count || 0, tasks: row.video_count || 0, persons: row.person_count || 0, anomalies: row.anomaly_count || 0 }, behaviors: row.behavior_distribution || {}, anomalies: row.anomaly_distribution || {}, trend: [] }
}
export const getVideoStreamUrl = id => `/api/videos/${id}/stream`
export const getVideoClips = async (id, params) => (await http.get(`/videos/${id}/clips`, { params })).data
export const uploadVideo = async file => { const form = new FormData(); form.append('file', file); return (await http.post('/videos/upload', form, { timeout: 0 })).data }
export const analyzeVideo = async id => (await http.post(`/videos/${id}/analyze`)).data
export const deleteVideo = async id => (await http.delete(`/videos/${id}`)).data
