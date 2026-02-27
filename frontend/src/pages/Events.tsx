import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { format } from 'date-fns'
import {
    Filter,
    Calendar,
    Camera,
    CheckCircle,
    XCircle,
    Clock,
    ChevronRight,
    RefreshCw
} from 'lucide-react'
import { useEvents } from '../hooks/useEvents'
import { useCameras } from '../hooks/useCameras'
import type { Event } from '../types'

export default function Events() {
    const { t } = useTranslation()
    const navigate = useNavigate()
    const {
        events,
        total,
        loading,
        error,
        filters,
        hasMore,
        fetchEvents,
        setFilters,
        resetFilters,
        loadMore,
    } = useEvents()

    const { cameras, fetchCameras } = useCameras()
    const [showFilters, setShowFilters] = useState(false)

    useEffect(() => {
        fetchCameras()
        fetchEvents()
    }, [fetchCameras, fetchEvents])

    const handleEventClick = (event: Event) => {
        navigate(`/events/${event.id}`)
    }

    const getVerificationBadge = (verified: boolean | null) => {
        if (verified === true) {
            return (
                <span className="badge badge-success flex items-center gap-1">
                    <CheckCircle size={12} />
                    {t('eventDetail.verified')}
                </span>
            )
        }
        if (verified === false) {
            return (
                <span className="badge badge-danger flex items-center gap-1">
                    <XCircle size={12} />
                    {t('eventDetail.rejected')}
                </span>
            )
        }
        return (
            <span className="badge badge-warning flex items-center gap-1">
                <Clock size={12} />
                {t('events.filters.pending')}
            </span>
        )
    }

    const getSequenceDisplay = (sequence: string[]) => {
        return sequence.map((_, idx) => (
            <span
                key={idx}
                className="inline-block w-2 h-2 rounded-full bg-industrial-success mr-1"
            />
        ))
    }

    return (
        <div className="h-full flex flex-col p-6">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-bold">{t('events.title')}</h1>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => fetchEvents()}
                        className="btn btn-ghost flex items-center gap-2"
                        disabled={loading}
                    >
                        <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                        {t('common.retry')}
                    </button>
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className={`btn ${showFilters ? 'btn-primary' : 'btn-ghost'} flex items-center gap-2`}
                    >
                        <Filter size={16} />
                        Filters
                    </button>
                </div>
            </div>

            {/* Filters */}
            {showFilters && (
                <div className="card mb-6">
                    <div className="grid grid-cols-4 gap-4">
                        {/* Camera Filter */}
                        <div>
                            <label className="block text-sm text-industrial-muted mb-1">
                                <Camera size={14} className="inline mr-1" />
                                {t('events.filters.camera')}
                            </label>
                            <select
                                value={filters.cameraId || ''}
                                onChange={(e) => setFilters({ cameraId: e.target.value || null })}
                                className="input w-full"
                            >
                                <option value="">{t('events.filters.all')}</option>
                                {cameras.map((cam) => (
                                    <option key={cam.id} value={cam.id}>
                                        {cam.name}
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Verification Filter */}
                        <div>
                            <label className="block text-sm text-industrial-muted mb-1">
                                <CheckCircle size={14} className="inline mr-1" />
                                {t('events.filters.verified')}
                            </label>
                            <select
                                value={filters.verified === null ? '' : String(filters.verified)}
                                onChange={(e) => {
                                    const val = e.target.value
                                    setFilters({
                                        verified: val === '' ? null : val === 'true',
                                    })
                                }}
                                className="input w-full"
                            >
                                <option value="">{t('events.filters.all')}</option>
                                <option value="true">{t('events.filters.verifiedOnly')}</option>
                                <option value="false">{t('events.filters.unverified')}</option>
                            </select>
                        </div>

                        {/* Date From */}
                        <div>
                            <label className="block text-sm text-industrial-muted mb-1">
                                <Calendar size={14} className="inline mr-1" />
                                {t('common.from')}
                            </label>
                            <input
                                type="date"
                                value={filters.fromDate ? format(filters.fromDate, 'yyyy-MM-dd') : ''}
                                onChange={(e) =>
                                    setFilters({
                                        fromDate: e.target.value ? new Date(e.target.value) : null,
                                    })
                                }
                                className="input w-full"
                            />
                        </div>

                        {/* Date To */}
                        <div>
                            <label className="block text-sm text-industrial-muted mb-1">
                                <Calendar size={14} className="inline mr-1" />
                                {t('common.to')}
                            </label>
                            <input
                                type="date"
                                value={filters.toDate ? format(filters.toDate, 'yyyy-MM-dd') : ''}
                                onChange={(e) =>
                                    setFilters({
                                        toDate: e.target.value ? new Date(e.target.value) : null,
                                    })
                                }
                                className="input w-full"
                            />
                        </div>
                    </div>

                    <div className="flex justify-end gap-2 mt-4">
                        <button onClick={resetFilters} className="btn btn-ghost">
                            {t('common.reset')}
                        </button>
                        <button onClick={() => fetchEvents()} className="btn btn-primary">
                            {t('common.apply')}
                        </button>
                    </div>
                </div>
            )}

            {/* Results Count */}
            <div className="text-sm text-industrial-muted mb-4">
                {total} events found
            </div>

            {/* Events Table */}
            <div className="flex-1 overflow-auto">
                {error ? (
                    <div className="text-center text-industrial-danger py-8">
                        {error}
                    </div>
                ) : events.length === 0 && !loading ? (
                    <div className="text-center text-industrial-muted py-8">
                        {t('events.noEvents')}
                    </div>
                ) : (
                    <table className="w-full">
                        <thead className="bg-industrial-surface sticky top-0">
                            <tr className="border-b border-industrial-border">
                                <th className="text-left p-3 font-medium">{t('events.table.time')}</th>
                                <th className="text-left p-3 font-medium">{t('events.table.camera')}</th>
                                <th className="text-left p-3 font-medium">{t('events.table.confidence')}</th>
                                <th className="text-left p-3 font-medium">{t('events.table.sequence')}</th>
                                <th className="text-left p-3 font-medium">{t('events.table.status')}</th>
                                <th className="w-10"></th>
                            </tr>
                        </thead>
                        <tbody>
                            {events.map((event) => (
                                <tr
                                    key={event.id}
                                    onClick={() => handleEventClick(event)}
                                    className="border-b border-industrial-border hover:bg-industrial-surface cursor-pointer transition-colors"
                                >
                                    <td className="p-3">
                                        <div className="font-medium">
                                            {format(new Date(event.start_ts), 'MMM d, yyyy')}
                                        </div>
                                        <div className="text-sm text-industrial-muted">
                                            {format(new Date(event.start_ts), 'HH:mm:ss')}
                                        </div>
                                    </td>
                                    <td className="p-3">
                                        {cameras.find((c) => c.id === event.camera_id)?.name || event.camera_id}
                                    </td>
                                    <td className="p-3">
                                        <div className="flex items-center gap-2">
                                            <div className="w-16 h-1.5 bg-industrial-border rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-industrial-accent"
                                                    style={{ width: `${event.confidence * 100}%` }}
                                                />
                                            </div>
                                            <span className="text-sm">{(event.confidence * 100).toFixed(0)}%</span>
                                        </div>
                                    </td>
                                    <td className="p-3">
                                        <div className="flex items-center">
                                            {getSequenceDisplay(event.sequence)}
                                            <span className="text-sm text-industrial-muted ml-2">
                                                {event.sequence.length} steps
                                            </span>
                                        </div>
                                    </td>
                                    <td className="p-3">{getVerificationBadge(event.verified)}</td>
                                    <td className="p-3">
                                        <ChevronRight size={16} className="text-industrial-muted" />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}

                {/* Load More */}
                {hasMore && (
                    <div className="p-4 text-center">
                        <button
                            onClick={loadMore}
                            className="btn btn-ghost"
                            disabled={loading}
                        >
                            {loading ? t('common.loading') : t('events.loadMore')}
                        </button>
                    </div>
                )}
            </div>
        </div>
    )
}
