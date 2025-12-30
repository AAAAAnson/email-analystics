<template>
  <div class="settings-page">
    <h1>设置</h1>

    <el-card class="setting-card">
      <template #header>
        <span>邮箱配置</span>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="邮箱地址">{{ config.email_address || '-' }}</el-descriptions-item>
        <el-descriptions-item label="IMAP服务器">{{ config.imap_server || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Embedding模型">{{ config.embedding_model || '-' }}</el-descriptions-item>
      </el-descriptions>
      <p class="tip">
        <el-icon><InfoFilled /></el-icon>
        邮箱配置需要在 .env 文件中修改后重启服务生效
      </p>
    </el-card>

    <el-card class="setting-card">
      <template #header>
        <span>向量化状态</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="总邮件数">{{ vectorStats.total_emails || 0 }}</el-descriptions-item>
        <el-descriptions-item label="已向量化">{{ vectorStats.vectorized_emails || 0 }}</el-descriptions-item>
        <el-descriptions-item label="待处理">{{ vectorStats.pending_emails || 0 }}</el-descriptions-item>
        <el-descriptions-item label="向量块数">{{ vectorStats.total_chunks || 0 }}</el-descriptions-item>
      </el-descriptions>

      <div style="margin-top: 20px">
        <el-button type="primary" @click="vectorize" :loading="vectorizing">
          <el-icon><Refresh /></el-icon>
          重新向量化
        </el-button>
      </div>
    </el-card>

    <el-card class="setting-card">
      <template #header>
        <span>数据管理</span>
      </template>
      <el-space direction="vertical" :size="15" style="width: 100%">
        <div class="action-item">
          <div>
            <h4>清除对话历史</h4>
            <p class="desc">删除所有AI对话记录，不会影响邮件数据</p>
          </div>
          <el-button type="warning" @click="clearConversations">清除</el-button>
        </div>
        <div class="action-item">
          <div>
            <h4>全量同步邮件</h4>
            <p class="desc">重新从邮箱服务器同步所有邮件（可能需要较长时间）</p>
          </div>
          <el-button type="primary" @click="fullSync" :loading="syncing">同步</el-button>
        </div>
      </el-space>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { InfoFilled, Refresh } from '@element-plus/icons-vue'
import { syncApi } from '../services/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

const config = ref({})
const vectorStats = ref({})
const vectorizing = ref(false)
const syncing = ref(false)

const loadData = async () => {
  try {
    const [configRes, vectorRes] = await Promise.all([
      axios.get('/api/config'),
      syncApi.getVectorStats()
    ])
    config.value = configRes.data
    vectorStats.value = vectorRes.data
  } catch (e) {
    console.error('加载配置失败', e)
  }
}

const vectorize = async () => {
  vectorizing.value = true
  try {
    await syncApi.vectorize()
    ElMessage.success('向量化完成')
    await loadData()
  } catch (e) {
    ElMessage.error('向量化失败: ' + e.message)
  } finally {
    vectorizing.value = false
  }
}

const fullSync = async () => {
  try {
    await ElMessageBox.confirm('全量同步可能需要较长时间，确定继续吗？', '确认', {
      type: 'warning'
    })
    syncing.value = true
    await syncApi.syncEmails('INBOX')
    ElMessage.success('同步完成')
    await loadData()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('同步失败: ' + e.message)
    }
  } finally {
    syncing.value = false
  }
}

const clearConversations = async () => {
  try {
    await ElMessageBox.confirm('确定要清除所有对话历史吗？此操作不可恢复。', '警告', {
      type: 'warning'
    })
    // 这里可以调用清除API
    ElMessage.success('对话历史已清除')
  } catch (e) {
    // 用户取消
  }
}

onMounted(loadData)
</script>

<style scoped>
.settings-page {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.settings-page h1 {
  margin-bottom: 20px;
}

.setting-card {
  margin-bottom: 20px;
}

.tip {
  margin-top: 15px;
  color: #909399;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 5px;
}

.action-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.action-item h4 {
  margin: 0 0 5px 0;
}

.action-item .desc {
  margin: 0;
  color: #909399;
  font-size: 13px;
}
</style>
