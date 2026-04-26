"""
QR Code Generator — Desktop App
"""

import tkinter as tk
from tkinter import filedialog, ttk
import qrcode
from PIL import Image, ImageTk
import subprocess
import tempfile
import os

# ── Palette ───────────────────────────────────────────────────────────────────
BG         = "#F5F5F5"
WHITE      = "#FFFFFF"
BLACK      = "#0A0A0A"
GREY_LIGHT = "#E0E0E0"
GREY_MID   = "#888888"
GREY_DARK  = "#2A2A2A"

FONT = "Helvetica Neue"
DEBOUNCE_MS = 300

EC_LEVELS = {
    "L — Low (7%)":        qrcode.constants.ERROR_CORRECT_L,
    "M — Medium (15%)":    qrcode.constants.ERROR_CORRECT_M,
    "Q — Quartile (25%)":  qrcode.constants.ERROR_CORRECT_Q,
    "H — High (30%)":      qrcode.constants.ERROR_CORRECT_H,
}

TYPES = ["URL", "Text", "WiFi", "Email", "SMS"]


# ── App ───────────────────────────────────────────────────────────────────────
class QRGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._qr_image: Image.Image | None = None
        self._debounce_id: str | None = None
        self._active_type = "URL"
        self._primary_input: tk.Text | None = None

        self._configure_window()
        self._build_ui()

    # ── Window ────────────────────────────────────────────────────────────────
    def _configure_window(self) -> None:
        self.root.title("QR Generator")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        w, h = 960, 640
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    # ── Top-level layout ──────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        # Black header bar
        hdr = tk.Frame(self.root, bg=BLACK, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="QR Code Generator", bg=BLACK, fg=WHITE,
                 font=(FONT, 15, "bold")).pack(side="left", padx=24)
        tk.Label(hdr, text="v2.0", bg=BLACK, fg=GREY_MID,
                 font=(FONT, 10)).pack(side="left")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        # Left panel — fixed width
        left = tk.Frame(body, bg=BG, width=430)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._build_left(left)

        # Divider
        tk.Frame(body, bg=GREY_LIGHT, width=1).pack(side="left", fill="y")

        # Right panel — expands
        right = tk.Frame(body, bg=WHITE)
        right.pack(side="left", fill="both", expand=True)
        self._build_right(right)

    # ── Left panel ────────────────────────────────────────────────────────────
    def _build_left(self, parent: tk.Frame) -> None:
        pad = tk.Frame(parent, bg=BG)
        pad.pack(fill="both", expand=True, padx=24, pady=20)

        # Content type selector
        tk.Label(pad, text="CONTENT TYPE", bg=BG, fg=GREY_MID,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(0, 8))

        type_bar = tk.Frame(pad, bg=BG)
        type_bar.pack(fill="x", pady=(0, 20))

        self._type_btns: dict[str, tk.Button] = {}
        for t in TYPES:
            btn = tk.Button(
                type_bar, text=t, font=(FONT, 10),
                relief="flat", bd=0, padx=12, pady=6,
                cursor="hand2", command=lambda x=t: self._switch_type(x),
            )
            btn.pack(side="left", padx=(0, 4))
            self._type_btns[t] = btn
        self._refresh_type_btns()

        # Dynamic form area
        self._form = tk.Frame(pad, bg=BG)
        self._form.pack(fill="x")
        self._form.columnconfigure(0, weight=1)

        # Error correction dropdown
        tk.Label(pad, text="ERROR CORRECTION", bg=BG, fg=GREY_MID,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(20, 6))
        self._ec_var = tk.StringVar(value=list(EC_LEVELS.keys())[1])
        ec = ttk.Combobox(pad, textvariable=self._ec_var,
                          values=list(EC_LEVELS.keys()),
                          state="readonly", font=(FONT, 11))
        ec.pack(fill="x")
        ec.bind("<<ComboboxSelected>>", lambda _e: self._generate_qr())
        self._style_combobox()

        # Inline feedback label
        self._err_lbl = tk.Label(pad, text="", bg=BG, fg=GREY_DARK,
                                  font=(FONT, 10), wraplength=370, justify="left")
        self._err_lbl.pack(anchor="w", pady=(6, 0))

        # Generate — primary button (black bg, always visible)
        tk.Button(
            pad, text="Generate QR Code",
            command=self._generate_qr,
            font=(FONT, 13, "bold"),
            bg=BLACK, fg=WHITE,
            activebackground=GREY_DARK, activeforeground=WHITE,
            relief="flat", bd=0, pady=13, cursor="hand2",
        ).pack(fill="x", pady=(18, 8))

        # Secondary row
        sec = tk.Frame(pad, bg=BG)
        sec.pack(fill="x")
        sec.columnconfigure((0, 1), weight=1)
        self._sec_btn(sec, "Copy to Clipboard", self._copy_clipboard).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        self._sec_btn(sec, "Clear", self._clear).grid(
            row=0, column=1, sticky="ew", padx=(4, 0))

        self._build_form()

    # ── Right panel ───────────────────────────────────────────────────────────
    def _build_right(self, parent: tk.Frame) -> None:
        self._canvas = tk.Canvas(parent, bg=WHITE, bd=0, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True, padx=30, pady=(30, 16))
        self._show_placeholder()

        btns = tk.Frame(parent, bg=WHITE)
        btns.pack(fill="x", padx=30, pady=(0, 24))
        btns.columnconfigure((0, 1), weight=1)
        self._sec_btn(btns, "Save as PNG", self._save_png).grid(
            row=0, column=0, sticky="ew", padx=(0, 6), ipady=5)
        self._sec_btn(btns, "Save as JPEG", self._save_jpeg).grid(
            row=0, column=1, sticky="ew", padx=(6, 0), ipady=5)

    # ── Form builders ─────────────────────────────────────────────────────────
    def _clear_form(self) -> None:
        for w in self._form.winfo_children():
            w.destroy()

    def _build_form(self) -> None:
        self._clear_form()
        self._form.columnconfigure(0, weight=1)
        {
            "URL":   self._form_url,
            "Text":  self._form_text,
            "WiFi":  self._form_wifi,
            "Email": self._form_email,
            "SMS":   self._form_sms,
        }[self._active_type]()

    def _form_url(self) -> None:
        self._flabel(self._form, "URL").grid(row=0, column=0, sticky="w", pady=(0, 5))
        inp = self._textarea(self._form, height=5)
        inp.grid(row=1, column=0, sticky="ew")
        ctr = self._ctrlabel(self._form)
        ctr.grid(row=2, column=0, sticky="e", pady=(3, 0))
        inp.bind("<KeyRelease>", lambda _e: (self._update_ctr(inp, ctr), self._debounce()))
        self._primary_input = inp

    def _form_text(self) -> None:
        self._flabel(self._form, "Plain Text").grid(row=0, column=0, sticky="w", pady=(0, 5))
        inp = self._textarea(self._form, height=5)
        inp.grid(row=1, column=0, sticky="ew")
        ctr = self._ctrlabel(self._form)
        ctr.grid(row=2, column=0, sticky="e", pady=(3, 0))
        inp.bind("<KeyRelease>", lambda _e: (self._update_ctr(inp, ctr), self._debounce()))
        self._primary_input = inp

    def _form_wifi(self) -> None:
        self._primary_input = None
        self._wifi_ssid = self._entry_row(self._form, "Network Name (SSID)", lrow=0, erow=1)
        self._wifi_pw   = self._entry_row(self._form, "Password", lrow=2, erow=3, show="•")

        self._flabel(self._form, "Security").grid(row=4, column=0, sticky="w", pady=(12, 5))
        self._wifi_enc = tk.StringVar(value="WPA/WPA2")
        sf = tk.Frame(self._form, bg=BG)
        sf.grid(row=5, column=0, sticky="w")
        for i, enc in enumerate(["WPA/WPA2", "WEP", "None"]):
            tk.Radiobutton(sf, text=enc, variable=self._wifi_enc, value=enc,
                          bg=BG, fg=BLACK, activebackground=BG, selectcolor=BG,
                          font=(FONT, 11), command=self._debounce,
                          ).grid(row=0, column=i, padx=(0, 12))

        self._wifi_hidden = tk.BooleanVar()
        tk.Checkbutton(self._form, text="Hidden network",
                      variable=self._wifi_hidden,
                      bg=BG, fg=GREY_DARK, activebackground=BG,
                      selectcolor=WHITE, font=(FONT, 10),
                      command=self._debounce,
                      ).grid(row=6, column=0, sticky="w", pady=(10, 0))

        for w in [self._wifi_ssid, self._wifi_pw]:
            w.bind("<KeyRelease>", lambda _e: self._debounce())

    def _form_email(self) -> None:
        self._primary_input = None
        self._email_to      = self._entry_row(self._form, "To (email address)", lrow=0, erow=1)
        self._email_subject = self._entry_row(self._form, "Subject", lrow=2, erow=3)
        self._flabel(self._form, "Body (optional)").grid(row=4, column=0, sticky="w", pady=(12, 5))
        self._email_body = self._textarea(self._form, height=3)
        self._email_body.grid(row=5, column=0, sticky="ew")
        for w in [self._email_to, self._email_subject, self._email_body]:
            w.bind("<KeyRelease>", lambda _e: self._debounce())

    def _form_sms(self) -> None:
        self._primary_input = None
        self._sms_number = self._entry_row(self._form, "Phone Number", lrow=0, erow=1)
        self._flabel(self._form, "Message").grid(row=2, column=0, sticky="w", pady=(12, 5))
        self._sms_msg = self._textarea(self._form, height=3)
        self._sms_msg.grid(row=3, column=0, sticky="ew")
        for w in [self._sms_number, self._sms_msg]:
            w.bind("<KeyRelease>", lambda _e: self._debounce())

    # ── Widget factories ──────────────────────────────────────────────────────
    def _flabel(self, p: tk.Frame, text: str) -> tk.Label:
        return tk.Label(p, text=text, bg=BG, fg=GREY_DARK, font=(FONT, 10, "bold"))

    def _entry_row(self, p: tk.Frame, label: str, *, lrow: int, erow: int, **kwargs) -> tk.Entry:
        top_pad = 12 if lrow > 0 else 0
        self._flabel(p, label).grid(row=lrow, column=0, sticky="w", pady=(top_pad, 5))
        e = tk.Entry(p, font=(FONT, 12), bg=WHITE, fg=BLACK,
                    insertbackground=BLACK, relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=GREY_LIGHT,
                    highlightcolor=GREY_DARK, **kwargs)
        e.grid(row=erow, column=0, sticky="ew", ipady=7)
        return e

    def _textarea(self, p: tk.Frame, height: int = 5) -> tk.Text:
        return tk.Text(p, height=height, wrap="word", font=(FONT, 12),
                      bg=WHITE, fg=BLACK, insertbackground=BLACK,
                      relief="flat", bd=0, padx=10, pady=8,
                      highlightthickness=1, highlightbackground=GREY_LIGHT,
                      highlightcolor=GREY_DARK)

    def _ctrlabel(self, p: tk.Frame) -> tk.Label:
        return tk.Label(p, text="0 chars", bg=BG, fg=GREY_MID, font=(FONT, 9))

    def _sec_btn(self, parent: tk.Frame, text: str, command) -> tk.Button:
        btn = tk.Button(parent, text=text, command=command,
                       font=(FONT, 10), bg=WHITE, fg=BLACK,
                       activebackground=BLACK, activeforeground=WHITE,
                       relief="flat", bd=0, pady=9,
                       highlightthickness=1, highlightbackground=GREY_LIGHT,
                       cursor="hand2")
        btn.bind("<Enter>", lambda _e: btn.configure(bg=BLACK, fg=WHITE))
        btn.bind("<Leave>", lambda _e: btn.configure(bg=WHITE, fg=BLACK))
        return btn

    def _style_combobox(self) -> None:
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TCombobox",
                   fieldbackground=WHITE, background=WHITE,
                   foreground=BLACK, selectbackground=GREY_LIGHT,
                   selectforeground=BLACK, bordercolor=GREY_LIGHT,
                   arrowcolor=GREY_DARK, relief="flat")

    def _refresh_type_btns(self) -> None:
        for t, btn in self._type_btns.items():
            if t == self._active_type:
                btn.configure(bg=BLACK, fg=WHITE,
                             activebackground=GREY_DARK, activeforeground=WHITE,
                             highlightthickness=0)
            else:
                btn.configure(bg=WHITE, fg=GREY_DARK,
                             activebackground=BLACK, activeforeground=WHITE,
                             highlightthickness=1, highlightbackground=GREY_LIGHT)

    @staticmethod
    def _update_ctr(widget: tk.Text, label: tk.Label) -> None:
        label.configure(text=f"{len(widget.get('1.0', 'end-1c'))} chars")

    def _show_placeholder(self) -> None:
        self._canvas.delete("all")
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width() or 420
        ch = self._canvas.winfo_height() or 460
        self._canvas.create_text(
            cw // 2, ch // 2,
            text="Your QR code\nwill appear here",
            fill=GREY_LIGHT, font=(FONT, 14), justify="center",
        )

    def _set_status(self, msg: str) -> None:
        self._err_lbl.configure(text=msg)

    # ── Events ────────────────────────────────────────────────────────────────
    def _switch_type(self, t: str) -> None:
        self._active_type = t
        self._refresh_type_btns()
        self._set_status("")
        self._qr_image = None
        self._show_placeholder()
        self._build_form()

    def _debounce(self) -> None:
        if self._debounce_id:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = self.root.after(DEBOUNCE_MS, self._generate_qr)

    def _get_content(self) -> str:
        t = self._active_type
        if t in ("URL", "Text"):
            return self._primary_input.get("1.0", "end-1c").strip()  # type: ignore[union-attr]
        if t == "WiFi":
            ssid = self._wifi_ssid.get().strip()
            if not ssid:
                return ""
            enc = {"WPA/WPA2": "WPA", "WEP": "WEP", "None": "nopass"}[self._wifi_enc.get()]
            hidden = ";H:true" if self._wifi_hidden.get() else ""
            return f"WIFI:T:{enc};S:{ssid};P:{self._wifi_pw.get()}{hidden};;"
        if t == "Email":
            to = self._email_to.get().strip()
            if not to:
                return ""
            sub  = self._email_subject.get().strip()
            body = self._email_body.get("1.0", "end-1c").strip()
            params = ([f"subject={sub}"] if sub else []) + ([f"body={body}"] if body else [])
            return f"mailto:{to}" + ("?" + "&".join(params) if params else "")
        if t == "SMS":
            num = self._sms_number.get().strip()
            if not num:
                return ""
            return f"smsto:{num}:{self._sms_msg.get('1.0', 'end-1c').strip()}"
        return ""

    # ── QR generation ─────────────────────────────────────────────────────────
    def _generate_qr(self) -> None:
        content = self._get_content()
        self._set_status("")
        if not content:
            self._qr_image = None
            self._show_placeholder()
            return
        try:
            qr = qrcode.QRCode(
                error_correction=EC_LEVELS[self._ec_var.get()],
                box_size=10, border=4,
            )
            qr.add_data(content)
            qr.make(fit=True)
        except qrcode.exceptions.DataOverflowError:
            self._set_status("Content too long for the selected error correction level.")
            return
        except Exception as exc:
            self._set_status(f"Error: {exc}")
            return
        self._qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        self._render_preview()

    def _render_preview(self) -> None:
        if not self._qr_image:
            return
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width() or 420
        ch = self._canvas.winfo_height() or 460
        size = min(cw, ch) - 20
        thumb = self._qr_image.copy()
        thumb.thumbnail((size, size), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(thumb)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, anchor="center", image=self._tk_img)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _copy_clipboard(self) -> None:
        if not self._qr_image:
            self._set_status("Generate a QR code first.")
            return
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = f.name
        self._qr_image.resize((800, 800), Image.LANCZOS).save(tmp, "PNG")
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'set the clipboard to (read (POSIX file "{tmp}") as TIFF picture)'],
                check=True, capture_output=True,
            )
            self._set_status("Copied to clipboard.")
        except Exception:
            self._set_status("Copy failed — try saving instead.")
        finally:
            os.unlink(tmp)

    def _save_png(self) -> None:
        self._save("png")

    def _save_jpeg(self) -> None:
        self._save("jpeg")

    def _save(self, fmt: str) -> None:
        if not self._qr_image:
            self._set_status("Generate a QR code first.")
            return
        ext = "jpg" if fmt == "jpeg" else "png"
        path = filedialog.asksaveasfilename(
            defaultextension=f".{ext}",
            filetypes=[("JPEG", "*.jpg")] if fmt == "jpeg" else [("PNG", "*.png")],
            title=f"Save as {fmt.upper()}",
        )
        if not path:
            return
        out = self._qr_image.resize((800, 800), Image.LANCZOS)
        out.save(path, "JPEG", quality=95) if fmt == "jpeg" else out.save(path, "PNG")
        self._set_status(f"Saved → {path}")

    def _clear(self) -> None:
        t = self._active_type
        try:
            if t in ("URL", "Text"):
                self._primary_input.delete("1.0", "end")  # type: ignore[union-attr]
            elif t == "WiFi":
                self._wifi_ssid.delete(0, "end")
                self._wifi_pw.delete(0, "end")
            elif t == "Email":
                self._email_to.delete(0, "end")
                self._email_subject.delete(0, "end")
                self._email_body.delete("1.0", "end")
            elif t == "SMS":
                self._sms_number.delete(0, "end")
                self._sms_msg.delete("1.0", "end")
        except Exception:
            pass
        self._set_status("")
        self._qr_image = None
        self._show_placeholder()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = QRGeneratorApp(root)
    root.mainloop()
