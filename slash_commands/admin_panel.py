import discord
from discord import app_commands
from collections import Counter
import json
import os
import dotenv
from typing import List, Dict, Optional
from .utils import load_user_subscriptions, check_allowed_channel
from utils import responses

# Load environment variables
dotenv.load_dotenv()

# Create a Modal class for adding new manga
class AddMangaModal(discord.ui.Modal, title="إضافة مانهوا جديدة"):
    # Create text input for manga name
    manga_name = discord.ui.TextInput(
        label="اسم المانهوا",
        placeholder="اكتب اسم المانهوا هنا...",
        required=True,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Get the manga name from the form
        new_manga_name = self.manga_name.value.strip()
        
        # Generate URL based on the manga name
        # Convert spaces to hyphens and make lowercase for the URL
        url_part = new_manga_name.lower().replace(' ', '-')
        new_manga_url = f"https://hijala.com/{url_part}/"
        
        # Create new manga entry
        new_manga = {
            "title": new_manga_name,
            "url": new_manga_url
        }
        
        # Get the manga list file path
        manga_list_path = os.getenv('MANGA_LIST_FILE', 'data/manga_list.json')
        
        try:
            # Load existing manga list
            with open(manga_list_path, 'r', encoding='utf-8') as f:
                manga_list = json.load(f)
                
            # Check if manga already exists
            for manga in manga_list:
                if manga["title"].lower() == new_manga_name.lower():
                    await interaction.response.send_message(
                        responses.ADMIN_PANEL["add_manga_duplicate"].format(manga=new_manga_name),
                        ephemeral=True
                    )
                    return
            
            # Add the new manga to the list
            manga_list.append(new_manga)
            
            # Save the updated list back to the file
            with open(manga_list_path, 'w', encoding='utf-8') as f:
                json.dump(manga_list, f, ensure_ascii=False, indent=2)
            
            # Send confirmation message
            await interaction.response.send_message(
                responses.ADMIN_PANEL["add_manga_success"].format(manga=new_manga_name),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                responses.ADMIN_PANEL["add_manga_error"].format(error=str(e)),
                ephemeral=True
            )

# Create a Modal class for removing manga
class RemoveMangaModal(discord.ui.Modal, title="حذف مانهوا"):
    # Create text input for manga name
    manga_name = discord.ui.TextInput(
        label="اسم المانهوا",
        placeholder="اكتب اسم المانهوا للحذف...",
        required=True,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Get the manga name from the form
        manga_name_to_remove = self.manga_name.value.strip()
        
        # Get the manga list file path
        manga_list_path = os.getenv('MANGA_LIST_FILE', 'data/manga_list.json')
        
        try:
            # Load existing manga list
            with open(manga_list_path, 'r', encoding='utf-8') as f:
                manga_list = json.load(f)
            
            # Try to find the manga by name
            manga_found = False
            for i, manga in enumerate(manga_list):
                if manga["title"].lower() == manga_name_to_remove.lower():
                    # Found the manga, remove it
                    removed_manga = manga_list.pop(i)
                    manga_found = True
                    break
            
            if not manga_found:
                # Manga not found in the list
                await interaction.response.send_message(
                    responses.ADMIN_PANEL["remove_manga_not_found"].format(manga=manga_name_to_remove),
                    ephemeral=True
                )
                return
            
            # Save the updated list back to the file
            with open(manga_list_path, 'w', encoding='utf-8') as f:
                json.dump(manga_list, f, ensure_ascii=False, indent=2)
            
            # Send confirmation message
            await interaction.response.send_message(
                responses.ADMIN_PANEL["remove_manga_success"].format(manga=manga_name_to_remove),
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                responses.ADMIN_PANEL["remove_manga_error"].format(error=str(e)),
                ephemeral=True
            )

# Create a View containing the add manga button
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)  # 3 minute timeout
    
    @discord.ui.button(label="إضافة مانهوا جديدة", style=discord.ButtonStyle.green, emoji="➕")
    async def add_manga_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check admin permissions again (in case the view is interacted with after being sent)
        admin_role_id = os.getenv('ADMIN_ROLE_ID')
        try:
            admin_role_id = int(admin_role_id) if admin_role_id and admin_role_id != '0' else None
        except ValueError:
            admin_role_id = None
            
        is_admin = False
        if admin_role_id:
            is_admin = any(role.id == admin_role_id for role in interaction.user.roles)
        else:
            is_admin = interaction.user.guild_permissions.administrator
            
        if not is_admin:
            await interaction.response.send_message(responses.ADMIN_PANEL["admin_only"], ephemeral=True)
            return
        
        # Open the modal for manga name input
        await interaction.response.send_modal(AddMangaModal())
    
    @discord.ui.button(label="حذف مانهوا", style=discord.ButtonStyle.red, emoji="🗑️")
    async def remove_manga_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check admin permissions again
        admin_role_id = os.getenv('ADMIN_ROLE_ID')
        try:
            admin_role_id = int(admin_role_id) if admin_role_id and admin_role_id != '0' else None
        except ValueError:
            admin_role_id = None
            
        is_admin = False
        if admin_role_id:
            is_admin = any(role.id == admin_role_id for role in interaction.user.roles)
        else:
            is_admin = interaction.user.guild_permissions.administrator
            
        if not is_admin:
            await interaction.response.send_message(responses.ADMIN_PANEL["admin_only"], ephemeral=True)
            return
        
        # Open the modal for manga name input to remove
        await interaction.response.send_modal(RemoveMangaModal())

def setup_admin_panel_command(tree):
    """Setup the admin panel command"""
    
    @tree.command(name="لوحة-التحكم", description="عرض لوحة التحكم للمشرفين فقط")
    async def admin_panel(interaction: discord.Interaction):
        # Check if command is allowed in this channel
        if not await check_allowed_channel(interaction):
            return
            
        # Check if user has the specific admin role ID
        admin_role_id = os.getenv('ADMIN_ROLE_ID')
        try:
            admin_role_id = int(admin_role_id) if admin_role_id and admin_role_id != '0' else None
        except ValueError:
            admin_role_id = None
            
        is_admin = False
        
        # Check for admin role if configured
        if admin_role_id:
            is_admin = any(role.id == admin_role_id for role in interaction.user.roles)
        else:
            # Fallback to administrator permission if no role ID is configured
            is_admin = interaction.user.guild_permissions.administrator
            
        if not is_admin:
            await interaction.response.send_message(responses.ADMIN_PANEL["admin_only"], ephemeral=True)
            return
            
        # Load user subscriptions data
        user_subscriptions = load_user_subscriptions()
        
        # 1. Count users with active notifications
        users_with_notifications = len(user_subscriptions.keys())
        
        # 2. Get top 3 most popular mangas
        all_manga_subscriptions = []
        for user_id, mangas in user_subscriptions.items():
            all_manga_subscriptions.extend(mangas)
        
        # Count manga occurrences
        manga_counter = Counter(all_manga_subscriptions)
        
        # Get top 3 (or fewer if not enough data)
        top_mangas = manga_counter.most_common(3)
        
        # 3. Count total manga in the system
        manga_list_path = os.getenv('MANGA_LIST_FILE', 'data/manga_list.json')
        total_manga_count = 0
        
        if os.path.exists(manga_list_path):
            try:
                with open(manga_list_path, 'r', encoding='utf-8') as f:
                    manga_list = json.load(f)
                    total_manga_count = len(manga_list)
            except Exception as e:
                print(f"Error loading manga list: {e}")
        
        # Create embed with all information
        embed = discord.Embed(
            title=f"⚙️ {responses.ADMIN_PANEL['title']}",
            description=responses.ADMIN_PANEL["description"],
            color=discord.Color.dark_blue()
        )
        
        
        # Add fields with information
        embed.add_field(
            name=responses.ADMIN_PANEL["users_count_title"],
            value=responses.ADMIN_PANEL["users_count_value"].format(count=users_with_notifications),
            inline=False
        )
        
        # Add top mangas section
        if top_mangas:
            top_manga_text = "\n".join([
                responses.ADMIN_PANEL["manga_entry"].format(number=i+1, manga=manga, count=count) 
                for i, (manga, count) in enumerate(top_mangas)
            ])
        else:
            top_manga_text = responses.ADMIN_PANEL["no_manga_data"]
            
        embed.add_field(
            name=responses.ADMIN_PANEL["popular_manga_title"],
            value=top_manga_text,
            inline=False
        )
        
        embed.add_field(
            name=responses.ADMIN_PANEL["total_manga_title"],
            value=responses.ADMIN_PANEL["total_manga_value"].format(count=total_manga_count),
            inline=False
        )
        
        # Add timestamp
        embed.timestamp = discord.utils.utcnow()
        
        # Create view with add manga button
        view = AdminPanelView()
        
        # Send the embed with the view
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True) 