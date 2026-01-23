import logging
import json
from database import SessionLocal, HazardPost, ImageAnalysis
from services.vision_service import vision_service
from services.incois_service import incois_service
from services.twilio_service import twilio_service
from services.image_service import image_service

# Configure logging
logger = logging.getLogger(__name__)

async def process_post_background(post_id: int):
    """
    Background task to process hazard post:
    1. AI Validation (Gemini)
    2. INCOIS Verification
    3. Update Post Status
    4. Send Alerts
    """
    logger.info(f"Starting background processing for post {post_id}")
    
    # Create new DB session for background task
    db = SessionLocal()
    try:
        post = db.query(HazardPost).filter(HazardPost.id == post_id).first()
        if not post:
            logger.error(f"Post {post_id} not found in background task")
            return

        # 1. Perform AI validation
        try:
            ai_result = await vision_service.analyze_image(post.image_path)
            
            # Store analysis results
            analysis = ImageAnalysis(
                post_id=post.id,
                labels=json.dumps(ai_result.get('labels', [])),
                objects=json.dumps(ai_result.get('objects', [])),
                web_entities=json.dumps(ai_result.get('web_entities', [])),
                ocean_related=ai_result.get('ocean_related', False),
                hazard_detected=ai_result.get('hazard_detected', False),
                confidence_score=ai_result.get('confidence_score', 0.0),
                scene_description=ai_result.get('scene_description'),
                detected_elements=json.dumps(ai_result.get('all_elements', []))
            )
            db.add(analysis)
            
            # Update post with AI results
            is_ocean = ai_result.get('ocean_related', False)
            is_hazard = ai_result.get('hazard_detected', False)
            
            post.ai_validated = is_ocean and is_hazard
            post.ai_confidence = ai_result.get('confidence_score', 0.0)
            post.ai_analysis = json.dumps(ai_result)
            
            # Explicit Rejection: only if AI is sure it is NOT related to ocean
            if not is_ocean and post.ai_confidence > 0.5:
                post.rejected = True
                post.rejection_reason = "Image not related to ocean hazard"
            else:
                post.rejected = False
            
            # Relevance Score using BLIP
            try:
                # Construct target tag for BLIP
                target_tag = f"{post.hazard_type.replace('_', ' ')} ocean hazard"
                relevance_score = await image_service.validate_image_relevance(post.image_path, target_tag)
                post.ai_relevance_score = relevance_score
                logger.info(f"BLIP Relevance Score: {relevance_score}% for tag '{target_tag}'")
            except Exception as e:
                logger.error(f"BLIP validation failed: {e}")
                post.ai_relevance_score = 0.0

            logger.info(f"AI validation complete: ocean_related={is_ocean}, "
                       f"hazard_detected={is_hazard}, rejected={post.rejected}")
            
        except Exception as e:
            logger.error(f"AI validation failed: {str(e)}")
            post.ai_validated = False
            post.ai_confidence = 0.0
            # Don't reject if the service itself fails
            
        # 2. Perform INCOIS validation
        try:
            incois_result = await incois_service.validate_hazard(
                post.hazard_type, post.latitude, post.longitude, post.timestamp
            )
            
            post.incois_validated = incois_result.get('validated', False)
            post.incois_correlation = incois_result.get('correlation')
            
            logger.info(f"INCOIS validation: {incois_result.get('validated')}")
            
        except Exception as e:
            logger.error(f"INCOIS validation failed: {str(e)}")
            post.incois_validated = False
        
        # 3. Determine final verification status
        if post.ai_validated and post.incois_validated:
            post.verified = True
            post.rejected = False
            message = "Report verified! Both AI and INCOIS confirm ocean hazard."
            await twilio_service.send_validation_alert(post.id, "verified")
            
        elif post.ai_validated:
            # AI says yes, but no INCOIS match yet
            post.verified = False
            post.rejected = False
            message = "Report pending: AI validated hazard, waiting for official correlation."
            
        elif post.rejected:
            # AI explicitly rejected
            message = f"Report rejected: {post.rejection_reason}"
            await twilio_service.send_validation_alert(post.id, "rejected", post.rejection_reason)
            
        else:
            # Fallback
            post.verified = False
            post.rejected = False
            message = "Pending manual review."
            
        db.commit()
        logger.info(f"Background processing complete for post {post_id}: {message}")
        
    except Exception as e:
        logger.error(f"Critical background error: {str(e)}")
        db.rollback()
    finally:
        db.close()
