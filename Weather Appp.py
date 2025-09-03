
import os
import sys
import math
import threading
from collections import defaultdict, Counter
from datetime import datetime

import requests
import pytz

from PySide6.QtCore import Qt, QSize, Signal, QObject
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QWidget, QLineEdit, QPushButton, QLabel, QVBoxLayout, QHBoxLayout,
    QFrame, QComboBox, QGridLayout, QMessageBox, QSizePolicy, QSpacerItem
)

# ------------------------------
# API Endpoints & Config
# ------------------------------
OWM_API_KEY = os.getenv("OWM_API_KEY", "743e2ebec8848f0bda5d7f53cc46b312")
OWM_GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
OWM_CURR_URL = "https://api.openweathermap.org/data/2.5/weather"
OWM_FCST_URL = "https://api.openweathermap.org/data/2.5/forecast"
OWM_ONECALL_30 = "https://api.openweathermap.org/data/3.0/onecall"
OWM_ONECALL_25 = "https://api.openweathermap.org/data/2.5/onecall"
OWM_ICON_URL = "https://openweathermap.org/img/wn/{}@4x.png"
IPINFO_URL = "http://ip-api.com/json"
TIMEOUT = 12

# ------------------------------
# Networking helpers
# ------------------------------
class WeatherClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise RuntimeError("Missing OWM_API_KEY.")
        self.key = api_key

    # Geocode text → lat/lon
    def geocode(self, query: str):
        r = requests.get(OWM_GEO_URL, params={"q": query, "limit": 1, "appid": self.key}, timeout=TIMEOUT)
        r.raise_for_status()
        items = r.json()
        if not items:
            raise RuntimeError("Location not found.")
        g = items[0]
        return g["lat"], g["lon"], f"{g.get('name','')}{', ' + g.get('country','') if g.get('country') else ''}"

    # Current weather (always available on free tier)
    def current(self, lat: float, lon: float, units: str):
        r = requests.get(OWM_CURR_URL, params={"lat": lat, "lon": lon, "appid": self.key, "units": units}, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        if j.get("cod") not in (200, "200", None):
            raise RuntimeError(j.get("message", "Failed to fetch current weather"))
        return j

    # 5‑day / 3‑hour forecast → aggregate into daily min/max + icon + main/desc
    def forecast_5day(self, lat: float, lon: float, units: str):
        r = requests.get(OWM_FCST_URL, params={"lat": lat, "lon": lon, "appid": self.key, "units": units}, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        if j.get("cod") not in ("200", 200):
            raise RuntimeError(j.get("message", "Failed to fetch forecast"))
        # group entries by date
        buckets: dict[str, list] = defaultdict(list)
        for item in j.get("list", []):
            date_key = datetime.utcfromtimestamp(item["dt"]).strftime("%Y-%m-%d")
            buckets[date_key].append(item)
        days = []
        for date_key, items in buckets.items():
            temps_min = [it["main"]["temp_min"] for it in items]
            temps_max = [it["main"]["temp_max"] for it in items]
            # pick icon near midday if possible; else most common
            noon_item = None
            for it in items:
                hour = datetime.utcfromtimestamp(it["dt"]).hour
                if hour == 12:
                    noon_item = it
                    break
            if noon_item is None:
                icons = [it["weather"][0]["icon"] for it in items]
                icon = Counter(icons).most_common(1)[0][0] if icons else None
                desc = Counter([it["weather"][0]["description"].title() for it in items]).most_common(1)[0][0] if items else ""
            else:
                icon = noon_item["weather"][0]["icon"]
                desc = noon_item["weather"][0]["description"].title()
            days.append({
                "date": date_key,
                "tmin": round(min(temps_min)),
                "tmax": round(max(temps_max)),
                "icon": icon,
                "desc": desc,
            })
        # sort by date and take next 5
        days.sort(key=lambda d: d["date"])
        return days[:5]

    # Alerts via One Call (try 3.0 then 2.5)
    def alerts(self, lat: float, lon: float):
        params = {"lat": lat, "lon": lon, "appid": self.key, "exclude": "current,minutely,hourly,daily"}
        # 3.0
        try:
            r = requests.get(OWM_ONECALL_30, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict) and j.get("alerts"):
                    return j["alerts"]
                # if empty list -> no alerts
                if isinstance(j, dict) and j.get("alerts", []) == []:
                    return []
        except Exception:
            pass
        # 2.5 fallback
        try:
            r = requests.get(OWM_ONECALL_25, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict) and j.get("alerts"):
                    return j["alerts"]
                if isinstance(j, dict) and j.get("alerts", []) == []:
                    return []
        except Exception:
            pass
        # unknown / not available
        return None

    @staticmethod
    def ip_location():
        try:
            r = requests.get(IPINFO_URL, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
            if data.get("lat") is None:
                return None
            return {
                "lat": data["lat"],
                "lon": data["lon"],
                "city": data.get("city") or "My location",
                "country": data.get("country", ""),
                "timezone": data.get("timezone", "UTC"),
            }
        except Exception:
            return None

# ------------------------------
# Thread wrapper
# ------------------------------
class WorkerSignals(QObject):
    result = Signal(dict)
    error = Signal(str)

class FetchThread(threading.Thread):
    def __init__(self, fn, *args, **kwargs):
        super().__init__(daemon=True)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self):
        try:
            res = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(res)
        except Exception as e:
            self.signals.error.emit(str(e))

# ------------------------------
# UI
# ------------------------------
class Card(QFrame):
    def __init__(self):
        super().__init__()
        self.setProperty("class", "card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

class WeatherApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Weather — OpenWeatherMap")
        self.resize(1024, 720)
        self.units = "metric"
        self.tzname = "UTC"
        self.city_label = ""

        try:
            self.client = WeatherClient(OWM_API_KEY)
        except RuntimeError as e:
            QMessageBox.critical(self, "API Key", str(e))
            sys.exit(1)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        # Header
        header = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search city: e.g., Dhaka, BD or Paris")
        self.search.returnPressed.connect(self.on_search)
        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.on_search)
        self.btn_loc = QPushButton("Use my location")
        self.btn_loc.clicked.connect(self.on_my_location)
        self.unit_box = QComboBox()
        self.unit_box.addItems(["Celsius", "Fahrenheit"])
        self.unit_box.currentIndexChanged.connect(self.on_units)
        header.addWidget(self.search, 3)
        header.addWidget(self.btn_search)
        header.addWidget(self.btn_loc)
        header.addWidget(self.unit_box)
        root.addLayout(header)

        # Current card
        self.current_card = Card()
        g = QGridLayout(self.current_card)
        g.setContentsMargins(16, 16, 16, 16)
        g.setHorizontalSpacing(24)

        self.lbl_city = QLabel("—")
        self.lbl_city.setObjectName("h1")
        self.lbl_updated = QLabel("Updated —")
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(QSize(110, 110))
        self.lbl_temp = QLabel("—")
        self.lbl_temp.setObjectName("temp")
        self.lbl_desc = QLabel("—")
        self.lbl_feels = QLabel("Feels like —")
        self.lbl_misc = QLabel("—")

        g.addWidget(self.lbl_city, 0, 0, 1, 2)
        g.addWidget(self.lbl_updated, 0, 2, 1, 1, alignment=Qt.AlignRight)
        g.addWidget(self.icon_label, 1, 0, 3, 1)
        g.addWidget(self.lbl_temp, 1, 1)
        g.addWidget(self.lbl_desc, 2, 1)
        g.addWidget(self.lbl_feels, 3, 1)
        g.addWidget(self.lbl_misc, 4, 0, 1, 3)

        root.addWidget(self.current_card)

        # Forecast card
        self.fc_card = Card()
        vfc = QVBoxLayout(self.fc_card)
        vfc.setContentsMargins(16, 16, 16, 16)
        self.lbl_fc_title = QLabel("5‑day forecast")
        self.lbl_fc_title.setObjectName("h2")
        vfc.addWidget(self.lbl_fc_title)
        self.fc_wrap = QHBoxLayout()
        self.fc_wrap.setSpacing(12)
        vfc.addLayout(self.fc_wrap)
        root.addWidget(self.fc_card)

        # Alerts card
        self.al_card = Card()
        val = QVBoxLayout(self.al_card)
        val.setContentsMargins(16, 16, 16, 16)
        self.lbl_al_title = QLabel("Weather alerts")
        self.lbl_al_title.setObjectName("h2")
        val.addWidget(self.lbl_al_title)
        self.alerts_container = QVBoxLayout()
        self.alerts_container.setSpacing(10)
        val.addLayout(self.alerts_container)
        root.addWidget(self.al_card)

        root.addSpacerItem(QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.apply_styles()
        self.on_my_location()

    # ---- Events ----
    def on_units(self, idx: int):
        self.units = "metric" if idx == 0 else "imperial"
        if self.city_label:
            self.on_search(force=self.city_label)

    def on_search(self, force: str | None = None):
        q = force if force else self.search.text().strip()
        if not q:
            return
        self.setEnabled(False)

        def task():
            lat, lon, label = self.client.geocode(q)
            curr = self.client.current(lat, lon, self.units)
            fc = self.client.forecast_5day(lat, lon, self.units)
            alerts = self.client.alerts(lat, lon)
            return {
                "lat": lat, "lon": lon, "label": label,
                "current": curr, "forecast": fc, "alerts": alerts,
            }

        t = FetchThread(task)
        t.signals.result.connect(self.update_ui)
        t.signals.error.connect(self.fail)
        t.start()

    def on_my_location(self):
        self.setEnabled(False)

        def task():
            loc = WeatherClient.ip_location()
            if not loc:
                raise RuntimeError("Couldn't detect your location. Try searching a city.")
            lat, lon = loc["lat"], loc["lon"]
            label = f"{loc['city']}{', ' + loc['country'] if loc['country'] else ''}"
            curr = self.client.current(lat, lon, self.units)
            fc = self.client.forecast_5day(lat, lon, self.units)
            alerts = self.client.alerts(lat, lon)
            return {"lat": lat, "lon": lon, "label": label, "current": curr, "forecast": fc, "alerts": alerts, "tz": loc.get("timezone", "UTC")}

        t = FetchThread(task)
        t.signals.result.connect(self.update_ui)
        t.signals.error.connect(self.fail)
        t.start()

    # ---- UI updates ----
    def fail(self, msg: str):
        self.setEnabled(True)
        QMessageBox.warning(self, "Error", msg)

    def update_ui(self, payload: dict):
        self.setEnabled(True)
        label = payload.get("label", "—")
        curr = payload.get("current", {})
        fc = payload.get("forecast", [])
        alerts = payload.get("alerts")

        # timezone
        tzname = payload.get("tz")
        if tzname is None:
            # try city timezone from current weather
            tzname = curr.get("timezone")
        self.tzname = "UTC" if tzname is None else (tzname if isinstance(tzname, str) else "UTC")
        tz = pytz.timezone(self.tzname)

        self.city_label = label
        self.lbl_city.setText(label)
        self.lbl_updated.setText(f"Updated {datetime.now(tz).strftime('%Y-%m-%d %H:%M')}")

        # -------- Current --------
        # Guard against missing keys (fixes KeyError 'current')
        main = curr.get("main", {})
        wind = curr.get("wind", {})
        weather0 = (curr.get("weather") or [{}])[0]

        temp = main.get("temp")
        feels = main.get("feels_like")
        humidity = main.get("humidity")
        pressure = main.get("pressure")
        wind_speed = wind.get("speed")
        desc = weather0.get("description", "—").title()
        icon = weather0.get("icon")

        deg = "°C" if self.units == "metric" else "°F"
        spd = "m/s" if self.units == "metric" else "mph"

        self.lbl_temp.setText(f"{round(temp) if isinstance(temp,(int,float)) else '—'}{deg}")
        self.lbl_desc.setText(desc)
        self.lbl_feels.setText(f"Feels like {round(feels)}{deg}" if isinstance(feels,(int,float)) else "Feels like —")
        self.lbl_misc.setText(f"Humidity {humidity}%   •   Wind {wind_speed} {spd}   •   Pressure {pressure} hPa")
        self._set_icon(self.icon_label, icon)

        # -------- Forecast --------
        # clear
        for i in reversed(range(self.fc_wrap.count())):
            w = self.fc_wrap.itemAt(i).widget()
            if w:
                w.setParent(None)
        for day in fc:
            card = Card()
            card.setFixedWidth(180)
            v = QVBoxLayout(card)
            v.setContentsMargins(12,12,12,12)
            v.setSpacing(8)
            dt = datetime.strptime(day["date"], "%Y-%m-%d")
            title = QLabel(dt.strftime("%a %d %b"))
            title.setAlignment(Qt.AlignCenter)
            title.setObjectName("h3")
            icon_lbl = QLabel()
            icon_lbl.setFixedSize(QSize(84,84))
            self._set_icon(icon_lbl, day.get("icon"))
            desc_lbl = QLabel(day.get("desc",""))
            desc_lbl.setAlignment(Qt.AlignCenter)
            tmin, tmax = day.get("tmin"), day.get("tmax")
            temps = QLabel(f"{tmin}{deg} / {tmax}{deg}")
            temps.setAlignment(Qt.AlignCenter)
            v.addWidget(title)
            v.addWidget(icon_lbl, alignment=Qt.AlignCenter)
            v.addWidget(desc_lbl)
            v.addWidget(temps)
            self.fc_wrap.addWidget(card)
        self.fc_wrap.addStretch(1)

        # -------- Alerts --------
        # clear
        for i in reversed(range(self.alerts_container.count())):
            w = self.alerts_container.itemAt(i).widget()
            if w:
                w.setParent(None)
        if alerts is None:
            muted = QLabel("Alerts not available on this API plan for this location.")
            muted.setObjectName("muted")
            self.alerts_container.addWidget(muted)
        elif alerts == []:
            muted = QLabel("No active alerts for this area.")
            muted.setObjectName("muted")
            self.alerts_container.addWidget(muted)
        else:
            for a in alerts:
                ac = Card()
                v = QVBoxLayout(ac)
                v.setContentsMargins(12,12,12,12)
                v.setSpacing(6)
                sender = a.get("sender_name", "Alert")
                event = a.get("event", "Weather Alert")
                start_ts = a.get("start")
                end_ts = a.get("end")
                try:
                    start = datetime.fromtimestamp(start_ts, tz).strftime('%Y-%m-%d %H:%M') if start_ts else "—"
                    end = datetime.fromtimestamp(end_ts, tz).strftime('%Y-%m-%d %H:%M') if end_ts else "—"
                except Exception:
                    start, end = "—", "—"
                title = QLabel(f"{event} — {sender}")
                title.setObjectName("h3")
                timing = QLabel(f"From {start} to {end}")
                body = QLabel(a.get("description", ""))
                body.setWordWrap(True)
                v.addWidget(title)
                v.addWidget(timing)
                v.addWidget(body)
                self.alerts_container.addWidget(ac)

    def _set_icon(self, label: QLabel, icon_code: str | None):
        if not icon_code:
            label.clear()
            return
        try:
            url = OWM_ICON_URL.format(icon_code)
            r = requests.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            pix = QPixmap()
            pix.loadFromData(r.content)
            label.setPixmap(pix.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception:
            label.clear()

    # ---- Styles ----
    def apply_styles(self):
        self.setStyleSheet(
            """
            QWidget { background-color: #0f172a; color: #e2e8f0; font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; font-size: 14px; }
            QLineEdit { background: #111827; border: 1px solid #1f2937; padding: 10px 12px; border-radius: 12px; }
            QLineEdit:focus { border-color: #3b82f6; }
            QPushButton { background: #1f2937; border: 1px solid #334155; padding: 10px 14px; border-radius: 12px; }
            QPushButton:hover { background: #273449; }
            QPushButton:pressed { background: #334155; }
            QComboBox { background: #111827; border: 1px solid #1f2937; padding: 8px 10px; border-radius: 10px; }
            QLabel#h1 { font-size: 22px; font-weight: 600; }
            QLabel#h2 { font-size: 18px; font-weight: 600; margin-bottom: 6px; }
            QLabel#h3 { font-size: 16px; font-weight: 600; }
            QLabel#temp { font-size: 44px; font-weight: 700; }
            QLabel#muted { color: #94a3b8; }
            QFrame[class="card"] { background: #0b1324; border: 1px solid #1e293b; border-radius: 16px; }
            """
        )


def main():
    app = QApplication(sys.argv)
    w = WeatherApp()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
