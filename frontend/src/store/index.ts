import { create } from 'zustand'
import type { Camera, DetectionFrame, Event, ActionFeedItem } from '../types'

// Camera Store
interface CameraStore {
    cameras: Camera[]
    selectedCameraId: string | null
    loading: boolean
    error: string | null

    setCameras: (cameras: Camera[]) => void
    selectCamera: (id: string | null) => void
    updateCameraStatus: (id: string, status: Camera['status']) => void
    setLoading: (loading: boolean) => void
    setError: (error: string | null) => void
}

export const useCameraStore = create<CameraStore>((set) => ({
    cameras: [],
    selectedCameraId: null,
    loading: false,
    error: null,

    setCameras: (cameras) => set({ cameras }),
    selectCamera: (id) => set({ selectedCameraId: id }),
    updateCameraStatus: (id, status) => set((state) => ({
        cameras: state.cameras.map((c) =>
            c.id === id ? { ...c, status } : c
        ),
    })),
    setLoading: (loading) => set({ loading }),
    setError: (error) => set({ error }),
}))

// Detection Store
interface DetectionStore {
    currentDetection: DetectionFrame | null
    actionFeed: ActionFeedItem[]
    maxFeedItems: number

    setDetection: (detection: DetectionFrame) => void
    addFeedItem: (item: ActionFeedItem) => void
    clearFeed: () => void
}

export const useDetectionStore = create<DetectionStore>((set) => ({
    currentDetection: null,
    actionFeed: [],
    maxFeedItems: 50,

    setDetection: (detection) => set({ currentDetection: detection }),
    addFeedItem: (item) => set((state) => ({
        actionFeed: [item, ...state.actionFeed].slice(0, state.maxFeedItems),
    })),
    clearFeed: () => set({ actionFeed: [] }),
}))

// Event Store
interface EventStore {
    events: Event[]
    selectedEvent: Event | null
    total: number
    page: number
    pageSize: number
    loading: boolean
    error: string | null

    // Filters
    filters: {
        cameraId: string | null
        verified: boolean | null
        fromDate: Date | null
        toDate: Date | null
    }

    setEvents: (events: Event[], total: number) => void
    appendEvents: (events: Event[]) => void
    selectEvent: (event: Event | null) => void
    updateEvent: (id: string, updates: Partial<Event>) => void
    setPage: (page: number) => void
    setFilters: (filters: Partial<EventStore['filters']>) => void
    resetFilters: () => void
    setLoading: (loading: boolean) => void
    setError: (error: string | null) => void
}

export const useEventStore = create<EventStore>((set) => ({
    events: [],
    selectedEvent: null,
    total: 0,
    page: 1,
    pageSize: 20,
    loading: false,
    error: null,
    filters: {
        cameraId: null,
        verified: null,
        fromDate: null,
        toDate: null,
    },

    setEvents: (events, total) => set({ events, total, page: 1 }),
    appendEvents: (events) => set((state) => ({
        events: [...state.events, ...events],
        page: state.page + 1,
    })),
    selectEvent: (event) => set({ selectedEvent: event }),
    updateEvent: (id, updates) => set((state) => ({
        events: state.events.map((e) =>
            e.id === id ? { ...e, ...updates } : e
        ),
        selectedEvent: state.selectedEvent?.id === id
            ? { ...state.selectedEvent, ...updates }
            : state.selectedEvent,
    })),
    setPage: (page) => set({ page }),
    setFilters: (filters) => set((state) => ({
        filters: { ...state.filters, ...filters },
        page: 1,
    })),
    resetFilters: () => set({
        filters: {
            cameraId: null,
            verified: null,
            fromDate: null,
            toDate: null,
        },
        page: 1,
    }),
    setLoading: (loading) => set({ loading }),
    setError: (error) => set({ error }),
}))

// UI Store
interface UIStore {
    language: 'en' | 'jp'
    showOverlays: {
        pose: boolean
        hands: boolean
        bottle: boolean
    }

    setLanguage: (lang: 'en' | 'jp') => void
    toggleOverlay: (type: 'pose' | 'hands' | 'bottle') => void
}

export const useUIStore = create<UIStore>((set) => ({
    language: 'en',
    showOverlays: {
        pose: true,
        hands: true,
        bottle: true,
    },

    setLanguage: (language) => set({ language }),
    toggleOverlay: (type) => set((state) => ({
        showOverlays: {
            ...state.showOverlays,
            [type]: !state.showOverlays[type],
        },
    })),
}))
