import { useState } from 'react'
import type { DetectionFrame } from '../types'

interface VideoPlayerProps {
    src: string
    detection?: DetectionFrame | null
}

export default function VideoPlayer({ src, detection }: VideoPlayerProps) {
    const [isLoading, setIsLoading] = useState(true)
    const [hasError, setHasError] = useState(false)

    return (
        <div className="relative w-full h-full bg-black rounded-lg overflow-hidden">
            {/* MJPEG Stream */}
            <img
                src={src}
                alt="Camera Feed"
                className="w-full h-full object-contain"
                onLoad={() => {
                    setIsLoading(false)
                    setHasError(false)
                }}
                onError={() => {
                    setIsLoading(false)
                    setHasError(true)
                }}
            />

            {/* Loading Overlay */}
            {isLoading && (
                <div className="absolute inset-0 flex items-center justify-center bg-industrial-surface">
                    <div className="text-industrial-muted">Loading stream...</div>
                </div>
            )}

            {/* Error Overlay */}
            {hasError && (
                <div className="absolute inset-0 flex items-center justify-center bg-industrial-surface">
                    <div className="text-industrial-danger">Failed to load video stream</div>
                </div>
            )}

            {/* Frame Info Overlay */}
            {detection && (
                <div className="absolute top-2 left-2 bg-black/70 text-white text-xs px-2 py-1 rounded">
                    Frame: {detection.frame_id}
                </div>
            )}
        </div>
    )
}
