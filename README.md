# QR Code Generator

A minimalist desktop application for generating QR codes — built with Python and tkinter.

> **Author:** João Vilas-Boas Correia — [joaopsn3@gmail.com](mailto:joaopsn3@gmail.com)

---

## Overview

QR Code Generator lets you turn any text, URL, email address, Wi-Fi config, or other content into a crisp, ready-to-export QR code — all without leaving your desktop. The interface is intentionally clean: a strict monochrome palette, generous spacing, and zero visual clutter so the QR code is always the star.

---

## Features

| Feature | Detail |
|---|---|
| Multi-line content input | Paste URLs, long text, Wi-Fi configs, emails, and more |
| Live preview | QR updates automatically as you type (300 ms debounce) |
| Error correction selector | Choose between L / M / Q / H levels |
| Save as PNG | Exported at 800 × 800 px |
| Save as JPEG | Exported at 800 × 800 px, quality 95 |
| Character counter | Displayed in real time below the input label |
| Clear button | Resets input and preview in one click |
| Inline error messages | Subtle dark-grey label — no pop-ups |

---

## Tech Stack

- **Python 3.10+**
- **tkinter** — built-in GUI toolkit, styled to a modern monochrome look
- **qrcode** — QR matrix generation
- **Pillow** — image manipulation and export

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/jovbcorreia/qrcode-generator.git
cd qrcode-generator
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the app

```bash
python app.py
```

The window opens centred on your screen at a fixed 900 × 600 px.

---

## Usage

1. Type or paste your content in the **Content** text area.
2. Select the **Error Correction** level from the dropdown (M is a good default).
3. The QR code preview updates live on the right panel.
4. Click **Save PNG** or **Save JPEG** to export the QR code at 800 × 800 px.
5. Use **Clear** to reset everything.

### Error Correction Levels

| Level | Recovery capacity |
|---|---|
| L | ~7% |
| M | ~15% (default) |
| Q | ~25% |
| H | ~30% |

Higher levels make the QR code denser but more resilient to damage or partial obscuring.

---

## Screenshots

> _Screenshots coming soon — have some to share? Open a PR!_

<!-- Replace the lines below with real screenshot paths once captured -->
<!-- ![Main window](screenshots/main.png) -->
<!-- ![QR code generated](screenshots/qr-generated.png) -->
<!-- ![Save dialog](screenshots/save-dialog.png) -->

---

## Project Structure

```
qrcode-generator/
├── app.py           # Single-file application
├── requirements.txt # Python dependencies
├── LICENSE          # MIT licence
└── README.md        # This file
```

---

## License

This project is licensed under the **MIT License**.  
Copyright © 2026 **João Vilas-Boas Correia** — [joaopsn3@gmail.com](mailto:joaopsn3@gmail.com)

See [LICENSE](LICENSE) for the full text.

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

*Could you share some screenshots of the app running on your machine? I'll add them to this README to give visitors a better first impression of QR Code Generator.*
