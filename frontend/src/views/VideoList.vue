<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { analyzeVideo, deleteVideo, getVideos, uploadVideo } from '../api/video.js'
import { formatDuration } from '../utils/format.js'
import { videoStatusLabel, videoStatusType } from '../utils/videoStatus.js'

const rows = ref([])
const router = useRouter()
const uploading = ref(false)
const retrying = ref(null)
const deleting = ref(null)
let timer
let loading = false

const load = async () => {
  if (loading) return
  loading = true
  try { rows.value = await getVideos() } finally { loading = false }
}
onMounted(() => { load().catch(() => ElMessage.error('视频列表加载失败')); timer = setInterval(() => load().catch(() => {}), 5000) })
onUnmounted(() => clearInterval(timer))

const handleUpload = async file => {
  uploading.value = true
  try {
    const result = await uploadVideo(file)
    ElMessage.success(result.status === 'failed' ? '视频已上传，但分析启动失败' : '视频已上传，分析任务已排队')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || error.response?.data?.detail || '上传失败')
  } finally { uploading.value = false }
  return false
}

const retry = async videoId => {
  retrying.value = videoId
  try {
    const result = await analyzeVideo(videoId)
    if (result.status === 'failed') throw new Error(result.error)
    ElMessage.success('分析任务已排队')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || error.message || '重试失败')
  } finally { retrying.value = null }
}

const remove = async video => {
  try {
    await ElMessageBox.confirm(
      `确定删除《${video.video_name}》？视频文件、分析结果及关联的人物、行为、异常记录都将永久删除。`,
      '删除视频',
      { confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger', type: 'warning' }
    )
  } catch { return }
  deleting.value = video.video_id
  try {
    const result = await deleteVideo(video.video_id)
    if (result.warnings?.length) ElMessage.warning(`数据库记录已删除，但部分文件清理失败：${result.warnings.join('；')}`)
    else ElMessage.success('视频已删除')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.message || error.response?.data?.detail || '删除失败')
  } finally { deleting.value = null }
}
</script>
<template>
  <section class="panel">
    <div class="section-head">
      <div><h2>视频资源</h2><p>上传视频后写入数据库，分析完成后可查看行为与异常时间轴</p></div>
      <div class="section-actions">
        <el-upload :show-file-list="false" accept="video/mp4,video/quicktime,video/x-matroska,video/webm" :before-upload="handleUpload">
          <el-button type="primary" :loading="uploading">上传视频</el-button>
        </el-upload>
        <el-tag type="success">{{ rows.length }} 个视频</el-tag>
      </div>
    </div>
    <el-table :data="rows">
      <el-table-column prop="video_name" label="视频名称" min-width="220" />
      <el-table-column label="时长" width="100"><template #default="scope">{{ formatDuration(scope.row.duration) }}</template></el-table-column>
      <el-table-column prop="fps" label="FPS" width="90" />
      <el-table-column label="分辨率" width="120"><template #default="scope">{{ scope.row.width }}×{{ scope.row.height }}</template></el-table-column>
      <el-table-column label="状态" min-width="210"><template #default="scope"><el-tooltip v-if="scope.row.analysis_error" :content="scope.row.analysis_error"><el-tag :type="videoStatusType(scope.row.status)" size="small">{{ videoStatusLabel(scope.row.status) }}</el-tag></el-tooltip><el-tag v-else :type="videoStatusType(scope.row.status)" size="small">{{ videoStatusLabel(scope.row.status) }}</el-tag><span v-if="scope.row.status === 'analyzing' && scope.row.analysis_progress != null" class="status-progress">{{ scope.row.analysis_progress }}% · {{ scope.row.processed_frames }}/{{ scope.row.total_frames }} 帧</span><span v-if="scope.row.analysis_error" class="status-error">{{ scope.row.analysis_error }}</span></template></el-table-column>
      <el-table-column label="操作" width="230"><template #default="scope"><el-button link type="primary" @click="router.push(`/video/${scope.row.video_id}`)">查看详情</el-button><el-button v-if="['pending', 'failed', 'uploaded_pending_analysis'].includes(scope.row.status)" link type="warning" :loading="retrying === scope.row.video_id" @click="retry(scope.row.video_id)">开始分析</el-button><el-button v-if="scope.row.deletable" link type="danger" :loading="deleting === scope.row.video_id" :disabled="['queued', 'analyzing', 'importing'].includes(scope.row.status)" @click="remove(scope.row)">删除</el-button></template></el-table-column>
    </el-table>
  </section>
</template>
