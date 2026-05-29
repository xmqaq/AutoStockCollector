import { ref, onUnmounted } from 'vue'

export interface WSMessage {
  type: string
  data: unknown
  timestamp: number
}

export interface WSOptions {
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  onMessage?: (msg: WSMessage) => void
  autoReconnect?: boolean
  reconnectInterval?: number
  heartbeatInterval?: number
}

class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string = ''
  private options: WSOptions = {}
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private isManualClose = false

  constructor() {}

  connect(url: string, options: WSOptions = {}) {
    this.url = url
    this.options = options
    this.isManualClose = false

    try {
      this.ws = new WebSocket(url)
      this.setupEventHandlers()
    } catch (error) {
      console.error('WebSocket connection error:', error)
      this.handleReconnect()
    }
  }

  private setupEventHandlers() {
    if (!this.ws) return

    this.ws.onopen = () => {
      console.log('WebSocket connected')
      this.startHeartbeat()
      this.options.onOpen?.()
    }

    this.ws.onclose = () => {
      console.log('WebSocket disconnected')
      this.stopHeartbeat()
      this.options.onClose?.()
      if (!this.isManualClose) {
        this.handleReconnect()
      }
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      this.options.onError?.(error)
    }

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WSMessage
        message.timestamp = Date.now()
        this.options.onMessage?.(message)
      } catch {
        console.error('Failed to parse WebSocket message')
      }
    }
  }

  private startHeartbeat() {
    if (this.options.heartbeatInterval) {
      this.heartbeatTimer = setInterval(() => {
        this.send({ type: 'ping', data: null })
      }, this.options.heartbeatInterval)
    }
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private handleReconnect() {
    if (this.options.autoReconnect !== false) {
      const interval = this.options.reconnectInterval || 5000
      this.reconnectTimer = setTimeout(() => {
        console.log('Attempting to reconnect...')
        this.connect(this.url, this.options)
      }, interval)
    }
  }

  send(data: unknown) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    } else {
      console.warn('WebSocket not connected, message not sent')
    }
  }

  close() {
    this.isManualClose = true
    this.stopHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  get readyState(): number {
    return this.ws?.readyState ?? WebSocket.CLOSED
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

const wsClient = ref<WebSocketClient | null>(null)
const isConnected = ref(false)
const lastMessage = ref<WSMessage | null>(null)
const messageQueue = ref<WSMessage[]>([])

export function useWebSocket() {
  function connect(url: string, options: WSOptions = {}) {
    if (wsClient.value) {
      wsClient.value.close()
    }

    wsClient.value = new WebSocketClient()
    wsClient.value.connect(url, {
      autoReconnect: true,
      reconnectInterval: 5000,
      heartbeatInterval: 30000,
      ...options,
      onOpen: () => {
        isConnected.value = true
        flushMessageQueue()
        options.onOpen?.()
      },
      onClose: () => {
        isConnected.value = false
        options.onClose?.()
      },
      onMessage: (msg) => {
        lastMessage.value = msg
        messageQueue.value.push(msg)
        if (messageQueue.value.length > 100) {
          messageQueue.value.shift()
        }
        options.onMessage?.(msg)
      },
    })
  }

  function disconnect() {
    wsClient.value?.close()
    wsClient.value = null
    isConnected.value = false
  }

  function send(data: unknown) {
    if (wsClient.value?.isConnected()) {
      wsClient.value.send(data)
    } else {
      console.warn('WebSocket not connected')
    }
  }

  function flushMessageQueue() {
    while (messageQueue.value.length > 0) {
      const msg = messageQueue.value.shift()
      lastMessage.value = msg
    }
  }

  function subscribe(type: string, callback: (data: unknown) => void) {
    const originalHandler = wsClient.value?.options.onMessage
    wsClient.value!.options.onMessage = (msg) => {
      if (msg.type === type) {
        callback(msg.data)
      }
      originalHandler?.(msg)
    }
  }

  return {
    isConnected,
    lastMessage,
    messageQueue,
    connect,
    disconnect,
    send,
    subscribe,
  }
}

export function createAlertWebSocket(onAlert: (alert: AlertData) => void) {
  const wsUrl = `ws://${window.location.host}/ws/alerts`
  
  const client = new WebSocketClient()
  client.connect(wsUrl, {
    autoReconnect: true,
    heartbeatInterval: 30000,
    onMessage: (msg) => {
      if (msg.type === 'alert') {
        onAlert(msg.data as AlertData)
      }
    },
  })

  return client
}

export interface AlertData {
  id: string
  code: string
  name: string
  type: 'price' | 'volume' | 'flow'
  level: 'info' | 'warning' | 'danger'
  message: string
  timestamp: number
}

export default useWebSocket