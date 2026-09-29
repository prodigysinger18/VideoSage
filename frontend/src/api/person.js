import { http, useMock } from './http.js'
import { mockPerson, mockPersons } from './mock.js'
import { getVideos } from './video.js'
export const getPersons = async videoId => {
  if (useMock) return mockPersons.filter(x => !videoId || x.video_id === Number(videoId))
  if (videoId) return (await http.get(`/persons/${videoId}`)).data.map(row => ({ ...row, video_id: Number(videoId) }))
  const videos = await getVideos()
  const groups = await Promise.all(videos.map(video => http.get(`/persons/${video.video_id}`)))
  return groups.flatMap((response, index) => response.data.map(row => ({ ...row, video_id: videos[index].video_id })))
}
export const getPerson = async (videoId, personId) => {
  if (useMock) return mockPerson(Number(videoId), Number(personId))
  const row = (await http.get(`/videos/${videoId}/persons/${personId}`)).data
  const upper = row.outfit?.upper || {}
  const lower = row.outfit?.lower || {}
  return { ...row, video_id: Number(videoId), pose: row.pose || {}, outfit: { upper_color: upper.color, upper_type: upper.type, upper_sleeve: upper.sleeve, lower_color: lower.color, lower_type: lower.type, lower_length: lower.length, confidence: row.outfit?.confidence, sample_count: row.outfit?.sample_count } }
}
export const getBehaviors = async (videoId, personId) => useMock ? mockPerson(Number(videoId), Number(personId)).behaviors : (await http.get(`/behaviors/${videoId}`)).data
export const getOutfit = async (videoId, personId) => useMock ? mockPerson(Number(videoId), Number(personId)).outfit : (await http.get(`/outfits/${videoId}`)).data
export const getPersonAnomalies = async (videoId, personId) => useMock ? mockPerson(Number(videoId), Number(personId)).anomalies : (await http.get(`/anomalies/${videoId}`)).data
