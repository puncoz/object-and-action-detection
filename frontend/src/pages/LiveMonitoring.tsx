import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
    Camera,
    Play,
    Square,
    Plus,
    Circle,
    AlertCircle,
    Trash2,
    X
} from 'lucide-react'
import { useCameras } from '../hooks/useCameras'
import { useWebSocket } from '../hooks/useWebSocket'
import { useDetectionStore } from '../store'
import VideoPlayer from '../components/VideoPlayer'
import ActionStatusCard from '../components/ActionStatusCard'
import LiveActionFeed from '../components/LiveActionFeed'
import type { CameraType } from '../types'

export default function LiveMonitoring() {
    const { t } = useTranslation()
    const {
        cameras,
        selectedCamera,
        selectedCameraId,
        loading,
        fetchCameras,
        addCamera,
        startCamera,
        stopCamera,
        deleteCamera,
        selectCamera,
        getMjpegUrl,
    } = useCameras()

    const { currentDetection } = useDetectionStore()
    const { isConnected } = useWebSocket({ cameraId: selectedCameraId })

    const [showAddModal, setShowAddModal] = useState(false)
    const [newCamera, setNewCamera] = useState({
        name: '',
        source: '',
        type: 'file' as CameraType,
    })

    useEffect(() => {
        fetchCameras()
    }, [fetchCameras])

    const handleAddCamera = async () => {
        if (newCamera.name && newCamera.source) {
            await addCamera(newCamera.name, newCamera.source, newCamera.type)
            setNewCamera({ name: '', source: '', type: 'file' })
            setShowAddModal(false)
        }
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'running':
                return 'text-industrial-success'
            case 'error':
                return 'text-industrial-danger'
            default:
                return 'text-industrial-muted'
        }
    }

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'running':
                return <Circle className="fill-current" size={8} />
            case 'error':
                return <AlertCircle size={12} />
            default:
                return <Circle size={8} />
        }
    }

    return (
        <div className="h-full flex">
            {/* Left Sidebar - Camera List */}
            <aside className="w-64 bg-industrial-surface border-r border-industrial-border flex flex-col">
                <div className="p-4 border-b border-industrial-border">
                    <div className="flex items-center justify-between mb-2">
                        <h2 className="font-semibold flex items-center gap-2">
                            <Camera size={18} />
                            {t('camera.title')}
                        </h2>
                        <button
                            onClick={() => setShowAddModal(true)}
                            className="p-1.5 rounded hover:bg-industrial-border transition-colors"
                            title={t('camera.add')}
                        >
                            <Plus size={16} />
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto p-2">
                    {loading && cameras.length === 0 ? (
                        <div className="text-center text-industrial-muted py-4">
                            {t('common.loading')}
                        </div>
                    ) : cameras.length === 0 ? (
                        <div className="text-center text-industrial-muted py-4 text-sm">
                            {t('camera.noCamera')}
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {cameras.map((camera) => (
                                <div
                                    key={camera.id}
                                    className={`p-3 rounded cursor-pointer transition-colors ${selectedCameraId === camera.id
                                        ? 'bg-industrial-accent/20 border border-industrial-accent/50'
                                        : 'hover:bg-industrial-border border border-transparent'
                                        }`}
                                    onClick={() => selectCamera(camera.id)}
                                >
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="font-medium truncate">{camera.name}</span>
                                        <span className={`flex items-center gap-1 ${getStatusColor(camera.status)}`}>
                                            {getStatusIcon(camera.status)}
                                        </span>
                                    </div>
                                    <div className="text-xs text-industrial-muted truncate">
                                        {camera.type}: {camera.source}
                                    </div>

                                    {/* Camera Controls */}
                                    <div className="flex items-center gap-2 mt-2">
                                        {camera.status === 'running' ? (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation()
                                                    stopCamera(camera.id)
                                                }}
                                                className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-industrial-danger/20 text-industrial-danger hover:bg-industrial-danger/30"
                                            >
                                                <Square size={10} />
                                                {t('camera.stop')}
                                            </button>
                                        ) : (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation()
                                                    startCamera(camera.id)
                                                }}
                                                className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-industrial-success/20 text-industrial-success hover:bg-industrial-success/30"
                                            >
                                                <Play size={10} />
                                                {t('camera.start')}
                                            </button>
                                        )}
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation()
                                                deleteCamera(camera.id)
                                            }}
                                            className="p-1 rounded text-industrial-muted hover:text-industrial-danger hover:bg-industrial-danger/10"
                                        >
                                            <Trash2 size={12} />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* System Status */}
                {selectedCamera && currentDetection && (
                    <div className="p-4 border-t border-industrial-border text-xs">
                        <div className="flex justify-between mb-1">
                            <span className="text-industrial-muted">{t('camera.fps')}:</span>
                            <span>{currentDetection.system.fps.toFixed(1)}</span>
                        </div>
                        <div className="flex justify-between mb-1">
                            <span className="text-industrial-muted">{t('camera.latency')}:</span>
                            <span>{currentDetection.system.latency_ms}ms</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-industrial-muted">WebSocket:</span>
                            <span className={isConnected ? 'text-industrial-success' : 'text-industrial-danger'}>
                                {isConnected ? 'Connected' : 'Disconnected'}
                            </span>
                        </div>
                    </div>
                )}
            </aside>

            {/* Main Content - Video Player */}
            <main className="flex-1 flex flex-col overflow-hidden">
                <div className="flex-1 p-4">
                    {selectedCamera && selectedCamera.status === 'running' ? (
                        <VideoPlayer
                            src={getMjpegUrl(selectedCamera.id)}
                            detection={currentDetection}
                        />
                    ) : (
                        <div className="h-full flex items-center justify-center bg-industrial-surface rounded-lg border border-industrial-border">
                            <div className="text-center text-industrial-muted">
                                <Camera size={48} className="mx-auto mb-4 opacity-50" />
                                <p>{selectedCamera ? t('camera.start') + ' camera to view feed' : t('camera.selectCamera')}</p>
                            </div>
                        </div>
                    )}
                </div>

                {/* Action Status */}
                {selectedCamera && currentDetection && (
                    <div className="px-4 pb-4">
                        <ActionStatusCard detection={currentDetection} />
                    </div>
                )}
            </main>

            {/* Right Sidebar - Live Action Feed */}
            <aside className="w-80 bg-industrial-surface border-l border-industrial-border" style={{ height: "500px" }}>
                <LiveActionFeed />
            </aside>

            {/* Add Camera Modal */}
            {showAddModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-industrial-surface border border-industrial-border rounded-lg p-6 w-96">
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-lg font-semibold">{t('camera.add')}</h3>
                            <button
                                onClick={() => setShowAddModal(false)}
                                className="p-1 rounded hover:bg-industrial-border"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm text-industrial-muted mb-1">Name</label>
                                <input
                                    type="text"
                                    value={newCamera.name}
                                    onChange={(e) => setNewCamera({ ...newCamera, name: e.target.value })}
                                    className="input w-full"
                                    placeholder="Camera 1"
                                />
                            </div>

                            <div>
                                <label className="block text-sm text-industrial-muted mb-1">Type</label>
                                <select
                                    value={newCamera.type}
                                    onChange={(e) => setNewCamera({ ...newCamera, type: e.target.value as CameraType })}
                                    className="input w-full"
                                >
                                    <option value="file">Video File</option>
                                    <option value="webcam">Webcam</option>
                                    <option value="rtsp">RTSP Stream</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm text-industrial-muted mb-1">Source</label>
                                <input
                                    type="text"
                                    value={newCamera.source}
                                    onChange={(e) => setNewCamera({ ...newCamera, source: e.target.value })}
                                    className="input w-full"
                                    placeholder={
                                        newCamera.type === 'file'
                                            ? '/path/to/video.mp4'
                                            : newCamera.type === 'webcam'
                                                ? '0'
                                                : 'rtsp://...'
                                    }
                                />
                            </div>

                            <div className="flex justify-end gap-2 pt-2">
                                <button
                                    onClick={() => setShowAddModal(false)}
                                    className="btn btn-ghost"
                                >
                                    {t('common.cancel')}
                                </button>
                                <button
                                    onClick={handleAddCamera}
                                    className="btn btn-primary"
                                    disabled={!newCamera.name || !newCamera.source}
                                >
                                    {t('camera.add')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
