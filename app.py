#!/usr/bin/env python3
import os
import json
import subprocess
import glob

from datetime import datetime, timedelta  # ← added for timestamps

from flask import Flask, render_template, request, redirect, url_for, session, jsonify  # ← added jsonify
from werkzeug.security import check_password_hash
import psutil
import requests
from exercise_app import exercise_bp
from basecamp_core import BASE_DIR, LOG_FILE, login_required, admin_required, log_action

app = Flask(__name__)
app.register_blueprint(exercise_bp, url_prefix="/exercise")


# ───────────── Services Configuration ─────────────
SERVICES = [
    {"label": "Navidrome", "unit": "navidrome.service"},
    {"label": "File Browser", "unit": "filebrowser.service"},
]

# ───────────── Config ─────────────
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "change-me-to-something-random")

# users.json will live next to this file

USERS_FILE = os.path.join(BASE_DIR, "users.json")


# Backup status JSON (written by /usr/local/bin/nas-backup.sh)
BACKUP_STATUS_FILE = "/var/lib/pinas/backup_status.json"


# Tailscale HTTPS host (used when coming in over VPN)
# Change this if your tailnet name ever changes.
TAILSCALE_HOST = os.environ.get("TAILSCALE_HOST", "pi-nas.tail6f44bf.ts.net")



# ───────────── Office Notify (ESP32-C3) ─────────────
OFFICE_NOTIFY_BASE = os.environ.get("OFFICE_NOTIFY_BASE", "http://office-notify.local")
OFFICE_NOTIFY_TIMEOUT = float(os.environ.get("OFFICE_NOTIFY_TIMEOUT", "1.5"))

VALID_OFFICE_MSGS = {"tea", "food", "free", "other"}

def office_notify_fetch_status():
    """Return (online_bool, payload_or_none)."""
    try:
        r = requests.get(f"{OFFICE_NOTIFY_BASE}/status", timeout=OFFICE_NOTIFY_TIMEOUT)
        r.raise_for_status()
        return True, r.json()
    except Exception:
        return False, None



# ───────────── User helpers ─────────────
def load_users():
    """Load users from users.json, returns dict like {username: {password_hash: '...', role: 'user'}}"""
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def get_user(username):
    users = load_users()
    return users.get(username)





def load_logs(limit=200):
    """Load the last `limit` log entries, newest first."""
    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r") as f:
            lines = f.readlines()
    except OSError:
        return []

    recent_lines = lines[-limit:]
    entries = []
    for line in recent_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    entries.reverse()  # newest first
    return entries


# ───────────── System Stats Helpers ─────────────
def get_uptime_and_boot_time():
    """Get system uptime and boot time."""
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_seconds = (datetime.now() - boot_time).total_seconds()
        
        # Format uptime
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        if days > 0:
            uptime_str = f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            uptime_str = f"{hours}h {minutes}m"
        else:
            uptime_str = f"{minutes}m"
        
        return {
            "uptime": uptime_str,
            "boot_time": boot_time.strftime("%d/%m/%Y %H:%M:%S")
        }
    except Exception as e:
        return {
            "uptime": "Unknown",
            "boot_time": "Unknown"
        }


def get_cpu_usage():
    """Get current CPU usage percentage."""
    try:
        return round(psutil.cpu_percent(interval=1), 1)
    except Exception:
        return None


def get_cpu_temperature():
    """Get CPU temperature and status badge."""
    try:
        # Try to read from thermal_zone (common on Raspberry Pi)
        temp = None
        temp_c = None
        
        # Check thermal zones
        thermal_zones = glob.glob("/sys/class/thermal/thermal_zone*/temp")
        for zone in thermal_zones:
            try:
                with open(zone, "r") as f:
                    raw_temp = int(f.read().strip())
                    # Some sensors report in millidegrees
                    if raw_temp > 1000:
                        temp_c = raw_temp / 1000.0
                    else:
                        temp_c = raw_temp
                    if temp_c is None or temp_c > 0:
                        temp = temp_c
                        break
            except (ValueError, IOError):
                continue
        
        if temp is None:
            # Fallback: try psutil (may not work on all systems)
            try:
                if hasattr(psutil, "sensors_temperatures"):
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for name, entries in temps.items():
                            for entry in entries:
                                if "cpu" in name.lower() or "core" in name.lower():
                                    temp = entry.current
                                    break
                            if temp:
                                break
            except Exception:
                pass
        
        if temp is None:
            return {"temperature": None, "status": "unknown", "label": "Unknown"}
        
        # Determine status badge
        if temp < 50:
            status = "cool"
            label = "Cool"
        elif temp <= 65:
            status = "warm"
            label = "Warm"
        else:
            status = "hot"
            label = "Hot"
        
        return {
            "temperature": round(temp, 1),
            "status": status,
            "label": label
        }
    except Exception:
        return {"temperature": None, "status": "unknown", "label": "Unknown"}


def get_ds18b20_temperature():
    """Read temperature from DS18B20 sensor."""
    try:
        # Find DS18B20 devices (they start with 28-)
        devices = glob.glob("/sys/bus/w1/devices/28-*/w1_slave")
        
        if not devices:
            return None
        
        # Use the first found device
        device_path = devices[0]
        
        with open(device_path, "r") as f:
            content = f.read()
            
        # DS18B20 format: last line contains t=12345 (temperature in millidegrees)
        if "t=" in content:
            temp_line = [line for line in content.split("\n") if "t=" in line]
            if temp_line:
                temp_raw = temp_line[0].split("t=")[-1].strip()
                if temp_raw and temp_raw != "":
                    temp_millidegrees = int(temp_raw)
                    temp_celsius = temp_millidegrees / 1000.0
                    return round(temp_celsius, 1)
        
        return None
    except Exception:
        return None


def get_service_status(service_unit):
    """Get systemd service status. Returns 'running', 'stopped', or 'unknown'."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_unit],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        status = result.stdout.strip().lower()
        if status == "active":
            return "running"
        elif status in ["inactive", "failed"]:
            return "stopped"
        else:
            return "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return "unknown"


def get_all_service_statuses():
    """Get status for all configured services."""
    services_status = []
    for service in SERVICES:
        status = get_service_status(service["unit"])
        services_status.append({
            "label": service["label"],
            "unit": service["unit"],
            "status": status
        })
    return services_status



# ───────────── NAS STORAGE helpers ─────────────

def get_nas_storage_stats():
    """Return capacity + file-type breakdown for /mnt/nasdata."""
    path = "/mnt/nasdata"

    # Overall disk usage
    try:
        usage = psutil.disk_usage(path)
        total = usage.total
        used = usage.used
        free = usage.free
        mounted = True
    except FileNotFoundError:
        return {
            "mounted": False,
            "path": path,
            "total": 0,
            "used": 0,
            "free": 0,
            "used_percent": 0,
            "file_types": [],
        }

    # File-type categories by extension
    extensions_map = {
        "video": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv"},
        "music": {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a"},
        "images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff"},
        "documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".py"},
        "archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    }

    type_sizes = {k: 0 for k in extensions_map}
    type_sizes["other"] = 0

    # Walk the NASDATA tree and sum file sizes by type
    for root, dirs, files in os.walk(path):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            fpath = os.path.join(root, fname)
            try:
                size = os.path.getsize(fpath)
            except OSError:
                continue

            matched = False
            for category, exts in extensions_map.items():
                if ext in exts:
                    type_sizes[category] += size
                    matched = True
                    break
            if not matched:
                type_sizes["other"] += size

    # Convert to list, sorted, with percentages of USED space
    file_types = []
    if used > 0:
        for label, size in type_sizes.items():
            if size <= 0:
                continue
            percent = round(size / used * 100, 1)
            file_types.append({
                "label": label.capitalize(),           # e.g. "Video"
                "bytes": size,
                "percent_of_used": percent,
            })
        file_types.sort(key=lambda x: x["bytes"], reverse=True)

    return {
        "mounted": mounted,
        "path": path,
        "total": total,
        "used": used,
        "free": free,
        "used_percent": round(used / total * 100, 1) if total else 0,
        "file_types": file_types,
    }






# ───────────── Network / VPN helpers ─────────────
def is_local_request():
    """
    Return True if the client appears to be on the home LAN,
    False if coming via VPN/remote (e.g. Tailscale).
    """
    # Prefer X-Forwarded-For if ever behind a proxy, otherwise remote_addr
    ip = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()

    # Common private LAN ranges
    local_prefixes = (
        "192.168.",
        "10.",
        "172.16.", "172.17.", "172.18.", "172.19.",
        "172.20.", "172.21.", "172.22.", "172.23.",
        "172.24.", "172.25.", "172.26.", "172.27.",
        "172.28.", "172.29.", "172.30.", "172.31.",
    )

    return any(ip.startswith(p) for p in local_prefixes)




# ───────────── Backup Status Helper ─────────────
def load_backup_status():
    """Load backup status from JSON file written by the backup script."""
    if not os.path.exists(BACKUP_STATUS_FILE):
        return {}

    try:
        with open(BACKUP_STATUS_FILE, "r") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    # Ensure keys exist so template doesn't blow up
    return {
        "status": data.get("status"),
        "last_attempt": data.get("last_attempt"),
        "last_success": data.get("last_success"),
    }





# ───────────── Routes ─────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, skip login page
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = get_user(username)

        if user and check_password_hash(user["password_hash"], password):
            session["logged_in"] = True
            session["username"] = username
            session["role"] = user.get("role", "user")
            session["name"] = user.get("name", username)
            log_action(username, "login", {"role": session["role"]})  # ← log successful login
            next_url = request.args.get("next") or url_for("dashboard")
            return redirect(next_url)
        else:
            error = "Invalid username or password"
            log_action(username or "unknown", "login_failed")  # ← log failed login

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    username = session.get("username")
    log_action(username, "logout")  # ← log logout
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    # Extract just the host part (no port)
    host = request.host.split(":")[0]

    on_lan = is_local_request()

    if on_lan:
        # ───────── LOCAL NETWORK: use plain HTTP + ports ─────────
        # "host" here will usually be your Pi's LAN IP, e.g. 192.168.0.132
        music_url = f"http://{host}:4533"
        file_explorer_url = f"http://{host}:8080"
        growstuff_url = "http://192.168.0.132:5000"
        router_url = "http://192.168.0.1"
    else:
        # ───────── TAILSCALE: Music + Files via HTTPS, GrowStuff direct HTTP ─────────
        base_host = TAILSCALE_HOST

        # These ports must match your tailscale serve config:
        #   44533 -> localhost:4533 (Music)
        #   48080 -> localhost:8080 (Files)
        music_url = f"https://{base_host}:44533/"
        file_explorer_url = f"https://{base_host}:48080/"

        # GrowStuff is not using tailscale serve anymore, just direct over Tailscale
        # (browser will say "Not secure" because it's HTTP, but it's still inside Tailscale)
        growstuff_url = f"http://100.119.255.83:5000"

        # Router: still LAN IP, reachable over Tailscale if routes are set up
        router_url = "http://192.168.0.1"

    links = [
        {
            "name": "Music",
            "url": music_url,
            "description": "Access and stream Basecamp music library.",
            "icon": "fa-solid fa-music",
        },
        {
            "name": "File Explorer",
            "url": file_explorer_url,
            "description": "View and manage all files stored on the Basecamp NAS.",
            "icon": "fa-solid fa-folder-open",
        },
        {
            "name": "GrowStuff Dashboard",
            "url": growstuff_url,
            "description": "View and control the GrowStuff Experimental Dashboard.",
            "icon": "fa-solid fa-seedling",
        },
        {
            "name": "Router Admin",
            "url": router_url,
            "description": "Access router settings and network controls.",
            "icon": "fa-solid fa-wifi",
        },
        {
            "name": "Exercise",
            "url": url_for("exercise.home"),
            "description": "Generate and run a quick workout.",
            "icon": "fa-solid fa-dumbbell",
        },


    ]

    username = session.get("username")
    log_action(username, "view_dashboard", {"on_lan": on_lan})

    # Load logs if admin
    logs = []
    if session.get("role") == "admin":
        logs = load_logs(limit=200)

    # Load system stats
    uptime_data = get_uptime_and_boot_time()
    cpu_usage = get_cpu_usage()
    cpu_temp = get_cpu_temperature()
    case_temp = get_ds18b20_temperature()
    services = get_all_service_statuses()

    # Load NAS storage stats
    nas_storage = get_nas_storage_stats()
    
    # Load backup status
    backup_status = load_backup_status()

    return render_template(
        "dashboard.html",
        links=links,
        logs=logs,
        uptime=uptime_data["uptime"],
        boot_time=uptime_data["boot_time"],
        cpu_usage=cpu_usage,
        cpu_temp=cpu_temp,
        case_temp=case_temp,
        services=services,
        nas_storage=nas_storage,
        nas_storage_json=json.dumps(nas_storage),
        backup_status=backup_status,
    )



@app.route("/run-backup", methods=["POST"])
@login_required
@admin_required
def run_backup():
    """Manually trigger NAS backup script."""
    username = session.get("username")
    log_action(username, "manual_backup_triggered")

    # Run the backup script in the background so the request returns quickly
    try:
        subprocess.Popen(["/usr/local/bin/nas-backup.sh"])
    except Exception as e:
        log_action(username, "manual_backup_error", {"error": str(e)})

    # Redirect back to dashboard backup page
    return redirect(url_for("dashboard") + "#backup")




@app.route("/logs")
@login_required
@admin_required
def view_logs():
    """Admin-only logs page - redirects to dashboard with logs view."""
    username = session.get("username")
    log_action(username, "view_logs")  # ← log that logs were viewed
    
    # Redirect to dashboard with hash to show logs page
    return redirect(url_for("dashboard") + "#logs")


@app.route("/log-action", methods=["POST"])
@login_required
def log_action_endpoint():
    """Endpoint for dashboard JS to log user actions (e.g. link clicks)."""
    username = session.get("username")
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}

    action = data.get("action", "unknown_action")
    details = {
        "target": data.get("target"),
        "extra": data.get("extra"),
    }

    log_action(username, action, details)
    return jsonify({"status": "ok"})


@app.route("/system-stats")
@login_required
def system_stats():
    """Display system statistics page."""
    username = session.get("username")
    log_action(username, "view_system_stats")
    
    # Gather all system stats
    uptime_data = get_uptime_and_boot_time()
    cpu_usage = get_cpu_usage()
    cpu_temp = get_cpu_temperature()
    case_temp = get_ds18b20_temperature()
    services = get_all_service_statuses()
    
    return render_template("system_stats.html",
                         uptime=uptime_data["uptime"],
                         boot_time=uptime_data["boot_time"],
                         cpu_usage=cpu_usage,
                         cpu_temp=cpu_temp,
                         case_temp=case_temp,
                         services=services)




@app.route("/office-notify/status", methods=["GET"])
@login_required
def office_notify_status():
    username = session.get("username")
    online, payload = office_notify_fetch_status()
    log_action(username, "office_notify_status", {"online": online})
    return jsonify({"online": online, "status": payload})


@app.route("/office-notify/send", methods=["POST"])
@login_required
def office_notify_send():
    username = session.get("username")

    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}

    msg = (data.get("msg") or "").strip().lower()

    if msg not in VALID_OFFICE_MSGS:
        log_action(username, "office_notify_send_invalid", {"msg": msg})
        return jsonify({"ok": False, "error": "invalid_msg"}), 400

    try:
        r = requests.get(
            f"{OFFICE_NOTIFY_BASE}/notify",
            params={"msg": msg},
            timeout=OFFICE_NOTIFY_TIMEOUT
        )
        r.raise_for_status()
        log_action(username, "office_notify_send", {"msg": msg})
        return jsonify({"ok": True})
    except Exception as e:
        log_action(username, "office_notify_send_failed", {"msg": msg, "error": str(e)})
        return jsonify({"ok": False, "error": "device_unreachable"}), 502





if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

