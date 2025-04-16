import requests
import json
import os
import logging
import dotenv
import base64
from bs4 import BeautifulSoup
import asyncio
import aiohttp

# Load environment variables
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manga_image")

# File path for manga images
MANGA_IMAGES_FILE = os.getenv('MANGA_IMAGES_FILE', 'data/manga_images.json')

# File path for manga data
MANGA_LIST_FILE = os.getenv('MANGA_LIST_FILE', 'data/manga_list.json')

# ImgBB API configuration
IMGBB_API_KEY = "9dd8f4d9cb0c448dac5a2d63d3ee4b93"
IMGBB_API_URL = "https://api.imgbb.com/1/upload"

# Load manga images from JSON file
def load_manga_images():
    """Load manga images from manga_images.json"""
    if os.path.exists(MANGA_IMAGES_FILE):
        try:
            with open(MANGA_IMAGES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading manga images: {e}")
    return {}

# Save manga images to JSON file
def save_manga_images(images_data):
    """Save manga images to manga_images.json"""
    try:
        with open(MANGA_IMAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(images_data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving manga images: {e}")
        return False

# Load manga data to get URLs
def load_manga_data():
    """Load manga data from manga_list.json"""
    try:
        with open(MANGA_LIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading manga data: {e}")
        return []

def get_manga_url(manga_title):
    """Get manga URL from manga_list.json"""
    manga_data = load_manga_data()
    for manga in manga_data:
        if manga.get("title") == manga_title:
            return manga.get("url")
    return None

async def upload_to_imgbb(image_data, manga_title):
    """Upload image data to ImgBB and return the hosted URL"""
    try:
        # Convert to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Prepare the payload
        payload = {
            'key': IMGBB_API_KEY,
            'image': image_base64,
            'name': f"{manga_title}_cover",
        }
        
        # Upload to ImgBB
        async with aiohttp.ClientSession() as session:
            async with session.post(IMGBB_API_URL, data=payload) as response:
                if response.status != 200:
                    logger.error(f"Failed to upload to ImgBB, status: {response.status}")
                    return None
                
                # Parse the response
                response_data = await response.json()
                
                if not response_data.get('success', False):
                    logger.error(f"ImgBB upload failed: {response_data}")
                    return None
                
                # Return the hosted image URL
                return response_data['data']['url']
    except Exception as e:
        logger.error(f"Error uploading to ImgBB: {e}")
        return None

async def fetch_manga_image_from_website(url, manga_title):
    """Fetch manga image from the Hijala website and upload to ImgBB"""
    if not url:
        return None
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Use aiohttp for async requests
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 404:
                    # Try fallback URL - hijala.com homepage
                    async with session.get("https://hijala.com/", headers=headers) as fallback_response:
                        if fallback_response.status != 200:
                            return None
                        content = await fallback_response.read()
                elif response.status != 200:
                    return None
                else:
                    content = await response.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Try different selectors to find manga cover images
            img_selectors = [
                'img.wp-post-image',
                '.entry-content img',
                '.post-thumbnail img',
                'article img',
                '.post img',
                '.main-content img'
            ]
            
            for selector in img_selectors:
                img_elements = soup.select(selector)
                
                for img_element in img_elements:
                    # Check for lazy loading attributes
                    image_url = None
                    for attr in ['data-src', 'data-lazy-src', 'data-original', 'src']:
                        if img_element.has_attr(attr) and img_element[attr] and not img_element[attr].startswith('data:image/svg'):
                            image_url = img_element[attr]
                            break
                    
                    if image_url and not image_url.startswith('data:image/svg'):
                        # Found a valid image URL, download the image
                        async with session.get(image_url, headers=headers) as img_response:
                            if img_response.status != 200:
                                continue
                            
                            img_data = await img_response.read()
                            
                            # Upload to ImgBB
                            imgbb_url = await upload_to_imgbb(img_data, manga_title)
                            
                            if imgbb_url:
                                # Save in manga_images.json
                                manga_images = load_manga_images()
                                manga_images[manga_title] = imgbb_url
                                save_manga_images(manga_images)
                                
                                return imgbb_url
            
            return None
            
    except Exception as e:
        logger.error(f"Error fetching manga image: {e}")
        return None

async def get_manga_image_url(manga_title):
    """Get manga image URL
    
    This function checks for custom images in manga_images.json, then tries to fetch
    the image directly from the manga's page on Hijala if needed.
    """
    # First, check if we have a custom image URL for this manga
    manga_images = load_manga_images()
    if manga_title in manga_images and manga_images[manga_title]:
        return manga_images[manga_title]
    
    # Get the manga URL from manga_list.json
    manga_url = get_manga_url(manga_title)
    if not manga_url:
        return None
    
    # Fetch the image from the website and upload to ImgBB
    image_url = await fetch_manga_image_from_website(manga_url, manga_title)
    
    return image_url

# For backwards compatibility
async def get_manga_image(manga_title):
    """Legacy function that now returns the URL to the image"""
    return await get_manga_image_url(manga_title) 