import discord
from discord import app_commands
import json
import os
import google.generativeai as genai
from typing import Literal, Optional, List
import asyncio
from dotenv import load_dotenv
from .utils import normalize_text, check_allowed_channel
from utils import responses


load_dotenv()

# Load manga list titles for recommendations
def load_manga_titles():
    """Load the manga titles from manga_list.json"""
    manga_list_file = os.getenv('MANGA_LIST_FILE', 'data/manga_list.json')
    try:
        with open(manga_list_file, 'r', encoding='utf-8') as f:
            manga_data = json.load(f)
            # Return titles for display and the full manga data (including URLs)
            return [manga['title'] for manga in manga_data], manga_data
    except Exception as e:
        print(f"Error loading manga titles: {e}")
        return [], []

# Load predefined categories from options.json
def load_categories():
    """Load the predefined categories from options.json"""
    options_file = 'data/options.json'
    try:
        with open(options_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('categories', [])
    except Exception as e:
        print(f"Error loading categories from options.json: {e}")
        # Return default categories if file can't be loaded
        return ["أكشن", "مغامرة", "كوميديا", "دراما", "خيال", "خيال علمي", "رعب"]

# Initialize the Gemini API client
def init_gemini_client():
    # First try to load from environment variable
    api_key = os.environ.get("GEMINI_API_KEY")
    
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        print(f"Error initializing Gemini client: {e}")
        return False

# Generate manga recommendations using Gemini API
async def generate_recommendations(تصنيف: str, الحالة: str):
    """Generate manga recommendations using Gemini API"""
    if not init_gemini_client():
        return "⚠️ Error: Failed to initialize Gemini API client."
    
    # Get the manga titles and data
    manga_titles, manga_data = load_manga_titles()
    if not manga_titles:
        return "⚠️ Error: Failed to load manga titles from manga_list.json"
    
    # Create a dictionary for quick lookup of manga URLs by title
    manga_url_map = {manga['title']: manga['url'] for manga in manga_data}
    
    # Create a string with markdown links for each manga - include all manga
    manga_links_list = [f"- [{manga['title']}]({manga['url']})" for manga in manga_data]
    manga_links = "\n".join(manga_links_list)
    
    # Create the prompt for Gemini
    prompt = f"""انت مساعد في موقع حجاله للمانهوا و تساعد الناس بتقديمهم افضل المانهوا حسب طلبهم وترد بأختصار بدون كلام زياده
اقترح أفضل 5 مانهوا تصنيف {تصنيف}، تكون {الحالة}، مع وصف قصير جدًا لكل، وترتيبها من 1 إلى 5 حسب الأفضلية.
ارسل ال 5 ترتيبات بدون اي كلام اخر

يجب أن تكون التوصيات بتنسيق ماركداون، مثل [اسم المانهوا](رابط المانهوا) من القائمة التالية:

{manga_links}

قواعد مهمة:
- اختر فقط من المانهوا المتاحة في هذه القائمة
- رتب التوصيات من 1 إلى 5 حسب الأفضلية
- استخدم تنسيق ماركداون للروابط [اسم المانهوا](رابط المانهوا) لكل توصية
- قدم المعلومات بتنسيق واضح لكل مانهوا
- استخدم اللغة العربية الفصحى مع تجنب الأخطاء اللغوية
- تجنب التكرار في المعلومات والأوصاف
- تجنب اي كلمه اخرى غير التوصيات فقط فلا تقول تفضل التوصيات او شئ
- تجنب كتابة اي مانهوا تخرج عن الوصف او تكون عكس الحاله

أرسل التوصيات فقط دون أي مقدمات أو تعليقات إضافية."""

    try:
        # Run Gemini in a separate thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: gemini_generate_content(prompt)
        )
        
        # Verify if response contains markdown links
        if '[' not in result or '](' not in result:
            print("Warning: Gemini response doesn't contain markdown links. Trying to process it.")
            # Try to add links if the response doesn't have them
            processed_result = result
            for title, url in manga_url_map.items():
                # Add markdown links to each manga title
                if title in processed_result:
                    processed_result = processed_result.replace(title, f"[{title}]({url})")
            return processed_result
        
        # Gemini successfully generated responses with markdown links
        return result
    except Exception as e:
        print(f"Error generating recommendations: {e}")
        # Return user-friendly message instead of error
        return "بالرجاء حاول مرة اخرى يوجد ضغط حاليا"

def gemini_generate_content(prompt):
    """Generate content using Gemini API (runs in executor)"""
    model = genai.GenerativeModel('gemini-2.0-flash')
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Gemini API error: {e}")
        # Check for quota-related errors
        if any(err_text in str(e).lower() for err_text in ['quota', 'rate limit', 'limit exceeded', 'too many requests']):
            return "بالرجاء حاول مرة اخرى يوجد ضغط حاليا"
        # Return a generic error message for other errors
        return "بالرجاء حاول مرة اخرى يوجد ضغط حاليا"

# Setup the recommend command
def setup_recommend_command(tree):
    print("Registering recommend command with name 'اقتراح'...")
    
    # Load predefined categories
    categories = load_categories()
    
    # Create choices list for categories (limited to 25 as per Discord's limit)
    category_choices = [app_commands.Choice(name=cat, value=cat) for cat in categories[:25]]
    
    @tree.command(
        name="اقتراح",
        description="الحصول على توصيات المانهوا حسب النوع وحالة الاكتمال"
    )
    @app_commands.choices(تصنيف=category_choices)
    async def recommend(
        interaction: discord.Interaction,
        تصنيف: str,
        الحالة: Literal["مكتملة الفصول", "غير مكتملة الفصول"]
    ):
        """يقترح المانهوا حسب النوع وحالة الاكتمال"""
        # Check if command is allowed in this channel
        if not await check_allowed_channel(interaction):
            return
            
        # Acknowledge the interaction first (important for slash commands)
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        # Generate recommendations using the selected category
        recommendations = await generate_recommendations(تصنيف, الحالة)
        
        # Create and send the embed with proper formatting for links
        embed = discord.Embed(
            title=f"🔖 {responses.RECOMMENDATIONS['title']} - {تصنيف}",
            description=recommendations,  # Using description for better URL rendering
            color=discord.Color.purple()
        )
        
        # Add footer with تصنيف and الحالة info
        embed.set_footer(text=f"hijala.com | التصنيف: {تصنيف} | الحالة: {الحالة}")
        
        try:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            # If there's an issue with the embed, try sending a plain message
            print(f"Error sending recommendations embed: {e}")
            try:
                await interaction.followup.send(
                    content=f"🔖 **{responses.RECOMMENDATIONS['title']} - {تصنيف}**\n\n{recommendations}\n\nhijala.com | التصنيف: {تصنيف} | الحالة: {الحالة}",
                    ephemeral=True
                )
            except Exception as e2:
                print(f"Error sending plain message: {e2}")
                await interaction.followup.send("حدث خطأ أثناء إرسال التوصيات. يرجى المحاولة مرة أخرى.", ephemeral=True)
    
    print("Recommend command registered successfully") 