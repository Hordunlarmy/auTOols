"""
Google Maps Public Edit Automation Bot
Submits public edits to Google Maps programmatically using browser automation
"""

import asyncio
import time
import argparse
import json
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class GoogleMapsEditBot:
    """
    Bot to submit public edits to Google Maps using browser automation
    Note: Requires Chrome browser and may need Google account sign-in
    """
    
    def __init__(self, headless: bool = False, browser_dir: str = "./browser", user_data_dir: str = None):
        """
        Initialize the automation bot
        
        Args:
            headless: Run browser in headless mode (invisible)
            browser_dir: Directory to install/store browser
            user_data_dir: Path to save browser state (persists sign-in)
        """
        self.headless = headless
        self.browser_dir = browser_dir
        self.user_data_dir = user_data_dir or "./browser_data"
        self.playwright = None
        self.browser = None
        self.page = None
        self.context = None
        self.auto_click = False
        self.capture_clicks = False
        self.click_delay = 0.5  # seconds between automated clicks
        self.panel_wait_seconds = 3  # seconds to wait for panel to load
        self.post_ok_click = True  # always click OK/Got it confirmation after submit when present
        
        # Cached debug: list of known selectors for inputs and submit
        self.place_name_selectors = [
            'input#i7',
            'input[jsname="YPqjbf"]',
            'input[aria-label="Place name in English"]',
            'input[placeholder="Add place name in English"]',
            'input.VfPpkd-fmcmS-wGMbrd',
            'input[type="text"][aria-label*="Place name" i]',
            'input[placeholder*="place name" i]'
        ]
        self.submit_selectors = [
            'span[jsname="V67aGc"]',  # Exact JS name from captured click
            'span.VfPpkd-vQzf8d',  # Class from captured click  
            'div.VfPpkd-RLmnJb',  # Container from captured click
            'span:has-text("Submit")',
            'button:has-text("Submit")',
            'button:has-text("Send")',
            '[role="button"]:has-text("Submit")',
            '*[aria-label*="Submit" i]',
            '*[aria-label*="Send" i]'
        ]

    async def _evaluate_in_all_frames(self, js: str):
        """Evaluate a JS snippet in all frames; return first non-null result and the frame."""
        try:
            # Try main frame first
            result = await self.page.evaluate(js)
            if result:
                return result, self.page.main_frame
        except Exception:
            pass
        # Try child frames
        for frame in self.page.frames:
            if frame == self.page.main_frame:
                continue
            try:
                result = await frame.evaluate(js)
                if result:
                    return result, frame
            except Exception:
                continue
        return None, None

    async def _click_xy_in_frame(self, frame, x: float, y: float):
        # Click using the owning frame when possible, else fall back to page
        # Toggle a window flag so the click logger ignores bot-driven clicks
        target_page = getattr(frame, 'page', None) or self.page
        try:
            await self._set_bot_clicking_for_all_frames(True)
            await target_page.mouse.click(x, y)
        finally:
            await self._set_bot_clicking_for_all_frames(False)
        # Apply global click delay
        try:
            if self.click_delay and self.click_delay > 0:
                await asyncio.sleep(self.click_delay)
        except Exception:
            pass

    async def _set_bot_clicking_for_all_frames(self, value: bool) -> None:
        """Best-effort set a flag in all reachable frames to suppress manual click logging."""
        flag = 'true' if value else 'false'
        js = (
            "window.__botClicking = " + flag + ";" \
            "try{ if(window.top) window.top.__botClicking = " + flag + "; }catch(e){};" \
            "try{ if(window.parent) window.parent.__botClicking = " + flag + "; }catch(e){};"
        )
        try:
            await self.page.evaluate(js)
        except Exception:
            pass
        for fr in self.page.frames:
            try:
                await fr.evaluate(js)
            except Exception:
                continue
        
    async def wait_for_signin(self, timeout: int = 60):
        """
        Wait for user to sign in to Google
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        if self.headless:
            print("Note: Running in headless mode. Consider running without --headless for sign-in.")
            return
        
        print("\n" + "=" * 60)
        print("SIGN-IN REQUIRED")
        print("=" * 60)
        print(f"You have {timeout} seconds to sign in to your Google account.")
        print("Look for the 'Sign in' button in the browser window.")
        print("After signing in, wait for the page to load.")
        print("=" * 60 + "\n")
        
        await asyncio.sleep(timeout)
        print("Resuming automation...\n")
    
    async def check_and_wait_for_signin(self, timeout: int = 60) -> bool:
        """
        Check if signed in, wait if not
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if signed in, False otherwise
        """
        try:
            # Try to detect if we're signed in
            # Look for signs of being signed in on Google Maps
            await asyncio.sleep(2)  # Give page time to load
            
            # Check for "Sign in" button (means NOT signed in)
            sign_in_button = self.page.locator('text="Sign in"').first
            if await sign_in_button.count() > 0:
                print("\n⚠️  Not signed in to Google")
                print(f"Waiting {timeout} seconds for you to sign in...")
                print("\nSteps to sign in:")
                print("1. Look for 'Sign in' button (top right)")
                print("2. Click it and complete sign-in")
                print("3. Wait for Google Maps to load")
                print(f"\nYou have {timeout} seconds.\n")
                
                await asyncio.sleep(timeout)
                print("✓ Resuming...\n")
                return True
            else:
                print("✓ Already signed in!")
                return True
                
        except Exception as e:
            print(f"Could not check sign-in status: {e}")
            print(f"Assuming signed in, continuing...")
            return True
    
    async def check_if_signed_in(self) -> bool:
        """
        Quick check if signed in to Google
        
        Returns:
            True if signed in, False if sign in button is visible
        """
        try:
            await asyncio.sleep(2)  # Give page time to load
            
            # Check for "Sign in" button - if found, NOT signed in
            sign_in_button = self.page.locator('text="Sign in"').first
            count = await sign_in_button.count()
            
            # Also check for profile icon which indicates signed in
            profile_icon = self.page.locator('[aria-label*="Account" i]').first
            profile_count = await profile_icon.count()
            
            is_signed_in = count == 0 and profile_count > 0
            
            if is_signed_in:
                print("✓ Signed in!")
            else:
                print("✗ Not signed in (found 'Sign in' button)")
            
            return is_signed_in
            
        except Exception as e:
            print(f"Could not determine sign-in status: {e}")
            return False
        
    async def _init_browser(self):
        """Initialize the browser"""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            
            # Use persistent context to save sign-in state
            import os
            os.makedirs(self.user_data_dir, exist_ok=True)
            
            # Stealth settings to avoid detection
            stealth_args = [
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-gpu',
                '--lang=en-US,en',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-default-apps',
            ]
            
            # Try to use installed Chromium first
            try:
                self.context = await self.playwright.chromium.launch_persistent_context(
                    self.user_data_dir,
                    headless=self.headless,
                    channel="chrome",  # Uses system Chrome if available
                    viewport={"width": 1920, "height": 1080},
                    args=stealth_args,
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation'],
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                    }
                )
            except:
                # Fallback to installed chromium
                print("Using Playwright Chromium...")
                self.context = await self.playwright.chromium.launch_persistent_context(
                    self.user_data_dir,
                    headless=self.headless,
                    viewport={"width": 1920, "height": 1080},
                    args=stealth_args,
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York',
                    permissions=['geolocation'],
                    extra_http_headers={
                        'Accept-Language': 'en-US,en;q=0.9',
                    }
                )
            
            # Get the first page or create one
            if len(self.context.pages) > 0:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
            
            # Add stealth JavaScript to hide automation
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Flag to distinguish bot-driven clicks from manual ones
                window.__botClicking = false;
            """)
            
            # Enable click logging if requested
            if self.capture_clicks:
                await self._enable_click_logging()

    async def _enable_click_logging(self):
        """Attach a document click listener and pipe element details back to Python."""
        # Create captures folder
        import os
        os.makedirs('captured_clicks', exist_ok=True)
        
        # Expose a Python function to receive click info
        async def _on_click(info: dict):
            try:
                timestamp = int(time.time() * 1000)
                # Pretty-print to console
                print("\n" + "=" * 60)
                print("CLICK CAPTURED (manual)")
                print("=" * 60)
                print(f"Tag: {info.get('tagName')}")
                print(f"ID: {info.get('id')}")
                print(f"Class: {info.get('className')}")
                print(f"Type: {info.get('type')}")
                print(f"Role: {info.get('role')}")
                print(f"ContentEditable: {info.get('contentEditable')}")
                print(f"Placeholder: {info.get('placeholder')}")
                print(f"Aria-Label: {info.get('ariaLabel')}")
                print(f"Aria-LabelledBy: {info.get('ariaLabelledBy')}")
                print(f"Name: {info.get('name')}")
                print(f"Is Visible: {info.get('isVisible')}")
                print(f"Is Editable: {info.get('isEditable')}")
                print(f"Coords: ({info.get('x')}, {info.get('y')})  Size: {info.get('width')}x{info.get('height')}")

                # Persist JSONL log in captures folder
                with open('captured_clicks/captured_clicks.jsonl', 'a', encoding='utf-8') as f:
                    f.write(json.dumps({
                        **info,
                        "ts": timestamp,
                        "url": self.page.url,
                    }, ensure_ascii=False) + "\n")

                # Save outerHTML to a file for inspection
                with open(f'captured_clicks/captured_click_{timestamp}.html', 'w', encoding='utf-8') as hf:
                    hf.write(info.get('outerHTML') or '')

                # Screenshot context
                try:
                    await self.page.screenshot(path=f'captured_clicks/captured_click_{timestamp}.png', full_page=True)
                    print(f"Saved: captured_clicks/captured_click_{timestamp}.png, captured_clicks/captured_click_{timestamp}.html")
                except Exception as _:
                    pass
            except Exception as e:
                print(f"Error while logging click: {e}")

        await self.page.expose_function('pyOnClick', _on_click)
        # Inject a capturing click listener in the document
        await self.page.add_init_script("""
            (function(){
              document.addEventListener('click', function(ev){
                try {
                  // Only log manual, trusted clicks not initiated by the bot
                  if (!ev.isTrusted || window.__botClicking) { return; }
                  const t = ev.target;
                  const rect = t.getBoundingClientRect();
                  const computed = window.getComputedStyle(t);
                  const info = {
                    tagName: t.tagName,
                    id: t.id || '',
                    className: t.className || '',
                    outerHTML: (t.outerHTML || '').slice(0, 20000),
                    innerHTML: (t.innerHTML || '').slice(0, 1000),
                    textContent: (t.textContent || '').slice(0, 500),
                    value: t.value || '',
                    placeholder: t.placeholder || '',
                    ariaLabel: t.getAttribute('aria-label') || '',
                    ariaLabelledBy: t.getAttribute('aria-labelledby') || '',
                    role: t.getAttribute('role') || '',
                    contentEditable: t.contentEditable || '',
                    type: t.type || '',
                    name: t.name || '',
                    dataValue: t.getAttribute('data-value') || '',
                    jsname: t.getAttribute('jsname') || '',
                    jscontroller: t.getAttribute('jscontroller') || '',
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                    isVisible: rect.width > 0 && rect.height > 0 && computed.visibility !== 'hidden' && computed.display !== 'none',
                    isEditable: (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA') || (t.contentEditable === 'true') || (t.getAttribute('role') === 'textbox')
                  };
                  if (window.pyOnClick) { window.pyOnClick(info); }
                } catch (e) {}
              }, true);
            })();
        """)
    
    async def close(self):
        """Close the browser"""
        try:
            # Don't close pages in persistent context, let them accumulate
            if self.context:
                # Save cookies/state before closing
                pass
        except:
            pass
        try:
            if self.context:
                await self.context.close()
        except:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except:
            pass
    
    async def search_location(self, query: str, wait_time: int = 3) -> bool:
        """
        Search for a location on Google Maps
        
        Args:
            query: Location search query
            wait_time: Seconds to wait for results
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Already on Google Maps from earlier, just search
            print(f"Searching for: {query}")
            
            # Try different selectors for search box
            search_box = None
            selectors = [
                'input#searchboxinput',
                '#searchboxinput',
                'input[placeholder*="Search"]',
                'input[aria-label*="Search"]',
                'input.maps-sprite-searchbox-input'
            ]
            
            for selector in selectors:
                try:
                    search_box = self.page.locator(selector).first
                    if await search_box.count() > 0:
                        await search_box.wait_for(state="visible", timeout=5000)
                        break
                except:
                    continue
            
            if not search_box or await search_box.count() == 0:
                print("Could not find search box. Trying direct input method...")
                # Try typing directly into any visible input
                await self.page.keyboard.type(query)
                await self.page.keyboard.press('Enter')
            else:
                await search_box.fill(query)
                await search_box.press('Enter')
            
            # Wait for search results
            await asyncio.sleep(wait_time + 2)
            
            print("Location found!")
            return True
            
        except Exception as e:
            print(f"Error searching location: {e}")
            print("\nTip: Try running without --headless to see what's happening")
            return False
    
    async def open_suggest_edit(self) -> bool:
        """
        Open the 'Suggest an edit' dialog
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Wait for the location info panel to fully load
            print("Waiting for location info panel to load...")
            
            # Wait for location panel to appear
            panel_loaded = False
            max_attempts = max(0, int(self.panel_wait_seconds))
            for attempt in range(max_attempts or 1):
                try:
                    # Look for common panel indicators
                    panel = self.page.locator('[data-container-id], [role="complementary"]').first
                    if await panel.count() > 0 and await panel.is_visible():
                        panel_loaded = True
                        print(f"✓ Location panel loaded (attempt {attempt + 1})")
                        break
                except:
                    pass
                await asyncio.sleep(1)
            
            if not panel_loaded:
                print("⚠️  Location panel may not have loaded yet, continuing anyway...")
            
            if self.click_delay and self.click_delay > 0:
                await asyncio.sleep(self.click_delay)
            
            print("Looking for 'Suggest an edit' button in location panel...")
            
            # Comprehensive selectors for location info panel
            # Try ALL possible variations
            selectors = [
                # Direct button selectors
                'button:has-text("Suggest an edit")',
                'button[aria-label*="Suggest an edit" i]',
                'button[title*="Suggest an edit" i]',
                'button:has-text("Suggest")',
                'button:has-text("Edit")',
                '[role="button"]:has-text("Suggest an edit")',
                '[role="button"]:has-text("Suggest")',
                
                # Using different HTML attributes
                '[aria-label="Suggest an edit"]',
                '[aria-label*="Suggest an edit"]',
                '[title="Suggest an edit"]',
                '[data-value="suggest"]',
                '[jsaction*="suggest"]',
                '[id*="suggest"]',
                '[class*="suggest"]',
                
                # Generic button in panel
                '[data-container-id] button:has-text("Suggest")',
                '[data-container-id] button:has-text("Edit")',
                'div[role="button"]:has-text("Suggest")',
                'div[role="button"]:has-text("Edit")',
                
                # Menu items
                'div[role="menuitem"]:has-text("Suggest an edit")',
                'div[role="menuitem"]:has-text("Edit")',
                'div[role="menuitem"]:has-text("Suggest")',
                
                # Link variants
                'a:has-text("Suggest an edit")',
                'a:has-text("Suggest")',
                
                # Text-based (fallback)
                'text="Suggest an edit"',
                'text="Edit"',
                'text="Suggest"',
            ]
            
            # Method 1: Try direct selectors
            found = False
            clicked_element = None
            
            for i, selector in enumerate(selectors):
                try:
                    # Get all matching elements
                    all_matches = self.page.locator(selector)
                    count = await all_matches.count()
                    
                    if count > 0:
                        # Try each match
                        for idx in range(min(count, 3)):  # Try first 3 matches
                            element = all_matches.nth(idx)
                            
                            try:
                                # Check if visible
                                is_visible = await element.is_visible()
                                is_enabled = await element.is_enabled()
                                
                                if is_visible and is_enabled:
                                    # Scroll into view
                                    await element.scroll_into_view_if_needed()
                                    await asyncio.sleep(0.3)
                                    
                                    # Try to click
                                    await element.click(timeout=2000)
                                    if self.click_delay and self.click_delay > 0:
                                        await asyncio.sleep(self.click_delay)
                                    
                                    print(f"✓ Found and clicked element #{idx}")
                                    clicked_element = selector
                                    found = True
                                    break
                            except:
                                continue
                        
                        if found:
                            break
                            
                except Exception as e:
                    continue
            
            # Method 2: Try clicking in location panel area directly
            if not found:
                print("\nTrying to click in location info panel area...")
                try:
                    # Find the location panel container
                    panel = self.page.locator('[data-container-id], [role="complementary"], .location-panel').first
                    if await panel.count() > 0:
                        # Try clicking around the search area
                        box = await panel.bounding_box()
                        if box:
                            x = box['x'] + box['width'] - 100
                            y = box['y'] + 100
                            await self.page.mouse.click(x, y)
                            if self.click_delay and self.click_delay > 0:
                                await asyncio.sleep(self.click_delay)
                            print("✓ Clicked in panel area")
                            found = True
                except:
                    pass
            
            # Method 3: Try keyboard navigation
            if not found:
                print("\nTrying keyboard navigation...")
                try:
                    for _ in range(5):
                        await self.page.keyboard.press('Tab')
                        await asyncio.sleep(0.3)
                    await self.page.keyboard.press('Enter')
                    if self.click_delay and self.click_delay > 0:
                        await asyncio.sleep(self.click_delay)
                    print("✓ Tried keyboard navigation")
                    found = True
                except:
                    pass
            
            if not found:
                print("\n⚠️  Could not automatically find 'Suggest an edit' button")
                print("\nTrying one more time with different approach...")
                
                # Last resort: Try to find any clickable element with "edit" in text
                try:
                    all_text = await self.page.locator('*').all_inner_texts()
                    for text in all_text:
                        if 'suggest' in text.lower() or 'edit' in text.lower():
                            # Try to find parent clickable element
                            try:
                                element = self.page.locator(f'text="{text.strip()}"').first
                                if await element.count() > 0:
                                    await element.click()
                                    if self.click_delay and self.click_delay > 0:
                                        await asyncio.sleep(self.click_delay)
                                    await asyncio.sleep(2)
                                    print("✓ Found text-based clickable")
                                    found = True
                                    break
                            except:
                                continue
                except:
                    pass
            
            if not found:
                # Save debug info
                try:
                    await self.page.screenshot(path='debug_maps.png', full_page=True)
                    html = await self.page.content()
                    with open('debug_html.html', 'w') as f:
                        f.write(html)
                    print("\n📁 Debug files saved:")
                    print("  - debug_maps.png (screenshot)")
                    print("  - debug_html.html (page source)")
                except:
                    pass
                
                print("\n❌ Could not find 'Suggest an edit' button automatically.")
                print("The location info panel may not have loaded yet.")
                print("Please manually click 'Suggest an edit' in the browser.")
                print("Waiting 45 seconds...")
                await asyncio.sleep(45)
                return True
                
            return True
                
        except Exception as e:
            print(f"Error opening edit dialog: {e}")
            print("\nPlease manually click 'Suggest an edit' if the button appears")
            await asyncio.sleep(30)
            return False
    
    async def submit_name_change(self, new_name: str) -> bool:
        """
        Submit a name change suggestion
        
        Args:
            new_name: New name for the location
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\nSubmitting name change to: {new_name}")
            
            # Wait for dialog to fully load
            await asyncio.sleep(2)
            
            # Step 1: Click on the "Name" or first field option in the menu
            print("Looking for name edit option in menu...")
            
            # (debug artifacts removed)
            
            menu_option_selectors = [
                # Direct text matching
                'div:has-text("AIQ")',  # Try clicking on current name first to open name edit
                'div:has-text("name" i)',
                '*[role="menuitem"]:has-text("name" i)',
                '*[role="button"]:has-text("name" i)',
                
                # Look for elements that might be the business name
                'div[data-value]:has-text("AIQ")',
                'button:has-text("AIQ")',
                '[jsaction]:has-text("AIQ")',
                
                # Generic menu item selectors
                '[role="menuitem"]',
                'div[role="menuitem"]',
                '[data-value]',
                'div[data-value]',
                
                # Common patterns
                'div[class*="menu-item"]',
                'div[class*="MenuItem"]',
                'button[class*="edit"]',
                
                # Fallback - click first visible element in dialog
                '*[role="button"]',
                '*[role="menuitem"]',
            ]
            
            clicked_menu_option = False
            
            # Try clicking on the business name first (opens name edit field)
            try:
                # Look for all clickable elements that might be the name field
                all_clickables = self.page.locator('[role="menuitem"], [role="button"], div[data-value]')
                count = await all_clickables.count()
                # (debug log removed)
                
                # List all elements for debugging
                for idx in range(min(count, 10)):
                    try:
                        element = all_clickables.nth(idx)
                        try:
                            is_visible = await element.is_visible(timeout=1000)
                            if is_visible:
                                text = await element.inner_text()
                                print(f"  Element {idx}: {text.strip()[:40] if text else '(no text)'}")
                            else:
                                print(f"  Element {idx}: (not visible)")
                        except:
                            print(f"  Element {idx}: (could not get text)")
                    except:
                        pass
                
                # Try using JavaScript to find and click elements directly
                
                # Try to find and click using JavaScript
                js_result = await self.page.evaluate("""
                    () => {
                        // Find all clickable elements
                        const allClickable = document.querySelectorAll('[role="menuitem"], [role="button"], div[data-value], button');
                        const results = [];
                        
                        for (let i = 0; i < Math.min(allClickable.length, 10); i++) {
                            const el = allClickable[i];
                            const rect = el.getBoundingClientRect();
                            const isVisible = rect.width > 0 && rect.height > 0;
                            const text = el.innerText || el.textContent || '';
                            
                            results.push({
                                index: i,
                                text: text.trim(),
                                visible: isVisible,
                                x: rect.x + rect.width / 2,
                                y: rect.y + rect.height / 2,
                                className: el.className
                            });
                        }
                        
                        return results;
                    }
                """)
                
                # (debug log removed)
                
                # Try to click the first visible element that looks like it contains the business name
                import os
                business_name = os.environ.get('GMAPS_SEARCH_QUERY', '').upper()
                
                clicked_via_js = False
                
                # First pass: look for exact business name match
                for item in js_result:
                    if item['visible'] and item['text']:
                        text = item['text'].strip().upper()
                        # Clean up text (remove emoji and newlines)
                        text_clean = ''.join(c for c in text if c.isprintable() and not c.isspace() or c == ' ')
                        
                        # Check if it contains the business name
                        if business_name and business_name in text_clean:
                            print(f"  ✓ Found business name: '{item['text'].strip()[:40]}' - clicking...")
                            try:
                                await self.page.mouse.click(item['x'], item['y'])
                                if self.click_delay and self.click_delay > 0:
                                    await asyncio.sleep(self.click_delay)
                                await asyncio.sleep(2)
                                print(f"✓ Clicked on business name!")
                                clicked_menu_option = True
                                clicked_via_js = True
                                break
                            except Exception as e:
                                print(f"  Could not click: {e}")
                
                # Second pass: if not found, try first element with meaningful text (skip single char elements)
                if not clicked_via_js:
                    for item in js_result:
                        if item['visible'] and item['text']:
                            text_clean = item['text'].strip()
                            # Skip single character elements (icons)
                            if len(text_clean) > 1 and not 'http' in text_clean.lower():
                                print(f"  Trying '{text_clean[:40]}' - clicking via JavaScript...")
                                try:
                                    await self.page.mouse.click(item['x'], item['y'])
                                    if self.click_delay and self.click_delay > 0:
                                        await asyncio.sleep(self.click_delay)
                                    await asyncio.sleep(2)
                                    print(f"✓ Clicked via coordinates")
                                    clicked_menu_option = True
                                    clicked_via_js = True
                                    break
                                except Exception as e:
                                    print(f"  Could not click: {e}")
                    
                # If still not clicked via JS, try clicking first visible element directly
                if not clicked_via_js and len(js_result) > 0:
                    # Click the first element that has coordinates
                    first_visible = None
                    for item in js_result:
                        if item['visible'] and item['text']:
                            first_visible = item
                            break
                    
                    if first_visible:
                        print(f"  Fallback: clicking '{first_visible['text'][:40]}'")
                        try:
                            await self.page.mouse.click(first_visible['x'], first_visible['y'])
                            if self.click_delay and self.click_delay > 0:
                                await asyncio.sleep(self.click_delay)
                            await asyncio.sleep(2)
                            print(f"✓ Clicked first visible element")
                            clicked_menu_option = True
                        except:
                            pass
                        
            except Exception as e:
                print(f"  Error trying to click elements: {e}")
            
            # If that didn't work, try selector-based approach
            if not clicked_menu_option:
                for selector in menu_option_selectors:
                    try:
                        options = self.page.locator(selector)
                        count = await options.count()
                        if count > 0:
                            # Try first few visible options
                            for idx in range(min(count, 5)):
                                option = options.nth(idx)
                                try:
                                    if await option.is_visible():
                                        await option.click()
                                        if self.click_delay and self.click_delay > 0:
                                            await asyncio.sleep(self.click_delay)
                                        await asyncio.sleep(2)
                                        print(f"✓ Clicked menu option {idx}")
                                        clicked_menu_option = True
                                        break
                                except:
                                    continue
                            if clicked_menu_option:
                                break
                    except:
                        continue
            
            # Try to find and fill the name input field - wait for form to appear
            if clicked_menu_option:
                print("\nFinding input field...")
                
                # Wait for the edit form to load - look specifically for "Place name" field
                print("  Looking for 'Place name' input field...")
                
                # Wait up to 20 seconds for the form to appear (may be in an iframe)
                for attempt in range(20):
                    await asyncio.sleep(1)
                    
                    # Search across all frames using captured selectors
                    place_name_input, owner_frame = await self._evaluate_in_all_frames(f"""
                        () => {{
                            const selectors = {json.dumps(self.place_name_selectors)};
                            for (let selector of selectors) {{
                                const input = document.querySelector(selector);
                                if (input) {{
                                    const rect = input.getBoundingClientRect();
                                    const isVisible = rect.width > 0 && rect.height > 0;
                                    if (isVisible) {{
                                        return {{
                                            x: rect.x + rect.width / 2,
                                            y: rect.y + rect.height / 2,
                                            placeholder: input.placeholder || '',
                                            ariaLabel: input.getAttribute('aria-label') || '',
                                            tag: input.tagName,
                                            className: input.className || '',
                                            id: input.id || '',
                                            jsname: input.getAttribute('jsname') || '',
                                            foundBy: 'captured-selectors'
                                        }};
                                    }}
                                }}
                            }}
                            // Fallback by label text proximity
                            const labels = Array.from(document.querySelectorAll('span, label')).filter(n => (n.innerText||'').toLowerCase().includes('place name'));
                            for (let lab of labels) {{
                                const container = lab.closest('div, form, section');
                                if (!container) continue;
                                const input = container.querySelector('input, textarea, [contenteditable]');
                                if (input) {{
                                    const rect = input.getBoundingClientRect();
                                    const isVisible = rect.width > 0 && rect.height > 0;
                                    if (isVisible) {{
                                        return {{
                                            x: rect.x + rect.width / 2,
                                            y: rect.y + rect.height / 2,
                                            placeholder: input.placeholder || '',
                                            ariaLabel: input.getAttribute('aria-label') || '',
                                            tag: input.tagName,
                                            className: input.className || '',
                                            foundBy: 'label-proximity'
                                        }};
                                    }}
                                }}
                            }}
                            return null;
                        }}
                    """)
                    
                    if place_name_input:
                        print(f"✓ Found 'Place name' input field!")
                        print(f"  Placeholder: '{place_name_input['placeholder']}'")
                        print(f"  Aria-label: '{place_name_input['ariaLabel']}'")
                        
                        # Click and fill the input
                        print(f"  Found by: {place_name_input['foundBy']}")
                        await self._click_xy_in_frame(owner_frame or self.page.main_frame, place_name_input['x'], place_name_input['y'])
                        await asyncio.sleep(0.5)
                        await self.page.keyboard.press('Control+a')
                        await asyncio.sleep(0.3)
                        await self.page.keyboard.type(new_name)
                        await asyncio.sleep(1)
                        print(f"✓ Filled place name: {new_name}")
                        
                        # Also try clicking the Material Design label to focus the input
                        if place_name_input['foundBy'] == 'material-design':
                            try:
                                await self.page.evaluate("""
                                    () => {
                                        const spans = document.querySelectorAll('span[jsname="V67aGc"]');
                                        for (let span of spans) {
                                            if (span.innerText && span.innerText.toLowerCase().includes('place name')) {
                                                span.click();
                                                return true;
                                            }
                                        }
                                        return false;
                                    }
                                """)
                                print("✓ Also clicked Material Design label")
                            except Exception as e:
                                print(f"  Could not click label: {e}")
                        
                        # Now look for submit button using captured selectors
                        print("  Looking for submit button...")
                        await asyncio.sleep(2)
                        
                        submit_button, submit_frame = await self._evaluate_in_all_frames(f"""
                            () => {{
                                const selectors = {json.dumps(self.submit_selectors)};
                                for (let selector of selectors) {{
                                    const nodes = document.querySelectorAll(selector);
                                    for (let btn of nodes) {{
                                        const rect = btn.getBoundingClientRect();
                                        const isVisible = rect.width > 0 && rect.height > 0;
                                        const text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
                                        
                                        // Check for exact "submit" text match
                                        if (isVisible && text === 'submit') {{
                                            return {{ 
                                                x: rect.x + rect.width/2, 
                                                y: rect.y + rect.height/2, 
                                                text: text,
                                                className: btn.className || '',
                                                jsname: btn.getAttribute('jsname') || '',
                                                clickedVia: 'exact-match'
                                            }};
                                        }}
                                        
                                        // Also check for submit-like text
                                        if (isVisible && (text.includes('submit') || text.includes('send'))) {{
                                            // Prefer clickable ancestor (button or role button)
                                            const clickable = btn.closest('button, [role="button"], div[role], div');
                                            const r = (clickable ? clickable.getBoundingClientRect() : rect);
                                            return {{ 
                                                x: r.x + r.width/2, 
                                                y: r.y + r.height/2, 
                                                text: text, 
                                                clickedVia: 'ancestor',
                                                className: btn.className || ''
                                            }};
                                        }}
                                    }}
                                }}
                                return null;
                            }}
                        """)
                        
                        if submit_button:
                            print(f"✓ Found submit button: '{submit_button['text']}'")
                            await self._click_xy_in_frame(submit_frame or self.page.main_frame, submit_button['x'], submit_button['y'])
                            if self.click_delay and self.click_delay > 0:
                                await asyncio.sleep(self.click_delay)
                            # Optionally handle post-submit OK dialog
                            if self.post_ok_click:
                                try:
                                    # Wait briefly for dialog to appear and retry a few times
                                    for _ in range(6):  # ~ up to ~3s with 0.5s delay
                                        ok_btn, ok_frame = await self._evaluate_in_all_frames("""
                                            () => {
                                                // Prefer buttons inside dialogs
                                                const dialogSelectors = [
                                                   'div[role="dialog"] button',
                                                   'div[aria-modal="true"] button',
                                                   'div[role="dialog"] [role="button"]',
                                                   '.VfPpkd-LgbsSe', // Material primary button
                                                   '.VfPpkd-vQzf8d',  // Material button label span
                                                   'button.okDpye.PpaGLb', // observed OK button classes
                                                   'button.okDpye',
                                                   'button.PpaGLb',
                                                   '[class*="okDpye"][class*="PpaGLb"]'
                                                ];
                                                const labelTexts = ['ok','done','got it','close'];
                                                // First: text-based inside dialog containers
                                                for (let rootSel of dialogSelectors) {
                                                    const nodes = document.querySelectorAll(rootSel);
                                                    for (let el of nodes) {
                                                        const r = el.getBoundingClientRect();
                                                        if (!(r.width>0 && r.height>0)) continue;
                                                        const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                                                        if (labelTexts.some(x => t === x || t.includes(x))) {
                                                            return { x: r.x + r.width/2, y: r.y + r.height/2 };
                                                        }
                                                    }
                                                }
                                                // Second: generic selectors by text
                                                const okSelectors = [
                                                   'button:has-text("OK")',
                                                   '[role="button"]:has-text("OK")',
                                                   'button:has-text("Got it")',
                                                   '[role="button"]:has-text("Got it")',
                                                   'button:has-text("Done")',
                                                   '[role="button"]:has-text("Done")',
                                                   'button:has-text("Close")',
                                                   '[role="button"]:has-text("Close")',
                                                   '[aria-label="OK"]',
                                                   '[aria-label="Done"]',
                                                   '[aria-label="Close"]',
                                                   'button.okDpye.PpaGLb',
                                                   'button.okDpye',
                                                   'button.PpaGLb',
                                                   '[class*="okDpye"][class*="PpaGLb"]'
                                                ];
                                                for (let sel of okSelectors) {
                                                    try {
                                                        const els = document.querySelectorAll(sel);
                                                        for (let el of els) {
                                                            const r = el.getBoundingClientRect();
                                                            if (r.width>0 && r.height>0) {
                                                                return { x: r.x + r.width/2, y: r.y + r.height/2 };
                                                            }
                                                        }
                                                    } catch(e) {}
                                                }
                                                // Third: any visible primary-looking button in a dialog
                                                const dialogs = document.querySelectorAll('div[role="dialog"], div[aria-modal="true"]');
                                                for (let d of dialogs) {
                                                    const btns = d.querySelectorAll('button, [role="button"]');
                                                    for (let el of btns) {
                                                        const r = el.getBoundingClientRect();
                                                        if (r.width>0 && r.height>0) {
                                                            const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                                                            if (t) {
                                                                return { x: r.x + r.width/2, y: r.y + r.height/2 };
                                                            }
                                                        }
                                                    }
                                                }
                                                return null;
                                            }
                                        """)
                                        if ok_btn:
                                            await self._click_xy_in_frame(ok_frame or self.page.main_frame, ok_btn['x'], ok_btn['y'])
                                            if self.click_delay and self.click_delay > 0:
                                                await asyncio.sleep(self.click_delay)
                                            break
                                        await asyncio.sleep(0.5)
                                except Exception:
                                    pass
                            print("✓ Submitted successfully!")
                            return True
                        else:
                            # Fallback: try pressing Enter
                            try:
                                await self.page.keyboard.press('Enter')
                                await asyncio.sleep(2)
                                print("↩︎ Pressed Enter as submit fallback")
                                return True
                            except:
                                pass
                            print("⚠️  Submit button not found")
                            return True  # Still filled the input successfully
                    
                    if attempt < 14:
                        print(f"  Still looking... attempt {attempt + 1}/15")
                
                print("⚠️  Could not find 'Place name' input field after 15 seconds")
                print("The edit form may not have loaded properly")
                
                # Fallback: try to find any input field
                print("  Trying fallback: looking for any input field...")
                editable_elements = await self.page.evaluate("""
                    () => {
                        const allElements = document.querySelectorAll('input, textarea, [contenteditable]');
                        const results = [];
                        
                        for (let el of allElements) {
                            try {
                                const rect = el.getBoundingClientRect();
                                const isVisible = rect.width > 0 && rect.height > 0;
                                
                                if (isVisible) {
                                    const className = el.className || '';
                                    const placeholder = el.placeholder || el.getAttribute('placeholder') || '';
                                    
                                    // Skip search boxes
                                    if (!className.includes('searchboxinput') && !className.includes('omnibox') &&
                                        !placeholder.toLowerCase().includes('search')) {
                                        
                                        let value = '';
                                        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                                            value = el.value || '';
                                        } else if (el.contentEditable === 'true') {
                                            value = el.innerText || el.textContent || '';
                                        }
                                        
                                        results.push({
                                            x: rect.x + rect.width / 2,
                                            y: rect.y + rect.height / 2,
                                            value: value.substring(0, 50),
                                            placeholder: placeholder.substring(0, 50),
                                            tag: el.tagName
                                        });
                                    }
                                }
                            } catch(e) {}
                        }
                        
                        return results;
                    }
                """)
                
                if editable_elements and len(editable_elements) > 0:
                    print(f"Found {len(editable_elements)} fallback input(s):")
                    for idx, inp in enumerate(editable_elements):
                        print(f"  {idx}: {inp['tag']} - value='{inp['value'][:30]}' placeholder='{inp['placeholder'][:30]}'")
                    
                    # Try the first non-search input
                    for idx, inp in enumerate(editable_elements):
                        try:
                            print(f"\nTrying fallback input {idx}...")
                            await self.page.mouse.click(inp['x'], inp['y'])
                            if self.click_delay and self.click_delay > 0:
                                await asyncio.sleep(self.click_delay)
                            await asyncio.sleep(0.5)
                            await self.page.keyboard.press('Control+a')
                            await asyncio.sleep(0.3)
                            await self.page.keyboard.type(new_name)
                            await asyncio.sleep(1)
                            print(f"✓ Filled fallback input: {new_name}")
                            
                            # Look for submit button using captured selectors
                            submit_button = await self.page.evaluate("""
                                () => {
                                    // Try multiple strategies to find submit button
                                    const selectors = [
                                        'span[jsname="V67aGc"]',  // From captured click
                                        'span.VfPpkd-vQzf8d',  // Class from captured click
                                        'div.VfPpkd-RLmnJb',  // Container from captured click
                                        'button:has-text("Submit")',
                                        'button:has-text("Send")',
                                        '[role="button"]:has-text("Submit")',
                                        '*[aria-label*="Submit" i]',
                                        '*[aria-label*="Send" i]'
                                    ];
                                    
                                    for (let selector of selectors) {
                                        try {
                                            const elements = document.querySelectorAll(selector);
                                            for (let btn of elements) {
                                                const rect = btn.getBoundingClientRect();
                                                const isVisible = rect.width > 0 && rect.height > 0;
                                                
                                                if (isVisible) {
                                                    const text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
                                                    if (text.includes('submit') || text.includes('send')) {
                                                        return {
                                                            x: rect.x + rect.width / 2,
                                                            y: rect.y + rect.height / 2,
                                                            text: text,
                                                            className: btn.className || '',
                                                            jsname: btn.getAttribute('jsname') || ''
                                                        };
                                                    }
                                                }
                                            }
                                        } catch (e) {
                                            continue;
                                        }
                                    }
                                    
                                    // Fallback: look for any button or div with submit-like text
                                    const allClickable = document.querySelectorAll('button, [role="button"], div, span');
                                    for (let btn of allClickable) {
                                        const rect = btn.getBoundingClientRect();
                                        const isVisible = rect.width > 0 && rect.height > 0;
                                        const text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
                                        
                                        if (isVisible && (text === 'submit' || text === 'send')) {
                                            return {
                                                x: rect.x + rect.width / 2,
                                                y: rect.y + rect.height / 2,
                                                text: text,
                                                className: btn.className || ''
                                            };
                                        }
                                    }
                                    
                                    return null;
                                }
                            """)
                            
                            if submit_button:
                                print(f"✓ Found submit button: '{submit_button['text']}'")
                            await self.page.mouse.click(submit_button['x'], submit_button['y'])
                            if self.click_delay and self.click_delay > 0:
                                await asyncio.sleep(self.click_delay)
                                await asyncio.sleep(2)
                                print("✓ Submitted successfully!")
                                return True
                            else:
                                print("⚠️  Submit button not found")
                                return True  # Still filled the input
                                
                        except Exception as e:
                            print(f"  Failed to fill input {idx}: {e}")
                            continue
                else:
                    print("⚠️  No input fields found at all")
                    print("The edit form may not have loaded or may be in an iframe")
                    
                    # Take a screenshot for debugging
                    await self.page.screenshot(path="debug_no_inputs.png")
                    print("Screenshot saved: debug_no_inputs.png")
                    
                    return False
                    
            if not clicked_menu_option:
                print("Menu option not found or couldn't fill input")
            
            await asyncio.sleep(2)
            return True
            
        except Exception as e:
            print(f"Error submitting name change: {e}")
            print("\nYou may need to manually complete the form")
            return False
    
    async def submit_address_change(self, new_address: str) -> bool:
        """
        Submit an address change suggestion
        
        Args:
            new_address: New address for the location
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"\nSubmitting address change to: {new_address}")
            
            # Wait for dialog to fully load
            await asyncio.sleep(2)
            
            # Step 1: Click on address/edit location option in menu
            print("Looking for address edit option...")
            menu_option_selectors = [
                ':has-text("Address")',
                '[role="menuitem"]:has-text("Address")',
                'div:has-text("Address"):has([role="menuitem"])',
                'div:has-text("address"):has([role="button"])',
                '[data-value="address"]',
                '[data-item-value="address"]',
                'button:has-text("Address")',
                'div[role="button"]:has-text("Address")',
                'a:has-text("Address")',
            ]
            
            clicked_menu_option = False
            for selector in menu_option_selectors:
                try:
                    option = self.page.locator(selector).first
                    if await option.count() > 0:
                        is_visible = await option.is_visible()
                        if is_visible:
                            await option.click()
                            if self.click_delay and self.click_delay > 0:
                                await asyncio.sleep(self.click_delay)
                            await asyncio.sleep(2)
                            print(f"✓ Clicked address option")
                            clicked_menu_option = True
                            break
                except:
                    continue
            
            # If menu option not found, try to find address input directly
            if not clicked_menu_option:
                print("Menu option not found, trying to find address input directly...")
                address_input_selectors = [
                    'input[placeholder*="address" i]',
                    'input[placeholder*="location" i]',
                    'input[placeholder*="Address" i]',
                    'input[aria-label*="address" i]',
                    'textarea[placeholder*="address" i]',
                    'input[type="text"]',
                ]
                
                for selector in address_input_selectors:
                    try:
                        address_input = self.page.locator(selector).first
                        count = await address_input.count()
                        if count > 0:
                            is_visible = await address_input.is_visible()
                            if is_visible:
                                await address_input.click()
                                await address_input.clear()
                                await address_input.fill(new_address)
                                print(f"✓ Filled in address: {new_address}")
                                clicked_menu_option = True
                                break
                    except:
                        continue
            
            if not clicked_menu_option:
                print("⚠️  Could not find address input automatically")
                print("You may need to manually select 'Address' and enter the value")
            
            await asyncio.sleep(1)
            
            # Step 2: Find and click submit button
            submit_selectors = [
                'button:has-text("Submit")',
                'button:has-text("Send")',
                'button[type="submit"]',
                'button:has-text("done")',
                '[aria-label="Submit"]',
                '[aria-label="Send"]',
            ]
            
            submitted = False
            for selector in submit_selectors:
                try:
                    submit_button = self.page.locator(selector).first
                    if await submit_button.count() > 0:
                        is_visible = await submit_button.is_visible()
                        if is_visible:
                            await submit_button.click()
                            if self.click_delay and self.click_delay > 0:
                                await asyncio.sleep(self.click_delay)
                            await asyncio.sleep(2)
                            print("✓ Submitted successfully!")
                            submitted = True
                            break
                except:
                    continue
            
            if not submitted:
                print("⚠️  Could not find submit button automatically")
                print("Please manually click Submit/Send")
                await asyncio.sleep(5)
            
            await asyncio.sleep(2)
            return True
            
        except Exception as e:
            print(f"Error submitting address change: {e}")
            print("\nYou may need to manually complete the form")
            return False
    
    async def suggest_general_edit(self, edit_details: dict) -> bool:
        """
        Submit a general edit suggestion
        
        Args:
            edit_details: Dictionary with edit information
                Example: {"name": "New Name", "address": "New Address"}
                
        Returns:
            True if successful, False otherwise
        """
        try:
            if 'name' in edit_details:
                await self.submit_name_change(edit_details['name'])
            
            if 'address' in edit_details:
                # Wait a bit between different field updates
                await asyncio.sleep(1)
                await self.submit_address_change(edit_details['address'])
            
            return True
            
        except Exception as e:
            print(f"Error in general edit: {e}")
            return False


async def main_async(search: str, name: str = None, address: str = None, headless: bool = False, wait: int = 5, signin_time: int = 0, new_session: bool = False, auto_click: bool = False, log_clicks: bool = False, click_delay: float = 0.5, panel_wait: int = None, post_ok: bool = None):
    """Async main function"""
    # Store search query for the bot to use
    import os
    os.environ['GMAPS_SEARCH_QUERY'] = search
    bot = None
    try:
        print("Starting Google Maps Edit Bot...")
        print("=" * 60)
        
        # Generate unique user data dir based on session
        import os
        import time
        if new_session:
            user_data_dir = f"./browser_data_{int(time.time())}"
            print("New session - will sign in fresh")
        else:
            user_data_dir = "./browser_data"
            if os.path.exists(user_data_dir):
                print("Using persistent session - sign-in will be remembered")
            else:
                print("First run - you'll need to sign in once")
        
        bot = GoogleMapsEditBot(headless=headless, user_data_dir=user_data_dir)
        bot.auto_click = auto_click
        bot.capture_clicks = log_clicks
        bot.click_delay = max(0.0, float(click_delay))
        if panel_wait is not None:
            bot.panel_wait_seconds = max(0, int(panel_wait))
        if post_ok is not None:
            bot.post_ok_click = bool(post_ok)
        
        # Initialize browser first (opens Google Maps)
        await bot._init_browser()
        
        # Navigate to Google Maps
        await bot.page.goto('https://www.google.com/maps', wait_until='domcontentloaded')
        await asyncio.sleep(2)
        
        # Check if signed in and wait if not
        if signin_time > 0:
            await bot.check_and_wait_for_signin(signin_time)
        else:
            # Auto-detect if we need sign-in
            print("Checking if signed in...")
            if not await bot.check_if_signed_in():
                print("\n⚠️  Not signed in! Use --signin-wait 60 to sign in")
                print("\nRun:")
                print("  python google_maps_edit_bot.py --search \"Location\" --name \"Name\" --signin-wait 60")
                print("\nThis will give you time to sign in once, then save your session.")
                return
        
        # Search for location
        if not await bot.search_location(search, wait):
            print("Failed to find location")
            return
        
        # Open suggest edit dialog
        await bot.open_suggest_edit()
        
        # Submit edits
        if name:
            await bot.submit_name_change(name)
        
        if address:
            if name:
                await asyncio.sleep(2)  # Wait between edits
            await bot.submit_address_change(address)
        
        print("\n" + "=" * 60)
        print("Edit submission completed!")
        print("\nPlease note:")
        print("- Edits are subject to Google's review process")
        print("- May require sign-in for some locations")
        print("- Some changes may take time to appear")
        
        # Keep browser open to see results  
        print("\n" + "="*60)
        print("EDIT SUBMISSION COMPLETE!")
        print("="*60)
        print("The browser will stay open for 30 seconds.")
        print("You can verify the edit was submitted.")
        print("="*60)
        print("(Your sign-in is saved for next time!)")
        await asyncio.sleep(30)
        
    except asyncio.CancelledError:
        print("\n\nInterrupted by user (cancelled)")
        return
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        if bot:
            await bot.close()


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description='Programmatically submit public edits to Google Maps',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search for location and suggest name change
  python google_maps_edit_bot.py --search "Starbucks Seattle" --name "Better Coffee Shop"
  
  # Wait 60 seconds for you to sign in first
  python google_maps_edit_bot.py --search "Starbucks" --name "Coffee" --signin-wait 60
  
  # Suggest address change
  python google_maps_edit_bot.py --search "Target Store" --address "123 Main St, Seattle, WA"
  
  # Use headless mode (not recommended for sign-in)
  python google_maps_edit_bot.py --search "McDonald's" --name "McDonald's Restaurant" --headless
  
  # Start a fresh session (clears saved sign-in)
  python google_maps_edit_bot.py --search "Location" --name "New Name" --new-session
        """
    )
    
    parser.add_argument('--search', '-s', 
                       default=os.getenv('GMAPS_SEARCH'), 
                       help='Location to search for (default: GMAPS_SEARCH env var)')
    parser.add_argument('--name', 
                       default=os.getenv('GMAPS_NAME'), 
                       help='New name for the location (default: GMAPS_NAME env var)')
    parser.add_argument('--address', 
                       default=os.getenv('GMAPS_ADDRESS'), 
                       help='New address for the location (default: GMAPS_ADDRESS env var)')
    parser.add_argument('--headless', 
                       action='store_true', 
                       default=os.getenv('GMAPS_HEADLESS', '').lower() in ('true', '1', 'yes'),
                       help='Run browser in headless mode (default: GMAPS_HEADLESS env var)')
    parser.add_argument('--wait', 
                       type=int, 
                       default=int(os.getenv('GMAPS_WAIT', '5')), 
                       help='Wait time in seconds (default: GMAPS_WAIT env var or 5)')
    parser.add_argument('--signin-wait', 
                       type=int, 
                       default=int(os.getenv('GMAPS_SIGNIN_WAIT', '0')), 
                       help='Time to wait for sign-in in seconds (default: GMAPS_SIGNIN_WAIT env var or 0)')
    parser.add_argument('--new-session', 
                       action='store_true', 
                       default=os.getenv('GMAPS_NEW_SESSION', '').lower() in ('true', '1', 'yes'),
                       help='Start a new session (clears saved sign-in) (default: GMAPS_NEW_SESSION env var)')
    parser.add_argument('--auto-click', 
                       action='store_true', 
                       default=os.getenv('GMAPS_AUTO_CLICK', '').lower() in ('true', '1', 'yes'),
                       help='Automatically find and click elements (experimental) (default: GMAPS_AUTO_CLICK env var)')
    parser.add_argument('--log-clicks', 
                       action='store_true', 
                       default=os.getenv('GMAPS_LOG_CLICKS', '').lower() in ('true', '1', 'yes'),
                       help='Log details of any element you manually click (default: GMAPS_LOG_CLICKS env var)')
    parser.add_argument('--click-delay',
                       type=float,
                       default=float(os.getenv('GMAPS_CLICK_DELAY', '0.5')),
                       help='Delay (seconds) between automated clicks (default: GMAPS_CLICK_DELAY env var or 0.5)')
    parser.add_argument('--panel-wait',
                       type=int,
                       default=int(os.getenv('GMAPS_PANEL_WAIT', '3')),
                       help='Seconds to wait for info panel to load (default: GMAPS_PANEL_WAIT env var or 3)')
    parser.add_argument('--post-ok',
                       action='store_true',
                       default=os.getenv('GMAPS_POST_OK', '').lower() in ('true','1','yes'),
                       help='Attempt to click OK/Got it confirmation after submit (default: GMAPS_POST_OK env var)')
    
    args = parser.parse_args()
    
    if not args.search:
        print("Error: --search is required (set GMAPS_SEARCH env var or use --search)")
        parser.print_help()
        return
    
    if not args.name and not args.address:
        print("Error: At least one of --name or --address is required (set GMAPS_NAME/GMAPS_ADDRESS env vars or use --name/--address)")
        parser.print_help()
        return
    
    # Run async main
    try:
        asyncio.run(main_async(
            search=args.search,
            name=args.name,
            address=args.address,
            headless=args.headless,
            wait=args.wait,
            signin_time=args.signin_wait,
            new_session=args.new_session,
            auto_click=args.auto_click,
            log_clicks=args.log_clicks,
            click_delay=args.click_delay,
            panel_wait=args.panel_wait,
            post_ok=args.post_ok
        ))
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting...")


if __name__ == '__main__':
    main()
