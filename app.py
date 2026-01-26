import streamlit as st
import pandas as pd
import json
import itertools
import requests
import base64
import qrcode
from io import BytesIO

# ==================================================
# CONSTANTS
# ==================================================
COPY_BOX_HEIGHT = 160
DEFAULT_SEPARATOR = "-"
DEFAULT_EXTRAS_MODE = "Single"
EXTRAS_PER_PAGE = 8

# ==================================================
# SETUP
# ==================================================
st.set_page_config(page_title="Blastline SKU Configurator", layout="wide")

# ==================================================
# GITHUB STORAGE (DISABLED FOR RENDER)
# ==================================================
class GithubStorage:
    """Handles data persistence to GitHub repository (disabled on Render)."""

    def __init__(self):
        self.can_connect = False

    def load(self):
        return None

    def save(self, data):
        return False

# ==================================================
# HELPERS
# ==================================================
def get_option_label(o):
    return f"{o['code']} : {o['name']}"

def normalize_fields(cat):
    fields = {}
    for i, (k, v) in enumerate(cat.get("fields", {}).items(), start=1):
        if isinstance(v, dict):
            fields[k] = v
        else:
            fields[k] = {"order": i, "options": v}
    cat["fields"] = fields

def ordered_fields(fields):
    return sorted(fields.keys(), key=lambda k: fields[k].get("order", 999))

def normalize_option_df(data):
    df = pd.DataFrame(data or [], columns=["code", "name", "order"])
    if df.empty:
        df = pd.DataFrame(columns=["code", "name", "order"])
    if df["order"].isnull().all():
        df["order"] = range(1, len(df) + 1)
    return df[["code", "name", "order"]]

def normalize_extras_df(data):
    df = pd.DataFrame(data or [], columns=["code", "name", "order"])
    if df.empty:
        df = pd.DataFrame(columns=["code", "name", "order"])
    if "order" not in df.columns or df["order"].isnull().all():
        df["order"] = range(1, len(df) + 1)
    return df[["code", "name", "order"]]

def generate_full_matrix(cat_data):
    normalize_fields(cat_data)
    fields = cat_data["fields"]
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)

    field_combos = []
    field_names = []

    for f in ordered_fields(fields):
        opts = fields[f]["options"]
        is_text = opts and opts[0].get("type") == "text"
        if not is_text and opts:
            field_names.append(f)
            field_combos.append([o["code"] for o in opts])

    if not field_combos:
        return pd.DataFrame(columns=["SKU"] + field_names)

    combinations = list(itertools.product(*field_combos))

    rows = []
    for combo in combinations:
        sku = sep.join(combo)
        row = {"SKU": sku}
        for i, fname in enumerate(field_names):
            row[fname] = combo[i]
        rows.append(row)

    return pd.DataFrame(rows)

def generate_qr_code(text, size=200):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer

def get_qr_code_base64(text):
    buffer = generate_qr_code(text)
    return base64.b64encode(buffer.getvalue()).decode()

def show_success(msg): st.success(msg)
def show_error(msg): st.error(msg)
def show_info(msg): st.info(msg)

# ==================================================
# INIT
# ==================================================
if "sku_data" not in st.session_state:
    gh = GithubStorage()
    st.session_state["sku_data"] = gh.load() or {"inventory": {}}

if "page" not in st.session_state:
    st.session_state["page"] = "home"

if "extras_page" not in st.session_state:
    st.session_state["extras_page"] = 0

def go(p):
    st.session_state["page"] = p
    st.rerun()

# ==================================================
# HOME
# ==================================================
def home():
    with st.sidebar:
        if st.button("⚙️ Settings", use_container_width=True):
            go("login")

    st.markdown(
        "<h2 style='text-align:center;'>Blastline SKU Configurator</h2>",
        unsafe_allow_html=True
    )

    inv = st.session_state["sku_data"]["inventory"]
    if not inv:
        st.warning("No categories available. Please contact admin.")
        return

    cat = st.selectbox("Product Category", list(inv.keys()))
    cat_data = inv[cat]
    normalize_fields(cat_data)

    fields = cat_data["fields"]
    extras = cat_data.get("extras", [])
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)
    extras_mode = cat_data.get("settings", {}).get("extras_mode", DEFAULT_EXTRAS_MODE)

    sel = {}
    chosen = []

    for f in ordered_fields(fields):
        opts = fields[f]["options"]
        is_text = opts and opts[0].get("type") == "text"
        if is_text:
            val = st.text_input(f)
            sel[f] = {"code": val, "name": val}
        else:
            if opts:
                o = st.selectbox(f, opts, format_func=lambda x: f"{x['code']} - {x['name']}")
                sel[f] = {"code": o["code"], "name": o["name"]}

    base = sep.join([sel[k]["code"] for k in ordered_fields(fields) if sel[k]["code"]])
    extras_codes = "".join([c["code"] for c in chosen])
    sku = base + (sep if base and extras_codes else "") + extras_codes

    if sku:
        st.success(f"Generated SKU: {sku}")
        st.image(generate_qr_code(sku))
    else:
        st.info("Select options to generate SKU")

# ==================================================
# LOGIN
# ==================================================
def login():
    pw = st.text_input("Admin Password", type="password")
    if st.button("Login"):
        if pw == "admin123":
            go("admin")
        else:
            show_error("Invalid password")

# ==================================================
# ADMIN
# ==================================================
def admin():
    st.title("Admin Settings")
    if st.button("← Back"):
        go("home")

    inv = st.session_state["sku_data"]["inventory"]
    cat = st.selectbox("Category", list(inv.keys()) if inv else [])

    if st.button("☁️ Save to Cloud"):
        show_error("Cloud save disabled on Render")

# ==================================================
# ROUTER
# ==================================================
if st.session_state["page"] == "home":
    home()
elif st.session_state["page"] == "login":
    login()
elif st.session_state["page"] == "admin":
    admin()
