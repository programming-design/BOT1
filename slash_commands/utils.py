import unicodedata
import json
import os
import dotenv
from typing import List, Dict, Optional
import discord

# Load environment variables
dotenv.load_dotenv()

def normalize_text(text):
    """
    Normalize text to ensure consistent handling of Arabic characters
    """
    if not text:
        return text
    
    # Normalize to NFC form (canonical composition)
    normalized = unicodedata.normalize('NFC', text)
    return normalized

def debug_unicode(text):
    """
    Debug function to print Unicode codepoints in a string
    """
    if not text:
        return "Empty text"
    
    result = []
    for i, char in enumerate(text):
        code_point = f"U+{ord(char):04X}"
        result.append(f"{i}: '{char}' ({code_point})")
    
    return "\n".join(result)

# User subscriptions management
SUBSCRIPTION_DB_PATH = os.getenv('USER_SUBSCRIPTIONS_FILE', 'data/user_subscriptions.json')

def load_user_subscriptions() -> Dict:
    """Load user subscriptions from JSON file"""
    if not os.path.exists(SUBSCRIPTION_DB_PATH):
        return {}
        
    try:
        with open(SUBSCRIPTION_DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading user subscriptions: {e}")
        return {}

def save_user_subscriptions(data: Dict) -> None:
    """Save user subscriptions to JSON file"""
    try:
        # Make sure the directory exists
        os.makedirs(os.path.dirname(SUBSCRIPTION_DB_PATH), exist_ok=True)
        
        with open(SUBSCRIPTION_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving user subscriptions: {e}")

def add_user_subscription(user_id: int, manga_title: str) -> bool:
    """Add a manga subscription for a user"""
    subscriptions = load_user_subscriptions()
    
    # Convert user_id to string because JSON keys must be strings
    user_id_str = str(user_id)
    
    # Initialize user entry if it doesn't exist
    if user_id_str not in subscriptions:
        subscriptions[user_id_str] = []
    
    # Don't add duplicates
    if manga_title not in subscriptions[user_id_str]:
        subscriptions[user_id_str].append(manga_title)
        print(f"Adding subscription for user {user_id_str} to manga '{manga_title}'")
        print(f"Saving to: {os.path.abspath(SUBSCRIPTION_DB_PATH)}")
        save_user_subscriptions(subscriptions)
        return True
    
    return False  # Already subscribed

def remove_user_subscription(user_id: int, manga_title: str) -> bool:
    """Remove a manga subscription for a user"""
    subscriptions = load_user_subscriptions()
    user_id_str = str(user_id)
    
    if user_id_str in subscriptions and manga_title in subscriptions[user_id_str]:
        subscriptions[user_id_str].remove(manga_title)
        print(f"Removing subscription for user {user_id_str} from manga '{manga_title}'")
        print(f"Saving to: {os.path.abspath(SUBSCRIPTION_DB_PATH)}")
        save_user_subscriptions(subscriptions)
        return True
    
    return False  # Not subscribed

def get_user_subscriptions(user_id: int) -> List[str]:
    """Get all manga subscriptions for a user"""
    subscriptions = load_user_subscriptions()
    user_id_str = str(user_id)
    
    if user_id_str in subscriptions:
        return subscriptions[user_id_str]
    
    return []

def get_manga_subscribers(manga_title: str) -> List[int]:
    """Get all users subscribed to a manga"""
    subscriptions = load_user_subscriptions()
    subscribers = []
    
    for user_id_str, manga_list in subscriptions.items():
        if manga_title in manga_list:
            subscribers.append(int(user_id_str))
    
    return subscribers

# Get channel restriction from env
COMMANDS_CHANNEL_ID = os.getenv('COMMANDS_CHANNEL_ID')  # Channel ID where commands are allowed

async def check_allowed_channel(interaction: discord.Interaction) -> bool:
    """Check if the command is being used in an allowed channel"""
    # If no channel ID is set, allow commands in all channels
    if not COMMANDS_CHANNEL_ID:
        return True
        
    # Check if the command is being used in the allowed channel
    if str(interaction.channel_id) == COMMANDS_CHANNEL_ID:
        return True
        
    # If not in the allowed channel, respond with an error message
    await interaction.response.send_message(
        f"⚠️ هذا الأمر يمكن استخدامه فقط في القناة المخصصة <#{COMMANDS_CHANNEL_ID}>",
        ephemeral=True
    )
    return False 