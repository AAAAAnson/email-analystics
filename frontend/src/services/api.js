import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000
})

// 邮件相关
export const emailApi = {
  getList(params) {
    return api.get('/emails', { params })
  },
  getDetail(id) {
    return api.get(`/emails/${id}`)
  },
  getStats() {
    return api.get('/emails/stats')
  },
  markAsRead(id) {
    return api.post(`/emails/${id}/read`)
  },
  delete(id) {
    return api.delete(`/emails/${id}`)
  }
}

// 同步相关
export const syncApi = {
  syncEmails(folder = 'INBOX') {
    return api.post('/sync/emails', null, { params: { folder } })
  },
  getStatus(folder = 'INBOX') {
    return api.get('/sync/status', { params: { folder } })
  },
  vectorize() {
    return api.post('/sync/vectorize')
  },
  getVectorStats() {
    return api.get('/sync/vector-stats')
  }
}

// 对话相关
export const chatApi = {
  send(message, sessionId = null, useRag = true) {
    return api.post('/chat', {
      message,
      session_id: sessionId,
      use_rag: useRag
    })
  },
  getHistory(sessionId, limit = 50) {
    return api.get('/chat/history', { params: { session_id: sessionId, limit } })
  },
  clearHistory(sessionId) {
    return api.delete('/chat/history', { params: { session_id: sessionId } })
  },
  getSessions() {
    return api.get('/chat/sessions')
  },
  search(query, topK = 5) {
    return api.post('/chat/search', { query, top_k: topK })
  },
  summarize(days = 7) {
    return api.post('/chat/summarize', null, { params: { days } })
  }
}

// 流式对话
export async function* streamChat(message, sessionId = null, useRag = true) {
  const response = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      use_rag: useRag
    })
  })

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const text = decoder.decode(value)
    const lines = text.split('\n')

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data === '[DONE]') return
        try {
          yield JSON.parse(data)
        } catch (e) {
          // 忽略解析错误
        }
      }
    }
  }
}

export default api
