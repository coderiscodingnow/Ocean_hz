from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# User Schemas
class UserCreate(BaseModel):
    user_id: str
    language_preference: str = "en"


class UserResponse(BaseModel):
    id: int
    user_id: str
    language_preference: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Hazard Post Schemas
class HazardPostCreate(BaseModel):
    user_id: str
    hazard_type: str  # tsunami, cyclone, high_tide
    severity: str  # low, medium, high
    description: Optional[str] = None
    latitude: float
    longitude: float
    location_name: Optional[str] = None
    synced: bool = True


class HazardPostResponse(BaseModel):
    id: int
    user_id: str
    hazard_type: str
    severity: str
    description: Optional[str]
    latitude: float
    longitude: float
    location_name: Optional[str]
    image_path: str
    watermarked_image_path: Optional[str]
    ai_validated: bool
    ai_confidence: float
    ai_relevance_score: float
    incois_validated: bool
    verified: bool
    rejected: bool
    rejection_reason: Optional[str]
    timestamp: datetime
    synced: bool
    
    class Config:
        from_attributes = True


# Image Analysis Schemas
class ImageAnalysisResponse(BaseModel):
    id: int
    post_id: int
    ocean_related: bool
    hazard_detected: bool
    confidence_score: float
    scene_description: Optional[str]
    detected_elements: Optional[str]
    analyzed_at: datetime
    
    class Config:
        from_attributes = True


class HazardPostDetail(HazardPostResponse):
    ai_analysis: Optional[str]
    incois_correlation: Optional[str]
    image_analysis: Optional[ImageAnalysisResponse]
    
    class Config:
        from_attributes = True


# INCOIS Alert Schemas
class INCOISAlertResponse(BaseModel):
    id: int
    alert_type: str
    severity: str
    title: str
    description: str
    latitude: float
    longitude: float
    affected_area: str
    radius_km: float
    issued_at: datetime
    valid_until: Optional[datetime]
    active: bool
    
    class Config:
        from_attributes = True


# Dashboard Schemas
class DashboardPost(BaseModel):
    id: int
    hazard_type: str
    severity: str
    description: Optional[str]
    latitude: float
    longitude: float
    location_name: Optional[str]
    watermarked_image_path: str
    ai_confidence: float
    ai_relevance_score: float
    verified: bool
    timestamp: datetime


class DashboardResponse(BaseModel):
    posts: List[DashboardPost]
    incois_alerts: List[INCOISAlertResponse]
    total_posts: int
    verified_posts: int
    pending_posts: int


# Translation Schemas
class TranslationRequest(BaseModel):
    text: str
    target_language: str  # en, hi, kn


class TranslationResponse(BaseModel):
    original_text: str
    translated_text: str
    target_language: str


# Validation Schemas
class ValidationResult(BaseModel):
    success: bool
    ai_validated: bool
    ai_confidence: float
    incois_validated: bool
    verified: bool
    rejected: bool
    rejection_reason: Optional[str]
    message: str


# Map Data Schemas
class MapMarker(BaseModel):
    id: int
    type: str  # post or incois_alert
    hazard_type: str
    severity: str
    latitude: float
    longitude: float
    title: str
    description: str
    timestamp: datetime
    verified: bool


class MapDataResponse(BaseModel):
    markers: List[MapMarker]
    heatmap_data: List[dict]


# Offline Sync Schemas
class OfflinePostSync(BaseModel):
    user_id: str
    hazard_type: str
    severity: str
    description: Optional[str]
    latitude: float
    longitude: float
    location_name: Optional[str]
    image_base64: str
    timestamp: str


class SyncResponse(BaseModel):
    success: bool
    post_id: Optional[int]
    message: str


# Safety Alert Schemas
class SafetyAlertCreate(BaseModel):
    location_name: str
    hazard_type: str


class SafetyAlertResponse(BaseModel):
    id: int
    location_name: str
    hazard_type: str
    active: bool
    created_at: datetime


    class Config:
        from_attributes = True


# SOS Schemas
class SOSReportCreate(BaseModel):
    emergency_type: str
    description: Optional[str] = None
    contact_number: Optional[str] = None
    latitude: float
    longitude: float
    location_name: Optional[str] = None


class SOSDeployment(BaseModel):
    deployed_by: str
    rescue_notes: Optional[str] = None


class SOSReportResponse(BaseModel):
    id: int
    emergency_type: str
    description: Optional[str]
    contact_number: Optional[str]
    latitude: float
    longitude: float
    location_name: Optional[str]
    image_path: Optional[str]
    active: bool
    deployed: bool
    resolved: bool
    deployed_by: Optional[str]
    deployed_at: Optional[datetime]
    rescue_notes: Optional[str]
    timestamp: datetime
    
    class Config:
        from_attributes = True

