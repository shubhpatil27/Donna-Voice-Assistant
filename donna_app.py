# donna_app.py
# Full assistant: portrait + siri-like orb + reliable conversation loop + transcript boxes
# Includes resource_path() fix so donna.jpg loads correctly in PyInstaller EXE and after installation.

import os
import re
import time
import threading
import queue
from urllib.parse import quote_plus
import math
import sys

import tkinter as tk
from PIL import Image, ImageTk

import speech_recognition as sr
import pyttsx3
import requests
import wikipedia

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------- CONFIG ----------------
WAKE_WORD = "donna"               # single-word wake; words after are treated as immediate command
CALIBRATE_SECONDS = 2.5
PHRASE_TIME_LIMIT = 10
COMMAND_RETRIES = 4
YESNO_RETRIES = 3
WIKI_SENTENCES = 2

# Portrait file (bundled via --add-data "donna.jpg;.")
PORTRAIT_FILE = "donna.jpg"

# Siri-style orb params (smaller)
GLITTER_COUNT = 28
RING_RADIUS = 92
GLITTER_SPEED = 0.03
GLITTER_COLORS = ["#69E8FF", "#66D6FF", "#3EC7FF", "#8FEFFF", "#BDF8FF"]


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource.
    Works for development (.py) and PyInstaller onefile/onedir (.exe).

    In PyInstaller, sys._MEIPASS points to the extracted bundle folder.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, relative_path)

    # If running as an installed EXE (frozen) but not using _MEIPASS for some reason,
    # look next to the executable.
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), relative_path)

    # Normal script run: next to this file
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


# ---------------- TEXT HELPERS ----------------
def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_yes(text: str) -> bool:
    return bool(re.search(r"\b(yes|yeah|yep|sure|go ahead|do it|correct|please)\b", normalize(text)))


def is_no(text: str) -> bool:
    return bool(re.search(r"\b(no|nope|cancel|wrong|don't|do not|stop)\b", normalize(text)))


def parse_command(text: str):
    t = normalize(text)
    if re.search(r"\b(close app|quit app|exit app)\b", t):
        return ("quit_app", None)
    if re.search(r"\b(stop listening|sleep|go to sleep)\b", t):
        return ("stop_listening", None)
    m = re.search(r"\b(search|google|look up|lookup|find)\b(\s+(for|about))?\s+(?P<q>.+)", t)
    if m:
        return ("google_search", m.group("q"))
    m2 = re.search(r"\b(play|youtube|search youtube)\b(\s+(for|about))?\s+(?P<q>.+)", t)
    if m2:
        q = m2.group("q").replace("on youtube", "").strip()
        return ("youtube_play", q)
    return ("unknown", text)


# ---------------- FREE SEARCH (DuckDuckGo + Wikipedia) ----------------
def get_free_answer(query: str) -> str | None:
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
            timeout=8,
        )
        data = r.json()
        abstract = (data.get("AbstractText") or "").strip()
        if abstract:
            return abstract
        related = data.get("RelatedTopics", [])
        for it in related:
            if isinstance(it, dict) and it.get("Text"):
                txt = it.get("Text").strip()
                if txt:
                    return txt
    except Exception:
        pass

    try:
        wikipedia.set_lang("en")
        s = wikipedia.summary(query, sentences=WIKI_SENTENCES, auto_suggest=True, redirect=True)
        s = (s or "").strip()
        return s if s else None
    except Exception:
        return None


# ---------------- CHROME CONTROLLER (Selenium) ----------------
class ChromeController:
    def __init__(self):
        self.lock = threading.Lock()
        self.driver = None

    def _ensure(self):
        if self.driver:
            return
        opts = Options()
        opts.add_argument("--start-maximized")
        opts.add_argument("--disable-notifications")
        opts.add_argument("--autoplay-policy=no-user-gesture-required")
        # Optional: persistent profile for better autoplay reliability:
        # opts.add_argument(r"--user-data-dir=C:\Users\user\AppData\Local\Google\Chrome\DonnaProfile")
        self.driver = webdriver.Chrome(options=opts)

    def open_google(self, q: str):
        with self.lock:
            self._ensure()
            url = f"https://www.google.com/search?q={quote_plus(q)}"
            self.driver.get(url)

    def _try_accept_youtube_consent(self):
        d = self.driver
        try:
            btns = d.find_elements(
                By.XPATH,
                "//*[self::button or self::tp-yt-paper-button]"
                "[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'accept')]",
            )
            if btns:
                btns[0].click()
                time.sleep(0.25)
        except Exception:
            pass

    def play_first_youtube(self, q: str):
        with self.lock:
            self._ensure()
            d = self.driver
            wait = WebDriverWait(d, 15)
            d.get("https://www.youtube.com/")
            time.sleep(0.6)
            self._try_accept_youtube_consent()
            search = wait.until(EC.presence_of_element_located((By.NAME, "search_query")))
            search.clear()
            search.send_keys(q)
            search.send_keys(Keys.ENTER)
            first = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "ytd-video-renderer a#video-title")))
            first.click()
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "video")))
            try:
                d.find_element(By.TAG_NAME, "body").send_keys("k")  # play/pause
            except Exception:
                pass


# ---------------- TTS voice selection ----------------
def pick_british_female_voice(engine: pyttsx3.Engine):
    voices = engine.getProperty("voices") or []

    def score(v):
        name = (getattr(v, "name", "") or "").lower()
        vid = (getattr(v, "id", "") or "").lower()
        s = 0
        if "hazel" in name or "hazel" in vid:
            s += 100
        if "en-gb" in name or "en-gb" in vid:
            s += 60
        if "british" in name or "united kingdom" in name:
            s += 40
        if "female" in name:
            s += 10
        return s

    best = None
    best_score = -1
    for v in voices:
        sc = score(v)
        if sc > best_score:
            best, best_score = v, sc

    if best and best_score > 0:
        engine.setProperty("voice", best.id)
    else:
        for v in voices:
            if "zira" in (getattr(v, "name", "") or "").lower():
                engine.setProperty("voice", v.id)
                break


# ---------------- DONNA ENGINE ----------------
class DonnaEngine:
    def __init__(self, ui_queue: queue.Queue, on_request_close_cb):
        self.ui_queue = ui_queue
        self.on_request_close_cb = on_request_close_cb
        self.stop_event = threading.Event()
        self.thread = None

        self.chrome = ChromeController()

        # TTS
        self.tts = pyttsx3.init()
        self.tts.setProperty("rate", 170)
        pick_british_female_voice(self.tts)

        # STT
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.9
        self.recognizer.non_speaking_duration = 0.5
        self.mic = sr.Microphone()

    def post(self, typ, value):
        self.ui_queue.put((typ, value))

    def speak(self, text: str):
        self.post("reply", text)
        self.post("status", "SPEAKING")
        try:
            self.tts.say(text)
            self.tts.runAndWait()
        except Exception:
            pass
        time.sleep(0.18)

    def listen(self, timeout=8, phrase_time_limit=PHRASE_TIME_LIMIT) -> str:
        self.post("status", "LISTENING")
        with self.mic as source:
            audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        try:
            text = (self.recognizer.recognize_google(audio) or "").strip()
            if text:
                self.post("heard", text)
            return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError:
            self.post("status", "ERROR: Speech service")
            return ""

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._main_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _main_loop(self):
        # calibrate
        self.post("status", f"CALIBRATING ({CALIBRATE_SECONDS:.1f}s)")
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=CALIBRATE_SECONDS)
        self.post("status", "IDLE")
        self.speak("Hello. I'm Donna. Say Donna when you need me.")

        while not self.stop_event.is_set():
            try:
                heard = self.listen(timeout=12, phrase_time_limit=PHRASE_TIME_LIMIT)
            except sr.WaitTimeoutError:
                continue
            if self.stop_event.is_set():
                break
            if not heard:
                continue

            low = normalize(heard)
            if WAKE_WORD not in low:
                continue

            # extract trailing command (if present in same utterance)
            parts = re.split(r"\b" + re.escape(WAKE_WORD) + r"\b", low, maxsplit=1)
            after = ""
            if len(parts) > 1:
                after = parts[1].strip(" ,.?")

            self.post("status", "AWAKE")
            if after:
                self.post("transcript", after)
                self.speak("Right — I heard that. Let me confirm.")
                intent, arg = parse_command(after)
                if intent == "unknown":
                    self.speak("Sorry, I couldn't understand that. Please say the command after I say ready.")
                    self.speak("Ready.")
                else:
                    if self._confirm_intent(intent, arg):
                        self._execute_intent(intent, arg)
                        continue
                    else:
                        self.speak("Okay — say the command again.")
            else:
                self.speak("Yes? How can I help?")

            # command collection loop
            while not self.stop_event.is_set():
                intent, arg = ("unknown", None)
                got_command = False
                for _ in range(COMMAND_RETRIES):
                    try:
                        cmd = self.listen(timeout=10, phrase_time_limit=PHRASE_TIME_LIMIT)
                    except sr.WaitTimeoutError:
                        cmd = ""
                    if not cmd:
                        self.speak("Sorry, I didn't catch that. Please say it again.")
                        continue
                    self.post("transcript", cmd)
                    intent, arg = parse_command(cmd)
                    if intent == "unknown":
                        self.speak("Sorry, I didn't understand. Please say it again.")
                        continue
                    got_command = True
                    break

                if not got_command:
                    self.speak("Let's try again. Say your command clearly.")
                    break

                if intent == "stop_listening":
                    self.speak("Alright. I will stay quiet. Say Donna when you need me.")
                    self.post("status", "IDLE")
                    break

                if intent == "quit_app":
                    self.speak("Closing the app now. Goodbye.")
                    self.on_request_close()
                    return

                if not self._confirm_intent(intent, arg):
                    continue

                self._execute_intent(intent, arg)
                break

    def _confirm_intent(self, intent, arg) -> bool:
        for _ in range(YESNO_RETRIES):
            if intent == "google_search":
                self.speak(f"You want me to search for {arg}. Shall I go ahead? Say yes or no.")
            elif intent == "youtube_play":
                self.speak(f"You want me to play {arg} on YouTube. Shall I go ahead? Say yes or no.")
            else:
                self.speak("Shall I go ahead? Say yes or no.")
            try:
                ans = self.listen(timeout=8, phrase_time_limit=5)
            except sr.WaitTimeoutError:
                ans = ""
            if is_yes(ans):
                self.speak("Confirmed.")
                return True
            if is_no(ans):
                self.speak("Okay, canceled.")
                return False
            self.speak("Please say yes or no.")
        self.speak("I didn't get a clear confirmation. Canceling.")
        return False

    def _execute_intent(self, intent, arg):
        self.post("status", "WORKING")
        if intent == "youtube_play":
            self.speak(f"Alright. Playing {arg}. Enjoy your music.")
            try:
                self.chrome.play_first_youtube(arg)
            except Exception:
                try:
                    self.chrome.play_first_youtube(arg)
                except Exception:
                    self.speak("I had trouble opening YouTube. Please say the command again.")
                    self.post("status", "ERROR")
                    return
            self.speak("Here you go — enjoy!")
            self.post("status", "IDLE")
            return

        if intent == "google_search":
            self.speak(f"Alright. Searching Google for {arg}.")
            try:
                self.chrome.open_google(arg)
            except Exception:
                pass
            ans = get_free_answer(arg)
            if ans:
                self.speak("Here's what I found.")
                self.speak(ans)
            else:
                self.speak("I opened Google, but couldn't find a quick summary.")
            self.speak("Anything else you would like?")
            self.post("status", "IDLE")
            return

    def on_request_close(self):
        try:
            self.post("status", "CLOSING")
        except Exception:
            pass
        try:
            self.on_request_close_cb()
        except Exception:
            pass


# ---------------- GUI: portrait + siri-like orb + transcript boxes ----------------
class PortraitUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Donna — Voice Assistant")
        self.geometry("880x660")
        self.configure(bg="#02030a")
        self.ui_queue = queue.Queue()

        # load portrait image (FIXED for PyInstaller + installer)
        img_path = resource_path(PORTRAIT_FILE)
        if not os.path.exists(img_path):
            raise FileNotFoundError(
                f"Portrait image not found at:\n{img_path}\n"
                f"Make sure '{PORTRAIT_FILE}' is bundled with PyInstaller (--add-data) "
                f"or placed next to the executable."
            )

        pil = Image.open(img_path).convert("RGBA")
        pil = pil.resize((420, 560), Image.LANCZOS)
        self.portrait_tk = ImageTk.PhotoImage(pil)

        self._build_layout()
        self.glitters = []
        self._init_glitters()

        self.engine = DonnaEngine(self.ui_queue, on_request_close_cb=self._request_close)
        self.engine.start()

        self.orb_phase = 0.0
        self.orb_level = 0.35
        self.orb_target = 0.35
        self.after(24, self._animate)
        self.after(80, self._poll_ui_queue)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self):
        header = tk.Frame(self, bg="#02030a")
        header.pack(fill="x", padx=14, pady=(10, 6))
        tk.Label(header, text="DONNA", fg="#CFEFFF", bg="#02030a",
                 font=("Segoe UI", 18, "bold")).pack(side="left")
        self.status_var = tk.StringVar(value="BOOTING")
        self.status_label = tk.Label(header, textvariable=self.status_var, bg="#071022",
                                     fg="#6BE8FF", padx=10, pady=6, font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side="right")

        body = tk.Frame(self, bg="#02030a")
        body.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        body.columnconfigure(1, weight=1)

        # left: portrait canvas
        self.canvas = tk.Canvas(body, width=460, height=600, bg="#02030a", bd=0, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        self.canvas.create_rectangle(0, 0, 460, 600, fill="#071022", outline="")
        self.canvas.create_image(230, 310, image=self.portrait_tk)
        self.center_x = 230
        self.center_y = 310

        # right: logs & transcript boxes
        right = tk.Frame(body, bg="#061323")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        tk.Label(right, text="Heard (raw)", bg="#061323", fg="#9FCFF0",
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(12, 4))
        self.heard_var = tk.StringVar(value="—")
        tk.Label(right, textvariable=self.heard_var, bg="#061323", fg="#E8F7FF",
                 wraplength=360, justify="left", font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", padx=10)

        tk.Label(right, text="Transcript (command)", bg="#061323", fg="#9FCFF0",
                 font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", padx=10, pady=(10, 4))
        self.transcript_var = tk.StringVar(value="—")
        tk.Label(right, textvariable=self.transcript_var, bg="#061323", fg="#E8F7FF",
                 wraplength=360, justify="left", font=("Segoe UI", 11)).grid(row=3, column=0, sticky="w", padx=10)

        tk.Label(right, text="Donna says", bg="#061323", fg="#9FCFF0",
                 font=("Segoe UI", 9, "bold")).grid(row=4, column=0, sticky="w", padx=10, pady=(10, 4))
        self.output_box = tk.Text(right, bg="#021826", fg="#E8F7FF", height=14,
                                  wrap="word", bd=0, font=("Consolas", 11))
        self.output_box.grid(row=5, column=0, sticky="nsew", padx=10, pady=(0, 12))
        self.output_box.insert("1.0", "—")
        self.output_box.configure(state="disabled")

    def _set_output(self, text: str):
        self.output_box.configure(state="normal")
        if self.output_box.get("1.0", "end").strip() == "—":
            self.output_box.delete("1.0", "end")
        ts = time.strftime("%H:%M:%S")
        self.output_box.insert("end", f"[{ts}] {text}\n\n")
        self.output_box.see("end")
        self.output_box.configure(state="disabled")

    def _init_glitters(self):
        self.glitters = []
        for i in range(GLITTER_COUNT):
            angle = (i / GLITTER_COUNT) * (2 * math.pi)
            speed = GLITTER_SPEED * (0.6 + 0.8 * (i % 5) / 5)
            radius_jitter = (RING_RADIUS * (0.88 + 0.08 * ((i % 7) / 7)))
            size = 1 + (i % 3)
            color = GLITTER_COLORS[i % len(GLITTER_COLORS)]
            self.glitters.append({
                "angle": angle,
                "speed": speed,
                "r": radius_jitter,
                "size": size,
                "color": color,
                "phase": (i % 10) / 10.0
            })

    def _poll_ui_queue(self):
        try:
            while True:
                typ, value = self.ui_queue.get_nowait()
                if typ == "status":
                    self._apply_status(value)
                elif typ == "heard":
                    self.heard_var.set(value if value else "—")
                elif typ == "transcript":
                    self.transcript_var.set(value if value else "—")
                elif typ == "reply":
                    self._set_output(value if value else "—")
        except queue.Empty:
            pass
        self.after(80, self._poll_ui_queue)

    def _apply_status(self, s: str):
        s_up = (s or "").upper()
        self.status_var.set(s_up)
        if "LISTEN" in s_up:
            self.orb_target = 0.9
        elif "SPEAK" in s_up:
            self.orb_target = 1.0
        elif "WORK" in s_up:
            self.orb_target = 0.95
        elif "ERROR" in s_up:
            self.orb_target = 1.0
        else:
            self.orb_target = 0.35

    def _animate(self):
        self.orb_phase += 0.08
        self.orb_level += (self.orb_target - self.orb_level) * 0.08

        self.canvas.delete("glitter")
        self.canvas.delete("siri_orb")

        cx, cy = self.center_x, self.center_y
        base_r = RING_RADIUS
        intensity = max(0.25, self.orb_level)

        # soft halo layers
        for i in range(3):
            r = base_r + 18 + i * 8 + (8 * intensity)
            try:
                self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                        fill="#041826", outline="", tags=("siri_orb", "glitter"))
            except Exception:
                pass

        # neon rings
        try:
            self.canvas.create_oval(cx - (base_r + 6), cy - (base_r + 6),
                                    cx + (base_r + 6), cy + (base_r + 6),
                                    outline="#5EE3FF", width=3, tags=("siri_orb",))
            self.canvas.create_oval(cx - (base_r - 8), cy - (base_r - 8),
                                    cx + (base_r - 8), cy + (base_r - 8),
                                    outline="#9B7DFF", width=2, tags=("siri_orb",))
            core_r = int(base_r * 0.48 + 6 * intensity)
            self.canvas.create_oval(cx - core_r, cy - core_r, cx + core_r, cy + core_r,
                                    fill="#041422", outline="", tags=("siri_orb",))
        except Exception:
            pass

        # rotating swirls (arcs)
        swirl_radius = base_r * 0.66
        swirl_thickness = int(12 * (0.6 + 0.6 * intensity))
        for k, col in enumerate(("#A855F7", "#2AE7FF", "#7EF0B8")):
            start_angle = (self.orb_phase * 20 + k * 45) % 360
            extent = 110 + int(25 * math.sin(self.orb_phase + k))
            steps = 12
            for s in range(steps):
                a0 = start_angle + (s / steps) * extent
                a1 = a0 + (extent / steps) * 0.9
                r_out = swirl_radius + 6 * math.sin(self.orb_phase * (1 + k * 0.2) + s * 0.12)
                bbox = (cx - r_out, cy - r_out, cx + r_out, cy + r_out)
                try:
                    self.canvas.create_arc(
                        bbox, start=a0, extent=(a1 - a0), style="arc",
                        outline=col, width=max(1, int(swirl_thickness * 0.14)),
                        tags=("siri_orb",)
                    )
                except Exception:
                    pass

        # center highlight
        try:
            shine_r = int(base_r * 0.22 + 4 * intensity)
            self.canvas.create_oval(cx - shine_r, cy - shine_r, cx + shine_r, cy + shine_r,
                                    fill="#DDFBFF", outline="", tags=("siri_orb",))
            self.canvas.create_oval(cx - int(shine_r * 0.55), cy - int(shine_r * 0.55),
                                    cx + int(shine_r * 0.55), cy + int(shine_r * 0.55),
                                    fill="#9EEAFF", outline="", tags=("siri_orb",))
        except Exception:
            pass

        # glitters
        for g in self.glitters:
            g["angle"] += g["speed"] * (0.6 + 1.5 * self.orb_level)
            a = g["angle"] + 0.2 * math.sin(self.orb_phase + g["phase"] * 2.1)
            rj = g["r"] * (0.92 + 0.08 * math.sin(self.orb_phase * 1.1 + g["phase"]))
            x = cx + math.cos(a) * rj
            y = cy + math.sin(a) * (rj * 0.82)
            size = max(1.0, g["size"] * (0.6 + 0.6 * (0.5 + 0.5 * math.sin(self.orb_phase + g["phase"]))))
            col = g["color"]
            try:
                self.canvas.create_oval(x - size * 1.2, y - size * 1.2, x + size * 1.2, y + size * 1.2,
                                        fill=col, outline="", tags=("glitter",))
                self.canvas.create_oval(x - size * 0.5, y - size * 0.5, x + size * 0.5, y + size * 0.5,
                                        fill="#FFFFFF", outline="", tags=("glitter",))
            except Exception:
                pass

        self.after(24, self._animate)

    def _request_close(self):
        self.after(0, self._on_close)

    def _on_close(self):
        try:
            self.engine.stop()
        except Exception:
            pass
        self.destroy()


# ---------------- ENTRY POINT ----------------
if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    ui = PortraitUI()
    ui.mainloop()
