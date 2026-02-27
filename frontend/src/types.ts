// API Types matching backend schemas

export type CameraType = 'rtsp' | 'file' | 'webcam'
export type CameraStatus = 'running' | 'stopped' | 'error'
export type ActionState = 'idle' | 'bottle_in_hand' | 'cap_opening' | 'drinking' | 'completed' | 'uncertain'

export interface Camera {
    id: string
    name: string
    source: string
    type: CameraType
    status: CameraStatus
    created_at: string
}

export interface CameraListResponse {
    cameras: Camera[]
    total: number
}

export interface BoundingBox {
    x1: number
    y1: number
    x2: number
    y2: number
}

export interface ActionSignals {
    hand_bottle_proximity: number
    neck_hand_proximity: number
    wrist_rotation: number
    mouth_bottle_proximity: number
    bottle_tilt: number
}

export interface ActionResult {
    state: ActionState
    confidence: number
    signals: ActionSignals
}

export interface PersonDetection {
    track_id: number
    person_bbox: BoundingBox | null
    bottle_bbox: BoundingBox | null
    action: ActionResult
}

export interface SystemStatus {
    fps: number
    latency_ms: number
    status: string
}

export interface DetectionFrame {
    ts: string
    camera_id: string
    frame_id: number
    people: PersonDetection[]
    system: SystemStatus
}

export interface Event {
    id: string
    camera_id: string
    track_id: number
    start_ts: string
    end_ts: string | null
    sequence: string[]
    confidence: number
    snapshot_path: string | null
    clip_path: string | null
    verified: boolean | null
    note: string | null
    created_at: string
}

export interface EventListResponse {
    events: Event[]
    total: number
    page: number
    page_size: number
}

export interface WSMessage {
    type: 'detection' | 'event' | 'status' | 'error' | 'keepalive' | 'pong'
    data?: unknown
}

// UI State types
export interface ActionFeedItem {
    id: string
    timestamp: Date
    cameraId: string
    trackId: number
    state: ActionState
    confidence: number
    isCompleted: boolean
}
