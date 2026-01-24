from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ocean_hazard.db")

engine = create_engine(DATABASE_URL)

if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True)
    language_preference = Column(String, default="en")  # en, hi, kn
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    posts = relationship("HazardPost", back_populates="user")


class HazardPost(Base):
    __tablename__ = "hazard_posts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.user_id"))
    
    # Content
    hazard_type = Column(String)  # tsunami, cyclone, high_tide
    severity = Column(String)  # low, medium, high
    description = Column(Text, nullable=True)
    
    # Location
    latitude = Column(Float)
    longitude = Column(Float)
    location_name = Column(String, nullable=True)
    
    # Image
    image_path = Column(String)
    watermarked_image_path = Column(String, nullable=True)
    
    # Validation Status
    ai_validated = Column(Boolean, default=False)
    ai_confidence = Column(Float, default=0.0)
    ai_relevance_score = Column(Float, default=0.0)  # Added relevance score
    ai_analysis = Column(Text, nullable=True)
    
    incois_validated = Column(Boolean, default=False)
    incois_correlation = Column(Text, nullable=True)
    
    verified = Column(Boolean, default=False)  # Both AI and INCOIS
    rejected = Column(Boolean, default=False)
    rejection_reason = Column(Text, nullable=True)
    
    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow)
    synced = Column(Boolean, default=True)  # False if uploaded offline
    
    # Relationships
    user = relationship("User", back_populates="posts")
    image_analysis = relationship("ImageAnalysis", back_populates="post", uselist=False)


class ImageAnalysis(Base):
    __tablename__ = "image_analysis"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("hazard_posts.id"))
    
    # Google Vision API Results
    labels = Column(Text)  # JSON string
    objects = Column(Text)  # JSON string
    landmarks = Column(Text, nullable=True)  # JSON string
    web_entities = Column(Text, nullable=True)  # JSON string
    
    # Ocean Hazard Detection
    ocean_related = Column(Boolean, default=False)
    hazard_detected = Column(Boolean, default=False)
    confidence_score = Column(Float, default=0.0)
    
    # Analysis Details
    scene_description = Column(Text, nullable=True)
    detected_elements = Column(Text, nullable=True)  # JSON string
    
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    post = relationship("HazardPost", back_populates="image_analysis")


class INCOISAlert(Base):
    __tablename__ = "incois_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Alert Details
    alert_type = Column(String)  # tsunami, cyclone, high_tide
    severity = Column(String)
    title = Column(String)
    description = Column(Text)
    
    # Location
    latitude = Column(Float)
    longitude = Column(Float)
    affected_area = Column(String)
    radius_km = Column(Float, default=50.0)
    
    # Timing
    issued_at = Column(DateTime)
    valid_until = Column(DateTime, nullable=True)
    
    # Source
    source = Column(String, default="INCOIS")
    external_id = Column(String, nullable=True)
    
    # Metadata
    fetched_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)


class AdminNotification(Base):
    __tablename__ = "admin_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Notification Details
    notification_type = Column(String)  # offline_post, validation_failed, system_error
    title = Column(String)
    message = Column(Text)
    
    # Related Data
    post_id = Column(Integer, nullable=True)
    user_id = Column(String, nullable=True)
    
    # SMS Status
    sms_sent = Column(Boolean, default=False)
    sms_sid = Column(String, nullable=True)
    sms_error = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    read = Column(Boolean, default=False)


class SafetyAlert(Base):
    __tablename__ = "safety_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    location_name = Column(String)  # Place to avoid
    hazard_type = Column(String)    # tsunami, cyclone, high_tide
    
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SOSReport(Base):
    __tablename__ = "sos_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Emergency Details
    emergency_type = Column(String)  # stranded, drowning, boat_accident, medical
    description = Column(Text, nullable=True)
    contact_number = Column(String, nullable=True)
    
    # Location
    latitude = Column(Float)
    longitude = Column(Float)
    location_name = Column(String, nullable=True)
    
    # Image
    image_path = Column(String, nullable=True)
    
    # Status
    active = Column(Boolean, default=True)
    deployed = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)
    
    # Deployment Details
    deployed_by = Column(String, nullable=True) # Team ID
    deployed_at = Column(DateTime, nullable=True)
    rescue_notes = Column(Text, nullable=True)
    
    # Metadata
    timestamp = Column(DateTime, default=datetime.utcnow)



# Create all tables
def init_db():
    Base.metadata.create_all(bind=engine)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
