# Ocean Hazard Reporting System - Feature Summary & Technical Report

## 1. Project Overview
The **Ocean Hazard Reporting System** is a resilient, offline-first web application designed for coastal communities to report and monitor ocean-related hazards (tsunamis, cyclones, high tides). It integrates advanced **AI validation** to filter crowdsourced reports and provides authorities with a comprehensive **Admin Dashboard** for crisis management.

## 2. Tested & Working Features

### 🚨 SOS Alert System
*   **Functionality:** Users can trigger emergency SOS alerts for critical incidents (drowning, boat accidents).
*   **Offline-First:** Alerts generated offline are stored locally (IndexedDB) and auto-synced when connectivity is restored.
*   **Rescue Workflow:**
    *   Admin sees active SOS alerts instantly.
    *   Rescue teams can be "Deployed", changing the status to "Recovery in Progress".
    *   Deployment details (Team ID, Notes) are visible on the dashboard.

### 📝 Crowdsourced Hazard Reporting
*   **Report Submission:** Users submit reports with images, location (GPS/IP), hazard type, and severity.
*   **Offline Mode:**
    *   Reports submitted without internet are saved to **IndexedDB**.
    *   Background sync mechanisms auto-upload reports when online.
    *   **Synchronized Validation:** Offline reports trigger the full AI validation pipeline immediately upon successful sync.

### 🤖 Dual-Layer AI Validation Pipeline
A robust pipeline filters noise and verifies report authenticity:

1.  **Content Analysis (Google Gemini 1.5 Flash):**
    *   Analyzes image to detect if it contains ocean/water bodies and hazards.
    *   **Auto-Rejection Logic:** Reports are automatically rejected **ONLY IF** Gemini is >50% confident the image is **NOT** ocean-related (e.g., a photo of a cat).

2.  **Contextual Relevance (Salesforce BLIP Model):**
    *   **Model:** `Salesforce/blip-image-captioning-base` (running locally via PyTorch/Transformers).
    *   **Process:** Generates a caption for the image and performs semantic matching against the reported hazard category (e.g., matching image caption to "tsunami").
    *   **Relevance Score:** Calculates a 0-100% score based on keyword intersection and semantic boost.
    *   **Warning Threshold:**
        *   **< 50%:** Displays a **Red Warning Badge** ("Low relevance - Image may not match category") to the admin.
        *   **50-69%:** Yellow (Medium confidence).
        *   **≥ 70%:** Green (High confidence).
    *   *Note:* BLIP scores are advisory and do not trigger auto-rejection.

### 🛡️ Admin Dashboard
*   **Validation Queue:** Admins review pending reports with AI insights (Gemini Confidence + BLIP Relevance Score).
*   **Decision Power:** One-click "Verify" or "Reject" (with reason).
*   **Safety Alerts:** Admins can broadcast "Places to Avoid" (e.g., "Marina Beach Zone A").
*   **Live Sensor Data:** Mocked real-time data from wave rider buoys and tide gauges along the coast.

### 🌊 INCOIS Data Integration (Chennai Simulation)
*   **Data Seeding:** The system is pre-seeded with a realistic **2004 Chennai Tsunami Scenario**.
*   **Active Alerts:**
    *   **Tsunami Warning:** Marina Beach (High Severity).
    *   **High Tide:** Ennore Port (Medium Severity).
*   **Visualization:** These alerts appear on the dashboard and map, simulating real data from the Indian National Centre for Ocean Information Services.

## 3. Technical Implementation Details

### 🏗️ Backend Architecture
*   **Framework:** **FastAPI** (Python) for high-performance, async API endpoints.
*   **Database:** **SQLite** with **SQLAlchemy** ORM.
*   **AI Engine:**
    *   `google-generativeai`: Python client for Gemini API.
    *   `torch` & `transformers`: For local inference of the BLIP model.
*   **Background Tasks:** Used for non-blocking AI analysis. The user gets an immediate "Received" response while AI processes text/images in the background.

### 💻 Frontend Architecture
*   **Core:** Vanilla **HTML5, CSS3, JavaScript (ES6+)**. No heavy framework overhead.
*   **Offline Storage:** **IndexedDB** for robust offline data persistence.
*   **Maps:** **Leaflet.js** for interactive hazard mapping.
*   **Service Workers:** Cache management and offline capability logic.

### 🔄 Data Flow: Offline-to-Online
1.  **User Post (Offline):** Image converted to Base64 -> Stored in IndexedDB (`'posts-store'`).
2.  **Network Restoration:** `offline-sync.js` detects `navigator.onLine`.
3.  **Sync Request:** POST `/api/offline/sync` sent with Base64 image.
4.  **Server Handling:**
    *   Decodes Base64 -> Saves to file system (`uploads/`).
    *   Adds **Watermark** (Location/Time).
    *   Inserts to DB with `ai_validated=False`.
    *   **Triggers Background Task:** Calls `process_post_background`.
5.  **AI Processing:**
    *   Gemini checks content.
    *   BLIP checks relevance.
    *   DB updated with scores.
6.  **Admin View:** Dashboard reflects the new post with full AI scores.

## 4. Tools & Technologies Used
| Category | Tool/Library | Purpose |
| :--- | :--- | :--- |
| **Backend** | Python 3.10+, FastAPI | API Server |
| **Database** | SQLite, SQLAlchemy | Data Persistence |
| **AI - Vision** | Google Gemini 1.5 Flash | Hazard/Ocean Detection |
| **AI - NLP/Vision** | Salesforce BLIP (Torch/Transformers) | Image Captioning & Relevance Scoring |
| **Frontend** | HTML, CSS, Vanilla JS | User Interface |
| **Maps** | Leaflet.js | Map Visualization |
| **Offline** | IndexedDB, Service Workers | Offline Availability |
| **External Data** | INCOIS (Simulated) | Government Alerts |

## 5. Deployment Note (Chennai Scenario)
The database has been seeded using `backend/seed_chennai.py` to simulate a critical disaster scenario in **Chennai, India**, featuring:
*   Tsunami alert at **Marina Beach**.
*   Active rescue operation at **Chennai Lighthouse**.
*   Safety alerts for **Besant Nagar** and **Kovalam**.

This provides a fully populated environment for testing and demonstration purposes.
