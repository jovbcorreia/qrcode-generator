"""
QR Forge — Desktop QR Code Generator
"""

import tkinter as tk
from tkinter import filedialog, ttk
import qrcode
from PIL import Image, ImageTk
import io

# ──────────────────────────────────────────────────────────────────────────────
# Palette
# ──────────────────────────────────────────────────────────────────────────────
BG          = "#F5F5F5"
WHITE       = "#FFFFFF"
BLACK       = "#0A0A0A"
GREY_LIGHT  = "#E0E0E0"
GREY_MID    = "#888888"
GREY_DARK   = "#2A2A2A"

FONT_FAMILY = "Helvetica Neue"          # falls back to Helvetica → system sans-serif

EC_LEVELS = {
    "L — Low (7%)":        qrcode.constants.ERROR_CORRECT_L,
    "M — Medium (15%)":    qrcode.constants.ERROR_CORRECT_M,
    "Q — Quartile (25%)":  qrcode.constants.ERROR_CORRECT_Q,
    "H — High (30%)":      qrcode.constants.ERROR_CORRECT_H,
}

DEBOUNCE_MS = 300


# ──────────────────────────────────────────────────────────────────────────────
# Application
# ──────────────────────────────────────────────────────────────────────────────
class QRGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._configure_window()

        self._qr_image: Image.Image | None = None   # full-res PIL image
        self._debounce_id: str | None = None

        self._build_ui()

    # ── Window setup ────────────────────────────────────────────────────────
    def _configure_window(self) -> None:
        self.root.title("QR Generator")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)

        w, h = 900, 600
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI construction ──────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # Root is two side-by-side columns
        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self) -> None:
        left = tk.Frame(self.root, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(30, 15), pady=30)
        left.columnconfigure(0, weight=1)

        # Title
        tk.Label(
            left, text="QR Forge", bg=BG, fg=BLACK,
            font=(FONT_FAMILY, 20, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        tk.Label(
            left, text="Generate QR codes instantly.", bg=BG, fg=GREY_MID,
            font=(FONT_FAMILY, 11),
        ).grid(row=1, column=0, sticky="w", pady=(0, 20))

        # ── Content input label + character counter ──
        row_frame = tk.Frame(left, bg=BG)
        row_frame.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        row_frame.columnconfigure(0, weight=1)

        tk.Label(
            row_frame, text="Content", bg=BG, fg=GREY_DARK,
            font=(FONT_FAMILY, 12, "bold"),
        ).grid(row=0, column=0, sticky="w")

        self._char_counter = tk.Label(
            row_frame, text="0 chars", bg=BG, fg=GREY_MID,
            font=(FONT_FAMILY, 10),
        )
        self._char_counter.grid(row=0, column=1, sticky="e")

        # Multi-line text input
        self._text_input = tk.Text(
            left,
            height=8,
            wrap="word",
            font=(FONT_FAMILY, 12),
            bg=WHITE,
            fg=BLACK,
            insertbackground=BLACK,
            relief="flat",
            bd=0,
            padx=12,
            pady=10,
            highlightthickness=1,
            highlightbackground=GREY_LIGHT,
            highlightcolor=GREY_DARK,
        )
        self._text_input.grid(row=3, column=0, sticky="ew")
        self._text_input.bind("<KeyRelease>", self._on_text_change)

        # ── Error correction dropdown ──
        tk.Label(
            left, text="Error Correction", bg=BG, fg=GREY_DARK,
            font=(FONT_FAMILY, 11, "bold"),
        ).grid(row=4, column=0, sticky="w", pady=(18, 4))

        self._ec_var = tk.StringVar(value=list(EC_LEVELS.keys())[1])  # default M
        self._ec_menu = ttk.Combobox(
            left,
            textvariable=self._ec_var,
            values=list(EC_LEVELS.keys()),
            state="readonly",
            font=(FONT_FAMILY, 11),
        )
        self._ec_menu.grid(row=5, column=0, sticky="ew")
        self._ec_menu.bind("<<ComboboxSelected>>", self._on_ec_change)
        self._style_combobox()

        # ── Error message label ──
        self._error_label = tk.Label(
            left, text="", bg=BG, fg=GREY_DARK,
            font=(FONT_FAMILY, 10), wraplength=380, justify="left",
        )
        self._error_label.grid(row=6, column=0, sticky="w", pady=(6, 0))

        # ── Buttons ──
        btn_frame = tk.Frame(left, bg=BG)
        btn_frame.grid(row=7, column=0, sticky="ew", pady=(24, 0))
        btn_frame.columnconfigure((0, 1, 2), weight=1)

        self._btn_generate = self._make_button(btn_frame, "Generate", self._generate_qr, primary=True)
        self._btn_generate.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._btn_save_png = self._make_button(btn_frame, "Save PNG", self._save_png)
        self._btn_save_png.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        self._btn_save_jpg = self._make_button(btn_frame, "Save JPEG", self._save_jpeg)
        self._btn_save_jpg.grid(row=0, column=2, sticky="ew", padx=(0, 6))

        self._btn_clear = self._make_button(btn_frame, "Clear", self._clear)
        self._btn_clear.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    def _build_right_panel(self) -> None:
        right = tk.Frame(self.root, bg=WHITE, highlightthickness=1, highlightbackground=GREY_LIGHT)
        right.grid(row=0, column=1, sticky="nsew", padx=(15, 30), pady=30)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        tk.Label(
            right, text="Preview", bg=WHITE, fg=GREY_MID,
            font=(FONT_FAMILY, 11),
        ).grid(row=0, column=0, pady=(16, 0))

        # Canvas for QR preview
        self._canvas = tk.Canvas(
            right, bg=WHITE, bd=0, highlightthickness=0,
            width=380, height=480,
        )
        self._canvas.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="nsew")

        self._show_placeholder()

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _make_button(self, parent, text: str, command, *, primary: bool = False) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=(FONT_FAMILY, 11),
            relief="flat",
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
        )
        if primary:
            btn.configure(bg=BLACK, fg=WHITE, activebackground=GREY_DARK, activeforeground=WHITE)
        else:
            btn.configure(bg=WHITE, fg=BLACK, activebackground=BLACK, activeforeground=WHITE,
                          highlightthickness=1, highlightbackground=GREY_LIGHT)

        def on_enter(e):
            btn.configure(bg=BLACK, fg=WHITE)

        def on_leave(e):
            if primary:
                btn.configure(bg=BLACK, fg=WHITE)
            else:
                btn.configure(bg=WHITE, fg=BLACK)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def _style_combobox(self) -> None:
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "TCombobox",
            fieldbackground=WHITE,
            background=WHITE,
            foreground=BLACK,
            selectbackground=GREY_LIGHT,
            selectforeground=BLACK,
            bordercolor=GREY_LIGHT,
            arrowcolor=GREY_DARK,
            relief="flat",
        )

    def _show_placeholder(self) -> None:
        self._canvas.delete("all")
        cw = self._canvas.winfo_reqwidth()
        ch = self._canvas.winfo_reqheight()
        self._canvas.create_text(
            cw // 2, ch // 2,
            text="Your QR code\nwill appear here",
            fill=GREY_LIGHT,
            font=(FONT_FAMILY, 14),
            justify="center",
        )

    def _set_error(self, msg: str) -> None:
        self._error_label.configure(text=msg)

    # ── Event handlers ───────────────────────────────────────────────────────
    def _on_text_change(self, _event=None) -> None:
        content = self._text_input.get("1.0", "end-1c")
        self._char_counter.configure(text=f"{len(content)} chars")

        # Debounce: cancel previous pending call
        if self._debounce_id:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = self.root.after(DEBOUNCE_MS, self._generate_qr)

    def _on_ec_change(self, _event=None) -> None:
        self._generate_qr()

    # ── QR generation ────────────────────────────────────────────────────────
    def _generate_qr(self) -> None:
        content = self._text_input.get("1.0", "end-1c").strip()
        self._set_error("")

        if not content:
            self._qr_image = None
            self._show_placeholder()
            return

        ec_level = EC_LEVELS[self._ec_var.get()]

        try:
            qr = qrcode.QRCode(
                error_correction=ec_level,
                box_size=10,
                border=4,
            )
            qr.add_data(content)
            qr.make(fit=True)
        except qrcode.exceptions.DataOverflowError:
            self._set_error("Content is too long for the selected error correction level.")
            return
        except Exception as exc:
            self._set_error(f"Error: {exc}")
            return

        self._qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        self._render_preview()

    def _render_preview(self) -> None:
        if self._qr_image is None:
            return

        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width() or self._canvas.winfo_reqwidth()
        ch = self._canvas.winfo_height() or self._canvas.winfo_reqheight()

        size = min(cw, ch) - 20
        thumb = self._qr_image.copy()
        thumb.thumbnail((size, size), Image.LANCZOS)

        self._tk_image = ImageTk.PhotoImage(thumb)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, anchor="center", image=self._tk_image)

    # ── Save handlers ────────────────────────────────────────────────────────
    def _save_png(self) -> None:
        self._save_image("png")

    def _save_jpeg(self) -> None:
        self._save_image("jpeg")

    def _save_image(self, fmt: str) -> None:
        if self._qr_image is None:
            self._set_error("Generate a QR code first.")
            return

        ext = "jpg" if fmt == "jpeg" else "png"
        filetypes = [("JPEG image", "*.jpg")] if fmt == "jpeg" else [("PNG image", "*.png")]

        path = filedialog.asksaveasfilename(
            defaultextension=f".{ext}",
            filetypes=filetypes,
            title=f"Save as {fmt.upper()}",
        )
        if not path:
            return

        output = self._qr_image.resize((800, 800), Image.LANCZOS)
        if fmt == "jpeg":
            output.save(path, "JPEG", quality=95)
        else:
            output.save(path, "PNG")

        self._set_error(f"Saved to {path}")

    # ── Clear ────────────────────────────────────────────────────────────────
    def _clear(self) -> None:
        self._text_input.delete("1.0", "end")
        self._char_counter.configure(text="0 chars")
        self._set_error("")
        self._qr_image = None
        self._show_placeholder()


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = QRGeneratorApp(root)
    root.mainloop()
