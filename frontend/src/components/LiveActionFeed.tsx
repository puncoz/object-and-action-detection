import { useTranslation } from 'react-i18next'
import { format } from 'date-fns'
import { Activity, CheckCircle, Hand, Wine, Droplets } from 'lucide-react'
import { useDetectionStore } from '../store'
import type { ActionState } from '../types'

const STATE_ICONS: Record<ActionState, React.ReactNode> = {
    idle: null,
    bottle_in_hand: <Hand size={14} />,
    cap_opening: <Wine size={14} />,
    drinking: <Droplets size={14} />,
    completed: <CheckCircle size={14} />,
    uncertain: null,
}

export default function LiveActionFeed() {
    const { t } = useTranslation()
    const { actionFeed } = useDetectionStore()

    return (
        <div className="h-full flex flex-col">
            <div className="p-4 border-b border-industrial-border">
                <h2 className="font-semibold flex items-center gap-2">
                    <Activity size={18} />
                    {t('feed.title')}
                </h2>
            </div>

            <div className="flex-1 overflow-y-auto">
                {actionFeed.length === 0 ? (
                    <div className="p-4 text-center text-industrial-muted text-sm">
                        {t('feed.empty')}
                    </div>
                ) : (
                    <div className="divide-y divide-industrial-border">
                        {actionFeed.map((item) => (
                            <div
                                key={item.id}
                                className={`p-3 hover:bg-industrial-border/50 transition-colors ${item.isCompleted ? 'bg-industrial-success/5' : ''
                                    }`}
                            >
                                <div className="flex items-start gap-3">
                                    {/* Icon */}
                                    <div
                                        className={`p-2 rounded-full ${item.isCompleted
                                                ? 'bg-industrial-success/20 text-industrial-success'
                                                : 'bg-industrial-accent/20 text-industrial-accent'
                                            }`}
                                    >
                                        {STATE_ICONS[item.state] || <Activity size={14} />}
                                    </div>

                                    {/* Content */}
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className={`font-medium state-${item.state}`}>
                                                {t(`action.states.${item.state}`)}
                                            </span>
                                            {item.isCompleted && (
                                                <span className="badge badge-success text-[10px]">
                                                    {t('feed.newEvent')}
                                                </span>
                                            )}
                                        </div>

                                        <div className="flex items-center gap-2 mt-1 text-xs text-industrial-muted">
                                            <span>{format(item.timestamp, 'HH:mm:ss')}</span>
                                            <span>|</span>
                                            <span>Track {item.trackId}</span>
                                            <span>|</span>
                                            <span>{(item.confidence * 100).toFixed(0)}%</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    )
}
