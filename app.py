import streamlit as st
import pandas as pd
import json
import itertools
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

def normalize_option_df(data):
    df = pd.DataFrame(data or [], columns=["code", "name", "order"])
    if df.empty:
        df = pd.DataFrame(columns=["code", "name", "order"])
    if df["order"].isnull().all():
        df["order"] = range(1, len(df) + 1)
    return df[["code", "name", "order"]]

def big_copy_box(text):
    return f"""
    <div onclick="copySKU()" style="cursor:pointer;background:#111;
    border:2px solid #4CAF50;border-radius:14px;padding:26px;text-align:center">
    <div style="font-size:44px;font-family:monospace;color:#4CAF50;font-weight:700">
    {text}
    </div>
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

    st.title("Blastline SKU Configurator")
    st.markdown("---")

    inv = st.session_state["sku_data"]["inventory"]
    if not inv:
        st.warning("No categories available")
        return

    cat = st.selectbox("Product Category", list(inv.keys()))
    cat_data = inv[cat]
    normalize_fields(cat_data)

    fields = cat_data["fields"]
    extras = cat_data.get("extras", [])
    sep = cat_data.get("settings", {}).get("separator", "")

    c1, c2 = st.columns(2)
    sel = {}

    with c1:
        st.subheader("Configuration")
        for f in ordered_fields(fields):
            opts = fields[f]["options"]
            is_text = opts and opts[0].get("type") == "text"
            if is_text:
                sel[f] = st.text_input(f)
            else:
                if opts:
                    o = st.selectbox(f, opts, format_func=get_option_label)
                    sel[f] = o["code"]

    with c2:
        st.subheader("Extras / Add-ons")
        chosen = []
        for e in extras:
            if st.checkbox(e["name"]):
                if e.get("code"):
                    chosen.append(e["code"])

        st.markdown("---")
        st.subheader("Generated SKU")

        base = sep.join([sel[k] for k in ordered_fields(fields) if sel.get(k)])
        sku = base + (sep if base and chosen else "") + "".join(chosen)

        if sku:
            st.components.v1.html(big_copy_box(sku), height=160)
        else:
            st.info("Select options to generate SKU")

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
# ADMIN
# ==================================================
def admin():
    st.title("⚙️ Admin Settings")

    inv = st.session_state["sku_data"]["inventory"]

    c1, c2 = st.columns([3, 1])
    with c1:
        cat = st.selectbox("Product Category", list(inv.keys()))
    with c2:
        with st.form("add_cat"):
            n = st.text_input("New Category", label_visibility="collapsed")
            if st.form_submit_button("➕ Add") and n:
                inv[n] = {"fields": {}, "extras": [], "settings": {"separator": "-", "extras_mode": "Multiple"}}
                st.rerun()

    if st.button("🗑️ Delete Category"):
        del inv[cat]
        st.rerun()

    tab1, tab2 = st.tabs(["🛠️ Configuration", "💾 Data I/O"])

    # ---------- CONFIG ----------
    with tab1:
        cat_data = inv[cat]
        normalize_fields(cat_data)
        fields = cat_data["fields"]

        st.subheader("➕ Add Field")
        with st.form("add_field"):
            a, b, c = st.columns([2, 1, 1])
            name = a.text_input("Field Name")
            ftype = c.selectbox("Type", ["Dropdown", "Text Input"])
            if b.form_submit_button("Add") and name:
                fields[name] = {
                    "order": len(fields) + 1,
                    "options": [{"type": "text", "code": "", "name": ""}] if ftype == "Text Input" else []
                }
                st.rerun()

        st.subheader("🔀 Field Order")
        df = pd.DataFrame([{"Field": k, "Order": v["order"]} for k, v in fields.items()])
        edited = st.data_editor(df, hide_index=True)
        if st.button("Apply Field Order"):
            for _, r in edited.iterrows():
                fields[r["Field"]]["order"] = int(r["Order"])
            st.rerun()

        st.subheader("✏️ Rename / Delete Field")
        field = st.selectbox("Select Field", ordered_fields(fields))
        new_name = st.text_input("Rename Field To", value=field)
        c1, c2 = st.columns(2)
        if c1.button("Rename"):
            if new_name and new_name not in fields:
                fields[new_name] = fields.pop(field)
                st.rerun()
        if c2.button("Delete"):
            del fields[field]
            st.rerun()

        st.subheader("🛠️ Field Options")
        opts = fields[field]["options"]
        if opts and opts[0].get("type") == "text":
            st.info("Text input field")
        else:
            df2 = normalize_option_df(opts)
            edited_df = st.data_editor(df2, num_rows="dynamic", hide_index=True)
            if st.button("Update Options"):
                fields[field]["options"] = edited_df.to_dict("records")

    # ---------- DATA I/O ----------
    with tab2:
        st.subheader("Export")
        st.download_button(
            "Download Config JSON",
            json.dumps(st.session_state["sku_data"], indent=2),
            "sku_config.json",
            "application/json"
        )

        st.subheader("Import")
        f = st.file_uploader("Upload Config JSON", type=["json"])
        if f and st.button("Load Config"):
            st.session_state["sku_data"] = json.load(f)
            st.rerun()

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
