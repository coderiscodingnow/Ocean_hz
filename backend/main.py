from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import os
import json
import shutil
from datetime import datetime
import logging
import schemas # Added to support schemas.ClassName usage
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


import database
from database import get_db, init_db, SessionLocal, User, HazardPost, ImageAnalysis, INCOISAlert, AdminNotification, SafetyAlert
from schemas import (
    UserCreate, UserResponse, HazardPostCreate, HazardPostResponse, HazardPostDetail,
    DashboardResponse, DashboardPost, INCOISAlertResponse, MapDataResponse, MapMarker,
    TranslationRequest, TranslationResponse, ValidationResult, OfflinePostSync, SyncResponse
)
from services.vision_service import vision_service
from services.twilio_service import twilio_service
from services.translation_service import translation_service
from services.incois_service import incois_service
from services.image_service import image_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Ocean Hazard Live Reporting System",
    description="Crowdsourced ocean hazard reporting with AI validation",
    version="1.0.0"
)

# CORS configuration
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("uploads/watermarked", exist_ok=True)

# Mount static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    logger.info("Database initialized")
    
    # Fetch and store INCOIS alerts
    db = SessionLocal()
    try:
        await sync_incois_alerts(db=db)
    except Exception as e:
        logger.error(f"Startup INCOIS sync failed: {str(e)}")
    finally:
        db.close()
    db = SessionLocal()
    try:
        await sync_incois_alerts(db)
    finally:
        db.close()


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down")


# Health check
@app.get("/")
async def root():
    return {
        "app": "Ocean Hazard Live Reporting System",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ==================== USER ENDPOINTS ====================

@app.post("/api/users", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create or get user"""
    # Check if user exists
    existing_user = db.query(User).filter(User.user_id == user.user_id).first()
    
    if existing_user:
        # Update language preference
        existing_user.language_preference = user.language_preference
        db.commit()
        db.refresh(existing_user)
        return existing_user
    
    # Create new user
    new_user = User(
        user_id=user.user_id,
        language_preference=user.language_preference
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    logger.info(f"User created: {user.user_id}")
    return new_user


@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: Session = Depends(get_db)):
    """Get user by ID"""
    user = db.query(User).filter(User.user_id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@app.put("/api/users/{user_id}/language")
async def update_language(user_id: str, language: str, db: Session = Depends(get_db)):
    """Update user language preference"""
    user = db.query(User).filter(User.user_id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if language not in ['en', 'hi', 'kn']:
        raise HTTPException(status_code=400, detail="Invalid language code")
    
    user.language_preference = language
    db.commit()
    
    return {"success": True, "language": language}



# ==================== HAZARD POST ENDPOINTS ====================
from background_tasks import process_post_background


@app.post("/api/posts", response_model=ValidationResult)
async def create_hazard_post(
    user_id: str = Form(...),
    hazard_type: str = Form(...),
    severity: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    description: Optional[str] = Form(None),
    location_name: Optional[str] = Form(None),
    synced: bool = Form(True),
    image: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """
    Create new hazard post with image
    Performs AI validation and INCOIS verification in background
    """
    try:
        # Validate hazard type
        if hazard_type not in ['tsunami', 'cyclone', 'high_tide']:
            raise HTTPException(status_code=400, detail="Invalid hazard type")
        
        # Validate severity
        if severity not in ['low', 'medium', 'high']:
            raise HTTPException(status_code=400, detail="Invalid severity level")
        
        # Save uploaded image
        timestamp = datetime.utcnow()
        filename = f"{user_id}_{int(timestamp.timestamp())}_{image.filename}"
        image_path = os.path.join("uploads", filename)
        
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        
        logger.info(f"Image uploaded: {image_path}")
        
        # Validate image format (Quick check)
        is_valid = await image_service.validate_image(image_path)
        if not is_valid:
            os.remove(image_path)
            raise HTTPException(status_code=400, detail="Invalid image file or format")
        
        # Add watermark (Fast operation)
        watermarked_path = await image_service.add_watermark(
            image_path, location_name or "Unknown", latitude, longitude, timestamp
        )
        
        # Create post record with initial state
        post = HazardPost(
            user_id=user_id,
            hazard_type=hazard_type,
            severity=severity,
            description=description,
            latitude=latitude,
            longitude=longitude,
            location_name=location_name,
            image_path=image_path,
            watermarked_image_path=watermarked_path,
            timestamp=timestamp,
            synced=synced,
            # Initial validation state
            ai_validated=False,
            ai_confidence=0.0,
            incois_validated=False,
            verified=False,
            rejected=False
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        
        logger.info(f"Post created: ID={post.id}")
        
        # If offline post, send SMS alert immediately
        if not synced:
            await twilio_service.send_offline_alert(
                post.id, location_name or f"{latitude}, {longitude}"
            )
        
        # Add to background tasks for heavy AI/INCOIS processing
        background_tasks.add_task(process_post_background, post.id)
        
        return ValidationResult(
            success=True,
            ai_validated=False,
            ai_confidence=0.0,
            incois_validated=False,
            verified=False,
            rejected=False,
            rejection_reason=None,
            message="Report submitted successfully! AI analysis is running in the background."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating post: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/posts", response_model=List[HazardPostResponse])
async def get_all_posts(
    verified_only: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all hazard posts"""
    query = db.query(HazardPost)
    
    if verified_only:
        query = query.filter(HazardPost.verified == True)
    
    posts = query.order_by(HazardPost.timestamp.desc()).limit(limit).all()
    
    return posts


@app.get("/api/posts/{post_id}", response_model=HazardPostDetail)
async def get_post(post_id: int, db: Session = Depends(get_db)):
    """Get specific post with details"""
    post = db.query(HazardPost).filter(HazardPost.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return post


# ==================== DASHBOARD ENDPOINTS ====================

@app.get("/api/dashboard", response_model=DashboardResponse)
async def get_dashboard(db: Session = Depends(get_db)):
    """Get dashboard data with all non-rejected posts and INCOIS alerts"""
    
    # Get all non-rejected posts (includes verified AND pending)
    # This ensures posts show up immediately while AI analyzes them
    all_posts = db.query(HazardPost).filter(
        HazardPost.rejected == False  # Show everything except rejected
    ).order_by(HazardPost.timestamp.desc()).limit(50).all()
    
    # Get INCOIS alerts (Limit to 2 as per user request)
    incois_alerts = db.query(INCOISAlert).filter(
        INCOISAlert.active == True
    ).order_by(INCOISAlert.issued_at.desc()).limit(2).all()
    
    # Get statistics
    total_posts = db.query(HazardPost).count()
    verified_count = db.query(HazardPost).filter(HazardPost.verified == True).count()
    pending_count = db.query(HazardPost).filter(
        HazardPost.verified == False,
        HazardPost.rejected == False
    ).count()
    rejected_count = db.query(HazardPost).filter(HazardPost.rejected == True).count()
    
    # Format posts for dashboard with status indicators
    dashboard_posts = [
        DashboardPost(
            id=post.id,
            hazard_type=post.hazard_type,
            severity=post.severity,
            description=post.description,
            latitude=post.latitude,
            longitude=post.longitude,
            location_name=post.location_name,
            watermarked_image_path=post.watermarked_image_path or post.image_path,
            ai_confidence=post.ai_confidence,
            ai_relevance_score=post.ai_relevance_score,
            verified=post.verified,
            timestamp=post.timestamp
        )
        for post in all_posts
    ]
    
    return DashboardResponse(
        posts=dashboard_posts,
        incois_alerts=[INCOISAlertResponse.model_validate(alert) for alert in incois_alerts],
        total_posts=total_posts,
        verified_posts=verified_count,
        pending_posts=pending_count
    )

# ==================== MAP ENDPOINTS ====================

@app.get("/api/map/data", response_model=MapDataResponse)
async def get_map_data(db: Session = Depends(get_db)):
    """Get map markers and heatmap data"""
    markers = []
    heatmap_data = []
    
    # Get verified posts
    posts = db.query(HazardPost).filter(HazardPost.verified == True).all()
    
    for post in posts:
        markers.append(MapMarker(
            id=post.id,
            type="post",
            hazard_type=post.hazard_type,
            severity=post.severity,
            latitude=post.latitude,
            longitude=post.longitude,
            title=f"{post.hazard_type.title()} - {post.severity.title()}",
            description=post.description or "No description",
            timestamp=post.timestamp,
            verified=post.verified
        ))
        
        # Add to heatmap
        heatmap_data.append({
            "lat": post.latitude,
            "lng": post.longitude,
            "intensity": 1.0 if post.severity == "high" else 0.6 if post.severity == "medium" else 0.3
        })
    
    # Get INCOIS alerts
    alerts = db.query(INCOISAlert).filter(INCOISAlert.active == True).all()
    
    for alert in alerts:
        markers.append(MapMarker(
            id=alert.id,
            type="incois_alert",
            hazard_type=alert.alert_type,
            severity=alert.severity,
            latitude=alert.latitude,
            longitude=alert.longitude,
            title=alert.title,
            description=alert.description,
            timestamp=alert.issued_at,
            verified=True
        ))
        
        # Add to heatmap with higher intensity
        heatmap_data.append({
            "lat": alert.latitude,
            "lng": alert.longitude,
            "intensity": 1.5
        })
    
    return MapDataResponse(
        markers=markers,
        heatmap_data=heatmap_data
    )


# ==================== TRANSLATION ENDPOINTS ====================

@app.post("/api/translate", response_model=TranslationResponse)
async def translate_text(request: TranslationRequest):
    """Translate text to target language"""
    try:
        translated = await translation_service.translate(
            request.text, request.target_language
        )
        
        return TranslationResponse(
            original_text=request.text,
            translated_text=translated,
            target_language=request.target_language
        )
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Translation failed")


@app.get("/api/ui-translations/{language}")
async def get_ui_translations(language: str):
    """Get UI element translations for specified language"""
    if language not in ['en', 'hi', 'kn']:
        raise HTTPException(status_code=400, detail="Invalid language code")
    
    # Define UI elements to translate
    ui_elements = {
        "app_title": "Ocean Hazard Live Reporting",
        "report_hazard": "Report Hazard",
        "dashboard": "Dashboard",
        "map": "Map",
        "select_language": "Select Language",
        "hazard_type": "Hazard Type",
        "tsunami": "Tsunami",
        "cyclone": "Cyclone",
        "high_tide": "High Tide",
        "severity": "Severity",
        "low": "Low",
        "medium": "Medium",
        "high": "High",
        "description": "Description",
        "location": "Location",
        "capture_image": "Capture Image",
        "upload_image": "Upload Image",
        "submit_report": "Submit Report",
        "verified_reports": "Verified Reports",
        "pending_reports": "Pending Reports",
        "incois_alerts": "INCOIS Alerts",
        "ai_confidence": "AI Confidence",
        "view_details": "View Details",
        "report_submitted": "Report Submitted Successfully",
        "report_verified": "Report Verified",
        "report_rejected": "Report Rejected",
        "offline_mode": "Offline Mode - Will sync when online",
        "network_restored": "Network Restored - Syncing data",
        "safety_guidelines": "Safety Guidelines",
        "evacuation_info": "Evacuation Information"
    }
    
    if language == 'en':
        return ui_elements
    
    try:
        translated = await translation_service.translate_ui_elements(
            ui_elements, language
        )
        return translated
    except Exception as e:
        logger.error(f"UI translation error: {str(e)}")
        return ui_elements  # Return English on error


# ==================== INCOIS SYNC ENDPOINTS ====================

@app.post("/api/incois/sync")
async def sync_incois_alerts(db: Session = Depends(get_db)):
    """Fetch and sync INCOIS alerts"""
    try:
        alerts = await incois_service.fetch_active_alerts()
        
        synced_count = 0
        
        for alert_data in alerts:
            # Check if alert already exists
            existing = db.query(INCOISAlert).filter(
                INCOISAlert.external_id == alert_data.get('id')
            ).first()
            
            if existing:
                # Update existing alert
                existing.active = alert_data.get('active', True)
                existing.valid_until = datetime.fromisoformat(alert_data.get('valid_until')) if alert_data.get('valid_until') else None
            else:
                # Create new alert
                new_alert = INCOISAlert(
                    alert_type=alert_data.get('alert_type'),
                    severity=alert_data.get('severity'),
                    title=alert_data.get('title'),
                    description=alert_data.get('description'),
                    latitude=alert_data.get('latitude'),
                    longitude=alert_data.get('longitude'),
                    affected_area=alert_data.get('affected_area'),
                    radius_km=alert_data.get('radius_km', 50.0),
                    issued_at=datetime.fromisoformat(alert_data.get('issued_at')),
                    valid_until=datetime.fromisoformat(alert_data.get('valid_until')) if alert_data.get('valid_until') else None,
                    source=alert_data.get('source', 'INCOIS'),
                    external_id=str(alert_data.get('id')),
                    active=alert_data.get('active', True)
                )
                db.add(new_alert)
                synced_count += 1
        
        db.commit()
        
        logger.info(f"Synced {synced_count} new INCOIS alerts")
        
        return {
            "success": True,
            "synced": synced_count,
            "total": len(alerts)
        }
        
    except Exception as e:
        logger.error(f"INCOIS sync error: {str(e)}")
        raise HTTPException(status_code=500, detail="INCOIS sync failed")


# ==================== OFFLINE SYNC ENDPOINTS ====================

@app.post("/api/offline/sync", response_model=SyncResponse)
async def sync_offline_post(
    sync_data: OfflinePostSync,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Sync offline post when network is restored"""
    try:
        import base64
        
        # Decode base64 image
        image_data = base64.b64decode(sync_data.image_base64)
        
        # Save image
        ts_str = sync_data.timestamp.replace('Z', '+00:00')
        timestamp = datetime.fromisoformat(ts_str)
        filename = f"{sync_data.user_id}_{int(timestamp.timestamp())}_offline.jpg"
        
        # Ensure path uses forward slashes for DB consistency
        image_path = f"uploads/{filename}" 
        
        # Use os.path.join for filesystem operations
        fs_image_path = os.path.join("uploads", filename)
        
        with open(fs_image_path, "wb") as f:
            f.write(image_data)
        
        # Add watermark (same as online posts)
        watermarked_path = await image_service.add_watermark(
            fs_image_path, 
            sync_data.location_name or "Unknown", 
            sync_data.latitude, 
            sync_data.longitude, 
            timestamp
        )
        
        # Create post (similar to create_hazard_post but from offline data)
        post = HazardPost(
            user_id=sync_data.user_id,
            hazard_type=sync_data.hazard_type,
            severity=sync_data.severity,
            description=sync_data.description,
            latitude=sync_data.latitude,
            longitude=sync_data.longitude,
            location_name=sync_data.location_name,
            image_path=image_path, # URL friendly path
            watermarked_image_path=watermarked_path,
            timestamp=timestamp,
            synced=True,  # Now synced
            # Initial validation state (will be updated by background task)
            ai_validated=False,
            ai_confidence=0.0,
            ai_relevance_score=0.0,
            incois_validated=False,
            verified=False,
            rejected=False
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        
        logger.info(f"Offline post synced: ID={post.id}")
        
        # Trigger AI validation in background (same as online posts)
        background_tasks.add_task(process_post_background, post.id)
        logger.info(f"Background AI validation queued for offline post {post.id}")
        
        return SyncResponse(
            success=True,
            post_id=post.id,
            message="Offline post synced successfully. AI validation in progress."
        )
        
    except Exception as e:
        logger.error(f"Offline sync error: {str(e)}")
        return SyncResponse(
            success=False,
            post_id=None,
            message=f"Sync failed: {str(e)}"
        )


# ==================== GUIDELINES ENDPOINTS ====================

@app.get("/api/guidelines/{hazard_type}")
async def get_safety_guidelines(hazard_type: str, language: str = "en"):
    """Get safety guidelines for specific hazard type"""
    guidelines = {
        "tsunami": {
            "title": "Tsunami Safety Guidelines",
            "precautions": [
                "Move to higher ground immediately",
                "Stay away from the beach and coastal areas",
                "Listen to emergency broadcasts",
                "Do not return until authorities say it's safe"
            ],
            "evacuation": [
                "Evacuate vertically (go to upper floors) if you cannot evacuate horizontally",
                "Take emergency supplies with you",
                "Help others who need assistance",
                "Follow designated evacuation routes"
            ],
            "dos": [
                "Stay informed through official channels",
                "Keep emergency kit ready",
                "Know your evacuation routes",
                "Practice evacuation drills"
            ],
            "donts": [
                "Don't go to the beach to watch the waves",
                "Don't wait for official warnings if you feel strong earthquake",
                "Don't return home until all-clear is given",
                "Don't drive unless absolutely necessary"
            ]
        },
        "cyclone": {
            "title": "Cyclone Safety Guidelines",
            "precautions": [
                "Stay indoors and away from windows",
                "Secure loose objects outside",
                "Stock up on food, water, and medicines",
                "Charge all electronic devices"
            ],
            "evacuation": [
                "Move to designated cyclone shelters if advised",
                "Take important documents and valuables",
                "Turn off electricity and gas",
                "Inform family members of your location"
            ],
            "dos": [
                "Monitor weather updates regularly",
                "Keep emergency supplies ready",
                "Reinforce doors and windows",
                "Stay in the strongest part of the building"
            ],
            "donts": [
                "Don't venture outside during the storm",
                "Don't use electrical appliances",
                "Don't touch wet switches or wires",
                "Don't spread rumors or unverified information"
            ]
        },
        "high_tide": {
            "title": "High Tide Safety Guidelines",
            "precautions": [
                "Stay away from low-lying coastal areas",
                "Monitor tide schedules and warnings",
                "Secure boats and marine equipment",
                "Be prepared to evacuate if necessary"
            ],
            "evacuation": [
                "Move to higher ground if flooding occurs",
                "Take valuables and important documents",
                "Follow local authority instructions",
                "Help elderly and children evacuate first"
            ],
            "dos": [
                "Check tide timings regularly",
                "Keep emergency contact numbers handy",
                "Maintain drainage systems around your property",
                "Stay informed about weather conditions"
            ],
            "donts": [
                "Don't park vehicles in low-lying areas",
                "Don't ignore warning signs",
                "Don't attempt to cross flooded areas",
                "Don't delay evacuation if advised"
            ]
        }
    }
    
    if hazard_type not in guidelines:
        raise HTTPException(status_code=404, detail="Hazard type not found")
    
    guideline_data = guidelines[hazard_type]
    
    # Translate if not English
    if language != 'en':
        try:
            # Translate all text fields
            for key in guideline_data:
                if isinstance(guideline_data[key], str):
                    guideline_data[key] = await translation_service.translate(
                        guideline_data[key], language
                    )
                elif isinstance(guideline_data[key], list):
                    translated_list = []
                    for item in guideline_data[key]:
                        translated_item = await translation_service.translate(item, language)
                        translated_list.append(translated_item)
                    guideline_data[key] = translated_list
        except Exception as e:
            logger.error(f"Guidelines translation error: {str(e)}")
    
    return guideline_data


# ==================== ADMIN ENDPOINTS ====================

class PostStatusUpdate(BaseModel):
    verified: bool
    rejected: bool
    rejection_reason: Optional[str] = None

@app.put("/api/admin/posts/{post_id}/status", response_model=HazardPostResponse)
async def update_post_status(post_id: int, status: PostStatusUpdate, db: Session = Depends(get_db)):
    """Update post status (verify/reject)"""
    post = db.query(HazardPost).filter(HazardPost.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    post.verified = status.verified
    post.rejected = status.rejected
    post.rejection_reason = status.rejection_reason
    
    db.commit()
    db.refresh(post)
    
    return post

# --- Safety Alerts Endpoints ---

@app.post("/api/admin/safety-alerts", response_model=schemas.SafetyAlertResponse)
def create_safety_alert(alert: schemas.SafetyAlertCreate, db: Session = Depends(get_db)):
    db_alert = SafetyAlert(
        location_name=alert.location_name,
        hazard_type=alert.hazard_type,
        active=True
    )
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert


@app.get("/api/safety-alerts", response_model=List[schemas.SafetyAlertResponse])
def get_active_safety_alerts(db: Session = Depends(get_db)):
    return db.query(SafetyAlert).filter(SafetyAlert.active == True).all()


@app.put("/api/admin/safety-alerts/{alert_id}/deactivate")
def deactivate_safety_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(SafetyAlert).filter(SafetyAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.active = False
    db.commit()
    return {"message": "Alert deactivated"}

@app.get("/api/admin/historical-data")
async def get_historical_data(db: Session = Depends(get_db)):
    """Get status for admin analysis (Sensors & Stats)"""
    
    # Get post stats
    total_posts = db.query(HazardPost).count()
    verified_posts = db.query(HazardPost).filter(HazardPost.verified == True).count()
    rejected_posts = db.query(HazardPost).filter(HazardPost.rejected == True).count()
    
    # Realistic Sensor Data - Active High Wave Alert on Kerala/Karnataka Coast
    sensors = [
        {"id": "WR-KOC-01", "location": "Kochi Coast, Kerala", "type": "Wave Rider Buoy", "status": "Operational", "reading": "Wave Height: 3.2m ⚠️"},
        {"id": "TG-MNG-02", "location": "Mangalore, Karnataka", "type": "Tide Gauge", "status": "Operational", "reading": "High Tide: +2.4m"},
        {"id": "DB-KAN-03", "location": "Kannur, Kerala", "type": "Data Buoy", "status": "Operational", "reading": "Swell: 3.5m"},
        {"id": "TB-KAR-04", "location": "Karwar, Karnataka", "type": "Tsunami Buoy", "status": "Operational", "reading": "Normal - 0.3m"},
        {"id": "WR-TRV-05", "location": "Trivandrum Coast", "type": "Wave Rider", "status": "Operational", "reading": "Wave Height: 3.5m ⚠️"},
        {"id": "TG-GOA-06", "location": "Goa Harbor", "type": "Tide Gauge", "status": "Operational", "reading": "Tide: +1.8m"},
        {"id": "DB-CHN-07", "location": "Chennai (East Coast)", "type": "Data Buoy", "status": "Operational", "reading": "CRITICAL: Wave Height 8.5m 🚨"},
        {"id": "TB-CHN-08", "location": "Chennai Marina", "type": "Tsunami Buoy", "status": "ALERT", "reading": "TSUNAMI CONFIRMED 🚨"}
    ]
    
    return {
        "sensor_data": sensors,
        "stats": {
            "total_reports": total_posts,
            "verified": verified_posts,
            "rejected": rejected_posts,
            "accuracy_rate": (verified_posts / total_posts * 100) if total_posts > 0 else 0
        }
    }


# ==================== SOS ENDPOINTS ====================

@app.post("/api/sos/reports", response_model=schemas.SOSReportResponse)
async def create_sos_report(
    emergency_type: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    description: Optional[str] = Form(None),
    contact_number: Optional[str] = Form(None),
    location_name: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Create a new SOS report"""
    
    image_path = None
    if image:
        timestamp = datetime.utcnow()
        filename = f"sos_{int(timestamp.timestamp())}_{image.filename}"
        image_path = os.path.join("uploads", filename)
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

    sos_report = database.SOSReport(
        emergency_type=emergency_type,
        latitude=latitude,
        longitude=longitude,
        description=description,
        contact_number=contact_number,
        location_name=location_name,
        image_path=image_path,
        active=True
    )
    
    db.add(sos_report)
    db.commit()
    db.refresh(sos_report)
    
    return sos_report


@app.get("/api/sos/reports", response_model=List[schemas.SOSReportResponse])
def get_sos_reports(active_only: bool = True, db: Session = Depends(get_db)):
    """Get SOS reports"""
    query = db.query(database.SOSReport)
    if active_only:
        query = query.filter(database.SOSReport.active == True, database.SOSReport.resolved == False)
    return query.order_by(database.SOSReport.timestamp.desc()).all()


@app.put("/api/sos/{sos_id}/deploy")
def deploy_rescue_team(sos_id: int, deployment: schemas.SOSDeployment, db: Session = Depends(get_db)):
    """Deploy rescue team to SOS location"""
    report = db.query(database.SOSReport).filter(database.SOSReport.id == sos_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="SOS Report not found")
        
    report.deployed = True
    report.deployed_by = deployment.deployed_by
    report.deployed_at = datetime.utcnow()
    report.rescue_notes = deployment.rescue_notes
    
    db.commit()
    return {"message": "Rescue team deployed successfully"}


@app.put("/api/sos/{sos_id}/resolve")
def resolve_sos_report(sos_id: int, db: Session = Depends(get_db)):
    """Mark SOS report as resolved"""
    report = db.query(database.SOSReport).filter(database.SOSReport.id == sos_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="SOS Report not found")
        
    report.resolved = True
    report.active = False
    
    db.commit()
    return {"message": "SOS report resolved"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

