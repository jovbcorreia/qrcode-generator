# QR Code Generator

> A modern **desktop application** to generate QR codes instantly — built entirely with Python, runs natively on **macOS · Windows · Linux**.

---

## Screenshots

### Light Mode — URL
![URL mode, light theme](screenshots/light-url.png)

### Light Mode — Email
![Email form with QR preview](screenshots/light-email.png)

### Dark Mode — vCard
![vCard form, dark theme](screenshots/dark-vcard.png)

---

## What is this?

**QR Code Generator** is a standalone **desktop app** — it opens as a native window on your computer, no browser and no internet connection needed.

You fill in a form (URL, Wi-Fi, contact, email, SMS, location, event…), the QR code appears live on screen, and you save it in the format and size you need.

Compatible with **macOS**, **Windows**, and **Linux** (any desktop with Python 3.10+).

---

## Features

### 9 Content Types

Each tab has a dedicated smart form that builds the correct QR payload automatically:

| Type | What it encodes | Use case |
|---|---|---|
| **URL** | Raw URL string | Link to any website |
| **Text** | Plain text | Notes, coupons, codes |
| **WiFi** | `WIFI:T:WPA;S:…;P:…;;` | Share Wi-Fi — phone scans and connects automatically |
| **Email** | `mailto:…?subject=…&body=…` | Pre-filled email compose |
| **SMS** | `smsto:number:message` | Pre-filled SMS to a number |
| **vCard** | `MECARD:N:…;TEL:…;EMAIL:…;` | Digital business card — scan to save contact |
| **GPS** | `geo:lat,lon?q=…` | Share a location — opens in Maps on any phone |
| **Calendar** | `BEGIN:VEVENT … END:VEVENT` | Add an event to the phone calendar |
| **Batch** | One QR per line | Export dozens of QR codes at once as a ZIP |

### Live Preview
QR code renders automatically as you type (300 ms debounce) — no need to click Generate.

### History Strip
Last 8 generated QR codes shown as thumbnails. Click any to reload it instantly.

### Auto-detect
When typing in the URL field, the app detects if the content looks like an email or phone number and suggests switching to the right tab.

### QR Colour Slider
Greyscale slider to change the QR foreground colour — from pure black to dark grey.

### Logo Overlay
Upload a PNG/JPEG logo to embed in the centre of the QR. Automatically forces **Error Correction H** (30%) to keep it scannable.

### Error Correction

| Level | Recovery | Best for |
|---|---|---|
| L | ~7% | Digital screens |
| M | ~15% | General use (default) |
| Q | ~25% | Printed materials |
| H | ~30% | Logos, stickers, outdoor |

### Export Options

| Action | Description |
|---|---|
| **Save PNG** | Lossless, configurable size |
| **Save JPEG** | Compressed quality 95, configurable size |
| **Save SVG** | Vector — scales infinitely |
| **Copy Image** | Copies QR to clipboard (macOS) |
| **Copy Text** | Copies the raw encoded string |
| **Print** | Sends to system printer |

### Export Sizes
400 px · 800 px · 1200 px · 2400 px

### Batch Export
Paste one item per line in the **Batch** tab → **Export all as ZIP** → get one PNG per line, named `qr_001.png`, `qr_002.png`, etc.

### Dark Mode
Toggle between light indigo and dark navy theme. Form data and QR are preserved across the switch.

---

## Tech Stack

| Library | Purpose |
|---|---|
| **Python 3.10+** | Language |
| **tkinter** | Native GUI (built-in, no install needed) |
| **qrcode** | QR matrix generation + SVG export |
| **Pillow** | Image manipulation, export, logo overlay |

No Electron. No web view. No framework overhead — pure Python running natively on your desktop.

---

## Getting Started

### 1. Clone

```bash
git clone https://github.com/jovbcorreia/qrcode-generator.git
cd qrcode-generator
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **macOS note:** If you get a `_tkinter` error, run `brew install python-tk@3.13` first.

### 3. Run

```bash
python3 app.py
```

The window opens centred on your screen and is fully resizable.

---

## Project Structure

```
qrcode-generator/
├── app.py            # Full application — single file
├── requirements.txt  # qrcode + Pillow
├── pyproject.toml    # Package metadata
├── LICENSE           # MIT licence
├── README.md         # This file
└── screenshots/
    ├── light-url.png
    ├── light-email.png
    └── dark-vcard.png
```

---

## Tips

- **Type in the form** → QR updates automatically
- **Click Generate** → forces re-render (useful after changing Error Correction)
- **Click a history thumbnail** → reloads that QR
- **Set Logo + Clear** → Clear also removes the logo

---

## License

MIT License — Copyright © 2026 **João Vilas-Boas Correia**

---

**Author:** João Vilas-Boas Correia — [joaopsn3@gmail.com](mailto:joaopsn3@gmail.com)  
**License:** MIT  
**Version:** 4.0.0  
**Platform:** macOS · Windows · Linux (desktop)
