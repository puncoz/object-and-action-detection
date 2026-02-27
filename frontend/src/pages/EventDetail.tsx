import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { format } from 'date-fns'
import {
    ArrowLeft,
    CheckCircle,
    XCircle,
    Clock,
    Download,
    MessageSquare,
    Camera,
    Play,
    Image,
} from 'lucide-react'
import { useEvents } from '../hooks/useEvents'

export default function EventDetail() {
    const { t } = useTranslation()
    const { eventId } = useParams<{ eventId: string }>()
    const navigate = useNavigate()
    const {
        selectedEvent: event,
        loading,
        error,
        fetchEvent,
        verifyEvent,
        addNote,
        getSnapshotUrl,
        getClipUrl,
    } = useEvents()

    const [noteText, setNoteText] = useState('')
    const [showNoteInput, setShowNoteInput] = useState(false)
    const [activeTab, setActiveTab] = useState<'clip' | 'snapshot'>('clip')

    useEffect(() => {
        if (eventId) {
            fetchEvent(eventId)
        }
    }, [eventId, fetchEvent])

    useEffect(() => {
        if (event?.note) {
            setNoteText(event.note)
        }
    }, [event])

    const handleVerify = async (verified: boolean) => {
        if (eventId) {
            await verifyEvent(eventId, verified)
        }
    }

    const handleSaveNote = async () => {
        if (eventId && noteText) {
            await addNote(eventId, noteText)
            setShowNoteInput(false)
        }
    }

    const handleExport = () => {
        if (event) {
            const dataStr = JSON.stringify(event, null, 2)
            const blob = new Blob([dataStr], { type: 'application/json' })
            const url = URL.createObjectURL(blob)
            const link = document.createElement('a')
            link.href = url
            link.download = `event_${event.id}.json`
            link.click()
            URL.revokeObjectURL(url)
        }
    }

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center">
                <div className="text-industrial-muted">{t('common.loading')}</div>
            </div>
        )
    }

    if (error || !event) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-4">
                <div className="text-industrial-danger">{error || 'Event not found'}</div>
                <button onClick={() => navigate('/events')} className="btn btn-ghost">
                    <ArrowLeft size={16} className="mr-2" />
                    Back to Events
                </button>
            </div>
        )
    }

    const duration = event.end_ts
        ? (new Date(event.end_ts).getTime() - new Date(event.start_ts).getTime()) / 1000
        : 0

    return (
        <div className="h-full flex flex-col p-6">
            {/* Header */}
            <div className="flex items-center gap-4 mb-6">
                <button
                    onClick={() => navigate('/events')}
                    className="p-2 rounded hover:bg-industrial-border transition-colors"
                >
                    <ArrowLeft size={20} />
                </button>
                <div>
                    <h1 className="text-2xl font-bold">{t('eventDetail.title')}</h1>
                    <div className="text-sm text-industrial-muted">ID: {event.id}</div>
                </div>
            </div>

            <div className="flex-1 grid grid-cols-3 gap-6 overflow-hidden">
                {/* Left: Media */}
                <div className="col-span-2 flex flex-col">
                    {/* Tabs */}
                    <div className="flex gap-2 mb-4">
                        <button
                            onClick={() => setActiveTab('clip')}
                            className={`btn ${activeTab === 'clip' ? 'btn-primary' : 'btn-ghost'} flex items-center gap-2`}
                        >
                            <Play size={16} />
                            {t('eventDetail.clip')}
                        </button>
                        <button
                            onClick={() => setActiveTab('snapshot')}
                            className={`btn ${activeTab === 'snapshot' ? 'btn-primary' : 'btn-ghost'} flex items-center gap-2`}
                        >
                            <Image size={16} />
                            {t('eventDetail.snapshot')}
                        </button>
                    </div>

                    {/* Media Content */}
                    <div className="flex-1 bg-black rounded-lg overflow-hidden">
                        {activeTab === 'clip' && event.clip_path ? (
                            <video
                                src={getClipUrl(event.id)}
                                controls
                                className="w-full h-full object-contain"
                            />
                        ) : activeTab === 'snapshot' && event.snapshot_path ? (
                            <img
                                src={getSnapshotUrl(event.id)}
                                alt="Event Snapshot"
                                className="w-full h-full object-contain"
                            />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-industrial-muted">
                                No {activeTab} available
                            </div>
                        )}
                    </div>
                </div>

                {/* Right: Metadata & Actions */}
                <div className="flex flex-col gap-4 overflow-y-auto">
                    {/* Verification Status */}
                    <div className="card">
                        <h3 className="font-semibold mb-3">Status</h3>
                        <div className="flex items-center gap-2 mb-4">
                            {event.verified === true && (
                                <span className="badge badge-success flex items-center gap-1">
                                    <CheckCircle size={14} />
                                    {t('eventDetail.verified')}
                                </span>
                            )}
                            {event.verified === false && (
                                <span className="badge badge-danger flex items-center gap-1">
                                    <XCircle size={14} />
                                    {t('eventDetail.rejected')}
                                </span>
                            )}
                            {event.verified === null && (
                                <span className="badge badge-warning flex items-center gap-1">
                                    <Clock size={14} />
                                    {t('eventDetail.pending')}
                                </span>
                            )}
                        </div>

                        <div className="flex gap-2">
                            <button
                                onClick={() => handleVerify(true)}
                                className={`btn flex-1 ${event.verified === true ? 'btn-success' : 'btn-ghost'
                                    } flex items-center justify-center gap-2`}
                            >
                                <CheckCircle size={16} />
                                {t('eventDetail.actions.verify')}
                            </button>
                            <button
                                onClick={() => handleVerify(false)}
                                className={`btn flex-1 ${event.verified === false ? 'btn-danger' : 'btn-ghost'
                                    } flex items-center justify-center gap-2`}
                            >
                                <XCircle size={16} />
                                {t('eventDetail.actions.reject')}
                            </button>
                        </div>
                    </div>

                    {/* Metadata */}
                    <div className="card">
                        <h3 className="font-semibold mb-3">{t('eventDetail.metadata')}</h3>
                        <dl className="space-y-2 text-sm">
                            <div className="flex justify-between">
                                <dt className="text-industrial-muted">
                                    <Camera size={14} className="inline mr-1" />
                                    Camera
                                </dt>
                                <dd>{event.camera_id}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt className="text-industrial-muted">Track ID</dt>
                                <dd>{event.track_id}</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt className="text-industrial-muted">Start</dt>
                                <dd>{format(new Date(event.start_ts), 'MMM d, HH:mm:ss')}</dd>
                            </div>
                            {event.end_ts && (
                                <div className="flex justify-between">
                                    <dt className="text-industrial-muted">End</dt>
                                    <dd>{format(new Date(event.end_ts), 'MMM d, HH:mm:ss')}</dd>
                                </div>
                            )}
                            <div className="flex justify-between">
                                <dt className="text-industrial-muted">{t('eventDetail.duration')}</dt>
                                <dd>{duration.toFixed(1)}s</dd>
                            </div>
                            <div className="flex justify-between">
                                <dt className="text-industrial-muted">{t('action.confidence')}</dt>
                                <dd>{(event.confidence * 100).toFixed(0)}%</dd>
                            </div>
                        </dl>
                    </div>

                    {/* Sequence */}
                    <div className="card">
                        <h3 className="font-semibold mb-3">{t('eventDetail.sequence')}</h3>
                        <div className="flex flex-wrap gap-2">
                            {event.sequence.map((state, idx) => (
                                <span
                                    key={idx}
                                    className={`badge badge-info state-${state}`}
                                >
                                    {idx + 1}. {t(`action.states.${state}`)}
                                </span>
                            ))}
                        </div>
                    </div>

                    {/* Note */}
                    <div className="card">
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="font-semibold">Note</h3>
                            <button
                                onClick={() => setShowNoteInput(!showNoteInput)}
                                className="btn btn-ghost btn-sm"
                            >
                                <MessageSquare size={14} />
                            </button>
                        </div>

                        {showNoteInput || event.note ? (
                            <div>
                                <textarea
                                    value={noteText}
                                    onChange={(e) => setNoteText(e.target.value)}
                                    placeholder={t('eventDetail.note.placeholder')}
                                    className="input w-full h-24 resize-none"
                                    readOnly={!showNoteInput}
                                />
                                {showNoteInput && (
                                    <div className="flex justify-end gap-2 mt-2">
                                        <button
                                            onClick={() => {
                                                setShowNoteInput(false)
                                                setNoteText(event.note || '')
                                            }}
                                            className="btn btn-ghost btn-sm"
                                        >
                                            {t('common.cancel')}
                                        </button>
                                        <button
                                            onClick={handleSaveNote}
                                            className="btn btn-primary btn-sm"
                                        >
                                            {t('eventDetail.note.save')}
                                        </button>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-sm text-industrial-muted">No note added</div>
                        )}
                    </div>

                    {/* Export */}
                    <button
                        onClick={handleExport}
                        className="btn btn-ghost flex items-center justify-center gap-2"
                    >
                        <Download size={16} />
                        {t('eventDetail.actions.export')}
                    </button>
                </div>
            </div>
        </div>
    )
}
