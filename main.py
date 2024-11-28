import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os


class ImageCropperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("batch-image-cropper")

        self.images = []
        self.image_paths = []
        self.current_image_index = 0
        self.crop_coords = (0, 0, 0, 0)
        self.is_cropping = False
        self.scale = 1.0  # Zoom ratio

        # Scrollable Canvas
        self.canvas_frame = tk.Frame(root)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="gray")
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scroll_y = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.scroll_x = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.configure(yscrollcommand=self.scroll_y.set, xscrollcommand=self.scroll_x.set)

        # Thumbnail Frame
        self.thumbnail_frame = tk.Frame(root, height=100, bg="white")
        self.thumbnail_frame.pack(fill=tk.X, padx=10, pady=5)

        # Buttons
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(fill=tk.X, pady=5)

        self.btn_load = tk.Button(self.btn_frame, text="Load Images", command=self.load_images)
        self.btn_load.pack(side=tk.LEFT, padx=10)

        self.btn_crop = tk.Button(self.btn_frame, text="Select Area and Crop", command=self.batch_crop)
        self.btn_crop.pack(side=tk.LEFT, padx=10)

        self.btn_save = tk.Button(self.btn_frame, text="Save Results", command=self.save_cropped_images)
        self.btn_save.pack(side=tk.LEFT, padx=10)

        self.canvas.bind("<ButtonPress-1>", self.start_crop)
        self.canvas.bind("<B1-Motion>", self.update_crop)
        self.canvas.bind("<ButtonRelease-1>", self.end_crop)
        self.canvas.bind("<MouseWheel>", self.zoom_image)

        self.root.bind("<Configure>", self.handle_resize)

    def load_images(self):
        file_paths = filedialog.askopenfilenames(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif")]
        )
        if not file_paths:
            return
        self.image_paths = list(file_paths)
        self.images = [Image.open(path) for path in self.image_paths]
        self.current_image_index = 0
        self.display_image()
        self.display_thumbnails()

    def display_image(self):
        if not self.images:
            return

        self.current_image = self.images[self.current_image_index]

        # Adjust image size according to the zoom ratio
        self.resized_image = self.current_image.resize(
            (int(self.current_image.width * self.scale), int(self.current_image.height * self.scale))
        )
        self.tk_image = ImageTk.PhotoImage(self.resized_image)

        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, self.resized_image.width, self.resized_image.height))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

    def display_thumbnails(self):
        # Initialize thumbnail frame
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()

        for index, image in enumerate(self.images):
            thumbnail = image.copy()
            thumbnail.thumbnail((100, 100))
            tk_thumbnail = ImageTk.PhotoImage(thumbnail)

            btn = tk.Button(
                self.thumbnail_frame,
                image=tk_thumbnail,
                command=lambda idx=index: self.select_image(idx),
            )
            btn.image = tk_thumbnail
            btn.pack(side=tk.LEFT, padx=5)

    def select_image(self, index):
        self.current_image_index = index
        self.display_image()

    def start_crop(self, event):
        self.is_cropping = True
        self.crop_coords = (
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
        )

    def update_crop(self, event):
        if not self.is_cropping:
            return
        x1, y1, _, _ = self.crop_coords
        x2, y2 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.crop_coords = (x1, y1, x2, y2)
        self.scroll_on_drag(event)
        self.display_image()
        self.canvas.create_rectangle(*self.crop_coords, outline="red", width=2)

    def end_crop(self, event):
        self.is_cropping = False

    def scroll_on_drag(self, event):
        margin = 20  # Distance from the edge of the screen to start scrolling
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Scroll calculate
        if event.x < margin:
            self.canvas.xview_scroll(-1, "units")
        elif event.x > canvas_width - margin:
            self.canvas.xview_scroll(1, "units")

        if event.y < margin:
            self.canvas.yview_scroll(-1, "units")
        elif event.y > canvas_height - margin:
            self.canvas.yview_scroll(1, "units")

    def zoom_image(self, event):
        zoom_factor = 0.1
        if event.delta > 0:
            self.scale += zoom_factor
        elif event.delta < 0:
            self.scale = max(0.1, self.scale - zoom_factor)  # Limit to a minimum of 10%
        self.display_image()

    def batch_crop(self):
        if not self.images:
            messagebox.showerror("Error", "No images available.")
            return
        if self.crop_coords == (0, 0, 0, 0):
            messagebox.showerror("Error", "Please select an area to crop.")
            return

        self.cropped_images = []
        for image in self.images:
            resized_image = image.resize(
                (int(image.width * self.scale), int(image.height * self.scale))
            )
            cropped = resized_image.crop(self.crop_coords)
            self.cropped_images.append(cropped)
        messagebox.showinfo("Success", "All images have been cropped!")

    def save_cropped_images(self):
        if not hasattr(self, 'cropped_images') or not self.cropped_images:
            messagebox.showerror("Error", "There is no image to save.")
            return
        save_dir = filedialog.askdirectory()
        if not save_dir:
            return
        for i, cropped in enumerate(self.cropped_images):
            save_path = os.path.join(save_dir, f"cropped_{i+1}.png")
            cropped.save(save_path)
        messagebox.showinfo("Success", f"The cropped image has been saved in {save_dir}.")

    def handle_resize(self, event):
        self.display_image()


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageCropperApp(root)
    root.mainloop()
