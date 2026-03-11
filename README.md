# Donna – Desktop Voice Assistant

Donna is a fully functional Windows desktop voice assistant built using Python.

It supports wake-word activation, voice confirmation, browser automation, animated UI effects, and Windows installer packaging.

This project demonstrates real-world desktop application development, speech recognition, automation, UI animation, and software packaging.

---

## 🎯 Features

- Wake word activation: `"donna"`
- Immediate command parsing (e.g., `donna play adele`)
- Voice confirmation system (Yes / No loop)
- Automatic YouTube first-result playback (hands-free)
- Google search + spoken summary (DuckDuckGo + Wikipedia)
- Siri-style animated portrait UI
- Real-time transcript display
- Desktop installer (.exe)
- GitHub version control

---

## 🖥️ Architecture Overview

Donna is built using:

| Component | Technology Used |
|-----------|-----------------|
| GUI | Tkinter |
| Voice Recognition | SpeechRecognition |
| Text-to-Speech | pyttsx3 |
| Web Automation | Selenium + Chrome |
| Search Summary | DuckDuckGo API + Wikipedia |
| Packaging | PyInstaller |
| Installer | Inno Setup |
| Version Control | Git + GitHub |

---

## 🧠 How It Works

1. The application listens continuously for the wake word `"donna"`.
2. If additional words follow the wake word, they are immediately treated as a command.
3. Donna confirms the detected intent verbally.
4. If confirmed:
   - YouTube command → opens Chrome → searches → plays first result automatically.
   - Google command → opens Google → fetches summary → reads it aloud.
5. UI updates:
   - "Heard (raw)"
   - Parsed transcript
   - Spoken output log
   - Animated Siri-style orb

---

## 🚀 What I Learned Building This

This project helped me understand and implement:

### 🔹 1. Desktop Application Development
- Designing structured GUI layouts using Tkinter
- Managing threading for real-time voice + UI updates
- Separating logic (engine) from interface (UI)

### 🔹 2. Speech Recognition & Audio Handling
- Microphone input using PyAudio
- Handling speech recognition errors
- Implementing confirmation loops
- Managing wake-word behavior

### 🔹 3. Text-to-Speech Systems
- Integrating pyttsx3
- Selecting system voices
- Managing audio timing to avoid feedback loops

### 🔹 4. Browser Automation
- Controlling Chrome using Selenium
- Handling YouTube autoplay
- Managing dynamic page loading

### 🔹 5. API Integration
- Using DuckDuckGo Instant Answer API
- Using Wikipedia API
- Parsing structured JSON responses

### 🔹 6. Packaging & Distribution
- Creating standalone EXE using PyInstaller
- Handling bundled resources with `sys._MEIPASS`
- Fixing runtime module issues in packaged apps
- Creating professional Windows installers using Inno Setup

### 🔹 7. Version Control & Project Structuring
- Proper `.gitignore` setup
- Git initialization and remote linking
- Publishing to GitHub
- Managing clean repository structure

---

## 📦 Running Locally

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python donna_app.py
