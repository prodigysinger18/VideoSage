<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { analyzeVideo, getVideo, getVideoStreamUrl } from '../api/video.js'
import { getPersons } from '../api/person.js'
import { getAnomalies } from '../api/result.js'
import StatCard from '../components/StatCard.vue'
import { formatDuration } from '../utils/format.js'
import { videoStatusLabel, videoStatusType } from '../utils/videoStatus.js'

const route = useRoute()
const router = useRouter()
const video = ref({ stats: {} })
const persons = ref([])
const anomalies = ref([])
const player = ref(null)
const playbackError = ref('')
const retrying = ref(false)
const resultsLoaded = ref(false)
let timer
const streamUrl = computed(() => getVideoStreamUrl(route.params.id))
const clipStart = computed(() => Math.max(0, Number(route.query.start) || 0))
const clipEnd = computed(() => Math.max(0, Number(route.query.end) || 0))
const duration = computed(() => Number(video.value.duration) || 0)

const markerStyle = item => ({ left: `${duration.value ? (Number(item.start_time) / duration.value) * 100 : 0}%` })
const seekTo = item => {
  if (!player.value) return
  player.value.currentTime = Number(item.start_time) || 0
  player.value.play().catch(() => {})
}
const onLoadedMetadata = async () => {
  if (!player.value || !clipStart.value) return
  player.value.currentTime = clipStart.value
  try { await player.value.play() } catch (_) {}
}
const onTimeUpdate = () => {
  if (player.value && clipEnd.value > 0 && player.value.currentTime >= clipEnd.value) player.value.pause()
}
const onVideoError = () => {
  const code = player.value?.error?.code
  playbackError.value = code === 4
    ? '无法播放：文件格式或编码不受浏览器支持，请使用 H.264 编码的 MP4 视频。'
    : '视频加载失败。请确认后端已启动，且数据库记录对应的视频文件仍存在。'
}
const load = async () => {
  const id = Number(route.params.id)
  video.value = await getVideo(id)
  if (video.value.status !== 'completed') resultsLoaded.value = false
  if (video.value.status === 'completed' && !resultsLoaded.value) {
    persons.value = await getPersons(id)
    anomalies.value = await getAnomalies(id)
    resultsLoaded.value = true
  }
}
const retry = async () => {
  retrying.value = true
  try {
    const result = await analyzeVideo(Number(route.params.id))
    if (result.status === 'failed') throw new Error(result.error)
    resultsLoaded.value = false
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || error.message || '分析启动失败')
  } finally { retrying.value = false }
}
onMounted(() => {
  load().catch(error => ElMessage.error(error.response?.data?.message || '视频信息加载失败'))
  timer = setInterval(() => load().catch(() => {}), 5000)
})
onUnmounted(() => clearInterval(timer))
</script>

<template>
  <div class="page">
    <section class="panel video-player-panel">
      <video ref="player" class="video-player" controls preload="metadata" playsinline @loadedmetadata="onLoadedMetadata" @timeupdate="onTimeUpdate" @error="onVideoError"><source :src="streamUrl" type="video/mp4" /></video>
      <p v-if="playbackError" class="playback-error" role="alert">{{ playbackError }}</p>
      <div v-if="duration" class="event-timeline">
        <span class="timeline-label">异常时间</span>
        <div class="timeline-track">
          <button v-for="(item, index) in anomalies" :key="`${item.start_time}-${index}`" class="event-marker" :style="markerStyle(item)" :title="`${item.event} ${item.start_time}s`" @click="seekTo(item)"><span /></button>
        </div>
        <span class="timeline-end">{{ formatDuration(duration) }}</span>
      </div>
      <div v-if="clipEnd > 0" class="clip-status">当前片段：{{ clipStart }}s - {{ clipEnd }}s</div>
    </section>

    <section class="panel info-band"><div><h2>{{ video.video_name || video.filename }}</h2><p v-if="video.analysis_error" role="alert">分析失败：{{ video.analysis_error }}</p><p v-if="video.status === 'analyzing' && video.analysis_progress != null">正在处理：{{ video.analysis_progress }}%（{{ video.processed_frames }}/{{ video.total_frames }} 帧）</p><el-button v-if="['pending', 'failed'].includes(video.status)" type="primary" :loading="retrying" @click="retry">{{ video.status === 'failed' ? '重新分析' : '开始分析' }}</el-button></div><el-tag :type="videoStatusType(video.status)">{{ videoStatusLabel(video.status) }}</el-tag><dl><div><dt>时长</dt><dd>{{ formatDuration(video.duration) }}</dd></div><div><dt>分辨率</dt><dd>{{ video.width }}×{{ video.height }}</dd></div><div><dt>帧率</dt><dd>{{ video.fps }} FPS</dd></div></dl></section>
    <div class="stat-grid"><StatCard label="人物数量" :value="video.stats?.persons || 0"/><StatCard label="行为事件" :value="video.stats?.behaviors || 0" tone="blue"/><StatCard label="异常事件" :value="video.stats?.anomalies || 0" tone="red"/><StatCard label="穿搭识别" :value="video.stats?.outfits || 0" tone="amber"/></div>

    <section class="panel"><div class="section-head"><div><h2>异常事件</h2><p>点击事件可在当前视频中定位，不会离开当前页面。</p></div><el-tag type="danger">{{ anomalies.length }} 条</el-tag></div><el-table :data="anomalies"><el-table-column prop="person_id" label="人物" width="80"/><el-table-column prop="event" label="事件" width="110"/><el-table-column label="穿着"><template #default="scope">{{ scope.row.outfit?.upper_color || '未知' }}上衣 / {{ scope.row.outfit?.lower_color || '未知' }}下装</template></el-table-column><el-table-column prop="start_time" label="开始(s)" width="100"/><el-table-column prop="end_time" label="结束(s)" width="100"/><el-table-column label="置信度" width="100"><template #default="scope">{{ ((scope.row.confidence || 0) * 100).toFixed(1) }}%</template></el-table-column><el-table-column label="操作" width="100"><template #default="scope"><el-button link type="primary" @click="seekTo(scope.row)">播放事件</el-button></template></el-table-column></el-table></section>

    <section class="panel"><header>人物列表</header><el-table :data="persons"><el-table-column prop="person_id" label="人物 ID"/><el-table-column prop="first_seen" label="首次出现(s)"/><el-table-column prop="last_seen" label="最后出现(s)"/><el-table-column prop="primary_action" label="主要行为"/><el-table-column label="操作"><template #default="scope"><el-button link type="primary" @click="router.push(`/video/${video.video_id}/person/${scope.row.person_id}`)">人物详情</el-button></template></el-table-column></el-table></section>
  </div>
</template>
