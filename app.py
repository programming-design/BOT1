import discord
import asyncio
from discord.ext import tasks
from discord import app_commands
import time
import os
import dotenv
from datetime import datetime
from slash_commands.utils import get_manga_subscribers
from utils import responses
from utils import manga_checker
import random
from discord import ui

# Load environment variables
dotenv.load_dotenv()

# Discord bot configuration from .env
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
MANGA_CHECK_INTERVAL = int(os.getenv('MANGA_CHECK_INTERVAL', '60'))  # Default to 60 seconds
COMMANDS_CHANNEL_ID = os.getenv('COMMANDS_CHANNEL_ID')  # Channel ID where commands are allowed

# Discord client setup
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Debug handler for command errors
@tree.error
async def on_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"Command error: {error}")
    await interaction.response.send_message(responses.GENERAL["error"].format(error=error), ephemeral=True)

# Load slash commands
from slash_commands.recommend import setup_recommend_command
from slash_commands.notification import setup_notify_command
from slash_commands.mine import setup_mine_command
from slash_commands.admin_panel import setup_admin_panel_command
from slash_commands.change_image import setup_change_image_command
print("Setting up slash commands...")

# Apply channel restrictions to all slash commands
setup_recommend_command(tree)
setup_notify_command(tree)
setup_mine_command(tree)
setup_admin_panel_command(tree)
setup_change_image_command(tree)

# Queue for notifications to be sent
notification_queue = []

def queue_discord_notification(content, title=None, url=None, is_update=False, manga_data=None):
    """Queue a Discord notification to be sent later"""
    notification_queue.append({
        "content": content,
        "title": title,
        "url": url,
        "is_update": is_update,
        "manga_data": manga_data
    })

async def send_discord_notification(content, title=None, url=None, is_update=False, manga_data=None):
    """Send notification using Discord bot"""
    try:
        # Tracking of sent notifications to prevent duplicates
        global sent_notifications
        if not hasattr(send_discord_notification, 'sent_notifications'):
            send_discord_notification.sent_notifications = set()
            
        # Create a unique identifier for this notification
        if manga_data and 'prev_episode' in manga_data and manga_data.get('prev_episode') and manga_data.get('episode') != manga_data.get('prev_episode'):
            notification_id = f"{title}:{manga_data.get('prev_episode')}->{manga_data.get('episode', '')}"
        else:
            notification_id = f"{title}:{manga_data.get('episode') if manga_data else ''}"
        
        # Check if we've already sent this notification
        if notification_id in send_discord_notification.sent_notifications:
            print(f"Skipping duplicate notification for {title}")
            return True
            
        # Add to sent notifications
        send_discord_notification.sent_notifications.add(notification_id)
        
        # Get subscribers for this manga
        subscribers = get_manga_subscribers(title) if title else []
        print(f"Sending notification for manga '{title}' to {len(subscribers)} subscribers")
        
        # If we have subscribers and it's an update, send enhanced DMs to them
        if subscribers and is_update and title:
            success_count = 0
            
            # Create a beautiful enhanced embed for DMs
            color = discord.Color.brand_red() if is_update else discord.Color.green()
            emoji = responses.CONTENT_UPDATES["manga_update"] if is_update else responses.CONTENT_UPDATES["manga_new"]
            
            # Try to get manga image 
            from slash_commands.manga_image import get_manga_image_url
            image_url = None
            
            try:
                image_url = await get_manga_image_url(title)
            except Exception as e:
                print(f"Error fetching manga image: {e}")
            
            # Create the enhanced embed with chapter info if available
            chapter_info = ""
            
            if manga_data:
                # Handle episode information
                if 'episode' in manga_data and manga_data['episode']:
                    # Special handling for unknown episodes
                    if manga_data['episode'] == "unknown":
                        chapter_info = f"\n\n**الفصل:** ?"
                    else:
                        try:
                            # Format episode number 
                            episode_num = int(manga_data['episode'])
                            chapter_info = f"\n\n**الفصل:** {episode_num}"
                        except (ValueError, TypeError):
                            # Fall back to string representation
                            chapter_info = f"\n\n**الفصل:** {manga_data['episode']}"
                # Legacy support
                elif 'chapter' in manga_data:
                    chapter_info = f"\n\n**الفصل:** {manga_data['chapter']}"
                
                # We're not showing previous episode info or position change info
            
            embed = discord.Embed(
                title=f"📣 {emoji.format(title=title)}",
                description=f"**{content}**{chapter_info}\n\n[🔗 اضغط هنا للقراءة]({url})",
                color=color,
                url=url or "",
                timestamp=datetime.utcnow()
            )
            
            # Add fields with extra information
            embed.add_field(name="🌟 المصدر", value="[hijala.com](https://hijala.com)", inline=True)
            
            # Set footer
            embed.set_footer(text="نظام إشعارات المانهوا • اضغط على الرابط للقراءة")
            
            # Add prettier divider with emoji
            embed.add_field(name="\u200b", value="•° ⭒ °•    •° ⭒ °•    •° ⭒ °•", inline=False)
            
            # Add random tips
            tips = [
                "💡 استخدم أمر `/متابعة` للاشتراك في مانهوا أخرى",
                "💡 استخدم أمر `/اعمالي` لإدارة اشتراكاتك",
                "💡 استخدم أمر `/اقتراح` للحصول على توصيات مانهوا"
            ]
            embed.add_field(name="", value=random.choice(tips), inline=False)
            
            # Create view with manga URL button
            view = None
            try:
                # Create a view with a button to the manga
                class MangaLinkView(ui.View):
                    def __init__(self, manga_url):
                        super().__init__(timeout=None)
                        
                        # Add URL button
                        url_button = ui.Button(
                            label="قراءة الفصل الجديد", 
                            style=discord.ButtonStyle.link, 
                            url=manga_url,
                            emoji="📖"
                        )
                        self.add_item(url_button)
                
                # Create the view if URL is valid
                if url:
                    view = MangaLinkView(url)
            except Exception as e:
                print(f"Error creating manga link view: {e}")
            
            for user_id in subscribers:
                try:
                    user = await client.fetch_user(user_id)
                    if user:
                        # If we have an image URL, set it as the thumbnail
                        if image_url:
                            embed.set_thumbnail(url=image_url)
                            
                        # Send the embed with the view
                        if view:
                            await user.send(embed=embed, view=view)
                        else:
                            await user.send(embed=embed)
                        success_count += 1
                except Exception as e:
                    print(f"Error sending DM to user {user_id}: {e}")
            
            print(f"Sent enhanced DM notifications to {success_count}/{len(subscribers)} subscribers for {title}")
            return True
        
        # If it's a new manga (not an update) or if no subscribers, we don't need to send anything
        # We're no longer sending notifications to the channel
        return True
    except Exception as e:
        print(f"Error sending Discord notification: {e}")
        return False

@tasks.loop(seconds=MANGA_CHECK_INTERVAL)
async def check_manga_loop():
    """Loop to check for manga updates every minute"""
    new_updates, new_titles = manga_checker.check_for_updates()
    
    # Debug log for updates
    print(f"Received updates: {len(new_updates) if new_updates else 0}")
    if new_updates:
        for manga in new_updates:
            manga_debug = {
                'title': manga['title'],
                'episode': manga.get('episode'),
                'prev_episode': manga.get('prev_episode'),
                'url': manga['url']
            }
            print(f"Update details: {manga_debug}")
    
    # Process updates and queue notifications
    if new_updates:
        for manga in new_updates:
            # Check if we have both current and previous episode numbers to determine if it's an update
            if 'episode' in manga and manga['episode'] and 'prev_episode' in manga and manga['prev_episode']:
                # We have episode numbers - this is a confirmed episode update
                try:
                    # Try to use as integer for clean formatting if possible
                    episode_num = int(manga['episode'])
                    prev_episode_num = int(manga['prev_episode'])
                    notification_content = responses.NOTIFICATIONS["episode_update_notification"].format(
                        manga=manga['title'],
                        episode=episode_num
                    )
                    print(f"Sending notification for episode update: {manga['prev_episode']} → {manga['episode']} for {manga['title']}")
                except (ValueError, TypeError):
                    # Handle unknown episodes or non-numeric formats
                    notification_content = responses.NOTIFICATIONS["episode_update_notification"].format(
                        manga=manga['title'],
                        episode=manga['episode']
                    )
                    print(f"Sending notification for episode update: {manga['prev_episode']} → {manga['episode']} for {manga['title']}")
                
                queue_discord_notification(
                    notification_content,
                    title=manga['title'],
                    url=manga['url'],
                    is_update=True,
                    manga_data=manga
                )
            # Use episode-specific notification if available (for other types of updates)
            elif 'episode' in manga and manga['episode']:
                try:
                    # Try to use as integer for clean formatting if possible
                    episode_num = int(manga['episode'])
                    notification_content = responses.NOTIFICATIONS["episode_update_notification"].format(
                        manga=manga['title'],
                        episode=episode_num
                    )
                except (ValueError, TypeError):
                    # Handle unknown episodes
                    if manga['episode'] == "unknown":
                        notification_content = responses.NOTIFICATIONS["unknown_episode_notification"].format(
                            manga=manga['title']
                        )
                    else:
                        # Fall back to string if not a valid number
                        notification_content = responses.NOTIFICATIONS["episode_update_notification"].format(
                            manga=manga['title'],
                            episode=manga['episode']
                        )
                
                queue_discord_notification(
                    notification_content,
                    title=manga['title'],
                    url=manga['url'],
                    is_update=True,
                    manga_data=manga
                )
            else:
                notification_content = responses.NOTIFICATIONS["update_notification"].format(
                    manga=manga['title']
                )
                
                queue_discord_notification(
                    notification_content,
                    title=manga['title'],
                    url=manga['url'],
                    is_update=True,
                    manga_data=manga
                )
    
    # Process new titles - we'll still queue these but they won't be sent to the channel
    if new_titles:
        for manga in new_titles:
            queue_discord_notification(
                responses.NOTIFICATIONS["new_manga_notification"].format(manga=manga['title']),
                title=manga['title'],
                url=manga['url'],
                is_update=False,
                manga_data=manga
            )
    
    # Process notification queue
    global notification_queue
    if notification_queue:
        for notification in notification_queue:
            await send_discord_notification(
                notification["content"],
                notification["title"],
                notification["url"],
                notification["is_update"],
                notification.get("manga_data")
            )
        notification_queue = []  # Clear the queue after processing

@tasks.loop(hours=1)
async def clear_notification_cache():
    """Clear the notification cache periodically to prevent memory leaks"""
    if hasattr(send_discord_notification, 'sent_notifications'):
        size_before = len(send_discord_notification.sent_notifications)
        send_discord_notification.sent_notifications.clear()
        print(f"Cleared {size_before} entries from notification cache")

@client.event
async def on_ready():
    """Event triggered when the bot is connected and ready"""
    print(f"Logged in as {client.user.name} ({client.user.id})")
    print("Bot is ready to send notifications")
    
    # Clear and re-sync slash commands with Discord to force update
    try:
        print("Clearing and re-syncing all slash commands...")
        # This will force a complete refresh of all commands
        await tree.sync()
        # Verify the commands are registered
        print(f"Command names registered: {[cmd.name for cmd in tree.get_commands()]}")
        print("Slash commands synchronized successfully")
        
        # Log channel restriction status
        if COMMANDS_CHANNEL_ID:
            print(f"Commands restricted to channel ID: {COMMANDS_CHANNEL_ID}")
        else:
            print("Commands are available in all channels (no restriction)")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    
    # Start the manga check loop
    if not check_manga_loop.is_running():
        check_manga_loop.start()
    
    # Start the notification cache clearing task
    if not clear_notification_cache.is_running():
        clear_notification_cache.start()
    
    # Bot is now sending notifications directly to users, not to the channel
    print("Bot will send notifications directly to subscribed users")

def main():
    """Main function to run the Discord bot"""
    print("Discord Bot Starting...")
    
    # Check if first run needed for manga checker
    storage_file = os.getenv('STORAGE_FILE', manga_checker.STORAGE_FILE)
    if not os.path.exists(storage_file):
        manga_checker.first_run()
    
    # Start the Discord bot
    print(f"Starting Discord bot...")
    try:
        # Run the Discord bot
        client.run(DISCORD_BOT_TOKEN)
    except discord.errors.LoginFailure as e:
        print(f"Error: Discord bot login failed. {e}")
        print("Running without Discord notifications...")
        run_without_discord()

def run_without_discord():
    """Run the manga checker without Discord integration if bot fails"""
    print("Falling back to standalone manga checker...")
    manga_checker.run_standalone()

if __name__ == "__main__":
    main() 