<template>
  <div class="home-page">
    <div class="page-header">
      <h1>邮件概览</h1>
      <el-button type="primary" @click="syncEmails" :loading="syncing">
        <el-icon><Refresh /></el-icon>
        同步邮件
      </el-button>
    </div>

    <div class="stat-cards">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总邮件数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.unread }}</div>
        <div class="stat-label">未读邮件</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.with_attachments }}</div>
        <div class="stat-label">含附件</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ vectorStats.vectorized_emails }}</div>
        <div class="stat-label">已向量化</div>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>同步状态</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="文件夹">{{ syncStatus.folder || 'INBOX' }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="syncStatus.status === 'completed' ? 'success' : 'warning'">
                {{ syncStatus.status || '未开始' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="上次同步">
              {{ syncStatus.last_sync_at || '从未' }}
            </el-descriptions-item>
            <el-descriptions-item label="邮件总数">{{ syncStatus.total_emails || 0 }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <span>常见发件人 Top 5</span>
          </template>
          <div class="top-senders">
            <div
              v-for="(item, index) in stats.top_senders?.slice(0, 5)"
              :key="index"
              class="sender-item"
            >
              <span class="sender-name">{{ item.sender }}</span>
              <el-tag size="small">{{ item.count }} 封</el-tag>
            </div>
            <el-empty v-if="!stats.top_senders?.length" description="暂无数据" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="quick-actions" style="margin-top: 20px">
      <template #header>
        <span>快速操作</span>
      </template>
      <el-space>
        <el-button @click="$router.push('/chat')">
          <el-icon><ChatDotRound /></el-icon>
          AI对话
        </el-button>
        <el-button @click="summarizeEmails" :loading="summarizing">
          <el-icon><Document /></el-icon>
          邮件摘要
        </el-button>
        <el-button @click="$router.push('/emails')">
          <el-icon><Folder /></el-icon>
          查看邮件
        </el-button>
      </el-space>
    </el-card>

    <!-- 邮件摘要对话框 -->
    <el-dialog v-model="showSummary" title="邮件摘要" width="60%">
      <div class="summary-content" v-html="summaryHtml"></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Refresh, ChatDotRound, Document, Folder } from '@element-plus/icons-vue'
import { emailApi, syncApi, chatApi } from '../services/api'
import { marked } from 'marked'
import { ElMessage } from 'element-plus'

const stats = ref({})
const syncStatus = ref({})
const vectorStats = ref({})
const syncing = ref(false)
const summarizing = ref(false)
const showSummary = ref(false)
const summaryHtml = ref('')

const loadData = async () => {
  try {
    const [statsRes, statusRes, vectorRes] = await Promise.all([
      emailApi.getStats(),
      syncApi.getStatus(),
      syncApi.getVectorStats()
    ])
    stats.value = statsRes.data
    syncStatus.value = statusRes.data
    vectorStats.value = vectorRes.data
  } catch (e) {
    console.error('加载数据失败', e)
  }
}

const syncEmails = async () => {
  syncing.value = true
  try {
    await syncApi.syncEmails()
    ElMessage.success('同步完成')
    await loadData()
  } catch (e) {
    ElMessage.error('同步失败: ' + e.message)
  } finally {
    syncing.value = false
  }
}

const summarizeEmails = async () => {
  summarizing.value = true
  try {
    const res = await chatApi.summarize(7)
    summaryHtml.value = marked(res.data.summary)
    showSummary.value = true
  } catch (e) {
    ElMessage.error('生成摘要失败: ' + e.message)
  } finally {
    summarizing.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.home-page {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
}

.top-senders .sender-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.top-senders .sender-item:last-child {
  border-bottom: none;
}

.sender-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-right: 10px;
}

.summary-content {
  line-height: 1.8;
}

.summary-content :deep(h1),
.summary-content :deep(h2),
.summary-content :deep(h3) {
  margin-top: 20px;
  margin-bottom: 10px;
}

.summary-content :deep(ul) {
  padding-left: 20px;
}
</style>
