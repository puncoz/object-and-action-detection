import { useCallback } from 'react'
import { useEventStore } from '../store'
import type { Event, EventListResponse } from '../types'

const API_BASE = '/api'

export function useEvents() {
    const {
        events,
        selectedEvent,
        total,
        page,
        pageSize,
        loading,
        error,
        filters,
        setEvents,
        appendEvents,
        selectEvent,
        updateEvent,
        setFilters,
        resetFilters,
        setLoading,
        setError,
    } = useEventStore()

    const fetchEvents = useCallback(async (append = false) => {
        setLoading(true)
        setError(null)

        try {
            const params = new URLSearchParams()
            params.set('page', append ? String(page + 1) : '1')
            params.set('page_size', String(pageSize))

            if (filters.cameraId) params.set('camera_id', filters.cameraId)
            if (filters.verified !== null) params.set('verified', String(filters.verified))
            if (filters.fromDate) params.set('from', filters.fromDate.toISOString())
            if (filters.toDate) params.set('to', filters.toDate.toISOString())

            const response = await fetch(`${API_BASE}/events?${params}`)

            if (!response.ok) {
                throw new Error(`Failed to fetch events: ${response.statusText}`)
            }

            const data: EventListResponse = await response.json()

            if (append) {
                appendEvents(data.events)
            } else {
                setEvents(data.events, data.total)
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
        } finally {
            setLoading(false)
        }
    }, [page, pageSize, filters, setEvents, appendEvents, setLoading, setError])

    const fetchEvent = useCallback(async (eventId: string): Promise<Event | null> => {
        try {
            const response = await fetch(`${API_BASE}/events/${eventId}`)

            if (!response.ok) {
                throw new Error(`Failed to fetch event: ${response.statusText}`)
            }

            const event: Event = await response.json()
            selectEvent(event)
            return event
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
            return null
        }
    }, [selectEvent, setError])

    const verifyEvent = useCallback(async (eventId: string, verified: boolean) => {
        try {
            const response = await fetch(`${API_BASE}/events/${eventId}/verify`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ verified }),
            })

            if (!response.ok) {
                throw new Error(`Failed to verify event: ${response.statusText}`)
            }

            const updatedEvent: Event = await response.json()
            updateEvent(eventId, { verified: updatedEvent.verified })
            return updatedEvent
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
            return null
        }
    }, [updateEvent, setError])

    const addNote = useCallback(async (eventId: string, note: string) => {
        try {
            const response = await fetch(`${API_BASE}/events/${eventId}/note`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ note }),
            })

            if (!response.ok) {
                throw new Error(`Failed to add note: ${response.statusText}`)
            }

            const updatedEvent: Event = await response.json()
            updateEvent(eventId, { note: updatedEvent.note })
            return updatedEvent
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
            return null
        }
    }, [updateEvent, setError])

    const getSnapshotUrl = useCallback((eventId: string) => {
        return `${API_BASE}/events/${eventId}/snapshot`
    }, [])

    const getClipUrl = useCallback((eventId: string) => {
        return `${API_BASE}/events/${eventId}/clip`
    }, [])

    return {
        events,
        selectedEvent,
        total,
        page,
        pageSize,
        loading,
        error,
        filters,
        hasMore: events.length < total,

        fetchEvents,
        fetchEvent,
        verifyEvent,
        addNote,
        selectEvent,
        setFilters,
        resetFilters,
        loadMore: () => fetchEvents(true),
        getSnapshotUrl,
        getClipUrl,
    }
}
