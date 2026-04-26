"""
QR Code Generator — Desktop App v3.0
Features: 9 content types · dark mode · history · colour slider
          SVG export · batch ZIP · logo overlay · print · auto-detect
"""

import tkinter as tk
from tkinter import filedialog, ttk
import qrcode
import qrcode.image.svg as qr_svg
from PIL import Image, ImageTk
import subprocess, tempfile, os, re, zipfile, io

# ── Palettes ──────────────────────────────────────────────────────────────────
LIGHT = dict(bg="#F5F5F5", surface="#FFFFFF", ink="#0A0A0A",
             border="#E0E0E0", muted="#888888", subtle="#2A2A2A")
DARK  = dict(bg="#141414", surface="#1F1F1F", ink="#F0F0F0",
             border="#333333", muted="#666666", subtle="#BBBBBB")

FONT        = "Helvetica Neue"
DEBOUNCE_MS = 300
HISTORY_MAX = 8

EC_LEVELS = {
    "L — Low (7%)":        qrcode.constants.ERROR_CORRECT_L,
    "M — Medium (15%)":    qrcode.constants.ERROR_CORRECT_M,
    "Q — Quartile (25%)":  qrcode.constants.ERROR_CORRECT_Q,
    "H — High (30%)":      qrcode.constants.ERROR_CORRECT_H,
}
EC_KEYS = list(EC_LEVELS.keys())

EXPORT_SIZES = {"400 px": 400, "800 px": 800, "1200 px": 1200, "2400 px": 2400}

TYPE_ROWS = [
    ("URL", "Text", "WiFi", "Email", "SMS"),
    ("vCard", "GPS", "Calendar", "Batch"),
]
ALL_TYPES = [t for row in TYPE_ROWS for t in row]


# ── App ───────────────────────────────────────────────────────────────────────
class QRGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root

        # persistent state
        self._dark            = False
        self._pal             = LIGHT.copy()
        self._active_type     = "URL"
        self._qr_image: Image.Image | None = None
        self._qr_content      = ""
        self._debounce_id: str | None = None
        self._primary_input: tk.Text | None = None
        self._history: list[dict] = []
        self._logo_path: str | None = None
        self._form_values: dict   = {}

        # shared tkinter vars (survive theme rebuild)
        self._fg_grey  = tk.IntVar(value=10)       # 10 = #0a0a0a … 136 = #888888
        self._ec_var   = tk.StringVar(value=EC_KEYS[1])
        self._size_var = tk.StringVar(value="800 px")

        self._configure_window()
        self._build_header()
        self._build_body()

    # ── Window ────────────────────────────────────────────────────────────────
    def _configure_window(self) -> None:
        self.root.title("QR Generator")
        self.root.resizable(False, False)
        w, h = 1100, 720
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.root.configure(bg=self._p("bg"))

    # ── Palette helper ────────────────────────────────────────────────────────
    def _p(self, key: str) -> str:
        return self._pal[key]

    def _fg_color(self) -> str:
        v = self._fg_grey.get()
        return f"#{v:02x}{v:02x}{v:02x}"

    # ── Header (never rebuilt) ────────────────────────────────────────────────
    def _build_header(self) -> None:
        hdr = tk.Frame(self.root, bg="#0A0A0A", height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="QR Code Generator", bg="#0A0A0A", fg="#FFFFFF",
                 font=(FONT, 15, "bold")).pack(side="left", padx=24)
        tk.Label(hdr, text="v3.0", bg="#0A0A0A", fg="#888888",
                 font=(FONT, 10)).pack(side="left")
        self._dark_btn = tk.Button(
            hdr, text="◐  Dark Mode", command=self._toggle_dark,
            font=(FONT, 10), bg="#0A0A0A", fg="#888888",
            activebackground="#0A0A0A", activeforeground="#FFFFFF",
            relief="flat", bd=0, padx=12, pady=6, cursor="hand2")
        self._dark_btn.pack(side="right", padx=16)

    # ── Body (rebuilt on theme change) ────────────────────────────────────────
    def _build_body(self) -> None:
        self._body = tk.Frame(self.root, bg=self._p("bg"))
        self._body.pack(fill="both", expand=True)

        left_wrap = tk.Frame(self._body, bg=self._p("bg"), width=490)
        left_wrap.pack(side="left", fill="y")
        left_wrap.pack_propagate(False)
        self._build_left(left_wrap)

        tk.Frame(self._body, bg=self._p("border"), width=1).pack(side="left", fill="y")

        right_wrap = tk.Frame(self._body, bg=self._p("surface"))
        right_wrap.pack(side="left", fill="both", expand=True)
        self._build_right(right_wrap)

    # ── Dark mode ─────────────────────────────────────────────────────────────
    def _toggle_dark(self) -> None:
        self._capture_form()
        self._dark = not self._dark
        self._pal  = DARK.copy() if self._dark else LIGHT.copy()
        self.root.configure(bg=self._p("bg"))
        self._dark_btn.configure(text="◑  Light Mode" if self._dark else "◐  Dark Mode")
        saved_img  = self._qr_image
        saved_cont = self._qr_content
        self._body.destroy()
        self._build_body()
        self._qr_image   = saved_img
        self._qr_content = saved_cont
        self._restore_form_partial()
        if saved_img:
            self._render_preview()

    # ── Left panel (scrollable) ───────────────────────────────────────────────
    def _build_left(self, parent: tk.Frame) -> None:
        cv = tk.Canvas(parent, bg=self._p("bg"), highlightthickness=0)
        sb = tk.Scrollbar(parent, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(cv, bg=self._p("bg"))
        win_id = cv.create_window((0, 0), window=inner, anchor="nw")

        def _sync_width(e):
            cv.itemconfigure(win_id, width=e.width)
        def _sync_scroll(e):
            cv.configure(scrollregion=cv.bbox("all"))

        cv.bind("<Configure>", _sync_width)
        inner.bind("<Configure>", _sync_scroll)
        cv.bind("<MouseWheel>",
                lambda e: cv.yview_scroll(-1 * (e.delta // 120), "units"))

        pad = tk.Frame(inner, bg=self._p("bg"))
        pad.pack(fill="both", expand=True, padx=22, pady=18)

        # ── Type selector ──────────────────────────────────────────────────
        tk.Label(pad, text="CONTENT TYPE", bg=self._p("bg"), fg=self._p("muted"),
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(0, 6))
        self._type_btns: dict[str, tk.Button] = {}
        for row_types in TYPE_ROWS:
            row = tk.Frame(pad, bg=self._p("bg"))
            row.pack(fill="x", pady=(0, 3))
            for t in row_types:
                btn = tk.Button(row, text=t, font=(FONT, 10),
                               relief="flat", bd=0, padx=10, pady=5,
                               cursor="hand2", command=lambda x=t: self._switch_type(x))
                btn.pack(side="left", padx=(0, 3))
                self._type_btns[t] = btn
        self._refresh_type_btns()

        # ── Dynamic form ───────────────────────────────────────────────────
        self._form = tk.Frame(pad, bg=self._p("bg"))
        self._form.pack(fill="x", pady=(14, 0))
        self._form.columnconfigure(0, weight=1)

        # ── QR foreground colour ───────────────────────────────────────────
        crow = tk.Frame(pad, bg=self._p("bg"))
        crow.pack(fill="x", pady=(16, 0))
        tk.Label(crow, text="QR COLOUR", bg=self._p("bg"), fg=self._p("muted"),
                 font=(FONT, 9, "bold")).pack(side="left")
        self._color_dot = tk.Label(crow, text="  ", bg=self._fg_color(),
                                    width=3, relief="flat")
        self._color_dot.pack(side="right")
        tk.Scale(pad, from_=10, to=136, orient="horizontal",
                variable=self._fg_grey,
                bg=self._p("bg"), fg=self._p("subtle"), troughcolor=self._p("border"),
                highlightthickness=0, showvalue=False, relief="flat",
                command=lambda _: (
                    self._color_dot.configure(bg=self._fg_color()),
                    self._debounce()),
                ).pack(fill="x")

        # ── Error correction ───────────────────────────────────────────────
        tk.Label(pad, text="ERROR CORRECTION", bg=self._p("bg"), fg=self._p("muted"),
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(14, 4))
        ec = ttk.Combobox(pad, textvariable=self._ec_var, values=EC_KEYS,
                          state="readonly", font=(FONT, 10))
        ec.pack(fill="x")
        ec.bind("<<ComboboxSelected>>", lambda _: self._generate_qr())

        # ── Export size ────────────────────────────────────────────────────
        tk.Label(pad, text="EXPORT SIZE", bg=self._p("bg"), fg=self._p("muted"),
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(12, 4))
        ttk.Combobox(pad, textvariable=self._size_var,
                     values=list(EXPORT_SIZES.keys()),
                     state="readonly", font=(FONT, 10)).pack(fill="x")
        self._style_combobox()

        # ── Status label ───────────────────────────────────────────────────
        self._status_lbl = tk.Label(pad, text="", bg=self._p("bg"), fg=self._p("subtle"),
                                     font=(FONT, 10), wraplength=430, justify="left")
        self._status_lbl.pack(anchor="w", pady=(8, 0))

        # ── Generate (primary) ─────────────────────────────────────────────
        tk.Button(pad, text="Generate QR Code", command=self._generate_qr,
                 font=(FONT, 13, "bold"),
                 bg=self._p("ink"), fg=self._p("surface"),
                 activebackground=self._p("subtle"), activeforeground=self._p("surface"),
                 relief="flat", bd=0, pady=13, cursor="hand2",
                 ).pack(fill="x", pady=(16, 8))

        # ── Secondary buttons ──────────────────────────────────────────────
        r1 = tk.Frame(pad, bg=self._p("bg"))
        r1.pack(fill="x")
        r1.columnconfigure((0, 1, 2), weight=1)
        self._sec_btn(r1, "Copy Image", self._copy_image).grid(
            row=0, column=0, sticky="ew", padx=(0, 3), ipady=4)
        self._sec_btn(r1, "Copy Text",  self._copy_raw).grid(
            row=0, column=1, sticky="ew", padx=(3, 3), ipady=4)
        self._sec_btn(r1, "Print",      self._print_qr).grid(
            row=0, column=2, sticky="ew", padx=(3, 0), ipady=4)

        r2 = tk.Frame(pad, bg=self._p("bg"))
        r2.pack(fill="x", pady=(6, 0))
        r2.columnconfigure((0, 1), weight=1)
        self._sec_btn(r2, "Set Logo", self._pick_logo).grid(
            row=0, column=0, sticky="ew", padx=(0, 3), ipady=4)
        self._sec_btn(r2, "Clear",    self._clear).grid(
            row=0, column=1, sticky="ew", padx=(3, 0), ipady=4)

        self._build_form()

    # ── Right panel ───────────────────────────────────────────────────────────
    def _build_right(self, parent: tk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(parent, bg=self._p("surface"), bd=0, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew", padx=24, pady=(20, 8))
        self._show_placeholder()

        # Logo info
        self._logo_lbl = tk.Label(parent, text="", bg=self._p("surface"),
                                   fg=self._p("muted"), font=(FONT, 9))
        self._logo_lbl.grid(row=1, column=0, sticky="w", padx=28)

        # Save buttons
        sf = tk.Frame(parent, bg=self._p("surface"))
        sf.grid(row=2, column=0, sticky="ew", padx=24, pady=(6, 10))
        sf.columnconfigure((0, 1, 2), weight=1)
        self._sec_btn(sf, "Save PNG",  self._save_png).grid(
            row=0, column=0, sticky="ew", padx=(0, 4), ipady=5)
        self._sec_btn(sf, "Save JPEG", self._save_jpeg).grid(
            row=0, column=1, sticky="ew", padx=(4, 4), ipady=5)
        self._sec_btn(sf, "Save SVG",  self._save_svg).grid(
            row=0, column=2, sticky="ew", padx=(4, 0), ipady=5)

        # History strip
        tk.Label(parent, text="RECENT", bg=self._p("surface"), fg=self._p("muted"),
                 font=(FONT, 8, "bold")).grid(row=3, column=0, sticky="w", padx=28)
        self._hist_frame = tk.Frame(parent, bg=self._p("surface"))
        self._hist_frame.grid(row=4, column=0, sticky="ew", padx=24, pady=(4, 16))
        self._render_history()

    # ── Form builders ─────────────────────────────────────────────────────────
    def _clear_form(self) -> None:
        for w in self._form.winfo_children():
            w.destroy()

    def _build_form(self) -> None:
        self._clear_form()
        self._form.columnconfigure(0, weight=1)
        self._primary_input = None
        {
            "URL":      self._form_url,
            "Text":     self._form_text,
            "WiFi":     self._form_wifi,
            "Email":    self._form_email,
            "SMS":      self._form_sms,
            "vCard":    self._form_vcard,
            "GPS":      self._form_gps,
            "Calendar": self._form_calendar,
            "Batch":    self._form_batch,
        }[self._active_type]()

    def _form_url(self) -> None:
        self._flabel(self._form, "URL").grid(row=0, column=0, sticky="w", pady=(0, 4))
        inp = self._textarea(self._form, height=4)
        inp.grid(row=1, column=0, sticky="ew")
        ctr = self._ctrlabel(self._form)
        ctr.grid(row=2, column=0, sticky="e", pady=(2, 0))
        inp.bind("<KeyRelease>",
                 lambda _: (self._update_ctr(inp, ctr), self._auto_detect(inp), self._debounce()))
        self._primary_input = inp

    def _form_text(self) -> None:
        self._flabel(self._form, "Plain Text").grid(row=0, column=0, sticky="w", pady=(0, 4))
        inp = self._textarea(self._form, height=4)
        inp.grid(row=1, column=0, sticky="ew")
        ctr = self._ctrlabel(self._form)
        ctr.grid(row=2, column=0, sticky="e", pady=(2, 0))
        inp.bind("<KeyRelease>", lambda _: (self._update_ctr(inp, ctr), self._debounce()))
        self._primary_input = inp

    def _form_wifi(self) -> None:
        self._wifi_ssid = self._entry_row(self._form, "Network Name (SSID)", 0, 1)
        self._wifi_pw   = self._entry_row(self._form, "Password",            2, 3, show="•")
        self._flabel(self._form, "Security").grid(row=4, column=0, sticky="w", pady=(10, 4))
        self._wifi_enc = tk.StringVar(value="WPA/WPA2")
        sf = tk.Frame(self._form, bg=self._p("bg"))
        sf.grid(row=5, column=0, sticky="w")
        for i, enc in enumerate(["WPA/WPA2", "WEP", "None"]):
            tk.Radiobutton(sf, text=enc, variable=self._wifi_enc, value=enc,
                          bg=self._p("bg"), fg=self._p("ink"),
                          activebackground=self._p("bg"), selectcolor=self._p("bg"),
                          font=(FONT, 10), command=self._debounce,
                          ).grid(row=0, column=i, padx=(0, 10))
        self._wifi_hidden = tk.BooleanVar()
        tk.Checkbutton(self._form, text="Hidden network", variable=self._wifi_hidden,
                      bg=self._p("bg"), fg=self._p("subtle"),
                      activebackground=self._p("bg"), selectcolor=self._p("surface"),
                      font=(FONT, 10), command=self._debounce,
                      ).grid(row=6, column=0, sticky="w", pady=(8, 0))
        for w in [self._wifi_ssid, self._wifi_pw]:
            w.bind("<KeyRelease>", lambda _: self._debounce())

    def _form_email(self) -> None:
        self._email_to      = self._entry_row(self._form, "To",      0, 1)
        self._email_subject = self._entry_row(self._form, "Subject", 2, 3)
        self._flabel(self._form, "Body").grid(row=4, column=0, sticky="w", pady=(10, 4))
        self._email_body = self._textarea(self._form, height=3)
        self._email_body.grid(row=5, column=0, sticky="ew")
        for w in [self._email_to, self._email_subject, self._email_body]:
            w.bind("<KeyRelease>", lambda _: self._debounce())

    def _form_sms(self) -> None:
        self._sms_number = self._entry_row(self._form, "Phone Number", 0, 1)
        self._flabel(self._form, "Message").grid(row=2, column=0, sticky="w", pady=(10, 4))
        self._sms_msg = self._textarea(self._form, height=3)
        self._sms_msg.grid(row=3, column=0, sticky="ew")
        for w in [self._sms_number, self._sms_msg]:
            w.bind("<KeyRelease>", lambda _: self._debounce())

    def _form_vcard(self) -> None:
        self._vc_name  = self._entry_row(self._form, "Full Name",    0, 1)
        self._vc_phone = self._entry_row(self._form, "Phone",        2, 3)
        self._vc_email = self._entry_row(self._form, "Email",        4, 5)
        self._vc_org   = self._entry_row(self._form, "Organisation", 6, 7)
        self._vc_url   = self._entry_row(self._form, "Website",      8, 9)
        for w in [self._vc_name, self._vc_phone, self._vc_email, self._vc_org, self._vc_url]:
            w.bind("<KeyRelease>", lambda _: self._debounce())

    def _form_gps(self) -> None:
        self._gps_lat   = self._entry_row(self._form, "Latitude  (e.g. 38.7169)", 0, 1)
        self._gps_lon   = self._entry_row(self._form, "Longitude (e.g. -9.1399)", 2, 3)
        self._gps_label = self._entry_row(self._form, "Label (optional)",         4, 5)
        for w in [self._gps_lat, self._gps_lon, self._gps_label]:
            w.bind("<KeyRelease>", lambda _: self._debounce())

    def _form_calendar(self) -> None:
        self._cal_title = self._entry_row(self._form, "Event Title",              0, 1)
        self._cal_start = self._entry_row(self._form, "Start  (YYYYMMDDTHHMMSS)", 2, 3)
        self._cal_end   = self._entry_row(self._form, "End    (YYYYMMDDTHHMMSS)", 4, 5)
        self._cal_loc   = self._entry_row(self._form, "Location",                 6, 7)
        for w in [self._cal_title, self._cal_start, self._cal_end, self._cal_loc]:
            w.bind("<KeyRelease>", lambda _: self._debounce())

    def _form_batch(self) -> None:
        self._flabel(self._form, "Items — one per line").grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        inp = self._textarea(self._form, height=5)
        inp.grid(row=1, column=0, sticky="ew")
        ctr = self._ctrlabel(self._form)
        ctr.grid(row=2, column=0, sticky="e", pady=(2, 0))
        inp.bind("<KeyRelease>", lambda _: (self._update_ctr(inp, ctr), self._debounce()))
        self._primary_input = inp
        self._sec_btn(self._form, "Export all as ZIP", self._batch_export).grid(
            row=3, column=0, sticky="ew", pady=(10, 0), ipady=4)

    # ── Widget factories ──────────────────────────────────────────────────────
    def _flabel(self, p: tk.Frame, text: str) -> tk.Label:
        return tk.Label(p, text=text, bg=self._p("bg"), fg=self._p("subtle"),
                       font=(FONT, 10, "bold"))

    def _entry_row(self, p: tk.Frame, label: str,
                   lrow: int, erow: int, **kw) -> tk.Entry:
        top = 10 if lrow > 0 else 0
        self._flabel(p, label).grid(row=lrow, column=0, sticky="w", pady=(top, 4))
        e = tk.Entry(p, font=(FONT, 11), bg=self._p("surface"), fg=self._p("ink"),
                    insertbackground=self._p("ink"), relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=self._p("border"),
                    highlightcolor=self._p("subtle"), **kw)
        e.grid(row=erow, column=0, sticky="ew", ipady=6)
        return e

    def _textarea(self, p: tk.Frame, height: int = 4) -> tk.Text:
        return tk.Text(p, height=height, wrap="word", font=(FONT, 11),
                      bg=self._p("surface"), fg=self._p("ink"),
                      insertbackground=self._p("ink"),
                      relief="flat", bd=0, padx=10, pady=8,
                      highlightthickness=1, highlightbackground=self._p("border"),
                      highlightcolor=self._p("subtle"))

    def _ctrlabel(self, p: tk.Frame) -> tk.Label:
        return tk.Label(p, text="0 chars", bg=self._p("bg"),
                       fg=self._p("muted"), font=(FONT, 9))

    def _sec_btn(self, parent: tk.Frame, text: str, command) -> tk.Button:
        ink, sur, brd = self._p("ink"), self._p("surface"), self._p("border")
        btn = tk.Button(parent, text=text, command=command,
                       font=(FONT, 10), bg=sur, fg=ink,
                       activebackground=ink, activeforeground=sur,
                       relief="flat", bd=0, pady=8,
                       highlightthickness=1, highlightbackground=brd,
                       cursor="hand2")
        btn.bind("<Enter>", lambda _: btn.configure(bg=ink, fg=sur))
        btn.bind("<Leave>", lambda _: btn.configure(bg=sur, fg=ink))
        return btn

    def _style_combobox(self) -> None:
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TCombobox",
                   fieldbackground=self._p("surface"), background=self._p("surface"),
                   foreground=self._p("ink"), selectbackground=self._p("border"),
                   selectforeground=self._p("ink"), bordercolor=self._p("border"),
                   arrowcolor=self._p("subtle"), relief="flat")

    def _refresh_type_btns(self) -> None:
        ink, sur, bg, brd = (self._p("ink"), self._p("surface"),
                              self._p("bg"), self._p("border"))
        for t, btn in self._type_btns.items():
            if t == self._active_type:
                btn.configure(bg=ink, fg=sur,
                             activebackground=self._p("subtle"),
                             activeforeground=sur, highlightthickness=0)
            else:
                btn.configure(bg=bg, fg=self._p("muted"),
                             activebackground=ink, activeforeground=sur,
                             highlightthickness=1, highlightbackground=brd)

    @staticmethod
    def _update_ctr(widget: tk.Text, label: tk.Label) -> None:
        label.configure(text=f"{len(widget.get('1.0', 'end-1c'))} chars")

    def _show_placeholder(self) -> None:
        self._canvas.delete("all")
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width() or 500
        ch = self._canvas.winfo_height() or 380
        self._canvas.create_text(cw // 2, ch // 2,
                                 text="Your QR code\nwill appear here",
                                 fill=self._p("border"), font=(FONT, 14),
                                 justify="center")

    def _set_status(self, msg: str) -> None:
        self._status_lbl.configure(text=msg)

    # ── History ───────────────────────────────────────────────────────────────
    def _add_to_history(self, img: Image.Image, content: str, typ: str) -> None:
        if self._history and self._history[0]["content"] == content:
            return
        self._history.insert(0, {"img": img.copy(), "content": content, "type": typ})
        self._history = self._history[:HISTORY_MAX]
        self._render_history()

    def _render_history(self) -> None:
        for w in self._hist_frame.winfo_children():
            w.destroy()
        for entry in self._history:
            thumb = entry["img"].copy()
            thumb.thumbnail((58, 58), Image.LANCZOS)
            tk_img = ImageTk.PhotoImage(thumb)
            btn = tk.Label(self._hist_frame, image=tk_img,
                          bg=self._p("surface"), cursor="hand2",
                          highlightthickness=1,
                          highlightbackground=self._p("border"))
            btn._img = tk_img  # type: ignore[attr-defined]
            btn.pack(side="left", padx=(0, 6))
            btn.bind("<Button-1>", lambda _e, e=entry: self._load_history(e))
            btn.bind("<Enter>", lambda _e, b=btn: b.configure(
                highlightbackground=self._p("subtle")))
            btn.bind("<Leave>", lambda _e, b=btn: b.configure(
                highlightbackground=self._p("border")))

    def _load_history(self, entry: dict) -> None:
        self._qr_image   = entry["img"]
        self._qr_content = entry["content"]
        self._render_preview()
        snippet = entry["content"][:50].replace("\n", " ")
        self._set_status(f"History [{entry['type']}]: {snippet}")

    # ── Auto-detect ───────────────────────────────────────────────────────────
    def _auto_detect(self, widget: tk.Text) -> None:
        text = widget.get("1.0", "end-1c").strip()
        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text):
            self._set_status("Looks like an email address — try the Email tab.")
        elif re.match(r"^\+?[\d\s\-()]{7,20}$", text):
            self._set_status("Looks like a phone number — try the SMS tab.")
        else:
            # clear only if status was a suggestion
            lbl = self._status_lbl.cget("text")
            if lbl.startswith("Looks like"):
                self._set_status("")

    # ── Events ────────────────────────────────────────────────────────────────
    def _switch_type(self, t: str) -> None:
        self._capture_form()
        self._active_type = t
        self._refresh_type_btns()
        self._set_status("")
        self._build_form()
        self._restore_form_partial()

    def _debounce(self) -> None:
        if self._debounce_id:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = self.root.after(DEBOUNCE_MS, self._generate_qr)

    # ── Form state persistence ────────────────────────────────────────────────
    def _capture_form(self) -> None:
        t = self._active_type
        try:
            if t in ("URL", "Text", "Batch"):
                self._form_values[f"{t}_main"] = self._primary_input.get("1.0", "end-1c")  # type: ignore
            elif t == "WiFi":
                self._form_values.update(wifi_ssid=self._wifi_ssid.get(),
                                         wifi_pw=self._wifi_pw.get())
            elif t == "Email":
                self._form_values.update(email_to=self._email_to.get(),
                                         email_subject=self._email_subject.get(),
                                         email_body=self._email_body.get("1.0", "end-1c"))
            elif t == "SMS":
                self._form_values.update(sms_number=self._sms_number.get(),
                                         sms_msg=self._sms_msg.get("1.0", "end-1c"))
            elif t == "vCard":
                self._form_values.update(vc_name=self._vc_name.get(),
                                         vc_phone=self._vc_phone.get(),
                                         vc_email=self._vc_email.get(),
                                         vc_org=self._vc_org.get(),
                                         vc_url=self._vc_url.get())
            elif t == "GPS":
                self._form_values.update(gps_lat=self._gps_lat.get(),
                                         gps_lon=self._gps_lon.get(),
                                         gps_label=self._gps_label.get())
            elif t == "Calendar":
                self._form_values.update(cal_title=self._cal_title.get(),
                                         cal_start=self._cal_start.get(),
                                         cal_end=self._cal_end.get(),
                                         cal_loc=self._cal_loc.get())
        except Exception:
            pass

    def _restore_form_partial(self) -> None:
        t  = self._active_type
        fv = self._form_values

        def _fill_entry(w: tk.Entry, key: str) -> None:
            if key in fv:
                w.delete(0, "end")
                w.insert(0, fv[key])

        def _fill_text(w: tk.Text, key: str) -> None:
            if key in fv:
                w.delete("1.0", "end")
                w.insert("1.0", fv[key])

        try:
            if t in ("URL", "Text", "Batch") and f"{t}_main" in fv and self._primary_input:
                _fill_text(self._primary_input, f"{t}_main")
            elif t == "WiFi":
                _fill_entry(self._wifi_ssid, "wifi_ssid")
                _fill_entry(self._wifi_pw,   "wifi_pw")
            elif t == "Email":
                _fill_entry(self._email_to,      "email_to")
                _fill_entry(self._email_subject,  "email_subject")
                _fill_text(self._email_body,      "email_body")
            elif t == "SMS":
                _fill_entry(self._sms_number, "sms_number")
                _fill_text(self._sms_msg,     "sms_msg")
            elif t == "vCard":
                for key, attr in [("vc_name", "_vc_name"), ("vc_phone", "_vc_phone"),
                                   ("vc_email", "_vc_email"), ("vc_org", "_vc_org"),
                                   ("vc_url", "_vc_url")]:
                    _fill_entry(getattr(self, attr), key)
            elif t == "GPS":
                _fill_entry(self._gps_lat,   "gps_lat")
                _fill_entry(self._gps_lon,   "gps_lon")
                _fill_entry(self._gps_label, "gps_label")
            elif t == "Calendar":
                for key, attr in [("cal_title", "_cal_title"), ("cal_start", "_cal_start"),
                                   ("cal_end", "_cal_end"), ("cal_loc", "_cal_loc")]:
                    _fill_entry(getattr(self, attr), key)
        except Exception:
            pass

    # ── Content assembly ──────────────────────────────────────────────────────
    def _get_content(self) -> str:
        t = self._active_type
        try:
            if t in ("URL", "Text"):
                return self._primary_input.get("1.0", "end-1c").strip()  # type: ignore
            if t == "Batch":
                lines = [l.strip() for l in
                         self._primary_input.get("1.0", "end-1c").splitlines() if l.strip()]  # type: ignore
                return lines[0] if lines else ""   # preview first item only
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
            if t == "vCard":
                name = self._vc_name.get().strip()
                if not name:
                    return ""
                s = f"MECARD:N:{name};"
                if p := self._vc_phone.get().strip(): s += f"TEL:{p};"
                if e := self._vc_email.get().strip(): s += f"EMAIL:{e};"
                if o := self._vc_org.get().strip():   s += f"ORG:{o};"
                if u := self._vc_url.get().strip():   s += f"URL:{u};"
                return s + ";"
            if t == "GPS":
                lat = self._gps_lat.get().strip()
                lon = self._gps_lon.get().strip()
                if not lat or not lon:
                    return ""
                lbl = self._gps_label.get().strip()
                return (f"geo:{lat},{lon}?q={lat},{lon}({lbl})"
                        if lbl else f"geo:{lat},{lon}")
            if t == "Calendar":
                title = self._cal_title.get().strip()
                if not title:
                    return ""
                lines = ["BEGIN:VEVENT", f"SUMMARY:{title}"]
                if s := self._cal_start.get().strip(): lines.append(f"DTSTART:{s}")
                if e := self._cal_end.get().strip():   lines.append(f"DTEND:{e}")
                if l := self._cal_loc.get().strip():   lines.append(f"LOCATION:{l}")
                lines.append("END:VEVENT")
                return "\n".join(lines)
        except Exception:
            pass
        return ""

    # ── QR generation ─────────────────────────────────────────────────────────
    def _generate_qr(self) -> None:
        content = self._get_content()
        self._set_status("")
        if not content:
            self._qr_image   = None
            self._qr_content = ""
            self._show_placeholder()
            return
        try:
            qr = qrcode.QRCode(
                error_correction=EC_LEVELS[self._ec_var.get()],
                box_size=10, border=4)
            qr.add_data(content)
            qr.make(fit=True)
        except qrcode.exceptions.DataOverflowError:
            self._set_status("Content too long for the selected error correction level.")
            return
        except Exception as exc:
            self._set_status(f"Error: {exc}")
            return

        img = qr.make_image(fill_color=self._fg_color(),
                            back_color=self._p("surface")).convert("RGBA")
        if self._logo_path:
            img = self._apply_logo(img)

        self._qr_image   = img.convert("RGB")
        self._qr_content = content
        self._render_preview()
        self._add_to_history(self._qr_image, content, self._active_type)

    def _apply_logo(self, img: Image.Image) -> Image.Image:
        try:
            logo = Image.open(self._logo_path).convert("RGBA")
            qw, qh = img.size
            max_size = int(min(qw, qh) * 0.28)
            logo.thumbnail((max_size, max_size), Image.LANCZOS)
            pos = ((qw - logo.width) // 2, (qh - logo.height) // 2)
            img.paste(logo, pos, logo)
            self._logo_lbl.configure(
                text=f"Logo: {os.path.basename(self._logo_path)}")
        except Exception as exc:
            self._set_status(f"Logo error: {exc}")
        return img

    def _render_preview(self) -> None:
        if not self._qr_image:
            return
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width() or 500
        ch = self._canvas.winfo_height() or 380
        size = min(cw, ch) - 20
        thumb = self._qr_image.copy()
        thumb.thumbnail((size, size), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(thumb)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, anchor="center", image=self._tk_img)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _copy_image(self) -> None:
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
                check=True, capture_output=True)
            self._set_status("Image copied to clipboard.")
        except Exception:
            self._set_status("Copy failed — try saving instead.")
        finally:
            os.unlink(tmp)

    def _copy_raw(self) -> None:
        if not self._qr_content:
            self._set_status("Generate a QR code first.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._qr_content)
        self._set_status("Raw content copied to clipboard.")

    def _print_qr(self) -> None:
        if not self._qr_image:
            self._set_status("Generate a QR code first.")
            return
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = f.name
        self._qr_image.resize((800, 800), Image.LANCZOS).save(tmp, "PNG")
        try:
            subprocess.run(["lpr", tmp], check=True)
            self._set_status("Sent to printer.")
        except Exception:
            self._set_status("Print failed — no printer configured.")
        finally:
            self.root.after(4000,
                            lambda: os.unlink(tmp) if os.path.exists(tmp) else None)

    def _pick_logo(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")],
            title="Choose logo image")
        if not path:
            return
        self._logo_path = path
        self._ec_var.set(EC_KEYS[3])   # force H for logo reliability
        self._set_status("Logo set. Error correction forced to H.")
        self._generate_qr()

    def _save_png(self)  -> None: self._save("png")
    def _save_jpeg(self) -> None: self._save("jpeg")

    def _save(self, fmt: str) -> None:
        if not self._qr_image:
            self._set_status("Generate a QR code first.")
            return
        size = EXPORT_SIZES[self._size_var.get()]
        ext  = "jpg" if fmt == "jpeg" else "png"
        path = filedialog.asksaveasfilename(
            defaultextension=f".{ext}",
            filetypes=[("JPEG", "*.jpg")] if fmt == "jpeg" else [("PNG", "*.png")],
            title=f"Save as {fmt.upper()}")
        if not path:
            return
        out = self._qr_image.resize((size, size), Image.LANCZOS)
        (out.save(path, "JPEG", quality=95)
         if fmt == "jpeg" else out.save(path, "PNG"))
        self._set_status(f"Saved {size}×{size} → {os.path.basename(path)}")

    def _save_svg(self) -> None:
        if not self._qr_content:
            self._set_status("Generate a QR code first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".svg",
            filetypes=[("SVG", "*.svg")],
            title="Save as SVG")
        if not path:
            return
        try:
            qr = qrcode.QRCode(
                error_correction=EC_LEVELS[self._ec_var.get()],
                box_size=10, border=4)
            qr.add_data(self._qr_content)
            qr.make(fit=True)
            img = qr.make_image(image_factory=qr_svg.SvgPathImage)
            img.save(path)
            self._set_status(f"SVG saved → {os.path.basename(path)}")
        except Exception as exc:
            self._set_status(f"SVG error: {exc}")

    def _batch_export(self) -> None:
        if not self._primary_input:
            return
        lines = [l.strip()
                 for l in self._primary_input.get("1.0", "end-1c").splitlines()
                 if l.strip()]
        if not lines:
            self._set_status("Add at least one item per line.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
            title="Save batch ZIP")
        if not path:
            return
        size = EXPORT_SIZES[self._size_var.get()]
        ec   = EC_LEVELS[self._ec_var.get()]
        fg   = self._fg_color()
        errors = 0
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, line in enumerate(lines, 1):
                try:
                    qr = qrcode.QRCode(error_correction=ec, box_size=10, border=4)
                    qr.add_data(line)
                    qr.make(fit=True)
                    img = qr.make_image(fill_color=fg, back_color="white").convert("RGB")
                    buf = io.BytesIO()
                    img.resize((size, size), Image.LANCZOS).save(buf, "PNG")
                    zf.writestr(f"qr_{i:03d}.png", buf.getvalue())
                except Exception:
                    errors += 1
        ok = len(lines) - errors
        self._set_status(
            f"Exported {ok}/{len(lines)} QR codes → {os.path.basename(path)}"
            + (f"  ({errors} failed)" if errors else ""))

    def _clear(self) -> None:
        t = self._active_type
        try:
            if t in ("URL", "Text", "Batch"):
                self._primary_input.delete("1.0", "end")  # type: ignore
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
            elif t == "vCard":
                for a in ("_vc_name", "_vc_phone", "_vc_email", "_vc_org", "_vc_url"):
                    getattr(self, a).delete(0, "end")
            elif t == "GPS":
                for a in ("_gps_lat", "_gps_lon", "_gps_label"):
                    getattr(self, a).delete(0, "end")
            elif t == "Calendar":
                for a in ("_cal_title", "_cal_start", "_cal_end", "_cal_loc"):
                    getattr(self, a).delete(0, "end")
        except Exception:
            pass
        self._logo_path = None
        self._logo_lbl.configure(text="")
        self._set_status("")
        self._qr_image   = None
        self._qr_content = ""
        self._form_values.clear()
        self._show_placeholder()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = QRGeneratorApp(root)
    root.mainloop()
