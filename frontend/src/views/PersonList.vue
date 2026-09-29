<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getVideos } from '../api/video.js'
import { getPersons } from '../api/person.js'
import { videoStatusLabel } from '../utils/videoStatus.js'

const route = useRoute()
const router = useRouter()
const videos = ref([])
const persons = ref([])
const selectedVideo = ref(null)
const loading = ref(false)

const loadPersons = async videoId => {
  selectedVideo.value = videos.value.find(video => video.video_id === Number(videoId)) || null
  persons.value = []
  if (!selectedVideo.value) return
  loading.value = true
  try {
    persons.value = await getPersons(Number(videoId))
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '人物数据加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    videos.value = await getVideos()
    await loadPersons(route.params.videoId)
  } catch (error) {
    ElMessage.error(error.response?.data?.message || '视频列表加载失败')
  }
})
watch(() => route.params.videoId, loadPersons)

const outfitText = row => {
  const upper = row.outfit?.upper || {}
  const lower = row.outfit?.lower || {}
  return `${upper.color || '未知'} ${upper.type || '上衣'} / ${lower.color || '未知'} ${lower.type || '下装'}`
}
</script>

<template>
  <div class="page">
    <section class="panel">
      <div class="section-head"><div><h2>人物分析</h2><p>按视频查看人物记录</p></div><el-button v-if="selectedVideo" @click="router.push('/persons')">返回视频列表</el-button></div>
      <el-table v-if="!selectedVideo" :data="videos" empty-text="暂无视频">
        <el-table-column prop="video_name" label="视频名称" min-width="260" />
        <el-table-column label="状态" width="120"><template #default="scope">{{ videoStatusLabel(scope.row.status) }}</template></el-table-column>
        <el-table-column label="操作" width="120"><template #default="scope"><el-button link type="primary" @click="router.push(`/persons/${scope.row.video_id}`)">查看人物</el-button></template></el-table-column>
      </el-table>
      <template v-else>
        <h3 class="person-video-title">{{ selectedVideo.video_name }}</h3>
        <el-table v-loading="loading" :data="persons" empty-text="该视频暂无人物分析结果">
          <el-table-column prop="person_id" label="人物编号" width="110" />
          <el-table-column label="出现时间" min-width="180"><template #default="scope">{{ scope.row.first_seen ?? '-' }}s - {{ scope.row.last_seen ?? '-' }}s</template></el-table-column>
          <el-table-column prop="primary_action" label="主要行为" min-width="120" />
          <el-table-column label="穿搭信息" min-width="220"><template #default="scope">{{ outfitText(scope.row) }}</template></el-table-column>
          <el-table-column label="操作" width="100"><template #default="scope"><el-button link type="primary" @click="router.push(`/video/${selectedVideo.video_id}/person/${scope.row.person_id}`)">查看详情</el-button></template></el-table-column>
        </el-table>
      </template>
    </section>
  </div>
</template>
