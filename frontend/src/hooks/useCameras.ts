import { useCallback } from 'react'
import { useCameraStore } from '../store'
import type { Camera, CameraListResponse, CameraType } from '../types'

const API_BASE = '/api'

export function useCameras() {
    const {
        cameras,
        selectedCameraId,
        loading,
        error,
        setCameras,
        selectCamera,
        updateCameraStatus,
        setLoading,
        setError,
    } = useCameraStore()

    const fetchCameras = useCallback(async () => {
        setLoading(true)
        setError(null)

        try {
            const response = await fetch(`${API_BASE}/cameras`)

            if (!response.ok) {
                throw new Error(`Failed to fetch cameras: ${response.statusText}`)
            }

            const data: CameraListResponse = await response.json()
            setCameras(data.cameras)
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
        } finally {
            setLoading(false)
        }
    }, [setCameras, setLoading, setError])

    const addCamera = useCallback(async (name: string, source: string, type: CameraType) => {
        try {
            const response = await fetch(`${API_BASE}/cameras`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, source, type }),
            })

            if (!response.ok) {
                throw new Error(`Failed to add camera: ${response.statusText}`)
            }

            const camera: Camera = await response.json()
            setCameras([...cameras, camera])
            return camera
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
            return null
        }
    }, [cameras, setCameras, setError])

    const startCamera = useCallback(async (cameraId: string) => {
        try {
            const response = await fetch(`${API_BASE}/cameras/${cameraId}/start`, {
                method: 'POST',
            })

            if (!response.ok) {
                throw new Error(`Failed to start camera: ${response.statusText}`)
            }

            updateCameraStatus(cameraId, 'running')
            return true
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
            updateCameraStatus(cameraId, 'error')
            return false
        }
    }, [updateCameraStatus, setError])

    const stopCamera = useCallback(async (cameraId: string) => {
        try {
            const response = await fetch(`${API_BASE}/cameras/${cameraId}/stop`, {
                method: 'POST',
            })

            if (!response.ok) {
                throw new Error(`Failed to stop camera: ${response.statusText}`)
            }

            updateCameraStatus(cameraId, 'stopped')
            return true
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
            return false
        }
    }, [updateCameraStatus, setError])

    const deleteCamera = useCallback(async (cameraId: string) => {
        try {
            const response = await fetch(`${API_BASE}/cameras/${cameraId}`, {
                method: 'DELETE',
            })

            if (!response.ok) {
                throw new Error(`Failed to delete camera: ${response.statusText}`)
            }

            setCameras(cameras.filter((c) => c.id !== cameraId))
            if (selectedCameraId === cameraId) {
                selectCamera(null)
            }
            return true
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
            return false
        }
    }, [cameras, selectedCameraId, setCameras, selectCamera, setError])

    const getMjpegUrl = useCallback((cameraId: string) => {
        return `${API_BASE}/cameras/${cameraId}/mjpeg`
    }, [])

    const selectedCamera = cameras.find((c) => c.id === selectedCameraId) ?? null

    return {
        cameras,
        selectedCamera,
        selectedCameraId,
        loading,
        error,

        fetchCameras,
        addCamera,
        startCamera,
        stopCamera,
        deleteCamera,
        selectCamera,
        getMjpegUrl,
    }
}
