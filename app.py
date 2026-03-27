"""
AutoPost Desktop App
Double-click to open. Fill in your keys, pick your niche, click Start.
"""

import customtkinter as ctk
import threading
import os
import sys
import json
import queue
import logging
from datetime import datetime
from pathlib import Path

# ── Config paths ─────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).parent
CONFIG_FILE = APP_DIR / "app_config.json"

# ── Appearance ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Niche presets ─────────────────────────────────────────────────────────────
NICHE_PRESETS = {
    "AI & Tech": {
        "niche": "AI, tech startups, and the future of business",
        "style": "Smart, direct, and a little dry. Like a founder texting a friend about something they just saw.",
        "subreddits": ["artificial", "singularity", "ChatGPT", "OpenAI", "MachineLearning", "technology", "startups", "Futurology"],
        "keywords": ["ai", "artificial intelligence", "openai", "chatgpt", "gpt", "llm", "machine learning", "startup", "funding", "nvidia", "anthropic", "tech"],
        "rss": ["https://techcrunch.com/feed/", "https://www.theverge.com/rss/index.xml", "https://www.wired.com/feed/rss", "https://feeds.feedburner.com/venturebeat/SZYF"],
    },
    "Business & Finance": {
        "niche": "business strategy, finance, investing, and entrepreneurship",
        "style": "Sharp, data-driven, and confident. Speaks to founders, investors, and operators.",
        "subreddits": ["business", "entrepreneur", "investing", "stocks", "personalfinance", "smallbusiness"],
        "keywords": ["business", "startup", "funding", "revenue", "profit", "investment", "ipo", "acquisition", "ceo", "founder"],
        "rss": ["https://fortune.com/feed/", "https://www.businessinsider.com/rss", "https://feeds.feedburner.com/entrepreneur/latest"],
    },
    "Crypto & Web3": {
        "niche": "cryptocurrency, blockchain, DeFi, and Web3",
        "style": "Informed and direct. No hype, just signal. Speaks to serious crypto investors.",
        "subreddits": ["CryptoCurrency", "Bitcoin", "ethereum", "CryptoMarkets", "defi", "NFT"],
        "keywords": ["bitcoin", "crypto", "blockchain", "ethereum", "defi", "nft", "web3", "token", "wallet", "protocol"],
        "rss": ["https://coindesk.com/arc/outboundfeeds/rss/", "https://decrypt.co/feed"],
    },
    "Fashion & Streetwear": {
        "niche": "fashion trends, streetwear, luxury brands, and designer drops",
        "style": "Bold, trend-aware, and culturally plugged in. Speaks to fashion enthusiasts.",
        "subreddits": ["fashion", "streetwear", "femalefashionadvice", "malefashionadvice", "sneakers", "Sneakers"],
        "keywords": ["fashion", "streetwear", "designer", "luxury", "sneaker", "drop", "collection", "trend", "style", "brand"],
        "rss": ["https://www.hypebeast.com/feed", "https://www.highsnobiety.com/feed/"],
    },
    "Fitness & Health": {
        "niche": "fitness, health, nutrition, and wellness",
        "style": "Motivational but grounded. Evidence-based. Speaks to people serious about their health.",
        "subreddits": ["fitness", "nutrition", "loseit", "gainit", "running", "bodybuilding", "yoga"],
        "keywords": ["fitness", "workout", "nutrition", "health", "diet", "exercise", "muscle", "weight", "cardio", "wellness"],
        "rss": ["https://www.menshealth.com/rss/all.xml/", "https://www.health.com/rss"],
    },
    "Marketing & Growth": {
        "niche": "digital marketing, growth hacking, SEO, and social media strategy",
        "style": "Practical, data-backed, and no fluff. Speaks to marketers and growth teams.",
        "subreddits": ["marketing", "digital_marketing", "SEO", "socialmedia", "content_marketing", "PPC"],
        "keywords": ["marketing", "seo", "growth", "conversion", "funnel", "ads", "social media", "content", "brand", "campaign"],
        "rss": ["https://feeds.feedburner.com/MarketingLand", "https://blog.hubspot.com/marketing/rss.xml"],
    },
    "Custom": {
        "niche": "",
        "style": "",
        "subreddits": [],
        "keywords": [],
        "rss": [],
    },
}


class AutoPostApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("AutoPost")
        self.geometry("720x600")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.log_queue = queue.Queue()
        self.bot_thread = None
        self.bot_running = False
        self._stop_event = threading.Event()

        self._load_config()
        self._build_ui()
        self._poll_logs()

    # ── Config ────────────────────────────────────────────────────────────────
    def _load_config(self):
        self.config_data = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    self.config_data = json.load(f)
            except Exception:
                pass

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config_data, f, indent=2)
        except Exception:
            pass

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="#111111", corner_radius=0, height=60)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="Auto", font=("", 20, "bold"), text_color="white").pack(side="left", padx=(24, 0), pady=16)
        ctk.CTkLabel(header, text="Post", font=("", 20, "bold"), text_color="#378fe9").pack(side="left", pady=16)
        ctk.CTkLabel(header, text="AI LinkedIn Bot", font=("", 13), text_color="#666").pack(side="left", padx=12, pady=16)

        # Tabs
        self.tabs = ctk.CTkTabview(self, fg_color="#0a0a0a", segmented_button_fg_color="#111111",
                                   segmented_button_selected_color="#0A66C2",
                                   segmented_button_selected_hover_color="#378fe9")
        self.tabs.pack(fill="both", expand=True, padx=0, pady=0)

        self.tabs.add("Setup")
        self.tabs.add("Dashboard")

        self._build_setup_tab()
        self._build_dashboard_tab()

        # If already configured, switch to dashboard
        if self.config_data.get("linkedin_token") and self.config_data.get("anthropic_key"):
            self.tabs.set("Dashboard")

    def _build_setup_tab(self):
        tab = self.tabs.tab("Setup")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="#0a0a0a")
        scroll.pack(fill="both", expand=True, padx=20, pady=16)

        # API Keys section
        ctk.CTkLabel(scroll, text="API Keys", font=("", 13, "bold"), text_color="#888").pack(anchor="w", pady=(0, 10))

        # LinkedIn token
        ctk.CTkLabel(scroll, text="LinkedIn Access Token", font=("", 13)).pack(anchor="w")
        ctk.CTkLabel(scroll, text="Get this from linkedin.com/developers → your app → Auth tab → OAuth token generator",
                     font=("", 11), text_color="#666", wraplength=620).pack(anchor="w", pady=(2, 6))
        self.linkedin_entry = ctk.CTkEntry(scroll, placeholder_text="Paste your LinkedIn access token...",
                                           show="*", height=38, font=("", 12))
        self.linkedin_entry.pack(fill="x", pady=(0, 4))
        if self.config_data.get("linkedin_token"):
            self.linkedin_entry.insert(0, self.config_data["linkedin_token"])
        ctk.CTkButton(scroll, text="Open LinkedIn Developers →", width=200, height=28,
                      font=("", 12), fg_color="transparent", border_width=1, border_color="#333",
                      command=lambda: os.startfile("https://www.linkedin.com/developers/apps")).pack(anchor="w", pady=(0, 16))

        # Anthropic key
        ctk.CTkLabel(scroll, text="Anthropic API Key", font=("", 13)).pack(anchor="w")
        ctk.CTkLabel(scroll, text="Get this from console.anthropic.com → API Keys → Create Key",
                     font=("", 11), text_color="#666").pack(anchor="w", pady=(2, 6))
        self.anthropic_entry = ctk.CTkEntry(scroll, placeholder_text="sk-ant-...",
                                            show="*", height=38, font=("", 12))
        self.anthropic_entry.pack(fill="x", pady=(0, 4))
        if self.config_data.get("anthropic_key"):
            self.anthropic_entry.insert(0, self.config_data["anthropic_key"])
        ctk.CTkButton(scroll, text="Open Anthropic Console →", width=200, height=28,
                      font=("", 12), fg_color="transparent", border_width=1, border_color="#333",
                      command=lambda: os.startfile("https://console.anthropic.com")).pack(anchor="w", pady=(0, 24))

        # Divider
        ctk.CTkFrame(scroll, height=1, fg_color="#222").pack(fill="x", pady=(0, 20))

        # Niche
        ctk.CTkLabel(scroll, text="What do you want to post about?", font=("", 13, "bold"), text_color="#888").pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(scroll, text="Choose a niche", font=("", 13)).pack(anchor="w", pady=(0, 6))
        self.niche_var = ctk.StringVar(value=self.config_data.get("niche_preset", "AI & Tech"))
        niche_menu = ctk.CTkOptionMenu(scroll, variable=self.niche_var,
                                       values=list(NICHE_PRESETS.keys()),
                                       command=self._on_niche_change,
                                       height=38, font=("", 13))
        niche_menu.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(scroll, text="Posting style / tone", font=("", 13)).pack(anchor="w", pady=(0, 6))
        self.style_entry = ctk.CTkEntry(scroll, height=38, font=("", 12))
        self.style_entry.pack(fill="x", pady=(0, 24))

        # Post times
        ctk.CTkFrame(scroll, height=1, fg_color="#222").pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(scroll, text="Post schedule", font=("", 13, "bold"), text_color="#888").pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(scroll, text="Post times (24hr format)", font=("", 13)).pack(anchor="w", pady=(0, 6))

        times_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        times_frame.pack(fill="x", pady=(0, 24))
        self.time_entries = []
        defaults = self.config_data.get("post_times", ["08:00", "13:00", "18:00"])
        for i, t in enumerate(defaults):
            e = ctk.CTkEntry(times_frame, width=100, height=38, font=("", 13))
            e.insert(0, t)
            e.pack(side="left", padx=(0, 10))
            self.time_entries.append(e)

        # Save button
        self.save_btn = ctk.CTkButton(scroll, text="Save & Go to Dashboard →",
                                      height=44, font=("", 14, "bold"),
                                      command=self._save_and_continue)
        self.save_btn.pack(fill="x", pady=(0, 20))

        self.setup_status = ctk.CTkLabel(scroll, text="", font=("", 12), text_color="#ef4444")
        self.setup_status.pack(anchor="w")

        # Set initial values
        self._on_niche_change(self.niche_var.get())

    def _on_niche_change(self, choice):
        preset = NICHE_PRESETS.get(choice, NICHE_PRESETS["AI & Tech"])
        self.style_entry.delete(0, "end")
        self.style_entry.insert(0, self.config_data.get("style", preset["style"]))

    def _save_and_continue(self):
        linkedin = self.linkedin_entry.get().strip()
        anthropic = self.anthropic_entry.get().strip()

        if not linkedin or not anthropic:
            self.setup_status.configure(text="Both API keys are required.", text_color="#ef4444")
            return

        niche_key = self.niche_var.get()
        preset = NICHE_PRESETS.get(niche_key, NICHE_PRESETS["AI & Tech"])

        times = [e.get().strip() for e in self.time_entries if e.get().strip()]
        if not times:
            times = ["08:00", "13:00", "18:00"]

        self.config_data = {
            "linkedin_token": linkedin,
            "anthropic_key": anthropic,
            "niche_preset": niche_key,
            "niche": preset["niche"],
            "style": self.style_entry.get().strip() or preset["style"],
            "subreddits": preset["subreddits"],
            "keywords": preset["keywords"],
            "rss": preset["rss"],
            "post_times": times,
        }
        self._save_config()
        self._write_env()
        self._write_settings()

        self.setup_status.configure(text="✓ Saved!", text_color="#22c55e")
        self.tabs.set("Dashboard")
        self._update_dashboard_info()

    def _write_env(self):
        env_path = APP_DIR / ".env"
        with open(env_path, "w") as f:
            f.write(f"LINKEDIN_ACCESS_TOKEN={self.config_data['linkedin_token']}\n")
            f.write(f"ANTHROPIC_API_KEY={self.config_data['anthropic_key']}\n")

    def _write_settings(self):
        settings_path = APP_DIR / "settings.py"
        subreddits = json.dumps(self.config_data["subreddits"], indent=4)
        keywords = json.dumps(self.config_data["keywords"], indent=4)
        rss = json.dumps(self.config_data["rss"], indent=4)
        times = json.dumps(self.config_data["post_times"])
        with open(settings_path, "w") as f:
            f.write(f'NICHE = "{self.config_data["niche"]}"\n\n')
            f.write(f'POSTING_STYLE = "{self.config_data["style"]}"\n\n')
            f.write(f'SUBREDDITS = {subreddits}\n\n')
            f.write(f'NICHE_KEYWORDS = {keywords}\n\n')
            f.write(f'RSS_FEEDS = {rss}\n\n')
            f.write(f'POST_TIMES = {times}\n\n')
            f.write(f'MIN_VIRAL_SCORE = 7\n')

    # ── Dashboard ─────────────────────────────────────────────────────────────
    def _build_dashboard_tab(self):
        tab = self.tabs.tab("Dashboard")

        # Status bar
        status_frame = ctk.CTkFrame(tab, fg_color="#111111", corner_radius=12, height=80)
        status_frame.pack(fill="x", padx=20, pady=(16, 12))
        status_frame.pack_propagate(False)

        self.status_dot = ctk.CTkLabel(status_frame, text="●", font=("", 20), text_color="#444")
        self.status_dot.pack(side="left", padx=(20, 8))

        info_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="y", pady=12)
        self.status_label = ctk.CTkLabel(info_frame, text="Bot is stopped", font=("", 14, "bold"))
        self.status_label.pack(anchor="w")
        self.niche_label = ctk.CTkLabel(info_frame, text="", font=("", 11), text_color="#666")
        self.niche_label.pack(anchor="w")

        # Start/Stop button
        self.start_btn = ctk.CTkButton(status_frame, text="Start Bot",
                                       width=120, height=40, font=("", 13, "bold"),
                                       fg_color="#0A66C2", hover_color="#378fe9",
                                       command=self._toggle_bot)
        self.start_btn.pack(side="right", padx=20)

        # Log
        ctk.CTkLabel(tab, text="Activity Log", font=("", 12), text_color="#666").pack(anchor="w", padx=20, pady=(0, 6))
        self.log_box = ctk.CTkTextbox(tab, fg_color="#111111", font=("Courier", 11),
                                      text_color="#aaa", wrap="word", corner_radius=12)
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.log_box.configure(state="disabled")

        self._update_dashboard_info()

    def _update_dashboard_info(self):
        niche = self.config_data.get("niche_preset", "Not configured")
        times = ", ".join(self.config_data.get("post_times", []))
        self.niche_label.configure(text=f"{niche}  ·  Posts at {times}" if times else niche)

    def _toggle_bot(self):
        if self.bot_running:
            self._stop_bot()
        else:
            self._start_bot()

    def _start_bot(self):
        if not self.config_data.get("linkedin_token"):
            self._log("⚠ No API keys configured. Go to Setup first.")
            self.tabs.set("Setup")
            return

        self._stop_event.clear()
        self.bot_running = True
        self.start_btn.configure(text="Stop Bot", fg_color="#ef4444", hover_color="#dc2626")
        self.status_dot.configure(text_color="#22c55e")
        self.status_label.configure(text="Bot is running")
        self._log("─" * 50)
        self._log(f"Bot started at {datetime.now().strftime('%H:%M:%S')}")

        self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self.bot_thread.start()

    def _stop_bot(self):
        self._stop_event.set()
        self.bot_running = False
        self.start_btn.configure(text="Start Bot", fg_color="#0A66C2", hover_color="#378fe9")
        self.status_dot.configure(text_color="#444")
        self.status_label.configure(text="Bot is stopped")
        self._log(f"Bot stopped at {datetime.now().strftime('%H:%M:%S')}")

    def _run_bot(self):
        try:
            # Redirect logging to our queue
            handler = QueueHandler(self.log_queue)
            logging.getLogger().addHandler(handler)
            logging.getLogger().setLevel(logging.INFO)

            import schedule
            import time
            from main import run_post_cycle
            from config import POST_TIMES

            self._log("Running first post now...")
            run_post_cycle()

            for t in POST_TIMES:
                schedule.every().day.at(t).do(run_post_cycle)
                self._log(f"Scheduled post at {t}")

            while not self._stop_event.is_set():
                schedule.run_pending()
                time.sleep(30)

        except Exception as e:
            self._log(f"Error: {e}")
            self.bot_running = False
            self.after(0, lambda: self.start_btn.configure(text="Start Bot", fg_color="#0A66C2"))
            self.after(0, lambda: self.status_dot.configure(text_color="#444"))
            self.after(0, lambda: self.status_label.configure(text="Bot stopped due to error"))

    def _log(self, msg):
        self.log_queue.put(msg)

    def _poll_logs(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(500, self._poll_logs)

    def _on_close(self):
        if self.bot_running:
            self._stop_event.set()
        self.destroy()


class QueueHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.q = q

    def emit(self, record):
        self.q.put(self.format(record))


if __name__ == "__main__":
    app = AutoPostApp()
    app.mainloop()
