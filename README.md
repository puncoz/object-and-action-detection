# Factory Action Console

Real-time worker hydration action detection UI for industrial automation. Detects the 3-step hydration sequence: lift bottle, open cap, drink water.

## Features

- Live camera monitoring with real-time overlays
- GPT-4V Vision-based action detection
- Action state machine: idle -> bottle_in_hand -> cap_opening -> drinking -> completed
- Event recording with video clips and snapshots
- Event review and verification workflow
- Multi-language support (English/Japanese)
- Dark industrial theme UI

## Tech Stack

- **Backend**: Python FastAPI, SQLAlchemy, OpenCV
- **Frontend**: React, Vite, TypeScript, Tailwind CSS, Zustand
- **Detection**: OpenAI GPT-4V Vision API
- **Database**: SQLite (dev) / PostgreSQL (prod)

## Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) (Python package manager)
- OpenAI API key with GPT-4V access

## Quick Start

### 1. Clone and Setup Environment

```bash
cd ai-hackathon

# Copy environment file
cp .env.example .env

# Edit .env and add your OpenAI API key
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment with uv
uv venv

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
uv pip install -e .

# Run the backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### 4. Access the Application

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000>
- API Docs: <http://localhost:8000/docs>

## Configuration

Edit `.env` file in the project root:

```env
# Database (sqlite for dev, postgresql for prod)
DB_TYPE=sqlite

# PostgreSQL credentials (if using postgresql)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=factory_console
DB_USER=your_username
DB_PASSWORD=your_password

# OpenAI API (required)
OPENAI_API_KEY=sk-your-api-key
OPENAI_MODEL=gpt-4o

# Detection settings
DETECTION_INTERVAL_MS=1500
CONFIDENCE_THRESHOLD=0.6
```

## Adding a Camera

### Video File (Demo Mode)

1. Click "+" in the camera sidebar
2. Select "Video File" type
3. Enter path to MP4 file: `/path/to/video.mp4`

### Webcam

1. Click "+" in the camera sidebar
2. Select "Webcam" type
3. Enter device index: `0` (default webcam)

### RTSP Stream

1. Click "+" in the camera sidebar
2. Select "RTSP Stream" type
3. Enter RTSP URL: `rtsp://username:password@ip:port/stream`

## API Endpoints

### Cameras

- `GET /api/cameras` - List all cameras
- `POST /api/cameras` - Add camera
- `POST /api/cameras/{id}/start` - Start processing
- `POST /api/cameras/{id}/stop` - Stop processing
- `GET /api/cameras/{id}/mjpeg` - MJPEG video stream

### Events

- `GET /api/events` - List events with filters
- `GET /api/events/{id}` - Get event details
- `POST /api/events/{id}/verify` - Verify/reject event
- `GET /api/events/{id}/snapshot` - Get snapshot image
- `GET /api/events/{id}/clip` - Get video clip

### WebSocket

- `WS /ws/cameras/{camera_id}` - Real-time detection stream

## Project Structure

```
ai-hackathon/
├── backend/
│   ├── app/
│   │   ├── api/           # REST and WebSocket routes
│   │   ├── core/          # Video capture, state machine, ring buffer
│   │   ├── detection/     # LLM detector, overlay rendering
│   │   └── services/      # Camera manager, event service
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── hooks/         # Custom hooks
│   │   └── store/         # Zustand state
│   └── package.json
└── .env.example
```

## Test Plan

### Action Detection Tests

1. Start backend with sample video in fake-live mode
2. Open browser to live monitoring page
3. Verify video stream displays with overlays
4. Test state transitions: idle -> bottle_in_hand -> cap_opening -> drinking -> completed
5. Verify event saved to database and appears in Events page

### Event Review Tests

1. Navigate to Events page
2. Apply filters (date, camera, verified)
3. Click event to open detail view
4. Play video clip, view snapshot
5. Test verify/reject buttons
6. Add note and verify persistence

### i18n Tests

1. Toggle language EN -> JP
2. Verify all labels change
3. Toggle back to EN

## Demo Scenarios (3 minutes)

### Demo 1: Live Detection (1 min)

- Show live camera feed with overlays
- Perform hydration action
- Watch state progression in real-time
- See event created in live feed

### Demo 2: Event Review (1 min)

- Open Events page
- Filter and find completed events
- Play back video clip
- Verify the event

### Demo 3: Multi-language (30 sec)

- Toggle EN to JP
- Show labels change throughout UI
- Demonstrate dark industrial theme

## Phase 2 Roadmap

- Multi-person tracking with unique IDs
- Additional objects: cups, tools, PPE
- Traditional ML pipeline (MediaPipe + YOLO) for offline mode
- Analytics dashboard with hydration reports
- Alert system for safety supervisors
- Mobile companion app
