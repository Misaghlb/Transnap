import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog, ttk
import json
import os
import webbrowser
import threading
from snipper import Snipper
from gemini_client import GeminiTranslator
import pyperclip
import keyring
import sys
import ctypes
from ctypes import windll, byref, create_string_buffer, create_unicode_buffer
import keyboard

# load_dotenv() # Removed as per requirement

class ScreenTranslatorApp:
    THEMES = {
        "dark": {
            "bg": "#202020",
            "fg": "white",
            "accent": "#0078D4",
            "text_bg": "#2d2d2d",
            "text_fg": "white",
            "secondary_text": "#aaaaaa",
            "btn_bg": "#3a3a3a",
            "btn_fg": "white",
            "btn_active": "#4a4a4a"
        },
        "light": {
            "bg": "#f3f3f3",
            "fg": "black",
            "accent": "#0078D4",
            "text_bg": "white",
            "text_fg": "black",
            "secondary_text": "#555555",
            "btn_bg": "#e0e0e0",
            "btn_fg": "black",
            "btn_active": "#d0d0d0"
        }
    }
    
    LANGUAGES = [
        "English", "Farsi", "German", "French", "Spanish", "Italian", "Portuguese", 
        "Russian", "Chinese (Simplified)", "Japanese", "Korean", "Arabic", "Hindi", 
        "Bengali", "Urdu", "Turkish", "Dutch", "Swedish", "Danish", "Norwegian", 
        "Finnish", "Polish", "Czech", "Slovak", "Hungarian", "Romanian", "Bulgarian", 
        "Croatian", "Serbian", "Slovenian", "Estonian", "Latvian", "Lithuanian", 
        "Greek", "Hebrew", "Indonesian", "Malay", "Tagalog", "Vietnamese", "Thai", 
        "Malayalam", "Tamil", "Telugu", "Kannada", "Marathi", "Nepali", "Punjabi", 
        "Sinhala", "Swahili", "Afrikaans", "Kazakh", "Uzbek", "Ukrainian", "Albanian", 
        "Pashto", "Odia", "Azerbaijani", "Belarusian", "Catalan", "Filipino"
    ]

    RTL_LANGUAGES = ["Farsi", "Arabic", "Hebrew", "Urdu", "Pashto", "Sindhi", "Kurdish"]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Transnap")
        self.root.geometry("500x450") 
        self.root.resizable(True, True)
        self.root.minsize(450, 400)
        
        # Set Icon
        try:
            icon_path = self.resource_path("assets/icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception as e:
            print(f"Failed to set icon: {e}")
        
        self.current_theme = "dark"
        self.colors = self.THEMES[self.current_theme]
        
        self.root.configure(bg=self.colors["bg"])
        
        # Load Vazir Font
        self.font_family = "Arial" # Fallback
        self.load_custom_font("fonts/Vazirmatn-Regular.ttf", "Vazirmatn")

        # Config path
        self.config_path = os.path.join(os.path.expanduser("~"), ".transnap_config.json")
        self.preferences = self.load_preferences()
        self.target_lang = self.preferences.get("language", "Farsi")
        self.shortcut = self.preferences.get("shortcut", "windows+shift+a")

        # Check for API Key
        self.api_key = self.load_config()
        # if not self.api_key:
        #     self.prompt_api_key() # Removed blocking prompt
            
        # Register Hotkey
        try:
            keyboard.add_hotkey(self.shortcut, lambda: self.root.after(0, self.start_snip))
        except Exception as e:
            print(f"Failed to register hotkey: {e}")
        
        self.create_widgets()

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except:
            return False

    def restart_as_admin(self):
        try:
            if sys.argv[0].endswith('.exe'):
                # If running as exe
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.argv[0], None, None, 1)
            else:
                # If running as python script
                # Try to use pythonw.exe to avoid console window
                executable = sys.executable
                if executable.endswith("python.exe"):
                    pythonw = executable.replace("python.exe", "pythonw.exe")
                    if os.path.exists(pythonw):
                        executable = pythonw
                
                # Quote arguments to handle spaces in paths
                args = f'"{sys.argv[0]}"'
                if len(sys.argv) > 1:
                    args += " " + " ".join([f'"{arg}"' for arg in sys.argv[1:]])

                ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, args, None, 1)
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restart as admin: {e}")

    def load_custom_font(self, font_path, font_name):
        # Resolve path for PyInstaller
        font_path = self.resource_path(font_path)
        
        if not os.path.exists(font_path):
            print(f"Font not found at {font_path}, using default.")
            return

        try:
            # Load font using GDI
            FR_PRIVATE = 0x10
            FR_NOT_ENUM = 0x20
            path_buf = create_unicode_buffer(os.path.abspath(font_path))
            add_font_resource_ex = windll.gdi32.AddFontResourceExW
            flags = FR_PRIVATE | FR_NOT_ENUM
            num_fonts_added = add_font_resource_ex(byref(path_buf), flags, 0)
            
            if num_fonts_added > 0:
                self.font_family = font_name
                print(f"Successfully loaded font: {font_name}")
            else:
                print("Failed to load font resource.")
        except Exception as e:
            print(f"Error loading font: {e}")

    def load_config(self):
        try:
            return keyring.get_password("Transnap", "api_key")
        except Exception as e:
            print(f"Error loading config: {e}")
        return None

    def save_config(self, api_key):
        try:
            if api_key:
                keyring.set_password("Transnap", "api_key", api_key)
            else:
                try:
                    keyring.delete_password("Transnap", "api_key")
                except keyring.errors.PasswordDeleteError:
                    pass # Password not found, ignore
        except Exception as e:
            print(f"Error saving config: {e}")

    def load_preferences(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading preferences: {e}")
        return {}

    def save_preferences(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.preferences, f)
        except Exception as e:
            print(f"Error saving preferences: {e}")

    def on_language_change(self, event=None):
        self.target_lang = self.lang_combo.get()
        self.preferences["language"] = self.target_lang
        self.save_preferences()

    def save_api_key_ui(self):
        key = self.api_entry.get().strip()
        if key:
            self.api_key = key
            self.save_config(key)
            messagebox.showinfo("Success", "API Key saved successfully!")
        else:
            messagebox.showwarning("Warning", "Please enter an API Key.")

    def save_shortcut_ui(self):
        new_shortcut = self.shortcut_entry.get().strip()
        if new_shortcut:
            try:
                # Remove old hotkey
                try:
                    keyboard.remove_hotkey(self.shortcut)
                except Exception:
                    pass # Might not be registered if it failed initially

                # Try to register new hotkey
                keyboard.add_hotkey(new_shortcut, lambda: self.root.after(0, self.start_snip))
                
                # If successful, update state and save
                self.shortcut = new_shortcut
                self.preferences["shortcut"] = self.shortcut
                self.save_preferences()
                messagebox.showinfo("Success", "Shortcut updated successfully!")
            except Exception as e:
                # Revert to old hotkey if new one fails
                try:
                    keyboard.add_hotkey(self.shortcut, lambda: self.root.after(0, self.start_snip))
                except Exception:
                    pass
                messagebox.showerror("Error", f"Invalid shortcut: {e}")
        else:
            messagebox.showwarning("Warning", "Please enter a shortcut.")

    def delete_api_key_ui(self):
        self.api_key = None
        self.api_entry.delete(0, tk.END)
        self.save_config(None) # Save as null/None
        messagebox.showinfo("Deleted", "API Key removed.")

    def show_help(self):
        help_text = (
            "How to use:\n"
            "1. Enter your Google Gemini API Key and click Save.\n"
            "2. Click '+ New' or use the hotkey to start snipping.\n"
            "3. Select an area on the screen to translate.\n\n"
            "Hotkeys:\n"
            f"• {self.shortcut}: Start Snipping\n"
            "• Esc: Cancel Snipping"
        )
        messagebox.showinfo("Help", help_text)

    def prompt_api_key(self):
        # Deprecated blocking prompt, keeping method for compatibility if needed, 
        # but logic moved to UI
        pass

    def open_get_key_url(self):
        webbrowser.open("https://aistudio.google.com/app/apikey")

    def create_widgets(self):
        # Clear existing widgets if any (for theme switch)
        for widget in self.root.winfo_children():
            widget.destroy()

        self.root.configure(bg=self.colors["bg"])

        # Main container
        main_frame = tk.Frame(self.root, bg=self.colors["bg"])
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Header / Title
        header_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        header_frame.pack(fill="x", pady=(0, 20))

        title_label = tk.Label(header_frame, text="Transnap", 
                               font=(self.font_family, 16, "bold"), 
                               bg=self.colors["bg"], fg=self.colors["fg"])
        title_label.pack(side="left")

        # Help Button
        help_btn = tk.Button(header_frame, text="?", command=self.show_help,
                             font=(self.font_family, 12, "bold"),
                             bg=self.colors["btn_bg"], fg=self.colors["btn_fg"],
                             activebackground=self.colors["btn_active"], activeforeground=self.colors["btn_fg"],
                             relief="flat", width=3, cursor="hand2")
        help_btn.pack(side="right")

        # API Key Section
        api_frame = tk.LabelFrame(main_frame, text="API Key", font=(self.font_family, 10),
                                  bg=self.colors["bg"], fg=self.colors["secondary_text"],
                                  bd=1, relief="solid")
        api_frame.pack(fill="x", pady=(0, 20), ipady=5)

        self.api_entry = tk.Entry(api_frame, show="*", font=("Arial", 10), 
                                  bg=self.colors["text_bg"], fg=self.colors["text_fg"],
                                  relief="flat", bd=5)
        self.api_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=5)
        
        if self.api_key:
            self.api_entry.insert(0, self.api_key)

        save_btn = tk.Button(api_frame, text="Save", command=self.save_api_key_ui,
                             font=(self.font_family, 9),
                             bg=self.colors["accent"], fg="white",
                             activebackground="#006CC1", activeforeground="white",
                             relief="flat", padx=10, cursor="hand2")
        save_btn.pack(side="left", padx=5)

        del_btn = tk.Button(api_frame, text="✖", command=self.delete_api_key_ui,
                            font=(self.font_family, 9),
                            bg="#d32f2f", fg="white",
                            activebackground="#b71c1c", activeforeground="white",
                            relief="flat", padx=5, cursor="hand2")
        del_btn.pack(side="left", padx=(0, 5))

        get_key_btn = tk.Button(api_frame, text="Get Key", command=self.open_get_key_url,
                             font=(self.font_family, 9),
                             bg=self.colors["btn_bg"], fg=self.colors["btn_fg"],
                             activebackground=self.colors["btn_active"], activeforeground=self.colors["btn_fg"],
                             relief="flat", padx=10, cursor="hand2")
        get_key_btn.pack(side="left", padx=(0, 5))

        # Shortcut Section
        shortcut_frame = tk.LabelFrame(main_frame, text="Shortcut", font=(self.font_family, 10),
                                  bg=self.colors["bg"], fg=self.colors["secondary_text"],
                                  bd=1, relief="solid")
        shortcut_frame.pack(fill="x", pady=(0, 20), ipady=5)

        self.shortcut_entry = tk.Entry(shortcut_frame, font=("Arial", 10), 
                                  bg=self.colors["text_bg"], fg=self.colors["text_fg"],
                                  relief="flat", bd=5)
        self.shortcut_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=5)
        self.shortcut_entry.insert(0, self.shortcut)

        shortcut_save_btn = tk.Button(shortcut_frame, text="Save", command=self.save_shortcut_ui,
                             font=(self.font_family, 9),
                             bg=self.colors["accent"], fg="white",
                             activebackground="#006CC1", activeforeground="white",
                             relief="flat", padx=10, cursor="hand2")
        shortcut_save_btn.pack(side="left", padx=5)

        # Language Selection
        lang_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        lang_frame.pack(fill="x", pady=(0, 20))
        
        lang_label = tk.Label(lang_frame, text="Target Language:", font=(self.font_family, 10),
                              bg=self.colors["bg"], fg=self.colors["fg"])
        lang_label.pack(side="left", padx=(0, 10))
        
        self.lang_combo = ttk.Combobox(lang_frame, values=self.LANGUAGES, state="readonly", font=(self.font_family, 9))
        self.lang_combo.set(self.target_lang)
        self.lang_combo.pack(side="left", fill="x", expand=True)
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_language_change)

        # Toolbar area
        toolbar = tk.Frame(main_frame, bg=self.colors["bg"])
        toolbar.pack(fill="x")

        # "New" Button
        self.new_btn = tk.Button(toolbar, text="+ New", command=self.start_snip, 
                                 font=(self.font_family, 12), 
                                 bg=self.colors["accent"], fg="white",
                                 activebackground="#006CC1", activeforeground="white",
                                 relief="flat", padx=20, pady=5, cursor="hand2")
        self.new_btn.pack(side="left")

        # Theme Toggle Button
        theme_btn = tk.Button(toolbar, text="Theme", command=self.toggle_theme,
                              font=(self.font_family, 10),
                              bg=self.colors["btn_bg"], fg=self.colors["btn_fg"],
                              activebackground=self.colors["btn_active"], activeforeground=self.colors["btn_fg"],
                              relief="flat", padx=10, pady=5, cursor="hand2")
        theme_btn.pack(side="right")

        # Admin / Game Mode Button (if not admin)
        if not self.is_admin():
            admin_btn = tk.Button(toolbar, text="⚠ Game Mode", command=self.restart_as_admin,
                                  font=(self.font_family, 10),
                                  bg="#FF9800", fg="white", # Orange warning color
                                  activebackground="#F57C00", activeforeground="white",
                                  relief="flat", padx=10, pady=5, cursor="hand2")
            admin_btn.pack(side="right", padx=(0, 10))
            
            # Add tooltip logic or simple hover if needed, but button text is clear enough for now.

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.colors = self.THEMES[self.current_theme]
        self.create_widgets()
        # Note: If result window is open, it won't update automatically with this simple implementation.
        # That's acceptable for now, or we could track it.

    def start_snip(self):
        self.previous_state = self.root.state()
        self.root.withdraw()
        snip_root = tk.Toplevel(self.root)
        Snipper(snip_root, self.on_snip_complete)

    def on_snip_complete(self, image):
        # self.root.deiconify() # Don't show main window yet
        if image:
            self.show_processing_window(image)
            threading.Thread(target=self.process_image, args=(image,)).start()
        else:
            self.root.deiconify() # Show if cancelled

    def show_processing_window(self, image):
        # Close existing window if open
        if hasattr(self, 'result_window') and self.result_window.winfo_exists():
            self.result_window.destroy()
            
        self.result_window = tk.Toplevel(self.root)
        self.result_window.title("Translation Result")
        
        # Make frameless and topmost
        self.result_window.overrideredirect(True)
        self.result_window.attributes("-topmost", True)
        
        self.result_window.geometry("550x500")
        # Add border
        self.result_window.configure(bg=self.colors["bg"], highlightthickness=1, highlightbackground=self.colors["secondary_text"])
        
        # Handle window closing to show main window
        # For frameless, we need our own close mechanism, but keep this for safety
        self.result_window.protocol("WM_DELETE_WINDOW", self.on_result_window_close)
        
        # Custom Title Bar
        title_bar = tk.Frame(self.result_window, bg=self.colors["bg"], relief="flat")
        title_bar.pack(fill="x", padx=2, pady=2)
        
        # Title
        lbl_title = tk.Label(title_bar, text="Translation Result", font=(self.font_family, 10, "bold"),
                             bg=self.colors["bg"], fg=self.colors["fg"])
        lbl_title.pack(side="left", padx=5)
        
        # Close Button
        close_btn = tk.Button(title_bar, text="✕", command=self.on_result_window_close,
                              font=("Arial", 10), bg=self.colors["bg"], fg=self.colors["fg"],
                              activebackground="#e81123", activeforeground="white",
                              bd=0, relief="flat", width=4, cursor="hand2")
        close_btn.pack(side="right")
        
        # Dragging bindings
        title_bar.bind("<ButtonPress-1>", self.start_move)
        title_bar.bind("<B1-Motion>", self.do_move)
        lbl_title.bind("<ButtonPress-1>", self.start_move)
        lbl_title.bind("<B1-Motion>", self.do_move)
        
        # Main container
        container = tk.Frame(self.result_window, bg=self.colors["bg"])
        container.pack(fill="both", expand=True)

        # Text Area - Using Canvas for image display
        # Create a frame to hold canvas and scrollbar
        canvas_frame = tk.Frame(container, bg=self.colors["text_bg"])
        canvas_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))
        
        # Add scrollbar
        self.scrollbar = tk.Scrollbar(canvas_frame, orient="vertical")
        self.scrollbar.pack(side="right", fill="y")
        
        # Add canvas
        self.canvas = tk.Canvas(canvas_frame, bg=self.colors["text_bg"], 
                               highlightthickness=0, yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Configure scrollbar
        self.scrollbar.config(command=self.canvas.yview)
        
        # Bind mouse wheel for scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Bottom Bar
        btn_frame = tk.Frame(container, bg=self.colors["bg"])
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # Status Label
        self.status_label = tk.Label(btn_frame, text="Processing...", font=(self.font_family, 10, "italic"), bg=self.colors["bg"], fg=self.colors["secondary_text"])
        self.status_label.pack(side="left")
        
        copy_btn = tk.Button(btn_frame, text="Copy", command=self.copy_to_clipboard,
                             font=(self.font_family, 10), 
                             bg=self.colors["btn_bg"], fg=self.colors["btn_fg"],
                             activebackground=self.colors["btn_active"], activeforeground=self.colors["btn_fg"], 
                             relief="flat", padx=15, pady=5, cursor="hand2")
        copy_btn.pack(side="right")

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.result_window.winfo_x() + deltax
        y = self.result_window.winfo_y() + deltay
        self.result_window.geometry(f"+{x}+{y}")

    def on_result_window_close(self):
        self.result_window.destroy()
        if hasattr(self, 'previous_state') and self.previous_state == 'iconic':
            self.root.iconify()
        else:
            self.root.deiconify()

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling"""
        if hasattr(self, 'canvas') and self.canvas.winfo_exists():
            try:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            except Exception:
                pass

    def process_image(self, image):
        try:
            translator = GeminiTranslator(self.api_key)
            translated_text = translator.translate_image(image, target_lang=self.target_lang)
            
            # Log the translation result to console
            print("\n" + "="*60)
            print("TRANSLATION RESULT")
            print("="*60)
            print(translated_text)
            print("="*60 + "\n")
            
            self.root.after(0, self.update_result_window, translated_text)
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"\n[ERROR] Translation failed: {str(e)}\n")
            self.root.after(0, self.update_result_window, error_msg)

    def update_result_window(self, text):
        if hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.status_label.config(text="Done", fg="#4CAF50")
            
            # Store text for copying
            self.current_text = text
            
            # Create image from text
            img = self.create_text_image(text)
            
            # Convert to PhotoImage
            from PIL import ImageTk
            self.photo = ImageTk.PhotoImage(img)
            
            # Clear canvas
            self.canvas.delete("all")
            
            # Add image to canvas
            self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
            
            # Configure scrolling
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # Dynamically resize window based on content
            # Get image dimensions
            img_width = img.width
            img_height = img.height
            
            # Add extra space for header, buttons, and padding
            extra_height = 120  # Header + buttons + margins
            total_height = img_height + extra_height
            
            # Set maximum and minimum heights
            max_height = 700
            min_height = 300
            
            # Clamp the height
            window_height = max(min_height, min(total_height, max_height))
            window_width = 550
            
            # Resize the window
            self.result_window.geometry(f"{window_width}x{int(window_height)}")
    
    def create_text_image(self, text):
        """Create an image with properly rendered RTL text and wrapping"""
        from PIL import Image, ImageDraw, ImageFont
        import re
        
        # Determine if error
        is_error = text.startswith("Error:")
        
        if is_error:
            text_content = text.replace("Error: ", "")
            title = "⚠ خطا"
            text_color = "#f44336"
        else:
            text_content = text
            title = "نتیجه ترجمه"
            text_color = self.colors["text_fg"]
        
        # Clean markdown formatting from text
        # Remove bold markers (**)
        text_content = re.sub(r'\*\*(.+?)\*\*', r'\1', text_content)
        # Remove italic markers (*)
        text_content = re.sub(r'\*(.+?)\*', r'\1', text_content)
        # Remove other common markdown
        text_content = re.sub(r'__(.+?)__', r'\1', text_content)
        text_content = re.sub(r'_(.+?)_', r'\1', text_content)
        
        # Fix bullet points (replace * at start of lines with •)
        text_content = re.sub(r'^\s*\*\s+', '• ', text_content, flags=re.MULTILINE)
        
        # Convert hex colors to RGB
        def hex_to_rgb(color):
            color_map = {
                'white': (255, 255, 255),
                'black': (0, 0, 0),
                'red': (255, 0, 0),
                'green': (0, 255, 0),
                'blue': (0, 0, 255)
            }
            if color.lower() in color_map:
                return color_map[color.lower()]
            hex_color = color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        bg_color = hex_to_rgb(self.colors["text_bg"])
        text_rgb = hex_to_rgb(text_color)
        accent_rgb = hex_to_rgb(self.colors["accent"])
        separator_rgb = hex_to_rgb(self.colors["secondary_text"])
        
        # Load fonts
        try:
            font_path = self.resource_path("fonts/Vazirmatn-Regular.ttf")
            if os.path.exists(font_path):
                title_font = ImageFont.truetype(font_path, 22)
                text_font = ImageFont.truetype(font_path, 16)
            else:
                title_font = ImageFont.load_default()
                text_font = ImageFont.load_default()
        except:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
        
        # Prepare text processing
        try:
            from arabic_reshaper import reshape
            from bidi.algorithm import get_display
            has_rtl_libs = True
        except ImportError:
            has_rtl_libs = False
            print("RTL libraries not found")

        # Layout configuration
        width = 470
        padding_x = 15  # Reduced horizontal padding
        padding_y = 20
        line_height = 30
        title_height = 40
        separator_margin = 15
        
        max_text_width = width - (padding_x * 2)
        
        # Determine text direction
        is_rtl = self.target_lang in self.RTL_LANGUAGES
        
        # Process Title
        if has_rtl_libs and is_rtl:
            bidi_title = get_display(reshape(title))
        else:
            bidi_title = title
            
        # Process Body Text with Wrapping
        final_lines = []
        
        paragraphs = text_content.split('\n')
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                final_lines.append("")
                continue
                
            # Manual wrapping logic
            words = paragraph.split(' ')
            current_line = []
            
            for word in words:
                # Check width of current line + word
                test_line = ' '.join(current_line + [word])
                # We measure the logical text width
                bbox = text_font.getbbox(test_line)
                text_w = bbox[2] - bbox[0]
                
                if text_w <= max_text_width:
                    current_line.append(word)
                else:
                    # Line full, push it
                    if current_line:
                        final_lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        # Word itself is too long, just push it
                        final_lines.append(word)
                        current_line = []
            
            if current_line:
                final_lines.append(' '.join(current_line))
        
        # Apply RTL to wrapped lines if needed
        display_lines = []
        for line in final_lines:
            if line.strip() and has_rtl_libs and is_rtl:
                reshaped = reshape(line)
                bidi_line = get_display(reshaped)
                display_lines.append(bidi_line)
            else:
                display_lines.append(line)
        
        # Calculate height
        num_lines = len(display_lines)
        height = (padding_y * 2 + (num_lines * line_height))
        
        # Create image
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        y = padding_y
        
        # Draw Text Lines
        for line in display_lines:
            if line.strip():
                bbox = draw.textbbox((0, 0), line, font=text_font)
                text_w = bbox[2] - bbox[0]
                
                if is_rtl:
                    # Right align
                    x = width - padding_x - text_w
                else:
                    # Left align
                    x = padding_x
                    
                draw.text((x, y), line, font=text_font, fill=text_rgb)
            y += line_height
            
        return img

    def copy_to_clipboard(self):
        if hasattr(self, 'current_text'):
            pyperclip.copy(self.current_text)
            messagebox.showinfo("Copied", "Text copied to clipboard!")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = ScreenTranslatorApp()
    app.run()
A