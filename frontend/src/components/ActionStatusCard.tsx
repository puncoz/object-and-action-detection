import { useTranslation } from 'react-i18next'
import { Droplets, Hand, Wine, Check } from 'lucide-react'
import type { DetectionFrame, ActionState } from '../types'

interface ActionStatusCardProps {
    detection: DetectionFrame
}

const STATE_ICONS: Record<string, React.ReactNode> = {
    idle: null,
    bottle_in_hand: <Hand size={20} />,
    cap_opening: <Wine size={20} />,
    drinking: <Droplets size={20} />,
    completed: <Check size={20} />,
}

export default function ActionStatusCard({ detection }: ActionStatusCardProps) {
    const { t } = useTranslation()

    // Get the first person's detection (simplified for MVP)
    const person = detection.people[0]
    if (!person) return null

    const { state, confidence } = person.action
    const isActive = state !== 'idle' && state !== 'uncertain'

    // Progress steps
    const steps: { key: ActionState; label: string }[] = [
        { key: 'bottle_in_hand', label: t('action.progress.lift') },
        { key: 'cap_opening', label: t('action.progress.cap') },
        { key: 'drinking', label: t('action.progress.drink') },
    ]

    const getStepStatus = (stepKey: ActionState) => {
        const order: ActionState[] = ['idle', 'bottle_in_hand', 'cap_opening', 'drinking', 'completed']
        const currentIdx = order.indexOf(state)
        const stepIdx = order.indexOf(stepKey)

        if (currentIdx > stepIdx) return 'completed'
        if (currentIdx === stepIdx) return 'active'
        return 'pending'
    }

    return (
        <div className="card">
            <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold">{t('action.title')}</h3>

                {/* Current State Badge */}
                <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${isActive ? 'bg-industrial-accent/20' : 'bg-industrial-border'
                    }`}>
                    {STATE_ICONS[state]}
                    <span className={`font-medium state-${state}`}>
                        {t(`action.states.${state}`)}
                    </span>
                    {isActive && (
                        <span className="text-sm text-industrial-muted">
                            ({(confidence * 100).toFixed(0)}%)
                        </span>
                    )}
                </div>
            </div>

            {/* Progress Bar */}
            <div className="flex items-center gap-2">
                {steps.map((step, idx) => {
                    const status = getStepStatus(step.key)

                    return (
                        <div key={step.key} className="flex items-center flex-1">
                            {/* Step Box */}
                            <div
                                className={`flex-1 py-2 px-3 rounded text-center text-sm font-medium transition-all ${status === 'completed'
                                        ? 'bg-industrial-success text-white'
                                        : status === 'active'
                                            ? 'bg-industrial-accent text-white animate-pulse'
                                            : 'bg-industrial-border text-industrial-muted'
                                    }`}
                            >
                                {step.label}
                            </div>

                            {/* Connector */}
                            {idx < steps.length - 1 && (
                                <div
                                    className={`w-4 h-0.5 ${status === 'completed' ? 'bg-industrial-success' : 'bg-industrial-border'
                                        }`}
                                />
                            )}
                        </div>
                    )
                })}
            </div>

            {/* Confidence Bar */}
            {isActive && (
                <div className="mt-4">
                    <div className="flex items-center justify-between text-xs text-industrial-muted mb-1">
                        <span>{t('action.confidence')}</span>
                        <span>{(confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-industrial-border rounded-full overflow-hidden">
                        <div
                            className="h-full bg-industrial-accent transition-all duration-300"
                            style={{ width: `${confidence * 100}%` }}
                        />
                    </div>
                </div>
            )}
        </div>
    )
}
