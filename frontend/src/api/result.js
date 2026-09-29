import { http, useMock } from './http.js'
import { mockAnomalies } from './mock.js'
import { getVideos } from './video.js'
export const getAnomalies = async videoId => {
  if (useMock) return mockAnomalies.filter(x => !videoId || x.video_id === Number(videoId))
  if (videoId) return (await http.get(`/anomalies/${videoId}`)).data.map(row => ({ ...row, video_id: Number(videoId) }))
  const videos = await getVideos()
  const groups = await Promise.all(videos.map(video => http.get(`/anomalies/${video.video_id}`)))
  return groups.flatMap((response, index) => response.data.map(row => ({ ...row, video_id: videos[index].video_id })))
}
export const askAgent = async payload => (await http.post('/chat', payload)).data
