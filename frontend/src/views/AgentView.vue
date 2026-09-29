<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { askAgent } from '../api/result.js'
import { getVideos } from '../api/video.js'
import { useRouter } from 'vue-router'

const videos = ref([])
const videoId = ref(null)
const question = ref('视频里有没有人摔倒？')
const loading = ref(false)
const result = ref(null)
const videoLoading = ref(false)
const router = useRouter()
const conversationId = ref(sessionStorage.getItem('videosage_conversation_id') || null)

const playClip = clip => router.push({
  path: `/video/${clip.video_id}`,
  query: { start: clip.start_time, end: clip.end_time }
})

onMounted(async () => {
  videoLoading.value = true
  try {
    videos.value = await getVideos()
    if (videos.value.length) videoId.value = videos.value[0].video_id
  } catch (error) {
    ElMessage.error(`视频列表加载失败：${error.response?.data?.detail || error.message}`)
  } finally {
    videoLoading.value = false
  }
})

const send = async () => {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  if (!videoId.value) {
    ElMessage.warning('请先选择视频')
    return
  }
  loading.value = true
  result.value = null
  try {
    result.value = await askAgent({ video_id: videoId.value, question: question.value.trim(), conversation_id: conversationId.value })
    if (result.value.conversation_id) {
      conversationId.value = result.value.conversation_id
      sessionStorage.setItem('videosage_conversation_id', conversationId.value)
    }
  } catch (error) {
    const detail = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(`Agent 请求失败：${detail}`)
  } finally {
    loading.value = false
  }
}
</script>
<template>
  <div class="agent-wrap">
    <section class="agent-copy">
      <small>VIDEOSAGE AGENT</small>
      <h2>询问视频中的人物与事件</h2>
      <p>先选择视频，再用自然语言查询行为时间、穿搭和异常事件。</p>
    </section>
    <section class="panel agent-panel">
      <el-form label-position="top">
        <el-form-item label="分析视频">
          <el-select v-model="videoId" placeholder="请选择视频" :loading="videoLoading" style="width: 100%">
            <el-option v-for="video in videos" :key="video.video_id" :label="video.video_name || video.filename" :value="video.video_id">
              <span>{{ video.video_name || video.filename }}</span>
              <small class="video-option-meta">#{{ video.video_id }} · {{ video.duration }}s · {{ video.width }}×{{ video.height }}</small>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="问题">
          <el-input v-model="question" type="textarea" :rows="4" placeholder="例如：这个视频里有没有人摔倒？" />
        </el-form-item>
      </el-form>
      <el-button type="primary" :loading="loading" :disabled="!videoId" @click="send">发送问题</el-button>
      <div v-if="result" class="answer">
        <small>{{ result.intent }}</small><p>{{ result.answer }}</p>
        <div v-if="result.clips?.length" class="clip-list">
          <el-button v-for="(clip, index) in result.clips" :key="`${clip.start_time}-${index}`" @click="playClip(clip)">
            播放 {{ clip.reason }} · {{ clip.start_time }}s - {{ clip.end_time }}s
          </el-button>
        </div>
        <el-collapse v-if="result.trace?.length">
          <el-collapse-item title="查看查询过程" name="trace">
            <el-steps direction="vertical" :active="result.trace.length">
              <el-step v-for="item in result.trace" :key="item.step" :title="item.step" :description="String(item.value)" />
            </el-steps>
          </el-collapse-item>
        </el-collapse>
        <el-collapse>
          <el-collapse-item v-if="result.evidence?.length" title="查看事实证据" name="evidence">
            <pre>{{ JSON.stringify(result.evidence, null, 2) }}</pre>
          </el-collapse-item>
          <el-collapse-item title="查看原始查询数据" name="data">
            <pre>{{ JSON.stringify(result.data, null, 2) }}</pre>
          </el-collapse-item>
        </el-collapse>
      </div>
    </section>
  </div>
</template>
