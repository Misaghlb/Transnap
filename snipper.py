import tkinter as tk
from PIL import Image, ImageTk, ImageGrab
import keyboard

class Snipper:
    def __init__(self, root, on_snip_complete):
        self.root = root
        self.on_snip_complete = on_snip_complete
        self.start_x = None
        self.start_y = None
        self.current_rect = None
        self.esc_hook = None
        
        # Capture screen immediately
        self.screen_image = ImageGrab.grab()
        self.photo_image = ImageTk.PhotoImage(self.screen_image)
        
        # Create a "dimmed" version of the screenshot
        # We can do this by creating a dark overlay or processing the image.
        # Processing image might be slow. Let's use a canvas with a semi-transparent rectangle?
        # Tkinter canvas doesn't support alpha transparency well for shapes *over* images in a complex way without some tricks.
        # Better approach: 
        # 1. Show the full bright screenshot on the canvas.
        # 2. Place a semi-transparent black window OVER it? No, that blocks events.
        # 3. Use a canvas with the image, and draw a semi-transparent polygon? Tkinter polygons can be stippled but not true alpha.
        # 4. Alternative: Create a darkened version of the image using PIL and show THAT.
        #    Then when selecting, show the BRIGHT part in the selection rectangle.
        
        enhancer = Image.new('RGBA', self.screen_image.size, (0, 0, 0, 100)) # Black with alpha
        # Actually, let's just darken the image
        self.dark_image = self.screen_image.point(lambda p: p * 0.5)
        self.dark_photo = ImageTk.PhotoImage(self.dark_image)
        
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.configure(cursor="cross")
        
        self.canvas = tk.Canvas(self.root, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Draw the dark image initially
        self.canvas.create_image(0, 0, image=self.dark_photo, anchor="nw", tags="bg")
        
        # Bind events
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        # Keep local bind as backup
        self.root.bind("<Escape>", self.exit_snipper)
        
        # Global hook for Esc
        try:
            self.esc_hook = keyboard.on_press_key("esc", self.on_global_esc)
        except Exception as e:
            print(f"Failed to set global hook: {e}")
        
        # Ensure we capture all events
        self.root.lift()
        self.root.focus_force()
        self.root.grab_set()
        self.root.focus_set()

    def on_global_esc(self, event):
        # Thread-safe call to exit
        self.root.after(0, self.exit_snipper)

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        
        # Create rectangle for selection border
        if self.current_rect:
            self.canvas.delete(self.current_rect)
        
        # We want to show the BRIGHT image inside the selection.
        # We can do this by creating an image item that is clipped? Tkinter doesn't support easy clipping.
        # Trick: 
        # 1. Clear canvas.
        # 2. Draw dark image.
        # 3. Draw a "hole" or draw the bright image chunk on top?
        # Drawing the bright image chunk on top is easier.
        
        self.selection_image_id = None
        self.current_rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, 
            outline="white", width=2
        )

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        
        # Update border
        self.canvas.coords(self.current_rect, self.start_x, self.start_y, cur_x, cur_y)
        
        # Update the "bright" reveal
        # To do this efficiently, we might need to just move a cropping of the bright image?
        # Or just redraw the bright image cropped.
        
        x1 = min(self.start_x, cur_x)
        y1 = min(self.start_y, cur_y)
        x2 = max(self.start_x, cur_x)
        y2 = max(self.start_y, cur_y)
        
        if x2 - x1 > 0 and y2 - y1 > 0:
            # Crop the bright image to this area
            # Note: Creating new PhotoImages constantly is slow and leaks memory if not careful.
            # But for a drag operation it might be okay if we keep a reference.
            # Optimization: Don't do it on every pixel move?
            
            # Actually, a better way for "dimming" in Tkinter without constant image creation:
            # Use 4 rectangles of "dim" color around the selection?
            # Top, Bottom, Left, Right.
            # And the center is transparent (showing the underlying window)? 
            # No, our window is the top one.
            # So we display the BRIGHT image as background.
            # And we draw 4 semi-transparent black rectangles around the selection.
            # Tkinter doesn't support alpha on rectangles easily (only stipple).
            # But we can use images for the dimming?
            
            # Let's stick to the "Bright Image Chunk" approach for now, it's simplest to implement if performance allows.
            
            try:
                cropped = self.screen_image.crop((x1, y1, x2, y2))
                self.current_bright_photo = ImageTk.PhotoImage(cropped)
                
                if hasattr(self, 'selection_image_id') and self.selection_image_id:
                    self.canvas.delete(self.selection_image_id)
                
                self.selection_image_id = self.canvas.create_image(x1, y1, image=self.current_bright_photo, anchor="nw")
                # Raise the border
                self.canvas.tag_raise(self.current_rect)
            except Exception:
                pass

    def on_button_release(self, event):
        if self.start_x is None or self.start_y is None:
            return

        end_x, end_y = (event.x, event.y)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        if x2 - x1 < 5 or y2 - y1 < 5:
            self.exit_snipper()
            return

        cropped_image = self.screen_image.crop((x1, y1, x2, y2))
        
        # Clean up hook before destroying
        if self.esc_hook:
            try:
                keyboard.unhook(self.esc_hook)
                self.esc_hook = None
            except:
                pass
                
        self.root.destroy()
        self.on_snip_complete(cropped_image)

    def exit_snipper(self, event=None):
        print("Exit snipper called")
        
        # Clean up hook
        if self.esc_hook:
            try:
                keyboard.unhook(self.esc_hook)
                self.esc_hook = None
            except:
                pass
                
        self.root.destroy()
        self.on_snip_complete(None)
