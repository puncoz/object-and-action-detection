import { useEffect, useRef, useCallback, useState } from 'react'
import type { DetectionFrame, ActionFeedItem } from '../types'
import { useDetectionStore } from '../store'

interface UseWebSocketOptions {
    cameraId: string | null
    onDetection?: (detection: DetectionFrame) => void
    onError?: (error: Error) => void
}

export function useWebSocket({ cameraId, onDetection, onError }: UseWebSocketOptions) {
    const wsRef = useRef<WebSocket | null>(null)
    const [isConnected, setIsConnected] = useState(false)
    const [lastMessage, setLastMessage] = useState<DetectionFrame | null>(null)
    const reconnectTimeoutRef = useRef<number | null>(null)

    const { setDetection, addFeedItem } = useDetectionStore()

    const connect = useCallback(() => {
        if (!cameraId) return

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const wsUrl = `${protocol}//${window.location.host}/ws/cameras/${cameraId}`

        try {
            const ws = new WebSocket(wsUrl)

            ws.onopen = () => {
                console.log('WebSocket connected')
                setIsConnected(true)
                // Subscribe to camera
                ws.send(JSON.stringify({ type: 'subscribe', camera_id: cameraId }))
            }

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data)

                    if (data.type === 'keepalive' || data.type === 'pong') {
                        return
                    }

                    // Handle detection frame
                    if (data.ts && data.camera_id && data.people) {
                        const detection = data as DetectionFrame
                        setLastMessage(detection)
                        setDetection(detection)
                        onDetection?.(detection)

                        // Add to feed if state changed significantly
                        detection.people.forEach((person) => {
                            if (person.action.state !== 'idle' && person.action.confidence > 0.3) {
                                const feedItem: ActionFeedItem = {
                                    id: `${detection.frame_id}-${person.track_id}`,
                                    timestamp: new Date(detection.ts),
                                    cameraId: detection.camera_id,
                                    trackId: person.track_id,
                                    state: person.action.state,
                                    confidence: person.action.confidence,
                                    isCompleted: person.action.state === 'completed',
                                }
                                addFeedItem(feedItem)
                            }
                        })
                    }
                } catch (e) {
                    console.error('Failed to parse WebSocket message:', e)
                }
            }

            ws.onerror = (event) => {
                console.error('WebSocket error:', event)
                onError?.(new Error('WebSocket connection error'))
            }

            ws.onclose = () => {
                console.log('WebSocket disconnected')
                setIsConnected(false)
                wsRef.current = null

                // Attempt reconnect after delay
                if (cameraId) {
                    reconnectTimeoutRef.current = window.setTimeout(() => {
                        connect()
                    }, 3000)
                }
            }

            wsRef.current = ws
        } catch (e) {
            console.error('Failed to create WebSocket:', e)
            onError?.(e as Error)
        }
    }, [cameraId, onDetection, onError, setDetection, addFeedItem])

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
            reconnectTimeoutRef.current = null
        }

        if (wsRef.current) {
            wsRef.current.close()
            wsRef.current = null
        }

        setIsConnected(false)
    }, [])

    useEffect(() => {
        if (cameraId) {
            connect()
        } else {
            disconnect()
        }

        return () => {
            disconnect()
        }
    }, [cameraId, connect, disconnect])

    const sendMessage = useCallback((message: object) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(message))
        }
    }, [])

    return {
        isConnected,
        lastMessage,
        sendMessage,
        reconnect: connect,
        disconnect,
    }
}
