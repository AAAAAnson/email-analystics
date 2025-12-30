<template>
  <div class="emails-page">
    <div class="emails-sidebar">
      <div class="search-box">
        <el-input
          v-model="searchQuery"
          placeholder="搜索邮件..."
          clearable
          @clear="loadEmails"
          @keyup.enter="loadEmails"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>

      <div class="email-list" v-loading="loading">
        <div
          v-for="email in emails"
          :key="email.id"
          class="email-item"
          :class="{ unread: !email.is_read, active: selectedEmail?.id === email.id }"
          @click="selectEmail(email)"
        >
          <div class="email-header">
            <span class="email-sender">{{ formatSender(email.sender) }}</span>
            <span class="email-date">{{ formatDate(email.date) }}</span>
          </div>
          <div class="email-subject">{{ email.subject || '(无主题)' }}</div>
          <div class="email-preview">{{ getPreview(email.body_text) }}</div>
        </div>

        <el-empty v-if="!loading && !emails.length" description="没有邮件" />
      </div>

      <div class="pagination">
        <el-pagination
          small
          layout="prev, pager, next"
          :total="total"
          :page-size="pageSize"
          v-model:current-page="currentPage"
          @current-change="loadEmails"
        />
      </div>
    </div>

    <div class="emails-main">
      <template v-if="selectedEmail">
        <div class="email-detail-header">
          <h2>{{ selectedEmail.subject || '(无主题)' }}</h2>
          <div class="email-meta">
            <div>
              <strong>发件人:</strong> {{ selectedEmail.sender }}
            </div>
            <div>
              <strong>收件人:</strong> {{ selectedEmail.recipients }}
            </div>
            <div>
              <strong>时间:</strong> {{ selectedEmail.date }}
            </div>
            <div v-if="selectedEmail.has_attachments">
              <el-tag type="info" size="small">
                <el-icon><Paperclip /></el-icon>
                {{ selectedEmail.attachments?.length || 0 }} 个附件
              </el-tag>
            </div>
          </div>
        </div>
        <div class="email-detail-body">
          <div v-if="selectedEmail.body_html" v-html="selectedEmail.body_html"></div>
          <pre v-else>{{ selectedEmail.body_text }}</pre>
        </div>
      </template>
      <el-empty v-else description="选择一封邮件查看详情" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Search, Paperclip } from '@element-plus/icons-vue'
import { emailApi } from '../services/api'
import dayjs from 'dayjs'

const emails = ref([])
const selectedEmail = ref(null)
const loading = ref(false)
const searchQuery = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const loadEmails = async () => {
  loading.value = true
  try {
    const res = await emailApi.getList({
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchQuery.value || undefined
    })
    emails.value = res.data.emails
    total.value = res.data.total
  } catch (e) {
    console.error('加载邮件失败', e)
  } finally {
    loading.value = false
  }
}

const selectEmail = async (email) => {
  try {
    const res = await emailApi.getDetail(email.id)
    selectedEmail.value = res.data
    // 更新列表中的已读状态
    email.is_read = true
  } catch (e) {
    console.error('加载邮件详情失败', e)
  }
}

const formatSender = (sender) => {
  if (!sender) return '未知'
  // 提取名字或邮箱
  const match = sender.match(/^(.+?)\s*<.*>$/)
  return match ? match[1] : sender.split('@')[0]
}

const formatDate = (date) => {
  if (!date) return ''
  const d = dayjs(date)
  const now = dayjs()
  if (d.isSame(now, 'day')) {
    return d.format('HH:mm')
  } else if (d.isSame(now, 'year')) {
    return d.format('MM-DD')
  }
  return d.format('YYYY-MM-DD')
}

const getPreview = (text) => {
  if (!text) return ''
  return text.substring(0, 100).replace(/\s+/g, ' ')
}

onMounted(loadEmails)
</script>

<style scoped>
.emails-page {
  height: 100%;
  display: flex;
}

.emails-sidebar {
  width: 350px;
  background: white;
  border-right: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
}

.search-box {
  padding: 15px;
  border-bottom: 1px solid #ebeef5;
}

.email-list {
  flex: 1;
  overflow-y: auto;
}

.email-item {
  padding: 15px;
  border-bottom: 1px solid #ebeef5;
  cursor: pointer;
  transition: background 0.2s;
}

.email-item:hover {
  background: #f5f7fa;
}

.email-item.unread {
  background: #ecf5ff;
}

.email-item.unread .email-subject {
  font-weight: bold;
}

.email-item.active {
  background: #e6f0ff;
  border-left: 3px solid #409eff;
}

.email-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}

.email-sender {
  font-weight: 500;
  color: #303133;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.email-date {
  color: #909399;
  font-size: 12px;
  margin-left: 10px;
}

.email-subject {
  color: #606266;
  margin-bottom: 5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.email-preview {
  color: #909399;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pagination {
  padding: 10px;
  border-top: 1px solid #ebeef5;
  display: flex;
  justify-content: center;
}

.emails-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.email-detail-header {
  padding: 20px;
  background: white;
  border-bottom: 1px solid #ebeef5;
}

.email-detail-header h2 {
  margin: 0 0 15px 0;
  font-size: 18px;
}

.email-meta {
  color: #606266;
  font-size: 14px;
}

.email-meta > div {
  margin-bottom: 5px;
}

.email-detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: white;
}

.email-detail-body pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
}
</style>
