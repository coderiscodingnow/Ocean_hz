from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import os
import logging
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration

logger = logging.getLogger(__name__)


class ImageProcessingService:
    """Service for image watermarking and processing"""
    
    def __init__(self):
        self.upload_dir = "uploads"
        self.watermarked_dir = "uploads/watermarked"
        
        # Create directories if they don't exist
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.watermarked_dir, exist_ok=True)

        try:
            logger.info("Loading BLIP model for image relevance...")
            self.processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            self.model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            logger.info("BLIP model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load BLIP model: {e}")
            self.processor = None
            self.model = None
    
    async def add_watermark(
        self, 
        image_path: str, 
        location_name: str, 
        latitude: float, 
        longitude: float,
        timestamp: datetime = None
    ) -> str:
        """
        Add watermark to image with location, date, and time
        
        Args:
            image_path: Path to original image
            location_name: Name of location
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            timestamp: Timestamp (defaults to now)
            
        Returns:
            Path to watermarked image
        """
        try:
            # Open image
            image = Image.open(image_path)
            
            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Create drawing context
            draw = ImageDraw.Draw(image)
            
            # Use default font (PIL's built-in)
            try:
                # Try to use a nicer font if available
                font_large = ImageFont.truetype("arial.ttf", 40)
                font_small = ImageFont.truetype("arial.ttf", 30)
            except:
                # Fallback to default
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Prepare watermark text
            if timestamp is None:
                timestamp = datetime.utcnow()
            
            date_str = timestamp.strftime("%d %b %Y")
            time_str = timestamp.strftime("%I:%M %p")
            coords_str = f"{latitude:.4f}, {longitude:.4f}"
            
            # Image dimensions
            width, height = image.size
            
            # Watermark position (bottom of image)
            margin = 20
            y_position = height - 150
            
            # Semi-transparent background for text
            overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            
            # Draw semi-transparent rectangle
            overlay_draw.rectangle(
                [(0, y_position - 20), (width, height)],
                fill=(0, 0, 0, 180)
            )
            
            # Composite overlay onto image
            image = image.convert('RGBA')
            image = Image.alpha_composite(image, overlay)
            image = image.convert('RGB')
            
            # Redraw on composited image
            draw = ImageDraw.Draw(image)
            
            # Draw watermark text
            text_color = (255, 255, 255)
            
            # Location
            if location_name:
                draw.text((margin, y_position), f"📍 {location_name}", 
                         fill=text_color, font=font_large)
            
            # Coordinates
            draw.text((margin, y_position + 45), coords_str, 
                     fill=text_color, font=font_small)
            
            # Date and time
            datetime_text = f"📅 {date_str}  🕐 {time_str}"
            draw.text((margin, y_position + 85), datetime_text, 
                     fill=text_color, font=font_small)
            
            # Generate watermarked filename
            original_filename = os.path.basename(image_path)
            watermarked_filename = f"wm_{original_filename}"
            watermarked_path = os.path.join(self.watermarked_dir, watermarked_filename)
            
            # Save watermarked image
            image.save(watermarked_path, quality=90)
            
            logger.info(f"Watermarked image saved: {watermarked_path}")
            
            return watermarked_path
            
        except Exception as e:
            logger.error(f"Error adding watermark: {str(e)}")
            # Return original path if watermarking fails
            return image_path
    
    async def validate_image(self, image_path: str) -> bool:
        """
        Validate image file
        
        Args:
            image_path: Path to image
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check file exists
            if not os.path.exists(image_path):
                return False
            
            # Check file size (max 10MB)
            max_size = int(os.getenv("MAX_IMAGE_SIZE_MB", "10")) * 1024 * 1024
            file_size = os.path.getsize(image_path)
            
            if file_size > max_size:
                logger.warning(f"Image too large: {file_size} bytes")
                return False
            
            # Try to open image
            with Image.open(image_path) as img:
                # Verify it's a valid image
                img.verify()
            
            return True
            
        except Exception as e:
            logger.error(f"Image validation failed: {str(e)}")
            return False

    async def validate_image_relevance(self, image_path: str, target_tag: str) -> float:
        """
        Validates if the image matches the target_tag and returns a percentage score.
        Uses BLIP to generate image caption and compares with target keywords.
        """
        logger.info(f"=== BLIP Validation Started ===")
        logger.info(f"Image path: {image_path}")
        logger.info(f"Target tag: {target_tag}")
        logger.info(f"Model loaded: {self.model is not None}")
        logger.info(f"Processor loaded: {self.processor is not None}")
        
        if not self.model or not self.processor:
            logger.warning("BLIP model not loaded, skipping relevance check.")
            return 0.0

        try:
            import asyncio
            
            def _predict():
                try:
                    logger.info("Starting BLIP prediction...")
                    # Load and process image
                    image = Image.open(image_path).convert('RGB')
                    logger.info(f"Image loaded successfully: {image.size}")
                    
                    # Generate caption
                    inputs = self.processor(images=image, return_tensors="pt")
                    logger.info("Image processed, generating caption...")
                    
                    with torch.no_grad():
                        out = self.model.generate(**inputs, max_length=50)
                    caption = self.processor.decode(out[0], skip_special_tokens=True)
                    
                    logger.info(f"✅ BLIP generated caption: '{caption}'")
                    
                    # Simple keyword-based relevance scoring
                    # Extract keywords from target tag
                    target_keywords = set(target_tag.lower().split())
                    caption_words = set(caption.lower().split())
                    
                    logger.info(f"Target keywords: {target_keywords}")
                    logger.info(f"Caption words: {caption_words}")
                    
                    # Calculate overlap
                    common_words = target_keywords.intersection(caption_words)
                    logger.info(f"Common words: {common_words}")
                    
                    # Base score on keyword overlap
                    if len(target_keywords) > 0:
                        keyword_score = (len(common_words) / len(target_keywords)) * 100
                    else:
                        keyword_score = 0.0
                    
                    logger.info(f"Base keyword score: {keyword_score}%")
                    
                    # Boost score if ocean/water/sea related words are found
                    ocean_keywords = {'ocean', 'sea', 'water', 'wave', 'tsunami', 'cyclone', 'storm', 'tide', 'beach', 'coast', 'marine', 'flood'}
                    caption_ocean_words = caption_words.intersection(ocean_keywords)
                    
                    if caption_ocean_words:
                        ocean_boost = min(30.0, len(caption_ocean_words) * 15)
                        keyword_score = min(100.0, keyword_score + ocean_boost)
                        logger.info(f"Ocean boost applied: +{ocean_boost}% (found: {caption_ocean_words})")
                    
                    # Check for hazard-specific keywords
                    hazard_keywords = {
                        'tsunami': {'wave', 'water', 'flood', 'ocean', 'sea'},
                        'cyclone': {'storm', 'wind', 'cloud', 'rain', 'cyclone'},
                        'high': {'tide', 'water', 'wave', 'ocean', 'flood'},
                        'tide': {'tide', 'water', 'wave', 'ocean', 'flood'}
                    }
                    
                    for hazard_type, keywords in hazard_keywords.items():
                        if hazard_type in target_tag.lower():
                            hazard_matches = caption_words.intersection(keywords)
                            if hazard_matches:
                                hazard_boost = min(25.0, len(hazard_matches) * 12)
                                keyword_score = min(100.0, keyword_score + hazard_boost)
                                logger.info(f"Hazard boost applied: +{hazard_boost}% (found: {hazard_matches})")
                            break
                    
                    final_score = round(keyword_score, 2)
                    logger.info(f"🎯 FINAL RELEVANCE SCORE: {final_score}%")
                    logger.info(f"=== BLIP Validation Complete ===")
                    return final_score
                    
                except Exception as inner_e:
                    logger.error(f"❌ Error in _predict: {str(inner_e)}", exc_info=True)
                    return 0.0

            result = await asyncio.to_thread(_predict)
            logger.info(f"Async thread returned: {result}")
            return result

        except Exception as e:
            logger.error(f"❌ Error validating image relevance: {str(e)}", exc_info=True)
            return 0.0



# Singleton instance
image_service = ImageProcessingService()
