<template>
  <div class="app-container">
    <header class="app-header">
      <div class="logo">
        <el-icon><Message /></el-icon>
        邮件智能助手
      </div>
      <nav class="nav-menu">
        <el-menu
          :default-active="$route.path"
          mode="horizontal"
          router
        >
          <el-menu-item index="/">
            <el-icon><HomeFilled /></el-icon>
            首页
          </el-menu-item>
          <el-menu-item index="/emails">
            <el-icon><Folder /></el-icon>
            邮件列表
          </el-menu-item>
          <el-menu-item index="/chat">
            <el-icon><ChatDotRound /></el-icon>
            AI助手
          </el-menu-item>
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon>
            设置
          </el-menu-item>
        </el-menu>
      </nav>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { Message, HomeFilled, Folder, ChatDotRound, Setting } from '@element-plus/icons-vue'
</script>
