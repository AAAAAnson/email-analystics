<template>
  <div class="chat-container">
    <div class="chat-sidebar">
      <div class="sidebar-header">
        <el-button type="primary" @click="newSession" style="width: 100%">
          <el-icon><Plus /></el-icon>
          新对话
        </el-button>
      </div>
      <div class="session-list">
        <div
          v-for="session in sessions"
          :key="session.session_id"
          class="session-item"
          :class="{ active: currentSessionId === session.session_id }"
          @click="loadSession(session.session_id)"
        >
          <el-icon><ChatDotSquare /></el-icon>
          <span>{{ formatSessionTime(session.created_at) }}</span>
        </div>
      </div>
    </div>

    <div class="chat-main">
      <div class="chat-messages" ref="messagesContainer">
        <div class="welcome-message" v-if="!messages.length">
          <el-icon :size="48" color="#409eff"><ChatDotRound /></el-icon>
          <h2>邮件智能助手</h2>
          <p>我可以帮你查询、分析邮件内容。试着问我：</p>
          <div class="suggestions">
            <el-tag
              v-for="(q, i) in suggestions"
              :key="i"
              @click="sendSuggestion(q)"
              class="suggestion-tag"
            >{{ q }}</el-tag>
          </div>
        </div>

        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="message"
          :class="msg.role"
        >
          <div class="message-avatar">
            <el-icon v-if="msg.role === 'user'"><User /></el-icon>
            <el-icon v-else><Monitor /></el-icon>
          </div>
          <div class="message-content" v-html="formatMessage(msg.content)"></div>
        </div>

        <div v-if="streaming" class="message assistant">
          <div class="message-avatar">
            <el-icon><Monitor /></el-icon>
          </div>
          <div class="message-content">
            <span v-html="formatMessage(streamingContent)"></span>
            <span class="cursor">|</span>
          </div>
        </div>
      </div>

      <div class="chat-input">
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="2"
          placeholder="输入你的问题，按Enter发送..."
          @keydown.enter.exact.prevent="sendMessage"
          :disabled="streaming"
        />
        <div class="input-actions">
          <el-checkbox v-model="useRag" label="使用邮件上下文" />
          <el-button
            type="primary"
            @click="sendMessage"
            :loading="streaming"
            :disabled="!inputMessage.trim()"
          >
            发送
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import { Plus, ChatDotSquare, ChatDotRound, User, Monitor } from '@element-plus/icons-vue'
import { chatApi, streamChat } from '../services/api'
import { marked } from 'marked'
import dayjs from 'dayjs'

const messages = ref([])
const sessions = ref([])
const currentSessionId = ref(null)
const inputMessage = ref('')
const streaming = ref(false)
const streamingContent = ref('')
const useRag = ref(true)
const messagesContainer = ref(null)

const suggestions = [
  '最近有哪些重要邮件？',
  '帮我找一下关于会议的邮件',
  '总结一下本周收到的邮件',
  '有没有需要回复的邮件？'
]

const loadSessions = async () => {
  try {
    const res = await chatApi.getSessions()
    sessions.value = res.data.sessions
  } catch (e) {
    console.error('加载会话列表失败', e)
  }
}

const loadSession = async (sessionId) => {
  currentSessionId.value = sessionId
  try {
    const res = await chatApi.getHistory(sessionId)
    messages.value = res.data.messages
    scrollToBottom()
  } catch (e) {
    console.error('加载会话历史失败', e)
  }
}

const newSession = () => {
  currentSessionId.value = null
  messages.value = []
}

const sendSuggestion = (text) => {
  inputMessage.value = text
  sendMessage()
}

const sendMessage = async () => {
  const text = inputMessage.value.trim()
  if (!text || streaming.value) return

  // 添加用户消息
  messages.value.push({ role: 'user', content: text })
  inputMessage.value = ''
  scrollToBottom()

  streaming.value = true
  streamingContent.value = ''

  try {
    for await (const chunk of streamChat(text, currentSessionId.value, useRag.value)) {
      if (chunk.session_id) {
        currentSessionId.value = chunk.session_id
      }
      if (chunk.content) {
        streamingContent.value += chunk.content
        scrollToBottom()
      }
    }

    // 添加助手消息
    messages.value.push({ role: 'assistant', content: streamingContent.value })
    streamingContent.value = ''

    // 刷新会话列表
    loadSessions()
  } catch (e) {
    console.error('发送消息失败', e)
    messages.value.push({
      role: 'assistant',
      content: '抱歉，处理消息时出现错误: ' + e.message
    })
  } finally {
    streaming.value = false
  }
}

const formatMessage = (content) => {
  if (!content) return ''
  return marked(content)
}

const formatSessionTime = (time) => {
  if (!time) return '新对话'
  return dayjs(time).format('MM-DD HH:mm')
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

onMounted(() => {
  loadSessions()
})
</script>

<style scoped>
.chat-container {
  height: 100%;
  display: flex;
}

.chat-sidebar {
  width: 250px;
  background: white;
  border-right: 1px solid #ebeef5;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 15px;
  border-bottom: 1px solid #ebeef5;
}

.session-list {
  flex: 1;
  overflow-y: auto;
}

.session-item {
  padding: 12px 15px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  border-bottom: 1px solid #f5f7fa;
  transition: background 0.2s;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item.active {
  background: #ecf5ff;
  color: #409eff;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.welcome-message {
  text-align: center;
  padding: 60px 20px;
  color: #606266;
}

.welcome-message h2 {
  margin: 20px 0 10px;
}

.suggestions {
  margin-top: 20px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.suggestion-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion-tag:hover {
  background: #409eff;
  color: white;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: #409eff;
  color: white;
}

.message.assistant .message-avatar {
  background: #67c23a;
  color: white;
}

.message-content {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
}

.message.user .message-content {
  background: #409eff;
  color: white;
  border-radius: 12px 12px 0 12px;
}

.message.assistant .message-content {
  background: white;
  border: 1px solid #ebeef5;
  border-radius: 12px 12px 12px 0;
}

.message-content :deep(pre) {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
  margin: 10px 0;
}

.message-content :deep(code) {
  font-family: 'Courier New', monospace;
}

.message-content :deep(p) {
  margin: 0 0 10px 0;
}

.message-content :deep(p:last-child) {
  margin-bottom: 0;
}

.cursor {
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

.chat-input {
  padding: 15px 20px;
  background: white;
  border-top: 1px solid #ebeef5;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 10px;
}
</style>
