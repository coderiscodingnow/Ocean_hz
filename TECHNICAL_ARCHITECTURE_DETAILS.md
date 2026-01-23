# Ocean Hazard Reporting System - Technical Architecture & Feature Deep Dive

This document provides an in-depth technical analysis of the Ocean Hazard Reporting System, breaking down specific architectural layers, data flows, and validation mechanisms.

## 1. Architectural Overview

The system follows a typical **Client-Server architecture** with a heavy emphasis on **Offline-First** capabilities at the edge.

*   **Client (Edge):** Browser-based Single Page Application (SPA). Handles UI, geolocation, image capture, and local data persistence via IndexedDB.
*   **Server (Core):** FastAPI (Python) backend serving RESTful endpoints. It acts as the orchestrator between the database, file system, and AI services.
*   **AI Services (Intelligence):** Hybrid model approach.
    *   **Cloud:** Google Gemini 1.5 Flash (via API) for general scene understanding.
    *   **Local:** Salesforce BLIP (via PyTorch) for privacy-preserving relevance scoring.
*   **Database:** Relational SQLite database accessed via SQLAlchemy ORM.

## 2. Frontend Layer

The frontend is built using **Vanilla JavaScript (ES6+)**, intentionally avoiding heavy frameworks (React/Vue) to ensure maximum compatibility and performance on low-end devices typical in coastal/remote areas.

*   **Structure:**
    *   `app.js`: Main application logic, router, and view manager.
    *   `api.js`: Centralized networking layer handling Fetch requests.
    *   `offline-sync.js`: Manages network state detection (`navigator.onLine`) and IndexedDB synchronization.
    *   `map.js`: Leaflet.js abstraction for map rendering and marker management.
*   **Performance:** Uses native DOM manipulation and CSS variables for theming. No build step required; runs directly in browser.

## 3. Data Layer (Backend)

The backend uses **SQLAlchemy** to map Python classes to database tables.

### Key Models (`database.py`):
1.  **`HazardPost`:** The core entity.
    *   Columns: `id`, `hazard_type`, `severity`, `latitude`, `longitude`, `image_path` (local path).
    *   Validation Fields: `ai_validated` (bool), `ai_confidence` (float), `ai_relevance_score` (float, BLIP), `verified` (admin status).
    *   Sync State: `synced` (bool) tracks origin (online upload vs sync).
2.  **`ImageAnalysis`:** Stores raw AI output.
    *   Columns: `labels` (JSON), `scene_description`, `confidence_score`.
3.  **`INCOISAlert`:** Stores external government alerts.
4.  **`SOSReport`:** Critical emergency data.

## 4. Offline and Network Handling

Designed for intermittent connectivity.

### The Offline Workflow:
1.  **Detection:** `window.addEventListener('offline', ...)` updates UI state.
2.  **Storage (IndexedDB):**
    *   When offline, `POST /api/posts` is intercepted.
    *   Image File -> **Base64 String**.
    *   Data Object -> Saved to `posts-store` in IndexedDB (Browser Database).
3.  **Synchronization:**
    *   When `online` event fires: Loop through all items in `posts-store`.
    *   Send to `/api/offline/sync` endpoint.
    *   On 200 OK: Remove from IndexedDB and notify user.

## 5. Public Dashboard

The dashboard aggregates data for public consumption.

*   **Data Fetching:** Calls `/api/dashboard` which returns a composite JSON object containing:
    *   `posts`: List of validated hazard reports.
    *   `incois_alerts`: Active government warnings.
    *   `stats`: Total counts for verified/pending reports.
*   **Filtering:** The backend filters out `rejected` posts automatically.
*   **Visual Indicators:** "AI Verified" badges appear on posts with high confidence scores (>80%).

## 6. Map Visualization Layer

Built on **Leaflet.js** and **OpenStreetMap**.

*   **Markers:** Custom SVG icons represent hazard types (Wave for Tsunami, Cloud for Cyclone).
*   **Heatmap Overlay:** Uses `leaflet-heat` plugin.
    *   **Logic:** Converts point data into a density map.
    *   **Weighting:** Data points are weighted by severity (High = 1.0 intensity, Low = 0.5).
*   **Clustering:** Groups nearby markers at low zoom levels to prevent clutter.

## 7. Image Validation Layer (AI Pipeline)

A sophisticated dual-check system ensures data quality.

### Stage 1: Google Gemini (Cloud)
*   **Role:** Broad Content Analysis.
*   **Prompt:** *"Analyze this image. Is it related to an ocean, beach, or flood? Identify any hazards."*
*   **Output:** JSON boolean (`ocean_related`) and Confidence Score (0.0 - 1.0).

### Stage 2: Salesforce BLIP (Local)
*   **Role:** Contextual Keyword Matching.
*   **Mechanism:**
    1.  Generates a generative caption for the image (e.g., *"a large wave crashing on a beach"*).
    2.  Compares caption words against the user's reported `hazard_type` (e.g., "tsunami").
    3.  **Scoring Algorithm:**
        *   Base Score: % of target keywords found in caption.
        *   **Bonus 1 (+30%):** If generic ocean words (`water`, `sea`, `wave`) are found.
        *   **Bonus 2 (+25%):** If specific hazard words (`flood`, `storm`) match.
        *   Final Score: 0 - 100%.

### Stage 3: Watermarking (Image Processing)
*   **Library:** Python `Pillow` (PIL).
*   **Action:** Overlays text on the bottom of the image containing:
    *   📍 Location Name / Lat-Long
    *   📅 Exact Timestamp (UTC)
*   **Purpose:** Prevents image reuse/fake location data.

## 8. Supported Ocean Hazard Types

The system strictly categorizes reports into three types for data consistency:

1.  **Tsunami:**
    *   *Keywords:* Seismic sea wave, massive displacement.
    *   *Validation:* Looking for "wave", "surge", "retreating water".
2.  **Cyclone (Storm Surge):**
    *   *Keywords:* Strong winds, heavy rain, rough sea.
    *   *Validation:* Looking for "cloud", "storm", "wind", "rain".
3.  **High Tide / Flood:**
    *   *Keywords:* Coastal inundation, rising water level.
    *   *Validation:* Looking for "flood", "water", "street".

## 9. Multilingual Support

The app supports **English**, **Hindi**, and **Kannada**.

*   **Implementation:** Client-side translation.
*   **Resource:** `translations.js` contains a dictionary map.
    ```javascript
    const translations = {
      'en': { 'report_hazard': 'Report Hazard' },
      'hi': { 'report_hazard': 'खतरे की रिपोर्ट करें' }
    }
    ```
*   **Dynamic Switching:** `data-i18n` attributes in HTML are targeted by a `updateLanguage()` function that swaps text content instantly without page reload.

## 10. Post Features & Image Upload Details

### The Upload Flow
1.  **Capture:** User takes photo (HTML5 Camera API) or selects file.
2.  **Validation (Client):** format check (.jpg, .png) and size check (< 5MB).
3.  **Transmission:**
    *   **Online:** Sent as `multipart/form-data`. Backend streams file to disk to keep memory usage low.
    *   **Offline:** File read as FileReader `DataURL` (Base64). Stored as string.
4.  **Processing:**
    *   `uploads/original_ID.jpg` -> Raw file saved.
    *   `uploads/watermarked/wm_ID.jpg` -> Processed file created.
5.  **Database Entry:** Path to `/watermarked/` version is stored as the primary display image.
