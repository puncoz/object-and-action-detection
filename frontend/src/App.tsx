import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Monitor, List, Globe } from 'lucide-react'
import { useUIStore } from './store'
import LiveMonitoring from './pages/LiveMonitoring'
import Events from './pages/Events'
import EventDetail from './pages/EventDetail'

function App() {
    const { t, i18n } = useTranslation()
    const { language, setLanguage } = useUIStore()

    const toggleLanguage = () => {
        const newLang = language === 'en' ? 'jp' : 'en'
        setLanguage(newLang)
        i18n.changeLanguage(newLang)
    }

    return (
        <div className="min-h-screen bg-industrial-bg flex flex-col">
            {/* Header */}
            <header className="bg-industrial-surface border-b border-industrial-border px-6 py-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-6">
                        <h1 className="text-xl font-bold text-industrial-accent">
                            {t('app.name')}
                        </h1>

                        <nav className="flex items-center gap-1">
                            <NavLink
                                to="/live"
                                className={({ isActive }) =>
                                    `flex items-center gap-2 px-4 py-2 rounded transition-colors ${isActive
                                        ? 'bg-industrial-accent/20 text-industrial-accent'
                                        : 'text-industrial-muted hover:text-industrial-text hover:bg-industrial-border'
                                    }`
                                }
                            >
                                <Monitor size={18} />
                                <span>{t('nav.liveMonitoring')}</span>
                            </NavLink>

                            <NavLink
                                to="/events"
                                className={({ isActive }) =>
                                    `flex items-center gap-2 px-4 py-2 rounded transition-colors ${isActive
                                        ? 'bg-industrial-accent/20 text-industrial-accent'
                                        : 'text-industrial-muted hover:text-industrial-text hover:bg-industrial-border'
                                    }`
                                }
                            >
                                <List size={18} />
                                <span>{t('nav.events')}</span>
                            </NavLink>
                        </nav>
                    </div>

                    <div className="flex items-center gap-4">
                        {/* Language Toggle */}
                        <button
                            onClick={toggleLanguage}
                            className="flex items-center gap-2 px-3 py-1.5 rounded border border-industrial-border hover:bg-industrial-border transition-colors"
                            title="Toggle Language"
                        >
                            <Globe size={16} />
                            <span className="text-sm font-medium uppercase">{language}</span>
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="flex-1 overflow-hidden">
                <Routes>
                    <Route path="/" element={<Navigate to="/live" replace />} />
                    <Route path="/live" element={<LiveMonitoring />} />
                    <Route path="/events" element={<Events />} />
                    <Route path="/events/:eventId" element={<EventDetail />} />
                </Routes>
            </main>
        </div>
    )
}

export default App
