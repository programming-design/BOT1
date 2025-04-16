import requests
from bs4 import BeautifulSoup
import json
import os
import time
import dotenv
from datetime import datetime
import re

# Load environment variables
dotenv.load_dotenv()

# Configuration from .env
URLS = {
    'updates': os.getenv('MANGA_UPDATES_URL', 'https://hijala.com/manga/?order=update'),
    'latest': os.getenv('MANGA_LATEST_URL', 'https://hijala.com/manga/?status=&type=&order=latest')
}
STORAGE_FILE = os.getenv('STORAGE_FILE', 'manga_seen.json')
MANGA_LIST_FILE = os.getenv('MANGA_LIST_FILE', 'manga_list.json')
NOTIFICATION_LOG_FILE = os.getenv('NOTIFICATION_LOG_FILE', 'notification_log.json')
CHECK_INTERVAL = int(os.getenv('MANGA_CHECK_INTERVAL', '60'))  # in seconds

# Store the last updates manga for reference
_last_updates_manga = None

def is_duplicate_notification(manga, lookback_period=3600):  # 1 hour lookback
    """Check if this notification was already sent recently"""
    # Create notification ID - combination of manga ID and episode
    # If we have both current and previous episode, include both to ensure episode changes are never considered duplicates
    if 'prev_episode' in manga and manga['prev_episode'] and manga.get('episode') != manga['prev_episode']:
        notification_id = f"{manga['id']}:{manga['prev_episode']}->{manga.get('episode', 'unknown')}"
    else:
        notification_id = f"{manga['id']}:{manga.get('episode', 'unknown')}"
    
    # Load notification history
    history = []
    if os.path.exists(NOTIFICATION_LOG_FILE):
        try:
            with open(NOTIFICATION_LOG_FILE, 'r') as f:
                history = json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading notification log, starting fresh")
    
    # Check for duplicates within lookback period
    current_time = time.time()
    for entry in history:
        if (entry['id'] == notification_id and 
            current_time - entry['timestamp'] < lookback_period):
            print(f"Skipping duplicate notification for {manga['title']} episode {manga.get('episode', 'unknown')}")
            return True
    
    # Not a duplicate, log this notification
    history.append({
        'id': notification_id,
        'manga_id': manga['id'],
        'title': manga['title'],
        'episode': manga.get('episode', 'unknown'),
        'prev_episode': manga.get('prev_episode'),
        'timestamp': current_time,
        'status': 'pending'  # Track notification status
    })
    
    # Only keep recent entries to prevent file growth
    history = [entry for entry in history 
               if current_time - entry['timestamp'] < 86400]  # 24 hours
    
    # Save updated history - use atomic write to prevent corruption
    temp_file = NOTIFICATION_LOG_FILE + '.tmp'
    try:
        with open(temp_file, 'w') as f:
            json.dump(history, f, indent=2)
        # Atomic replace
        if os.path.exists(NOTIFICATION_LOG_FILE):
            os.replace(temp_file, NOTIFICATION_LOG_FILE)
        else:
            os.rename(temp_file, NOTIFICATION_LOG_FILE)
    except Exception as e:
        print(f"Error saving notification log: {e}")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass
    
    return False

def mark_notification_sent(manga):
    """Mark a notification as successfully sent"""
    if not os.path.exists(NOTIFICATION_LOG_FILE):
        return
    
    notification_id = f"{manga['id']}:{manga.get('episode', 'unknown')}"
    
    try:
        with open(NOTIFICATION_LOG_FILE, 'r') as f:
            history = json.load(f)
        
        # Update status for matching notification
        for entry in history:
            if entry['id'] == notification_id and entry['status'] == 'pending':
                entry['status'] = 'sent'
                entry['sent_timestamp'] = time.time()
                break
        
        # Save updated history - use atomic write
        temp_file = NOTIFICATION_LOG_FILE + '.tmp'
        with open(temp_file, 'w') as f:
            json.dump(history, f, indent=2)
        # Atomic replace
        os.replace(temp_file, NOTIFICATION_LOG_FILE)
    except Exception as e:
        print(f"Error updating notification status: {e}")
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

def fetch_manga(url):
    """Fetch manga from the specified website URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise exception for HTTP errors
        
        soup = BeautifulSoup(response.text, 'html.parser')
        manga_items = soup.select('.listupd .bsx')
        
        manga_list = []
        unknown_episodes_count = 0
        known_episodes_count = 0
        
        for item in manga_items:
            # Get the main link element
            link = item.select_one('a')
            if not link:
                continue
                
            href = link['href']
            
            # Extract title from multiple possible locations
            title_element = item.select_one('.tt') or link.get('title')
            title = title_element.get_text(strip=True) if hasattr(title_element, 'get_text') else str(title_element)
            
            # Extract manga ID (slug) from URL
            manga_id = href.rstrip('/').split('/')[-1]
            
            # Try to extract episode directly from the listing
            episode = None
            epxs_element = item.select_one('.epxs')
            if epxs_element:
                text_content = epxs_element.get_text(strip=True)
                
                # Check for "فصل ?" format
                if "?" in text_content:
                    # Only log extreme cases to reduce noise
                    unknown_episodes_count += 1
                    episode = "unknown"
                else:
                    episode_match = re.search(r'(\d+)', text_content)
                    if episode_match:
                        episode = episode_match.group(1)
                        known_episodes_count += 1
            
            manga_data = {
                'id': manga_id, 
                'title': title, 
                'url': href
            }
            
            if episode:
                manga_data['episode'] = episode
                
            manga_list.append(manga_data)
        
        # Log summary instead of individual entries
        if known_episodes_count > 0:
            print(f"Found {known_episodes_count} manga with known episode numbers")
        if unknown_episodes_count > 0:
            print(f"Found {unknown_episodes_count} manga with unknown episode markers")
            
        return manga_list
    except requests.exceptions.RequestException as e:
        print(f"Error fetching manga: {e}")
        return []

def fetch_manga_episode(url):
    """Fetch the episode/chapter number for a specific manga URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        manga_title = "unknown"
        
        # Try to get manga title for better logging
        title_element = soup.select_one('.tt')
        if title_element:
            manga_title = title_element.get_text(strip=True)
        
        print(f"Analyzing page for manga '{manga_title}'")
        
        # Method 1: Look in the bigor element (similar to JavaScript)
        bigor_element = soup.select_one('.bigor')
        if bigor_element:
            adds_element = bigor_element.select_one('.adds')
            if adds_element:
                epxs_element = adds_element.select_one('.epxs')
                if epxs_element:
                    text_content = epxs_element.get_text(strip=True)
                    
                    # Check for "فصل ?" format
                    if "?" in text_content:
                        return "unknown"  # Return "unknown" instead of null
                    
                    episode_match = re.search(r'(\d+)', text_content)
                    if episode_match:
                        episode_number = int(episode_match.group(1))
                        print(f"Found episode {episode_number} for manga '{manga_title}'")
                        return str(episode_number)  # Return as string for consistency
        
        # Method 2: Look for adds element anywhere
        adds_element = soup.select_one('.adds')
        if adds_element:
            epxs_element = adds_element.select_one('.epxs')
            if epxs_element:
                text_content = epxs_element.get_text(strip=True)
                
                # Check for "فصل ?" format
                if "?" in text_content:
                    return "unknown"  # Return "unknown" instead of null
                
                episode_match = re.search(r'(\d+)', text_content)
                if episode_match:
                    episode_number = int(episode_match.group(1))
                    print(f"Found episode {episode_number} for manga '{manga_title}'")
                    return str(episode_number)  # Return as string for consistency
        
        # Method 3: Use JavaScript document.querySelectorAll('.adds') approach
        adds_elements = soup.select('.adds')
        for i, adds_element in enumerate(adds_elements):
            epxs_element = adds_element.select_one('.epxs')
            if epxs_element:
                text_content = epxs_element.get_text(strip=True)
                
                # Check for "فصل ?" format
                if "?" in text_content:
                    # Check if this adds is linked to our manga title
                    bigor = adds_element.find_parent('.bigor')
                    if bigor:
                        tt_element = bigor.select_one('.tt')
                        if tt_element:
                            found_title = tt_element.get_text(strip=True)
                            # If title matches, this is definitely the right episode
                            if found_title.lower() == manga_title.lower():
                                return "unknown"
                    
                    # If we can't confirm the match, still return this as a possible episode marker
                    return "unknown"
                
                episode_match = re.search(r'(\d+)', text_content)
                if episode_match:
                    episode_number = int(episode_match.group(1))
                    
                    # Check if this adds is linked to our manga title
                    bigor = adds_element.find_parent('.bigor')
                    if bigor:
                        tt_element = bigor.select_one('.tt')
                        if tt_element:
                            found_title = tt_element.get_text(strip=True)
                            # If title matches, this is definitely the right episode
                            if found_title.lower() == manga_title.lower():
                                print(f"Found episode {episode_number} for manga '{manga_title}'")
                                return str(episode_number)
                    
                    # If we can't confirm the match, still return this as a possible episode
                    print(f"Found potential episode {episode_number} for manga '{manga_title}'")
                    return str(episode_number)
        
        # Method 4: Look for any epxs elements on the page
        epxs_elements = soup.select('.epxs')
        for epxs_element in epxs_elements:
            text_content = epxs_element.get_text(strip=True)
            
            # Check for "فصل ?" format
            if "?" in text_content:
                return "unknown"  # Return "unknown" instead of null
            
            episode_match = re.search(r'(\d+)', text_content)
            if episode_match:
                episode_number = int(episode_match.group(1))
                print(f"Found episode {episode_number} for manga '{manga_title}'")
                return str(episode_number)  # Return as string for consistency
        
        # Method 5: Try to find any element with episodeNumber info in scripts
        script_elements = soup.select('script')
        for script in script_elements:
            if script.string and 'episodeNumber' in script.string:
                episode_match = re.search(r'episodeNumber["\']?\s*:\s*["\']?(\d+)', script.string)
                if episode_match:
                    episode_number = int(episode_match.group(1))
                    print(f"Found episode {episode_number} for manga '{manga_title}' in script")
                    return str(episode_number)
        
        print(f"Could not find episode number for manga '{manga_title}'")
        return None
    except Exception as e:
        print(f"Error fetching episode info: {e}")
        return None

def load_seen_manga():
    """Load the previously seen manga"""
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r') as f:
                data = json.load(f)
                # If it's already a dictionary, return it as a list with one item
                if isinstance(data, dict):
                    return [data]
                # Handle old format (list of dicts)
                elif data and isinstance(data, list):
                    if isinstance(data[0], str):
                        # Convert old format to new format
                        return [{'id': manga_id, 'title': manga_id, 'url': ''} for manga_id in data]
                    else:
                        # Return only the first item from the list format
                        return [data[0]] if data else []
        except json.JSONDecodeError:
            print(f"Error reading {STORAGE_FILE}, starting with empty list")
    return []

def load_manga_list():
    """Load the current manga list from manga_list.json"""
    if os.path.exists(MANGA_LIST_FILE):
        try:
            with open(MANGA_LIST_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {MANGA_LIST_FILE}, starting with empty list")
    return []

def save_manga_data(manga_list):
    """Save the current manga data to the storage file"""
    
    # Load existing data to check if there's a change
    existing_data = None
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r') as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    # Only save the last manga from the list
    if manga_list:
        # Get the first manga (most recently updated)
        last_manga = manga_list[0]
        
        # Start with basic information
        manga_data = {
            'id': last_manga['id'],
            'title': last_manga['title'],
            'url': last_manga['url'],
        }
        
        # Get current episode info if available
        if 'episode' in last_manga and last_manga['episode'] is not None:
            # Store as string to maintain consistency
            manga_data['episode'] = str(last_manga['episode'])
            
            # Log if there's a change from previously saved data
            if existing_data and isinstance(existing_data, dict) and existing_data.get('id') == last_manga['id']:
                if existing_data.get('episode') != manga_data['episode']:
                    prev_episode = existing_data.get('episode')
                    print(f"Updating episode: {prev_episode} → {manga_data['episode']} for {last_manga['title']}")
                    
                    # Add prev_episode for notification tracking
                    manga_data['prev_episode'] = prev_episode
                    
                    # Make sure the current manga in the list also has prev_episode set
                    if 'prev_episode' not in last_manga:
                        last_manga['prev_episode'] = prev_episode
            elif existing_data and (not isinstance(existing_data, dict) or existing_data.get('id') != last_manga['id']):
                print(f"Saving new manga: {last_manga['title']} with episode {manga_data['episode']}")
        else:
            # Always include the episode field, even if null
            manga_data['episode'] = None
            
            # Log if this is a new manga
            if not existing_data or (isinstance(existing_data, dict) and existing_data.get('id') != last_manga['id']):
                print(f"Saving new manga: {last_manga['title']} with no episode information")
        
        # Save only the last manga
        with open(STORAGE_FILE, 'w') as f:
            json.dump(manga_data, f, indent=2)
        
        print(f"Saved last manga {last_manga['title']} to {STORAGE_FILE}")
    
    return True

def update_manga_list(new_manga):
    """Update the manga_list.json file with new manga titles and episode information"""
    if not new_manga:
        return
        
    current_list = load_manga_list()
    
    # Create a lookup by URL for faster access
    manga_dict = {item['url']: item for item in current_list}
    
    # Add new manga or update episode information
    added = 0
    updated = 0
    
    for manga in new_manga:
        # Store episode as string for consistency
        episode = str(manga['episode']) if 'episode' in manga and manga['episode'] is not None else None
        
        if manga['url'] in manga_dict:
            # Update episode if there's a change
            existing = manga_dict[manga['url']]
            if 'episode' in manga and manga['episode'] is not None:
                if 'episode' not in existing or existing['episode'] != episode:
                    existing['episode'] = episode
                    updated += 1
        else:
            # Add new manga with all info including episode
            manga_data = {
                'id': manga['id'],
                'title': manga['title'],
                'url': manga['url']
            }
            if 'episode' in manga and manga['episode'] is not None:
                manga_data['episode'] = episode
                
            current_list.append(manga_data)
            manga_dict[manga['url']] = manga_data
            added += 1
    
    # Save the updated list if changes were made
    if added > 0 or updated > 0:
        with open(MANGA_LIST_FILE, 'w') as f:
            json.dump(current_list, f, indent=2)
        
        changes = []
        if added > 0:
            changes.append(f"{added} new")
        if updated > 0:
            changes.append(f"{updated} episode updates")
            
        print(f"Updated {MANGA_LIST_FILE} with {' and '.join(changes)}")
    
    return current_list

def get_last_updates_manga():
    """Get the last updates manga list retrieved during check_for_updates"""
    global _last_updates_manga
    return _last_updates_manga

def check_for_updates():
    """Check for manga updates and new manga"""
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] Checking for updates...", flush=True)
    
    # Fetch manga from both URLs
    updates_manga = fetch_manga(URLS['updates'])
    latest_manga = fetch_manga(URLS['latest'])
    
    # Store updates_manga for reference
    global _last_updates_manga
    _last_updates_manga = updates_manga
    
    if not updates_manga and not latest_manga:
        print(" No manga found or error occurred while fetching")
        return None, None

    # Load previously seen manga (for position change detection)
    seen_manga = load_seen_manga()
    
    # Load manga list for comprehensive episode checking
    manga_list = load_manga_list()
    manga_dict = {item['url']: item for item in manga_list}
    
    # Check if first manga has changed position
    first_manga_changed = False
    if updates_manga and seen_manga:
        # Get the first manga ID from current updates
        current_first_id = updates_manga[0]['id']
        # Check if it matches the saved manga
        if seen_manga[0]['id'] != current_first_id:
            print(f"Position change detected: {updates_manga[0]['title']} is now the first manga")
            first_manga_changed = True
    
    # Check for new updates
    new_updates = []
    
    # Check if the currently saved manga has an episode update compared to the previously saved one
    if updates_manga and len(seen_manga) > 0:
        saved_manga = seen_manga[0]
        current_first_manga = updates_manga[0]
        
        # Check if it's the same manga
        if saved_manga['id'] == current_first_manga['id']:
            # Get current episode
            if 'episode' not in current_first_manga:
                current_episode = fetch_manga_episode(current_first_manga['url'])
                current_first_manga['episode'] = current_episode
            else:
                current_episode = current_first_manga['episode']
            
            # If we have a saved episode to compare with
            if 'episode' in saved_manga and saved_manga['episode'] and current_episode:
                try:
                    # Compare as numbers if possible
                    current_episode_num = int(current_episode)
                    saved_episode_num = int(saved_manga['episode'])
                    
                    if current_episode_num > saved_episode_num:
                        print(f"Detected episode change in saved manga: {saved_manga['episode']} → {current_episode} for {current_first_manga['title']}")
                        current_first_manga['prev_episode'] = saved_manga['episode']
                        # Add to new_updates to trigger notification after checking for duplicates
                        if not is_duplicate_notification(current_first_manga):
                            new_updates.append(current_first_manga)
                except (ValueError, TypeError):
                    # Compare as strings
                    if current_episode != saved_manga['episode']:
                        print(f"Detected episode change in saved manga: {saved_manga['episode']} → {current_episode} for {current_first_manga['title']}")
                        current_first_manga['prev_episode'] = saved_manga['episode']
                        # Add to new_updates to trigger notification after checking for duplicates
                        if not is_duplicate_notification(current_first_manga):
                            new_updates.append(current_first_manga)
    
    # Process all manga from updates
    for manga in updates_manga:
        # If episode is not already set in the listing, fetch it
        if 'episode' not in manga:
            current_episode = fetch_manga_episode(manga['url'])
            manga['episode'] = current_episode
        else:
            current_episode = manga['episode']
        
        # Skip if we have no episode info
        if current_episode is None:
            continue
            
        # Check if we've seen this manga before
        if manga['url'] in manga_dict:
            prev_manga = manga_dict[manga['url']]
            prev_episode = prev_manga.get('episode')
            
            # Skip if both episodes are None or unknown
            if (prev_episode is None and current_episode is None) or \
               (prev_episode == "unknown" and current_episode == "unknown"):
                continue
                
            # If we now have episode info when we didn't before
            if prev_episode is None and current_episode is not None:
                print(f"New episode information detected for {manga['title']}: Chapter {current_episode}")
                manga['prev_episode'] = prev_episode
                if not is_duplicate_notification(manga):
                    new_updates.append(manga)
                continue
            
            # If we lost episode info, don't consider as update
            if prev_episode is not None and current_episode is None:
                print(f"Warning: Lost episode information for {manga['title']}. Previous was {prev_episode}")
                continue
                
            # Handle "unknown" episode markers
            if current_episode == "unknown" or prev_episode == "unknown":
                # If we went from unknown to a number, it's an update
                if current_episode != "unknown" and prev_episode == "unknown":
                    print(f"Episode update detected for {manga['title']}: unknown → {current_episode}")
                    manga['prev_episode'] = prev_episode
                    if not is_duplicate_notification(manga):
                        new_updates.append(manga)
                continue
                
            # Both episodes are not None or "unknown", compare them
            try:
                current_episode_num = int(current_episode)
                prev_episode_num = int(prev_episode)
                
                if current_episode_num > prev_episode_num:
                    print(f"Updating episode: {prev_episode} → {current_episode} for {manga['title']}")
                    # Store previous episode to enable episode-specific notifications
                    manga['prev_episode'] = prev_episode
                    # Add to new_updates to trigger notification after checking for duplicates
                    if not is_duplicate_notification(manga):
                        new_updates.append(manga)
                elif current_episode_num < prev_episode_num:
                    print(f"Warning: Current episode ({current_episode}) is less than previous ({prev_episode}) for {manga['title']}. Possible data error.")
            except (ValueError, TypeError) as e:
                # If we can't compare as numbers, use string comparison
                if current_episode != prev_episode:
                    print(f"Episode change detected for {manga['title']}: {prev_episode} → {current_episode}")
                    manga['prev_episode'] = prev_episode
                    if not is_duplicate_notification(manga):
                        new_updates.append(manga)
        else:
            # New manga, not seen before
            print(f"New manga detected: {manga['title']} with episode {current_episode}")
            if not is_duplicate_notification(manga):
                new_updates.append(manga)
    
    # Check for new manga titles
    new_titles = []
    
    # Use manga_dict for truly new manga detection
    for manga in latest_manga:
        if manga['url'] not in manga_dict:
            # If episode is not already set in the listing, fetch it
            if 'episode' not in manga:
                episode = fetch_manga_episode(manga['url'])
                manga['episode'] = episode
            else:
                # Don't log this to reduce noise
                pass
                
            print(f"New manga title detected: {manga['title']} with episode {manga.get('episode')}")
            if not is_duplicate_notification(manga):
                new_titles.append(manga)
    
    # Report findings in console
    if new_updates:
        print(f"\nFound {len(new_updates)} new manga updates!")
        for manga in new_updates:
            episode_info = f" (Chapter: {manga['episode']})" if 'episode' in manga and manga['episode'] else ""
            print(f"📢 New manga update: {manga['title']}{episode_info}")
            print(f"   URL: {manga['url']}")
            # Mark as successfully notified
            mark_notification_sent(manga)
    
    if new_titles:
        print(f"\nFound {len(new_titles)} new manga titles!")
        for manga in new_titles:
            episode_info = f" (Chapter: {manga['episode']})" if 'episode' in manga and manga['episode'] else ""
            print(f"🆕 New manga released: {manga['title']}{episode_info}")
            print(f"   URL: {manga['url']}")
            # Mark as successfully notified
            mark_notification_sent(manga)
    
    if not new_updates and not new_titles:
        print("No new manga or updates detected")
    
    # Combine all manga for tracking and update manga_list.json
    all_manga = updates_manga + [m for m in latest_manga if m['id'] not in {manga['id'] for manga in updates_manga}]
    update_manga_list(all_manga)
    
    # We'll only save the first manga from updates_manga (most recently updated)
    if updates_manga:
        save_manga_data(updates_manga)
    else:
        # If no updates, save the first manga from latest
        if latest_manga:
            save_manga_data(latest_manga)
    
    # Check for missed notifications
    reconcile_notifications()
    
    return new_updates, new_titles

def reconcile_notifications():
    """Check for any missed notifications by comparing notification log with manga list"""
    if not os.path.exists(NOTIFICATION_LOG_FILE) or not os.path.exists(MANGA_LIST_FILE):
        return
    
    try:
        # Load notification history
        with open(NOTIFICATION_LOG_FILE, 'r') as f:
            history = json.load(f)
        
        # Load manga list
        manga_list = load_manga_list()
        
        # Get pending notifications that might have been missed
        current_time = time.time()
        pending_notifications = [entry for entry in history 
                                if entry['status'] == 'pending' and 
                                current_time - entry['timestamp'] > 1800]  # 30 minutes
        
        if pending_notifications:
            print(f"Found {len(pending_notifications)} pending notifications that may have been missed")
            
            # Update their status
            for entry in pending_notifications:
                entry['status'] = 'retry_needed'
                entry['retry_timestamp'] = current_time
                print(f"Marking notification for retry: {entry['title']} episode {entry['episode']}")
            
            # Save updated history
            temp_file = NOTIFICATION_LOG_FILE + '.tmp'
            with open(temp_file, 'w') as f:
                json.dump(history, f, indent=2)
            # Atomic replace
            os.replace(temp_file, NOTIFICATION_LOG_FILE)
            
    except Exception as e:
        print(f"Error during notification reconciliation: {e}")

def first_run():
    """Initial run to save current manga titles and updates"""
    print("First run - Saving current manga titles and updates...")
    
    updates_manga = fetch_manga(URLS['updates'])
    latest_manga = fetch_manga(URLS['latest'])
    
    # Combine all manga for potential fetching
    all_manga = updates_manga + [m for m in latest_manga if m['id'] not in {manga['id'] for manga in updates_manga}]
    manga_count = len(all_manga)
    
    if all_manga:
        first_manga = updates_manga[0] if updates_manga else latest_manga[0] if latest_manga else None
        
        if first_manga:
            print(f"Fetching episode information for {first_manga['title']}...")
            # Only fetch episode if not already set from listing
            if 'episode' not in first_manga:
                episode = fetch_manga_episode(first_manga['url'])
                if episode:
                    first_manga['episode'] = episode
                    print(f"Found episode {episode} for {first_manga['title']} by fetching page")
                else:
                    first_manga['episode'] = None
                    print(f"No episode found for {first_manga['title']}")
            else:
                print(f"Using episode {first_manga['episode']} for {first_manga['title']} from listing")
                
            # Save only the first manga to manga_seen.json
            save_manga_data([first_manga])
            print(f"Saved first manga {first_manga['title']} to {STORAGE_FILE}")
        
        # Fetch episodes for a reasonable number of manga to avoid excessive requests
        print(f"Fetching episodes for top manga (this may take a while)...")
        manga_to_process = min(10, len(all_manga))
        
        for i in range(manga_to_process):
            manga = all_manga[i]
            try:
                # Only fetch episode if not already set from listing
                if 'episode' not in manga:
                    print(f"Fetching episode for {manga['title']} ({i+1}/{manga_to_process})...")
                    episode = fetch_manga_episode(manga['url'])
                    manga['episode'] = episode
                    if episode:
                        print(f"Found episode {episode} for {manga['title']}")
                    else:
                        print(f"No episode found for {manga['title']}")
                else:
                    print(f"Using episode {manga['episode']} for {manga['title']} from listing")
            except Exception as e:
                print(f"Error fetching episode for {manga['title']}: {e}")
        
        # Update manga_list.json with ALL manga
        update_manga_list(all_manga)
        print(f"Saved {len(all_manga)} manga to manga list")
    else:
        print("No manga found or error occurred during initial fetch")

def reset_manga_list():
    """Reset the manga_list.json file"""
    with open(MANGA_LIST_FILE, 'w') as f:
        json.dump([], f, indent=2)
    print(f"Reset {MANGA_LIST_FILE} to empty list")

def run_standalone():
    """Run the manga checker without Discord integration"""
    print("Manga Checker Starting...")
    
    # Check if first run needed for manga_seen.json
    first_run_needed = not os.path.exists(STORAGE_FILE)
    
    # Check if manga_list.json exists, create it if not
    if not os.path.exists(MANGA_LIST_FILE):
        print(f"{MANGA_LIST_FILE} not found, creating empty list")
        reset_manga_list()
    
    # Create notification log if it doesn't exist
    if not os.path.exists(NOTIFICATION_LOG_FILE):
        print(f"{NOTIFICATION_LOG_FILE} not found, creating empty list")
        with open(NOTIFICATION_LOG_FILE, 'w') as f:
            json.dump([], f, indent=2)
    
    if first_run_needed:
        first_run()
    
    print(f"Monitoring for new manga releases and updates every {CHECK_INTERVAL} seconds...")
    print(f"Press Ctrl+C to stop")
    
    try:
        while True:
            check_for_updates()
            time.sleep(CHECK_INTERVAL)  # Check every interval
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    run_standalone() 
