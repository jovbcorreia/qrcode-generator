"""
QR Code Generator — Desktop App v4.0
Modern design: indigo palette · rounded buttons · dark navy mode
"""

import tkinter as tk
from tkinter import filedialog, ttk
import tkinter.font as tkf
import qrcode
import qrcode.image.svg as qr_svg
from PIL import Image, ImageTk
import subprocess, tempfile, os, re, zipfile, io

# ── Palettes ──────────────────────────────────────────────────────────────────
LIGHT = dict(
    bg       = "#EEF2FF",   # indigo-50
    surface  = "#FFFFFF",
    ink      = "#1E1B4B",   # indigo-950
    primary  = "#4F46E5",   # indigo-600
    prim_h   = "#4338CA",   # indigo-700
    muted    = "#6366F1",   # indigo-500
    border   = "#C7D2FE",   # indigo-200
    subtle   = "#818CF8",   # indigo-400
    input_bg = "#F5F3FF",   # violet-50
)
DARK = dict(
    bg       = "#0F172A",   # slate-900
    surface  = "#1E293B",   # slate-800
    ink      = "#E2E8F0",   # slate-200
    primary  = "#6366F1",   # indigo-500
    prim_h   = "#818CF8",   # indigo-400
    muted    = "#94A3B8",   # slate-400
    border   = "#334155",   # slate-700
    subtle   = "#4F46E5",   # indigo-600
    input_bg = "#1E1B4B",   # indigo-950
)

# Action colours — same in light and dark
C = dict(
    generate = ("#4F46E5", "#4338CA"),
    copy_img = ("#0EA5E9", "#0284C7"),
    copy_txt = ("#8B5CF6", "#7C3AED"),
    print_   = ("#10B981", "#059669"),
    logo     = ("#F59E0B", "#D97706"),
    clear    = ("#EF4444", "#DC2626"),
    save_png = ("#059669", "#047857"),
    save_jpg = ("#2563EB", "#1D4ED8"),
    save_svg = ("#7C3AED", "#6D28D9"),
    batch    = ("#4F46E5", "#4338CA"),
)

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


# ── App ───────────────────────────────────────────────────────────────────────
class QRGeneratorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._dark           = False
        self._pal            = LIGHT.copy()
        self._active_type    = "URL"
        self._qr_image: Image.Image | None = None
        self._qr_content     = ""
        self._debounce_id: str | None = None
        self._primary_input: tk.Text | None = None
        self._history: list[dict] = []
        self._logo_path: str | None = None
        self._form_values: dict = {}
        self._fg_grey  = tk.IntVar(value=10)
        self._ec_var   = tk.StringVar(value=EC_KEYS[1])
        self._size_var = tk.StringVar(value="800 px")

        self._configure_window()
        self._build_header()
        self._build_body()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _configure_window(self) -> None:
        self.root.title("QR Generator")
        self.root.resizable(True, True)
        self.root.minsize(900, 580)
        w, h = 1100, 700
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self.root.configure(bg=self._p("bg"))

    def _p(self, k: str) -> str:
        return self._pal[k]

    def _fg_color(self) -> str:
        v = self._fg_grey.get()
        return f"#{v:02x}{v:02x}{v:02x}"

    # ── Dark mode ─────────────────────────────────────────────────────────────
    def _toggle_dark(self) -> None:
        self._capture_form()
        self._dark = not self._dark
        self._pal  = DARK.copy() if self._dark else LIGHT.copy()
        self.root.configure(bg=self._p("bg"))
        self._dark_btn.configure(
            text="☀  Light Mode" if self._dark else "◐  Dark Mode")
        saved_img, saved_cont = self._qr_image, self._qr_content
        self._body.destroy()
        self._build_body()
        self._qr_image, self._qr_content = saved_img, saved_cont
        self._restore_form_partial()
        if saved_img:
            self._render_preview()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self) -> None:
        hdr = tk.Frame(self.root, bg="#1E1B4B", height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        lf = tk.Frame(hdr, bg="#1E1B4B")
        lf.pack(side="left", padx=24, fill="y")
        tk.Label(lf, text="⬛", bg="#1E1B4B", fg="#818CF8",
                 font=(FONT, 18)).pack(side="left", padx=(0, 10))
        tk.Label(lf, text="QR Code Generator", bg="#1E1B4B", fg="#FFFFFF",
                 font=(FONT, 14, "bold")).pack(side="left")
        tk.Label(lf, text=" v4.0", bg="#1E1B4B", fg="#6366F1",
                 font=(FONT, 10)).pack(side="left")

        self._dark_btn = tk.Button(
            hdr, text="◐  Dark Mode", command=self._toggle_dark,
            font=(FONT, 10), bg="#312E81", fg="#A5B4FC",
            activebackground="#3730A3", activeforeground="#FFFFFF",
            relief="flat", bd=0, padx=14, pady=7, cursor="hand2")
        self._dark_btn.pack(side="right", padx=20)

    # ── Body ──────────────────────────────────────────────────────────────────
    def _build_body(self) -> None:
        self._body = tk.Frame(self.root, bg=self._p("bg"))
        self._body.pack(fill="both", expand=True)

        left = tk.Frame(self._body, bg=self._p("bg"), width=490)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._build_left(left)

        tk.Frame(self._body, bg=self._p("border"), width=1).pack(side="left", fill="y")

        right = tk.Frame(self._body, bg=self._p("surface"))
        right.pack(side="left", fill="both", expand=True)
        self._build_right(right)

    # ── Left panel ────────────────────────────────────────────────────────────
    def _build_left(self, parent: tk.Frame) -> None:
        # ── Scrollable top area (form only) ───────────────────────────────
        scroll_wrap = tk.Frame(parent, bg=self._p("bg"))
        scroll_wrap.pack(fill="both", expand=True)

        cv = tk.Canvas(scroll_wrap, bg=self._p("bg"), highlightthickness=0)
        sb = tk.Scrollbar(scroll_wrap, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(cv, bg=self._p("bg"))
        wid = cv.create_window((0, 0), window=inner, anchor="nw")
        cv.bind("<Configure>",    lambda e: cv.itemconfigure(wid, width=e.width))
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<MouseWheel>",
                lambda e: cv.yview_scroll(-1 * (e.delta // 120), "units"))

        pad = tk.Frame(inner, bg=self._p("bg"))
        pad.pack(fill="both", expand=True, padx=20, pady=14)

        # Type selector pills
        self._slbl(pad, "CONTENT TYPE")
        self._type_btns: dict[str, tk.Canvas] = {}
        for row_types in TYPE_ROWS:
            rf = tk.Frame(pad, bg=self._p("bg"))
            rf.pack(fill="x", pady=(0, 3))
            for t in row_types:
                btn = self._pill(rf, t, lambda x=t: self._switch_type(x),
                                 active=(t == self._active_type))
                btn.pack(side="left", padx=(0, 4))
                self._type_btns[t] = btn

        # Dynamic form
        self._form = tk.Frame(pad, bg=self._p("bg"))
        self._form.pack(fill="x", pady=(12, 0))
        self._form.columnconfigure(0, weight=1)

        # QR Colour
        self._slbl(pad, "QR COLOUR", top=14)
        crow = tk.Frame(pad, bg=self._p("bg"))
        crow.pack(fill="x", pady=(4, 0))
        self._color_dot = tk.Label(crow, text="", bg=self._fg_color(),
                                    width=4, height=1, bd=0, relief="flat")
        self._color_dot.pack(side="right", padx=(8, 0))
        tk.Scale(crow, from_=10, to=136, orient="horizontal",
                variable=self._fg_grey,
                bg=self._p("bg"), fg=self._p("ink"),
                troughcolor=self._p("border"),
                highlightthickness=0, showvalue=False, relief="flat",
                command=lambda _: (
                    self._color_dot.configure(bg=self._fg_color()),
                    self._debounce()),
                ).pack(side="left", fill="x", expand=True)

        # Status
        self._status_lbl = tk.Label(pad, text="", bg=self._p("bg"),
                                     fg=self._p("muted"),
                                     font=(FONT, 10), wraplength=420, justify="left")
        self._status_lbl.pack(anchor="w", pady=(8, 0))

        self._build_form()

        # ── Fixed bottom bar (always visible, outside scroll) ─────────────
        bottom = tk.Frame(parent, bg=self._p("bg"))
        bottom.pack(fill="x", padx=20, pady=(8, 14))

        # Generate hero button
        self._rbtn(bottom, "Generate QR Code", self._generate_qr,
                  bg=C["generate"][0], hover=C["generate"][1],
                  font=(FONT, 12, "bold"), radius=12, h=44,
                  ).pack(fill="x", pady=(0, 8))

        # Row 1
        r1 = tk.Frame(bottom, bg=self._p("bg"))
        r1.pack(fill="x", pady=(0, 5))
        r1.columnconfigure((0, 1, 2), weight=1)
        self._rbtn(r1, "Copy Image", self._copy_image,
                  bg=C["copy_img"][0], hover=C["copy_img"][1], radius=9, h=34,
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._rbtn(r1, "Copy Text",  self._copy_raw,
                  bg=C["copy_txt"][0], hover=C["copy_txt"][1], radius=9, h=34,
                  ).grid(row=0, column=1, sticky="ew", padx=(4, 4))
        self._rbtn(r1, "Print",      self._print_qr,
                  bg=C["print_"][0],  hover=C["print_"][1],   radius=9, h=34,
                  ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        # Row 2
        r2 = tk.Frame(bottom, bg=self._p("bg"))
        r2.pack(fill="x")
        r2.columnconfigure((0, 1), weight=1)
        self._rbtn(r2, "Set Logo", self._pick_logo,
                  bg=C["logo"][0],  hover=C["logo"][1],  radius=9, h=34,
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._rbtn(r2, "Clear",    self._clear,
                  bg=C["clear"][0], hover=C["clear"][1], radius=9, h=34,
                  ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

    # ── Right panel ───────────────────────────────────────────────────────────
    def _build_right(self, parent: tk.Frame) -> None:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        # QR preview (white card, always white even in dark mode)
        cf = tk.Frame(parent, bg=self._p("border"), bd=0)
        cf.grid(row=0, column=0, sticky="nsew", padx=20, pady=(14, 6))
        cf.rowconfigure(0, weight=1); cf.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(cf, bg="#FFFFFF", bd=0, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        self._show_placeholder()

        # Logo label
        self._logo_lbl = tk.Label(parent, text="", bg=self._p("surface"),
                                   fg=self._p("muted"), font=(FONT, 9))
        self._logo_lbl.grid(row=1, column=0, sticky="w", padx=22, pady=(0, 2))

        # ── Error correction + Export size (compact row) ───────────────────
        ctrl = tk.Frame(parent, bg=self._p("surface"))
        ctrl.grid(row=2, column=0, sticky="ew", padx=20, pady=(2, 6))
        ctrl.columnconfigure((0, 1), weight=1)

        ec_f = tk.Frame(ctrl, bg=self._p("surface"))
        ec_f.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        tk.Label(ec_f, text="ERROR CORRECTION", bg=self._p("surface"),
                 fg=self._p("muted"), font=(FONT, 8, "bold")).pack(anchor="w")
        ec = ttk.Combobox(ec_f, textvariable=self._ec_var, values=EC_KEYS,
                          state="readonly", font=(FONT, 10))
        ec.pack(fill="x", pady=(3, 0))
        ec.bind("<<ComboboxSelected>>", lambda _: self._generate_qr())

        sz_f = tk.Frame(ctrl, bg=self._p("surface"))
        sz_f.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        tk.Label(sz_f, text="EXPORT SIZE", bg=self._p("surface"),
                 fg=self._p("muted"), font=(FONT, 8, "bold")).pack(anchor="w")
        ttk.Combobox(sz_f, textvariable=self._size_var,
                     values=list(EXPORT_SIZES.keys()),
                     state="readonly", font=(FONT, 10)).pack(fill="x", pady=(3, 0))
        self._style_combobox()

        # Save buttons
        sf = tk.Frame(parent, bg=self._p("surface"))
        sf.grid(row=3, column=0, sticky="ew", padx=20, pady=(2, 8))
        sf.columnconfigure((0, 1, 2), weight=1)
        self._rbtn(sf, "Save PNG",  self._save_png,
                  bg=C["save_png"][0], hover=C["save_png"][1], radius=10, h=38,
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._rbtn(sf, "Save JPEG", self._save_jpeg,
                  bg=C["save_jpg"][0], hover=C["save_jpg"][1], radius=10, h=38,
                  ).grid(row=0, column=1, sticky="ew", padx=(4, 4))
        self._rbtn(sf, "Save SVG",  self._save_svg,
                  bg=C["save_svg"][0], hover=C["save_svg"][1], radius=10, h=38,
                  ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        # History strip
        tk.Label(parent, text="RECENT", bg=self._p("surface"),
                 fg=self._p("muted"), font=(FONT, 8, "bold"),
                 ).grid(row=4, column=0, sticky="w", padx=24)
        self._hist_frame = tk.Frame(parent, bg=self._p("surface"))
        self._hist_frame.grid(row=5, column=0, sticky="ew", padx=20, pady=(3, 12))
        self._render_history()

    # ── Widget factories ──────────────────────────────────────────────────────
    def _rbtn(self, parent: tk.Frame, text: str, command,
              *, bg: str, hover: str, fg: str = "#FFFFFF",
              radius: int = 10, h: int = 36, font=None) -> tk.Canvas:
        """Rounded Canvas button."""
        if font is None:
            font = (FONT, 11)
        pbg = parent.cget("bg")
        st  = {"hovered": False}

        c = tk.Canvas(parent, height=h, highlightthickness=0, bd=0, bg=pbg)

        def draw(color: str) -> None:
            c.delete("all")
            w = c.winfo_width(); hh = c.winfo_height()
            if w < 4 or hh < 4:
                return
            r = min(radius, w // 2, hh // 2)
            pts = [r,0, w-r,0, w,0, w,r, w,hh-r, w,hh,
                   w-r,hh, r,hh, 0,hh, 0,hh-r, 0,r, 0,0]
            c.create_polygon(pts, smooth=True, fill=color, outline=color)
            c.create_text(w // 2, hh // 2, text=text, fill=fg, font=font)

        c.bind("<Button-1>",  lambda e: command())
        c.bind("<Enter>",     lambda e: (st.update(hovered=True),  draw(hover)))
        c.bind("<Leave>",     lambda e: (st.update(hovered=False), draw(bg)))
        c.bind("<Configure>", lambda e: draw(hover if st["hovered"] else bg))
        c.after(10, lambda: draw(bg))
        return c

    def _pill(self, parent: tk.Frame, text: str, command,
              *, active: bool = False) -> tk.Canvas:
        """Pill-shaped type selector chip."""
        font = (FONT, 10)
        tf   = tkf.Font(family=font[0], size=font[1])
        tw   = tf.measure(text) + 26
        th   = 28
        pbg  = parent.cget("bg")
        st   = {"active": active, "h": False}

        c = tk.Canvas(parent, width=tw, height=th,
                     highlightthickness=0, bd=0, bg=pbg)

        def draw() -> None:
            c.delete("all")
            w = c.winfo_width() or tw
            h = c.winfo_height() or th
            r = h // 2
            if st["active"]:
                fill, outline, tc = self._p("primary"), self._p("primary"), "#FFFFFF"
            elif st["h"]:
                fill, outline, tc = self._p("border"), self._p("primary"), self._p("primary")
            else:
                fill, outline, tc = pbg, self._p("border"), self._p("muted")
            pts = [r,0, w-r,0, w,0, w,r, w,h-r, w,h,
                   w-r,h, r,h, 0,h, 0,h-r, 0,r, 0,0]
            c.create_polygon(pts, smooth=True, fill=fill, outline=outline, width=1.5)
            c.create_text(w // 2, h // 2, text=text, fill=tc, font=font)

        c.set_active = lambda v: (st.update(active=v), draw())  # type: ignore[attr-defined]
        c.bind("<Button-1>",  lambda e: command())
        c.bind("<Enter>",     lambda e: (st.update(h=True),  draw()))
        c.bind("<Leave>",     lambda e: (st.update(h=False), draw()))
        c.bind("<Configure>", lambda e: draw())
        c.after(10, draw)
        return c

    def _refresh_type_btns(self) -> None:
        for t, c in self._type_btns.items():
            c.set_active(t == self._active_type)  # type: ignore[attr-defined]

    def _slbl(self, parent, text: str, top: int = 0) -> None:
        tk.Label(parent, text=text, bg=self._p("bg"), fg=self._p("muted"),
                 font=(FONT, 8, "bold")).pack(anchor="w", pady=(top, 0))

    def _flabel(self, p, text: str) -> tk.Label:
        return tk.Label(p, text=text, bg=self._p("bg"), fg=self._p("ink"),
                       font=(FONT, 10, "bold"))

    def _entry_row(self, p, label: str, lrow: int, erow: int, **kw) -> tk.Entry:
        top = 10 if lrow > 0 else 0
        self._flabel(p, label).grid(row=lrow, column=0, sticky="w", pady=(top, 4))
        e = tk.Entry(p, font=(FONT, 11), bg=self._p("input_bg"), fg=self._p("ink"),
                    insertbackground=self._p("ink"), relief="flat", bd=0,
                    highlightthickness=2, highlightbackground=self._p("border"),
                    highlightcolor=self._p("primary"), **kw)
        e.grid(row=erow, column=0, sticky="ew", ipady=7)
        return e

    def _textarea(self, p, height: int = 4) -> tk.Text:
        return tk.Text(p, height=height, wrap="word", font=(FONT, 11),
                      bg=self._p("input_bg"), fg=self._p("ink"),
                      insertbackground=self._p("ink"),
                      relief="flat", bd=0, padx=10, pady=8,
                      highlightthickness=2, highlightbackground=self._p("border"),
                      highlightcolor=self._p("primary"))

    def _ctrlabel(self, p) -> tk.Label:
        return tk.Label(p, text="0 chars", bg=self._p("bg"),
                       fg=self._p("muted"), font=(FONT, 9))

    def _style_combobox(self) -> None:
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TCombobox",
                   fieldbackground=self._p("input_bg"), background=self._p("input_bg"),
                   foreground=self._p("ink"), selectbackground=self._p("border"),
                   selectforeground=self._p("ink"), bordercolor=self._p("border"),
                   arrowcolor=self._p("primary"), relief="flat")

    def _show_placeholder(self) -> None:
        self._canvas.delete("all")
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width() or 420
        ch = self._canvas.winfo_height() or 340
        self._canvas.create_text(cw // 2, ch // 2,
                                 text="Your QR code\nwill appear here",
                                 fill="#C7D2FE", font=(FONT, 14), justify="center")

    def _set_status(self, msg: str) -> None:
        try:
            self._status_lbl.configure(text=msg)
        except Exception:
            pass

    # ── Form builders ─────────────────────────────────────────────────────────
    def _clear_form(self) -> None:
        for w in self._form.winfo_children():
            w.destroy()

    def _build_form(self) -> None:
        self._clear_form()
        self._form.columnconfigure(0, weight=1)
        self._primary_input = None
        {
            "URL": self._form_url, "Text": self._form_text,
            "WiFi": self._form_wifi, "Email": self._form_email,
            "SMS": self._form_sms, "vCard": self._form_vcard,
            "GPS": self._form_gps, "Calendar": self._form_calendar,
            "Batch": self._form_batch,
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
                      activebackground=self._p("bg"), selectcolor=self._p("input_bg"),
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
        self._rbtn(self._form, "Export all as ZIP", self._batch_export,
                  bg=C["batch"][0], hover=C["batch"][1], radius=10, h=36,
                  ).grid(row=3, column=0, sticky="ew", pady=(10, 0))

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
            lbl = tk.Label(self._hist_frame, image=tk_img,
                          bg=self._p("surface"), cursor="hand2",
                          highlightthickness=2,
                          highlightbackground=self._p("border"),
                          relief="flat")
            lbl._img = tk_img  # type: ignore[attr-defined]
            lbl.pack(side="left", padx=(0, 6))
            lbl.bind("<Button-1>", lambda _e, e=entry: self._load_history(e))
            lbl.bind("<Enter>",
                     lambda _e, b=lbl: b.configure(highlightbackground=self._p("primary")))
            lbl.bind("<Leave>",
                     lambda _e, b=lbl: b.configure(highlightbackground=self._p("border")))

    def _load_history(self, entry: dict) -> None:
        self._qr_image   = entry["img"]
        self._qr_content = entry["content"]
        self._render_preview()
        self._set_status(
            f"History [{entry['type']}]: {entry['content'][:50].replace(chr(10), ' ')}")

    # ── Auto-detect ───────────────────────────────────────────────────────────
    def _auto_detect(self, widget: tk.Text) -> None:
        text = widget.get("1.0", "end-1c").strip()
        if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text):
            self._set_status("Looks like an email — try the Email tab.")
        elif re.match(r"^\+?[\d\s\-()]{7,20}$", text):
            self._set_status("Looks like a phone number — try the SMS tab.")
        elif self._status_lbl.cget("text").startswith("Looks like"):
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

    @staticmethod
    def _update_ctr(widget: tk.Text, label: tk.Label) -> None:
        label.configure(text=f"{len(widget.get('1.0', 'end-1c'))} chars")

    # ── Form state ────────────────────────────────────────────────────────────
    def _capture_form(self) -> None:
        t = self._active_type
        try:
            if t in ("URL", "Text", "Batch"):
                self._form_values[f"{t}_m"] = self._primary_input.get("1.0", "end-1c")  # type: ignore
            elif t == "WiFi":
                self._form_values.update(w_ssid=self._wifi_ssid.get(), w_pw=self._wifi_pw.get())
            elif t == "Email":
                self._form_values.update(e_to=self._email_to.get(),
                                         e_sub=self._email_subject.get(),
                                         e_body=self._email_body.get("1.0", "end-1c"))
            elif t == "SMS":
                self._form_values.update(s_num=self._sms_number.get(),
                                         s_msg=self._sms_msg.get("1.0", "end-1c"))
            elif t == "vCard":
                self._form_values.update(vc_n=self._vc_name.get(), vc_p=self._vc_phone.get(),
                                         vc_e=self._vc_email.get(), vc_o=self._vc_org.get(),
                                         vc_u=self._vc_url.get())
            elif t == "GPS":
                self._form_values.update(g_lat=self._gps_lat.get(), g_lon=self._gps_lon.get(),
                                         g_lbl=self._gps_label.get())
            elif t == "Calendar":
                self._form_values.update(c_ttl=self._cal_title.get(), c_sta=self._cal_start.get(),
                                         c_end=self._cal_end.get(), c_loc=self._cal_loc.get())
        except Exception:
            pass

    def _restore_form_partial(self) -> None:
        fv = self._form_values
        t  = self._active_type

        def fe(w: tk.Entry, k: str) -> None:
            if k in fv:
                w.delete(0, "end"); w.insert(0, fv[k])

        def ft(w: tk.Text, k: str) -> None:
            if k in fv:
                w.delete("1.0", "end"); w.insert("1.0", fv[k])

        try:
            if t in ("URL", "Text", "Batch") and self._primary_input:
                ft(self._primary_input, f"{t}_m")
            elif t == "WiFi":
                fe(self._wifi_ssid, "w_ssid"); fe(self._wifi_pw, "w_pw")
            elif t == "Email":
                fe(self._email_to, "e_to"); fe(self._email_subject, "e_sub")
                ft(self._email_body, "e_body")
            elif t == "SMS":
                fe(self._sms_number, "s_num"); ft(self._sms_msg, "s_msg")
            elif t == "vCard":
                for k, a in [("vc_n","_vc_name"),("vc_p","_vc_phone"),("vc_e","_vc_email"),
                              ("vc_o","_vc_org"),("vc_u","_vc_url")]:
                    fe(getattr(self, a), k)
            elif t == "GPS":
                fe(self._gps_lat,"g_lat"); fe(self._gps_lon,"g_lon"); fe(self._gps_label,"g_lbl")
            elif t == "Calendar":
                for k, a in [("c_ttl","_cal_title"),("c_sta","_cal_start"),
                              ("c_end","_cal_end"),("c_loc","_cal_loc")]:
                    fe(getattr(self, a), k)
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
                return lines[0] if lines else ""
            if t == "WiFi":
                ssid = self._wifi_ssid.get().strip()
                if not ssid: return ""
                enc = {"WPA/WPA2":"WPA","WEP":"WEP","None":"nopass"}[self._wifi_enc.get()]
                hidden = ";H:true" if self._wifi_hidden.get() else ""
                return f"WIFI:T:{enc};S:{ssid};P:{self._wifi_pw.get()}{hidden};;"
            if t == "Email":
                to = self._email_to.get().strip()
                if not to: return ""
                sub  = self._email_subject.get().strip()
                body = self._email_body.get("1.0","end-1c").strip()
                p = ([f"subject={sub}"] if sub else []) + ([f"body={body}"] if body else [])
                return f"mailto:{to}" + ("?" + "&".join(p) if p else "")
            if t == "SMS":
                num = self._sms_number.get().strip()
                if not num: return ""
                return f"smsto:{num}:{self._sms_msg.get('1.0','end-1c').strip()}"
            if t == "vCard":
                name = self._vc_name.get().strip()
                if not name: return ""
                s = f"MECARD:N:{name};"
                if p := self._vc_phone.get().strip(): s += f"TEL:{p};"
                if e := self._vc_email.get().strip(): s += f"EMAIL:{e};"
                if o := self._vc_org.get().strip():   s += f"ORG:{o};"
                if u := self._vc_url.get().strip():   s += f"URL:{u};"
                return s + ";"
            if t == "GPS":
                lat, lon = self._gps_lat.get().strip(), self._gps_lon.get().strip()
                if not lat or not lon: return ""
                lbl = self._gps_label.get().strip()
                return f"geo:{lat},{lon}?q={lat},{lon}({lbl})" if lbl else f"geo:{lat},{lon}"
            if t == "Calendar":
                ttl = self._cal_title.get().strip()
                if not ttl: return ""
                ls = ["BEGIN:VEVENT", f"SUMMARY:{ttl}"]
                if s := self._cal_start.get().strip(): ls.append(f"DTSTART:{s}")
                if e := self._cal_end.get().strip():   ls.append(f"DTEND:{e}")
                if l := self._cal_loc.get().strip():   ls.append(f"LOCATION:{l}")
                ls.append("END:VEVENT")
                return "\n".join(ls)
        except Exception:
            pass
        return ""

    # ── QR generation ─────────────────────────────────────────────────────────
    def _generate_qr(self) -> None:
        content = self._get_content()
        self._set_status("")
        if not content:
            self._qr_image = None; self._qr_content = ""
            self._show_placeholder(); return
        try:
            qr = qrcode.QRCode(error_correction=EC_LEVELS[self._ec_var.get()],
                               box_size=10, border=4)
            qr.add_data(content); qr.make(fit=True)
        except qrcode.exceptions.DataOverflowError:
            self._set_status("Content too long for the selected error correction level.")
            return
        except Exception as exc:
            self._set_status(f"Error: {exc}"); return

        img = qr.make_image(fill_color=self._fg_color(),
                            back_color="#FFFFFF").convert("RGBA")
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
            mx = int(min(qw, qh) * 0.28)
            logo.thumbnail((mx, mx), Image.LANCZOS)
            pos = ((qw - logo.width) // 2, (qh - logo.height) // 2)
            img.paste(logo, pos, logo)
            self._logo_lbl.configure(text=f"Logo: {os.path.basename(self._logo_path)}")
        except Exception as exc:
            self._set_status(f"Logo error: {exc}")
        return img

    def _render_preview(self) -> None:
        if not self._qr_image: return
        self._canvas.update_idletasks()
        cw = self._canvas.winfo_width() or 420
        ch = self._canvas.winfo_height() or 340
        size = min(cw, ch) - 20
        thumb = self._qr_image.copy()
        thumb.thumbnail((size, size), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(thumb)
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, anchor="center", image=self._tk_img)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _copy_image(self) -> None:
        if not self._qr_image:
            self._set_status("Generate a QR code first."); return
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = f.name
        self._qr_image.resize((800, 800), Image.LANCZOS).save(tmp, "PNG")
        try:
            subprocess.run(["osascript", "-e",
                f'set the clipboard to (read (POSIX file "{tmp}") as TIFF picture)'],
                check=True, capture_output=True)
            self._set_status("Image copied to clipboard.")
        except Exception:
            self._set_status("Copy failed — try saving instead.")
        finally:
            os.unlink(tmp)

    def _copy_raw(self) -> None:
        if not self._qr_content:
            self._set_status("Generate a QR code first."); return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._qr_content)
        self._set_status("Raw content copied to clipboard.")

    def _print_qr(self) -> None:
        if not self._qr_image:
            self._set_status("Generate a QR code first."); return
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp = f.name
        self._qr_image.resize((800, 800), Image.LANCZOS).save(tmp, "PNG")
        try:
            subprocess.run(["lpr", tmp], check=True)
            self._set_status("Sent to printer.")
        except Exception:
            self._set_status("Print failed — no printer configured.")
        finally:
            self.root.after(4000, lambda: os.unlink(tmp) if os.path.exists(tmp) else None)

    def _pick_logo(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")],
            title="Choose logo image")
        if not path: return
        self._logo_path = path
        self._ec_var.set(EC_KEYS[3])
        self._set_status("Logo set — error correction forced to H.")
        self._generate_qr()

    def _save_png(self)  -> None: self._save("png")
    def _save_jpeg(self) -> None: self._save("jpeg")

    def _save(self, fmt: str) -> None:
        if not self._qr_image:
            self._set_status("Generate a QR code first."); return
        size = EXPORT_SIZES[self._size_var.get()]
        ext  = "jpg" if fmt == "jpeg" else "png"
        path = filedialog.asksaveasfilename(
            defaultextension=f".{ext}",
            filetypes=[("JPEG","*.jpg")] if fmt == "jpeg" else [("PNG","*.png")],
            title=f"Save as {fmt.upper()}")
        if not path: return
        out = self._qr_image.resize((size, size), Image.LANCZOS)
        out.save(path, "JPEG", quality=95) if fmt == "jpeg" else out.save(path, "PNG")
        self._set_status(f"Saved {size}×{size} → {os.path.basename(path)}")

    def _save_svg(self) -> None:
        if not self._qr_content:
            self._set_status("Generate a QR code first."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".svg", filetypes=[("SVG","*.svg")], title="Save as SVG")
        if not path: return
        try:
            qr = qrcode.QRCode(error_correction=EC_LEVELS[self._ec_var.get()],
                               box_size=10, border=4)
            qr.add_data(self._qr_content); qr.make(fit=True)
            qr.make_image(image_factory=qr_svg.SvgPathImage).save(path)
            self._set_status(f"SVG saved → {os.path.basename(path)}")
        except Exception as exc:
            self._set_status(f"SVG error: {exc}")

    def _batch_export(self) -> None:
        if not self._primary_input: return
        lines = [l.strip() for l in
                 self._primary_input.get("1.0","end-1c").splitlines() if l.strip()]
        if not lines:
            self._set_status("Add at least one item per line."); return
        path = filedialog.asksaveasfilename(
            defaultextension=".zip", filetypes=[("ZIP","*.zip")], title="Save batch ZIP")
        if not path: return
        size = EXPORT_SIZES[self._size_var.get()]
        ec, fg, errors = EC_LEVELS[self._ec_var.get()], self._fg_color(), 0
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, line in enumerate(lines, 1):
                try:
                    qr = qrcode.QRCode(error_correction=ec, box_size=10, border=4)
                    qr.add_data(line); qr.make(fit=True)
                    img = qr.make_image(fill_color=fg, back_color="white").convert("RGB")
                    buf = io.BytesIO()
                    img.resize((size, size), Image.LANCZOS).save(buf, "PNG")
                    zf.writestr(f"qr_{i:03d}.png", buf.getvalue())
                except Exception:
                    errors += 1
        ok = len(lines) - errors
        self._set_status(f"Exported {ok}/{len(lines)} QR codes → {os.path.basename(path)}"
                        + (f"  ({errors} failed)" if errors else ""))

    def _clear(self) -> None:
        t = self._active_type
        try:
            if t in ("URL","Text","Batch"):
                self._primary_input.delete("1.0","end")  # type: ignore
            elif t == "WiFi":
                self._wifi_ssid.delete(0,"end"); self._wifi_pw.delete(0,"end")
            elif t == "Email":
                self._email_to.delete(0,"end"); self._email_subject.delete(0,"end")
                self._email_body.delete("1.0","end")
            elif t == "SMS":
                self._sms_number.delete(0,"end"); self._sms_msg.delete("1.0","end")
            elif t == "vCard":
                for a in ("_vc_name","_vc_phone","_vc_email","_vc_org","_vc_url"):
                    getattr(self,a).delete(0,"end")
            elif t == "GPS":
                for a in ("_gps_lat","_gps_lon","_gps_label"):
                    getattr(self,a).delete(0,"end")
            elif t == "Calendar":
                for a in ("_cal_title","_cal_start","_cal_end","_cal_loc"):
                    getattr(self,a).delete(0,"end")
        except Exception:
            pass
        self._logo_path = None
        self._logo_lbl.configure(text="")
        self._set_status("")
        self._qr_image = None; self._qr_content = ""
        self._form_values.clear()
        self._show_placeholder()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = QRGeneratorApp(root)
    root.mainloop()
