import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import os
import threading

# ── Palette ──────────────────────────────────────────────────────────────────
BG       = "#16161e"
SURFACE  = "#1f1f2b"
SURFACE2 = "#2a2a3a"
BORDER   = "#383850"
ACCENT   = "#7c6af7"
ACCENT_H = "#9d8fff"
FG       = "#cdd6f4"
FG_DIM   = "#565f89"
THUMB_BG = "#1a1a26"
CANVAS_BG= "#0f0f17"


def _apply_ttk_style():
    s = ttk.Style()
    s.theme_use("clam")

    # scrollbar track + thumb
    for orient in ("Vertical", "Horizontal"):
        s.configure(
            f"Dark.{orient}.TScrollbar",
            gripcount=0,
            background=BORDER,
            darkcolor=BORDER,
            lightcolor=BORDER,
            troughcolor=SURFACE,
            bordercolor=SURFACE,
            arrowcolor=FG_DIM,
            arrowsize=10,
            relief="flat",
        )
        s.map(
            f"Dark.{orient}.TScrollbar",
            background=[("active", ACCENT), ("!active", BORDER)],
        )


class _Tooltip:
    def __init__(self, widget, text):
        self._widget = widget
        self._text = text
        self._tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
        y = self._widget.winfo_rooty() - 26
        self._tip = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=self._text,
            bg="#2a2a3a", fg=FG, relief=tk.FLAT,
            font=("Segoe UI", 8), padx=6, pady=3,
        ).pack()

    def _hide(self, _event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


class ImageCropperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Batch Image Cropper")
        self.root.configure(bg=BG)
        self.root.minsize(860, 580)

        _apply_ttk_style()

        self.images = []
        self.image_paths = []
        self.current_image_index = 0
        self.crop_coords = None          # original image pixel coords
        self.scale = 1.0
        self.history = []                # undo stack: list of image lists
        self.thumbnail_buttons = []
        self._resize_job = None
        self._closing = False
        self._drag_mode = None           # 'new' | 'move' | handle name
        self._drag_start_canvas = None
        self._drag_orig_coords = None

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()

    def _build_ui(self):
        self._build_toolbar()
        self._build_canvas()
        self._build_thumbnail_strip()
        self._build_statusbar()

    # ── Toolbar ──────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        bar = tk.Frame(self.root, bg=SURFACE, pady=10)
        bar.pack(fill=tk.X, side=tk.TOP)

        # 1px bottom border
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X)

        left = tk.Frame(bar, bg=SURFACE)
        left.pack(side=tk.LEFT, padx=14)

        self.btn_load  = self._btn(left, "＋  Load Images",   self.load_images,        style="primary")
        self.btn_crop  = self._btn(left, "✂  Crop All",       self.batch_crop,         style="normal")
        self.btn_undo  = self._btn(left, "↩  Undo",           self.undo_crop,          style="ghost")
        self.btn_clear = self._btn(left, "✕  Clear",          self.clear_crop,         style="ghost")
        self.btn_save  = self._btn(left, "↓  Save Results",   self.save_images,        style="normal")

        for btn in (self.btn_load, self.btn_crop, self.btn_undo, self.btn_clear, self.btn_save):
            btn.pack(side=tk.LEFT, padx=3)

        # separator
        tk.Frame(bar, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=14, pady=2)

        # zoom controls
        zoom_frame = tk.Frame(bar, bg=SURFACE)
        zoom_frame.pack(side=tk.LEFT)

        self._btn(zoom_frame, "−", self.zoom_out, style="ghost").pack(side=tk.LEFT, padx=2)
        self.btn_zoom_level = self._btn(zoom_frame, "100%", self.zoom_reset, style="ghost")
        self.btn_zoom_level.pack(side=tk.LEFT, padx=2)
        self._btn(zoom_frame, "＋", self.zoom_in, style="ghost").pack(side=tk.LEFT, padx=2)
        self._btn(zoom_frame, "⤢  Fit", self.zoom_fit, style="ghost").pack(side=tk.LEFT, padx=2)

        # separator
        tk.Frame(bar, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=14, pady=2)

        right = tk.Frame(bar, bg=SURFACE)
        right.pack(side=tk.LEFT)

        tk.Label(right, text="Format", bg=SURFACE, fg=FG_DIM,
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(0, 8))

        self.save_format = tk.StringVar(value="PNG")
        self._fmt_buttons = {}
        for fmt in ("PNG", "JPEG", "WEBP"):
            btn = tk.Button(
                right, text=fmt,
                command=lambda f=fmt: self._select_format(f),
                font=("Segoe UI", 8, "bold"),
                relief=tk.FLAT, bd=0, padx=12, pady=5,
                cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=2)
            self._fmt_buttons[fmt] = btn
        self._select_format("PNG")

    def _select_format(self, fmt):
        self.save_format.set(fmt)
        for f, btn in self._fmt_buttons.items():
            if f == fmt:
                btn.config(bg=ACCENT, fg="#ffffff",
                           activebackground=ACCENT_H, activeforeground="#ffffff")
            else:
                btn.config(bg=SURFACE2, fg=FG_DIM,
                           activebackground=BORDER, activeforeground=FG)

    def _btn(self, parent, text, cmd, style="normal"):
        cfg = {
            "primary": dict(bg=ACCENT,   fg="#ffffff", abg=ACCENT_H,  afg="#ffffff"),
            "normal":  dict(bg=SURFACE2, fg=FG,        abg=BORDER,    afg=FG),
            "ghost":   dict(bg=SURFACE,  fg=FG_DIM,    abg=SURFACE2,  afg=FG),
        }[style]

        btn = tk.Button(
            parent, text=text, command=cmd,
            bg=cfg["bg"], fg=cfg["fg"],
            activebackground=cfg["abg"], activeforeground=cfg["afg"],
            relief=tk.FLAT, bd=0, padx=14, pady=7,
            font=("Segoe UI", 9), cursor="hand2",
        )
        _bg, _abg = cfg["bg"], cfg["abg"]
        btn.bind("<Enter>", lambda e: btn.config(bg=_abg))
        btn.bind("<Leave>", lambda e: btn.config(bg=_bg))
        return btn

    # ── Main canvas ──────────────────────────────────────────────────────────

    def _build_canvas(self):
        outer = tk.Frame(self.root, bg=BG)
        outer.pack(fill=tk.BOTH, expand=True)

        # right scrollbar
        sy = ttk.Scrollbar(outer, orient=tk.VERTICAL,   style="Dark.Vertical.TScrollbar")
        sy.pack(side=tk.RIGHT, fill=tk.Y)

        # bottom scrollbar
        sx = ttk.Scrollbar(outer, orient=tk.HORIZONTAL, style="Dark.Horizontal.TScrollbar")
        sx.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(outer, bg=CANVAS_BG, highlightthickness=0,
                                yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sy.config(command=self.canvas.yview)
        sx.config(command=self.canvas.xview)

        self.canvas.bind("<ButtonPress-1>",   self.start_crop)
        self.canvas.bind("<B1-Motion>",      self.update_crop)
        self.canvas.bind("<ButtonRelease-1>", self.end_crop)
        self.canvas.bind("<MouseWheel>",     self.scroll_or_zoom)
        self.canvas.bind("<Shift-MouseWheel>", self.scroll_horizontal)
        self.canvas.bind("<Motion>",         self.update_cursor_coords)
        self.canvas.bind("<ButtonPress-2>",  self.pan_start)
        self.canvas.bind("<B2-Motion>",      self.pan_move)
        self.canvas.bind("<ButtonRelease-2>", self.pan_end)
        self.root.bind("<Configure>",        self.handle_resize)

        self._canvas_placeholder()

    def _canvas_placeholder(self):
        self.canvas.delete("placeholder")
        cx = self.canvas.winfo_width() / 2 or 400
        cy = self.canvas.winfo_height() / 2 or 260
        self.canvas.create_text(
            cx, cy,
            text="Load images to get started",
            fill=FG_DIM, font=("Segoe UI", 13),
            tags="placeholder",
        )
        self.canvas.configure(scrollregion=(0, 0, 0, 0))

    # ── Thumbnail strip ──────────────────────────────────────────────────────

    def _build_thumbnail_strip(self):
        # 1px top border
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X)

        outer = tk.Frame(self.root, bg=THUMB_BG, height=118)
        outer.pack(fill=tk.X)
        outer.pack_propagate(False)

        sx = ttk.Scrollbar(outer, orient=tk.HORIZONTAL, style="Dark.Horizontal.TScrollbar")
        sx.pack(side=tk.BOTTOM, fill=tk.X)

        self.thumb_canvas = tk.Canvas(outer, bg=THUMB_BG, highlightthickness=0,
                                      xscrollcommand=sx.set)
        self.thumb_canvas.pack(fill=tk.BOTH, expand=True)
        sx.config(command=self.thumb_canvas.xview)

        self.thumbnail_frame = tk.Frame(self.thumb_canvas, bg=THUMB_BG)
        self.thumb_canvas.create_window((0, 0), window=self.thumbnail_frame, anchor=tk.NW)
        self.thumbnail_frame.bind(
            "<Configure>",
            lambda e: self.thumb_canvas.configure(scrollregion=self.thumb_canvas.bbox("all")),
        )

    # ── Status bar ───────────────────────────────────────────────────────────

    def _build_statusbar(self):
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X)
        bar = tk.Frame(self.root, bg=SURFACE, pady=5)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self.status_var, bg=SURFACE, fg=FG_DIM,
                 font=("Segoe UI", 8), anchor=tk.W, padx=14).pack(fill=tk.X)

    def _on_close(self):
        self._closing = True
        self.root.destroy()

    # ── Image loading ────────────────────────────────────────────────────────

    def load_images(self):
        file_paths = filedialog.askopenfilenames(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.gif *.webp")]
        )
        if not file_paths:
            return
        self._set_loading(True)
        self.status_var.set("Loading images…")
        threading.Thread(target=self._load_images_thread, args=(file_paths,), daemon=True).start()

    def _load_images_thread(self, file_paths):
        images, valid_paths = [], []
        for path in file_paths:
            try:
                img = Image.open(path)
                img.load()
                images.append(img)
                valid_paths.append(path)
            except Exception:
                pass
        if not self._closing:
            self.root.after(0, self._on_images_loaded, valid_paths, images)

    def _on_images_loaded(self, file_paths, images):
        self.image_paths = file_paths
        self.images = images
        self.current_image_index = 0
        self.crop_coords = None
        self.history = []
        self.scale = 1.0
        self.display_image()
        self.display_thumbnails()
        self._set_loading(False)
        self._update_undo_btn()
        self.status_var.set(f"Loaded {len(self.images)} image(s)")

    def _set_loading(self, loading: bool):
        state = tk.DISABLED if loading else tk.NORMAL
        for btn in (self.btn_load, self.btn_crop, self.btn_save):
            btn.config(state=state)

    # ── Display ──────────────────────────────────────────────────────────────

    def display_image(self):
        if not self.images:
            return

        img = self.images[self.current_image_index]
        resized = img.resize((int(img.width * self.scale), int(img.height * self.scale)))
        self.tk_image = ImageTk.PhotoImage(resized)

        self.canvas.delete("all")
        self.canvas.config(scrollregion=(0, 0, resized.width, resized.height))
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.btn_zoom_level.config(text=f"{int(self.scale * 100)}%")
        self._draw_crop_rect()

    def _draw_crop_rect(self):
        self.canvas.delete("crop_rect")
        if self.crop_coords is None:
            return
        x1, y1, x2, y2 = self.crop_coords
        lx = min(x1, x2) * self.scale
        ly = min(y1, y2) * self.scale
        rx = max(x1, x2) * self.scale
        ry = max(y1, y2) * self.scale

        # dark overlay on excluded area — stipple gives semi-transparent feel
        iw = int(self.images[self.current_image_index].width  * self.scale)
        ih = int(self.images[self.current_image_index].height * self.scale)
        for coords in (
            (0,  0,  iw, ly),
            (0,  ry, iw, ih),
            (0,  ly, lx, ry),
            (rx, ly, iw, ry),
        ):
            self.canvas.create_rectangle(
                *coords, fill="#000000", outline="",
                stipple="gray50", tags="crop_rect",
            )

        # dashed selection border
        self.canvas.create_rectangle(
            lx, ly, rx, ry,
            outline=ACCENT_H, width=2, dash=(6, 4), tags="crop_rect",
        )
        # corner handles
        h = 7
        for hx, hy in ((lx, ly), (rx, ly), (lx, ry), (rx, ry)):
            self.canvas.create_rectangle(
                hx - h, hy - h, hx + h, hy + h,
                fill=ACCENT_H, outline=CANVAS_BG, width=2, tags="crop_rect",
            )

    def display_thumbnails(self):
        for widget in self.thumbnail_frame.winfo_children():
            widget.destroy()
        self.thumbnail_buttons = []

        for index, image in enumerate(self.images):
            thumbnail = image.copy()
            thumbnail.thumbnail((88, 88))
            tk_thumbnail = ImageTk.PhotoImage(thumbnail)

            btn = tk.Button(
                self.thumbnail_frame,
                image=tk_thumbnail,
                command=lambda idx=index: self.select_image(idx),
                bg=THUMB_BG, activebackground=SURFACE2,
                relief=tk.FLAT, bd=0, cursor="hand2",
                padx=0, pady=0,
            )
            btn.image = tk_thumbnail
            btn.pack(side=tk.LEFT, padx=7, pady=10)
            _Tooltip(btn, os.path.basename(self.image_paths[index]))
            self.thumbnail_buttons.append(btn)

        self._highlight_thumbnail()

    def _highlight_thumbnail(self):
        for i, btn in enumerate(self.thumbnail_buttons):
            if i == self.current_image_index:
                btn.config(bg=ACCENT, highlightbackground=ACCENT,
                           highlightthickness=2, relief=tk.FLAT, bd=2)
            else:
                btn.config(bg=THUMB_BG, highlightbackground=THUMB_BG,
                           highlightthickness=0, relief=tk.FLAT, bd=0)

    def select_image(self, index):
        self.current_image_index = index
        self._highlight_thumbnail()
        self.display_image()

    # ── Crop interaction ─────────────────────────────────────────────────────

    _HANDLE_HIT = 10   # canvas-pixel hit radius for handles

    _HANDLE_CURSORS = {
        'TL': 'size_nw_se', 'TR': 'size_ne_sw',
        'BL': 'size_ne_sw', 'BR': 'size_nw_se',
        'TM': 'size_ns',    'BM': 'size_ns',
        'ML': 'size_we',    'MR': 'size_we',
        'move': 'fleur',    'new': 'crosshair',
    }

    def _canvas_to_image(self, cx, cy):
        if not self.images:
            return cx, cy
        img = self.images[self.current_image_index]
        return (
            max(0.0, min(cx / self.scale, img.width)),
            max(0.0, min(cy / self.scale, img.height)),
        )

    def _norm_canvas(self):
        if self.crop_coords is None:
            return None
        x1, y1, x2, y2 = self.crop_coords
        return (
            min(x1, x2) * self.scale, min(y1, y2) * self.scale,
            max(x1, x2) * self.scale, max(y1, y2) * self.scale,
        )

    def _hit_test(self, cx, cy):
        """Return hit zone: handle name | 'move' | 'new'."""
        nc = self._norm_canvas()
        if nc is None:
            return 'new'
        lx, ly, rx, ry = nc
        mx, my = (lx + rx) / 2, (ly + ry) / 2
        handles = {
            'TL': (lx, ly), 'TM': (mx, ly), 'TR': (rx, ly),
            'ML': (lx, my),                  'MR': (rx, my),
            'BL': (lx, ry), 'BM': (mx, ry), 'BR': (rx, ry),
        }
        h = self._HANDLE_HIT
        for name, (hx, hy) in handles.items():
            if abs(cx - hx) <= h and abs(cy - hy) <= h:
                return name
        if lx <= cx <= rx and ly <= cy <= ry:
            return 'move'
        return 'new'

    def start_crop(self, event):
        if not self.images:
            return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        hit = self._hit_test(cx, cy)
        self._drag_mode = hit
        self._drag_start_canvas = (cx, cy)
        self._drag_orig_coords = self.crop_coords

        if hit == 'new':
            ox, oy = self._canvas_to_image(cx, cy)
            self.crop_coords = (ox, oy, ox, oy)

    def update_crop(self, event):
        if self._drag_mode is None:
            return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.scroll_on_drag(event)

        if self._drag_mode == 'new':
            x1, y1, _, _ = self.crop_coords
            x2, y2 = self._canvas_to_image(cx, cy)
            self.crop_coords = (x1, y1, x2, y2)

        elif self._drag_mode == 'move':
            sx, sy = self._drag_start_canvas
            dx, dy = (cx - sx) / self.scale, (cy - sy) / self.scale
            ox1, oy1, ox2, oy2 = self._drag_orig_coords
            img = self.images[self.current_image_index]
            # clamp so box stays inside image
            w, h = abs(ox2 - ox1), abs(oy2 - oy1)
            nx1 = max(0, min(ox1 + dx, img.width  - w))
            ny1 = max(0, min(oy1 + dy, img.height - h))
            self.crop_coords = (nx1, ny1, nx1 + w, ny1 + h)

        else:
            # resize: _drag_orig_coords is normalized (lx,ly,rx,ry) in image px
            ox1, oy1, ox2, oy2 = self._drag_orig_coords
            lx = min(ox1, ox2); ly = min(oy1, oy2)
            rx = max(ox1, ox2); ry = max(oy1, oy2)
            mx, my = self._canvas_to_image(cx, cy)
            img = self.images[self.current_image_index]
            mx = max(0, min(mx, img.width))
            my = max(0, min(my, img.height))

            if 'L' in self._drag_mode: lx = mx
            if 'R' in self._drag_mode: rx = mx
            if 'T' in self._drag_mode: ly = my
            if 'B' in self._drag_mode: ry = my
            self.crop_coords = (lx, ly, rx, ry)

        self._draw_crop_rect()
        self._update_status_coords()

    def end_crop(self, event):
        self._drag_mode = None
        self._drag_start_canvas = None
        self._drag_orig_coords = None
        self._update_status_coords()

    def clear_crop(self):
        self.crop_coords = None
        self.canvas.delete("crop_rect")
        if self.images:
            img = self.images[self.current_image_index]
            self.status_var.set(f"Zoom: {self.scale * 100:.0f}%  |  {img.width} × {img.height} px")
        else:
            self.status_var.set("Ready")

    def _update_status_coords(self):
        if self.crop_coords is None:
            return
        x1, y1, x2, y2 = self.crop_coords
        ox1, oy1 = int(min(x1, x2)), int(min(y1, y2))
        ox2, oy2 = int(max(x1, x2)), int(max(y1, y2))
        w, h = ox2 - ox1, oy2 - oy1
        self.status_var.set(
            f"Zoom: {self.scale * 100:.0f}%  |  Crop: ({ox1}, {oy1}) → ({ox2}, {oy2})   {w} × {h} px"
        )

    def update_cursor_coords(self, event):
        if self._drag_mode is not None or not self.images:
            return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        hit = self._hit_test(cx, cy)
        self.canvas.config(cursor=self._HANDLE_CURSORS.get(hit, 'crosshair'))
        ox, oy = self._canvas_to_image(cx, cy)
        self.status_var.set(f"Zoom: {self.scale * 100:.0f}%  |  Position: ({int(ox)}, {int(oy)})")

    def scroll_on_drag(self, event):
        margin = 20
        if event.x < margin:
            self.canvas.xview_scroll(-1, "units")
        elif event.x > self.canvas.winfo_width() - margin:
            self.canvas.xview_scroll(1, "units")
        if event.y < margin:
            self.canvas.yview_scroll(-1, "units")
        elif event.y > self.canvas.winfo_height() - margin:
            self.canvas.yview_scroll(1, "units")

    def pan_start(self, event):
        self.canvas.config(cursor="fleur")
        self.canvas.scan_mark(event.x, event.y)

    def pan_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def pan_end(self, event):
        self.canvas.config(cursor="")

    def zoom_in(self):
        self.scale = round(min(self.scale + 0.1, 10.0), 1)
        self.display_image()

    def zoom_out(self):
        self.scale = round(max(self.scale - 0.1, 0.1), 1)
        self.display_image()

    def zoom_reset(self):
        self.scale = 1.0
        self.display_image()

    def zoom_fit(self):
        if not self.images:
            return
        img = self.images[self.current_image_index]
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 2 or ch < 2:
            return
        scale = min(cw / img.width, ch / img.height)
        self.scale = round(max(0.1, min(scale, 10.0)), 2)
        self.display_image()

    def scroll_or_zoom(self, event):
        if event.state & 0x4:  # Ctrl held
            if event.delta > 0:
                self.scale += 0.1
            elif event.delta < 0:
                self.scale = max(0.1, self.scale - 0.1)
            self.display_image()
        else:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def scroll_horizontal(self, event):
        self.canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")

    # ── Crop & Save ──────────────────────────────────────────────────────────

    def batch_crop(self):
        if not self.images:
            self.status_var.set("No images loaded.")
            return
        if self.crop_coords is None:
            self.status_var.set("Please select an area to crop.")
            return

        x1, y1, x2, y2 = self.crop_coords
        orig_box = (int(min(x1, x2)), int(min(y1, y2)), int(max(x1, x2)), int(max(y1, y2)))

        if orig_box[0] == orig_box[2] or orig_box[1] == orig_box[3]:
            self.status_var.set("Please select an area to crop.")
            return

        # push current state to undo stack
        self.history.append(self.images[:])

        new_images = []
        for image in self.images:
            box = (
                max(0, orig_box[0]),
                max(0, orig_box[1]),
                min(image.width, orig_box[2]),
                min(image.height, orig_box[3]),
            )
            new_images.append(image.crop(box))

        self.images = new_images
        self.crop_coords = None
        self.display_image()
        self.display_thumbnails()
        self._update_undo_btn()
        self.status_var.set(f"Cropped {len(self.images)} image(s)  —  Undo available")

    def undo_crop(self):
        if not self.history:
            return
        self.images = self.history.pop()
        self.crop_coords = None
        self.display_image()
        self.display_thumbnails()
        self._update_undo_btn()
        depth = len(self.history)
        self.status_var.set(
            f"Undo complete  —  {depth} step(s) remaining" if depth else "Undo complete"
        )

    def _update_undo_btn(self):
        self.btn_undo.config(state=tk.NORMAL if self.history else tk.DISABLED)

    def save_images(self):
        if not self.images:
            self.status_var.set("No images to save.")
            return
        save_dir = filedialog.askdirectory()
        if not save_dir:
            return

        fmt = self.save_format.get()
        ext = fmt.lower()
        for i, img in enumerate(self.images):
            if fmt == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            base = os.path.splitext(os.path.basename(self.image_paths[i]))[0]
            save_path = self._unique_path(save_dir, f"{base}_cropped", ext)
            img.save(save_path, format=fmt)
        self.status_var.set(f"Saved {len(self.images)} image(s) to {save_dir}")

    def _unique_path(self, directory, stem, ext):
        path = os.path.join(directory, f"{stem}.{ext}")
        counter = 1
        while os.path.exists(path):
            path = os.path.join(directory, f"{stem}_{counter}.{ext}")
            counter += 1
        return path

    def handle_resize(self, event):
        if event.widget is not self.root:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        target = self.display_image if self.images else self._canvas_placeholder
        self._resize_job = self.root.after(100, target)


if __name__ == "__main__":
    root = tk.Tk()
    app = ImageCropperApp(root)
    root.mainloop()
