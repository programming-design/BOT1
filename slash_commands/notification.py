import discord
from discord import app_commands, ui
import json
import os
import asyncio
import dotenv
from typing import List, Optional
from .utils import normalize_text, add_user_subscription, remove_user_subscription, check_allowed_channel
from .manga_image import get_manga_image_url
import logging
from utils import responses

# Load environment variables
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification")

# Load manga data from JSON file
def load_manga_data():
    """Load the manga data from manga_list.json"""
    manga_list_file = os.getenv('MANGA_LIST_FILE', 'data/manga_list.json')
    try:
        with open(manga_list_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading manga data: {e}")
        return []

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

class MangaView(ui.View):
    def __init__(self, manga_url: str, manga_title: str):
        super().__init__(timeout=None)  # No timeout for buttons
        self.manga_url = manga_url
        self.manga_title = manga_title
        
        # Add URL button
        url_button = ui.Button(
            label="الذهاب إلى المانهوا", 
            style=discord.ButtonStyle.link, 
            url=manga_url,
            emoji="🔗"
        )
        self.add_item(url_button)
    
    @ui.button(label="تفعيل الإشعارات", style=discord.ButtonStyle.success, emoji="🔔")
    async def enable_notifications(self, interaction: discord.Interaction, button: ui.Button):
        """Enable notifications for this manga"""
        user_id = interaction.user.id
        success = add_user_subscription(user_id, self.manga_title)
        
        if success:
            await interaction.response.send_message(
                responses.NOTIFICATIONS["subscribed"].format(manga=self.manga_title),
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                responses.NOTIFICATIONS["already_subscribed"].format(manga=self.manga_title),
                ephemeral=True
            )

def setup_notify_command(tree):
    print("Registering notify command with name 'متابعة'...")
    
    @tree.command(
        name="متابعة",
        description="الحصول على إشعار لمانهوا محددة"
    )
    @app_commands.autocomplete(العمل=MangaSelectAutocomplete().autocomplete)
    async def notify(
        interaction: discord.Interaction,
        العمل: str,
    ):
        """يرسل إشعارات للفصول الجديدة من المانهوا المحددة"""
        # Check if command is allowed in this channel
        if not await check_allowed_channel(interaction):
            return
            
        # Set ephemeral=True in the defer call to make the entire response ephemeral
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        # Find the manga in the list
        manga_data = load_manga_data()
        selected_manga = next((manga for manga in manga_data if manga["title"] == العمل), None)
        
        if not selected_manga:
            await interaction.followup.send(responses.NOTIFICATIONS["manga_not_found"].format(manga=العمل))
            return
        
        # Create embed
        embed = discord.Embed(
            title=f"📚 {selected_manga['title']}",
            url=selected_manga['url'],
            description=f"✅ سوف تتلقى إشعارات عند نشر فصول جديدة من هذه المانهوا",
            color=discord.Color.green()
        )
        
        # Try to fetch manga image
        image_url = await get_manga_image_url(selected_manga['title'])
        
        # Add fields to the embed
        embed.add_field(name="المصدر", value="[hijala.com](https://hijala.com)", inline=True)
        embed.set_footer(text="نظام إشعارات المانهوا")
            
        # Create view with buttons
        view = MangaView(manga_url=selected_manga['url'], manga_title=selected_manga['title'])
        
        # If we found an image, set it as the thumbnail
        if image_url:
            embed.set_thumbnail(url=image_url)
            await interaction.followup.send(embed=embed, view=view)
        else:
            # No image found or error occurred, send without image
            await interaction.followup.send(embed=embed, view=view)

    print("Notify command registered successfully") 