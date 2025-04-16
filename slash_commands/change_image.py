import discord
from discord import app_commands
import json
import os
import aiohttp
import io
import logging
import asyncio
import dotenv
import base64
from typing import List, Optional
from .utils import normalize_text, check_allowed_channel

# Load environment variables
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("change_image")

# File paths
MANGA_LIST_FILE = os.getenv('MANGA_LIST_FILE', 'data/manga_list.json')
MANGA_IMAGES_FILE = os.getenv('MANGA_IMAGES_FILE', 'data/manga_images.json')
IMGBB_API_KEY = "9dd8f4d9cb0c448dac5a2d63d3ee4b93"  # ImgBB API key
IMGBB_API_URL = "https://api.imgbb.com/1/upload"

# Load manga data from JSON file
def load_manga_data():
    """Load the manga data from manga_list.json"""
    try:
        with open(MANGA_LIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading manga data: {e}")
        return []

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

# Upload image to ImgBB from URL
async def upload_image_to_imgbb(image_url, manga_title):
    """Upload an image to ImgBB from a URL and return the hosted URL"""
    try:
        # First, fetch the image data from the provided URL
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch image from URL: {image_url}, status: {response.status}")
                    return None
                
                # Get image data
                image_data = await response.read()
                
                # Convert to base64
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                
                # Upload to ImgBB
                payload = {
                    'key': IMGBB_API_KEY,
                    'image': image_base64,
                    'name': f"{manga_title}_cover",
                }
                
                # Send the request to ImgBB
                async with session.post(IMGBB_API_URL, data=payload) as upload_response:
                    if upload_response.status != 200:
                        logger.error(f"Failed to upload to ImgBB, status: {upload_response.status}")
                        return None
                    
                    # Parse the response
                    response_data = await upload_response.json()
                    
                    if not response_data.get('success', False):
                        logger.error(f"ImgBB upload failed: {response_data}")
                        return None
                    
                    # Return the hosted image URL
                    return response_data['data']['url']
    except Exception as e:
        logger.error(f"Error uploading image to ImgBB: {e}")
        return None

# Check if URL is a valid image
async def is_valid_image_url(url):
    """Check if the URL leads to a valid image"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True) as response:
                if response.status != 200:
                    return False
                
                content_type = response.headers.get('Content-Type', '')
                return content_type.startswith('image/')
    except Exception as e:
        logger.error(f"Error checking image URL: {e}")
        return False

# Autocomplete for manga selection
class MangaSelectAutocomplete(app_commands.Transformer):
    async def transform(self, interaction: discord.Interaction, value: str) -> str:
        return value

    async def autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        manga_data = load_manga_data()
        
        # If no input, return the first 25 titles
        if not current:
            choices = [
                app_commands.Choice(name=manga["title"], value=manga["title"])
                for manga in manga_data[:25]
            ]
            return choices
        
        # Normalize the input for consistent comparison
        current_normalized = normalize_text(current.lower())
        
        # Filter manga titles that contain the current input (case insensitive)
        filtered_manga = []
        for manga in manga_data:
            manga_title_normalized = normalize_text(manga["title"].lower())
            if current_normalized in manga_title_normalized:
                filtered_manga.append(manga)
                if len(filtered_manga) >= 25:  # Limit to 25 results
                    break
        
        # Return filtered choices
        choices = [
            app_commands.Choice(name=manga["title"], value=manga["title"])
            for manga in filtered_manga
        ]
        
        return choices

# Setup change_image command
def setup_change_image_command(tree):
    print("Registering change image command with name 'تغيير-صورة'...")
    
    @tree.command(
        name="تغيير-صورة",
        description="تغيير صورة غلاف المانهوا"
    )
    @app_commands.autocomplete(اسم_العمل=MangaSelectAutocomplete().autocomplete)
    async def change_image(
        interaction: discord.Interaction,
        اسم_العمل: str,
        الصوره_لينك: str,
    ):
        """تغيير صورة غلاف المانهوا للإشعارات"""
        # Check if command is allowed in this channel
        if not await check_allowed_channel(interaction):
            return
            
        # First, check permissions - only admins can change manga images
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ عذراً، هذا الأمر متاح للمشرفين فقط.", ephemeral=True)
            return
            
        # Acknowledge the interaction first
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        # Find the manga in the list
        manga_data = load_manga_data()
        selected_manga = next((manga for manga in manga_data if manga["title"] == اسم_العمل), None)
        
        if not selected_manga:
            await interaction.followup.send(f"❌ لم يتم العثور على مانهوا باسم '{اسم_العمل}'", ephemeral=True)
            return
        
        # Check if the URL is a valid image
        is_valid = await is_valid_image_url(الصوره_لينك)
        if not is_valid:
            await interaction.followup.send("❌ الرابط الذي أدخلته لا يحتوي على صورة صالحة. يرجى التأكد من صحة الرابط وأنه يشير إلى صورة.", ephemeral=True)
            return
        
        # Upload the image to ImgBB
        hosted_image_url = await upload_image_to_imgbb(الصوره_لينك, اسم_العمل)
        
        if not hosted_image_url:
            await interaction.followup.send("❌ فشل في رفع الصورة إلى الخادم. يرجى المحاولة مرة أخرى لاحقاً أو استخدام رابط آخر.", ephemeral=True)
            return
        
        # Load current images data
        manga_images = load_manga_images()
        
        # Update the image URL for this manga in the JSON to use the ImgBB URL
        manga_images[اسم_العمل] = hosted_image_url
        
        # Save the updated images data
        if save_manga_images(manga_images):
            # Create embed to show the change
            embed = discord.Embed(
                title=f"✅ تم تغيير صورة {اسم_العمل}",
                description="تم تحديث صورة الغلاف بنجاح",
                color=discord.Color.green()
            )
            
            # Set the thumbnail to use the hosted image URL
            embed.set_thumbnail(url=hosted_image_url)
            embed.add_field(name="المصدر", value="[hijala.com](https://hijala.com)", inline=True)
            embed.set_footer(text="نظام إشعارات المانهوا")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("❌ حدث خطأ أثناء حفظ الصورة. يرجى المحاولة مرة أخرى لاحقاً.", ephemeral=True)
    
    print("Change image command registered successfully") 