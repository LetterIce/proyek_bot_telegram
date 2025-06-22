import logging
import io
import requests
from PIL import Image
from typing import Optional, Tuple
import asyncio
import aiohttp

# Add HEIC support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    logging.warning("pillow-heif not installed. HEIC support disabled.")

logger = logging.getLogger(__name__)

# Supported image formats - added HEIC, removed BMP
SUPPORTED_FORMATS = ['JPEG', 'JPG', 'PNG', 'GIF', 'WEBP', 'HEIC']
MAX_IMAGE_SIZE = 200 * 1024 * 1024  # 200MB (increased from 50MB)
MAX_DIMENSION = 32768  # Max width/height (increased from 16384)

async def download_image(bot, file_id: str) -> Optional[bytes]:
    """Download image from Telegram using aiohttp for better async support."""
    try:
        # Get file info from Telegram
        file = await bot.get_file(file_id)
        if not file.file_path:
            logger.error("No file path received from Telegram")
            return None
        
        # Log file size from Telegram
        if hasattr(file, 'file_size') and file.file_size:
            logger.info(f"Telegram file size: {file.file_size} bytes")
            if file.file_size > MAX_IMAGE_SIZE:
                logger.warning(f"File too large according to Telegram: {file.file_size} bytes > {MAX_IMAGE_SIZE}")
                return None
        
        # Construct download URL correctly - avoid duplication
        file_path = file.file_path
        if file_path.startswith('https://'):
            # If file_path is already a full URL, use it directly
            download_url = file_path
        else:
            # Construct the URL properly
            download_url = f"https://api.telegram.org/file/bot{bot.token}/{file_path}"
        
        logger.info(f"Downloading image from: {download_url}")
        
        # Download the file using aiohttp with timeout
        timeout = aiohttp.ClientTimeout(total=180)  # 3 minutes timeout (increased from 60 seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(download_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to download image: HTTP {response.status} - {response.reason}")
                    logger.error(f"URL that failed: {download_url}")
                    return None
                
                # Get content length if available
                content_length = response.headers.get('content-length')
                if content_length:
                    size = int(content_length)
                    logger.info(f"Expected download size: {size} bytes")
                    if size > MAX_IMAGE_SIZE:
                        logger.warning(f"Image too large: {size} bytes > {MAX_IMAGE_SIZE}")
                        return None
                
                # Read data in chunks to handle large files better
                image_data = b''
                chunk_size = 8192
                async for chunk in response.content.iter_chunked(chunk_size):
                    image_data += chunk
                    if len(image_data) > MAX_IMAGE_SIZE:
                        logger.warning(f"Downloaded image too large: {len(image_data)} bytes > {MAX_IMAGE_SIZE}")
                        return None
                
                if len(image_data) == 0:
                    logger.error("Downloaded empty file")
                    return None
                
                logger.info(f"Successfully downloaded image: {len(image_data)} bytes")
                return image_data
        
    except asyncio.TimeoutError:
        logger.error("Timeout while downloading image")
        return None
    except aiohttp.ClientError as e:
        logger.error(f"Network error downloading image: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading image: {e}", exc_info=True)
        return None

def validate_and_process_image(image_data: bytes) -> Optional[bytes]:
    """Validate and process image data."""
    try:
        # Open image with PIL
        image = Image.open(io.BytesIO(image_data))
        logger.info(f"Original image: {image.format}, {image.mode}, {image.size}")
        
        # Check format
        if image.format not in SUPPORTED_FORMATS:
            logger.warning(f"Unsupported image format: {image.format}")
            return None
        
        # Check dimensions and aggressively resize if needed
        width, height = image.size
        
        # For very large images, resize more aggressively
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            # Use a more conservative max dimension for processing
            target_dimension = min(4096, MAX_DIMENSION)
            ratio = min(target_dimension / width, target_dimension / height)
            new_size = (int(width * ratio), int(height * ratio))
            
            # Use NEAREST for very large images to save memory
            if width > 16384 or height > 16384:
                image = image.resize(new_size, Image.Resampling.NEAREST)
            else:
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            logger.info(f"Resized image from {width}x{height} to {new_size[0]}x{new_size[1]}")
        
        # Convert to RGB if necessary (required for JPEG)
        if image.mode not in ['RGB']:
            if image.mode == 'RGBA':
                # Create white background for transparent images
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            else:
                image = image.convert('RGB')
            logger.info(f"Converted image mode to RGB")
        
        # Save processed image to bytes with lower quality for large images
        output = io.BytesIO()
        
        # Adjust quality based on image size
        width, height = image.size
        total_pixels = width * height
        
        if total_pixels > 4000000:  # > 4MP
            quality = 70
        elif total_pixels > 2000000:  # > 2MP
            quality = 80
        else:
            quality = 85
            
        image.save(output, format='JPEG', quality=quality, optimize=True)
        processed_data = output.getvalue()
        
        logger.info(f"Processed image: {len(processed_data)} bytes (quality: {quality})")
        return processed_data
        
    except MemoryError:
        logger.error("Not enough memory to process image")
        return None
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return None

def get_image_info(image_data: bytes) -> dict:
    """Get image information."""
    try:
        image = Image.open(io.BytesIO(image_data))
        return {
            'format': image.format,
            'mode': image.mode,
            'size': image.size,
            'width': image.size[0],
            'height': image.size[1]
        }
    except Exception as e:
        logger.error(f"Error getting image info: {e}")
        return {}

def is_image_file(filename: str) -> bool:
    """Check if filename is an image file."""
    if not filename:
        return False
    
    extension = filename.lower().split('.')[-1]
    return extension in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic']
