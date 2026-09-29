<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { VideoCamera, User, ChatDotRound } from '@element-plus/icons-vue'
const route = useRoute()
const title = computed(() => route.meta.title || 'VideoSage')
</script>
<template>
  <el-container class="shell">
    <el-aside width="224px" class="sidebar">
      <div class="brand"><span class="brand-mark">VS</span><div><strong>VideoSage</strong><small>视频理解平台</small></div></div>
      <el-menu router :default-active="route.path" class="menu">
        <el-menu-item index="/videos"><el-icon><VideoCamera /></el-icon>视频管理</el-menu-item>
        <el-menu-item index="/persons"><el-icon><User /></el-icon>人物分析</el-menu-item>
        <el-menu-item index="/agent"><el-icon><ChatDotRound /></el-icon>Agent 问答</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar"><div><small>ANALYTICS CONSOLE</small><h1>{{ title }}</h1></div><el-tag type="success" effect="plain">系统在线</el-tag></el-header>
      <el-main class="content"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
