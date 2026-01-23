import streamlit as st
import pandas as pd
import json
import itertools
import math
import requests
import base64

# ==================================================
# 1. SETUP
# ==================================================
st.set_page_config(page_title="Blastline SKU Configurator", layout="wide")

# ==================================================
# 2. GITHUB STORAGE
# ==================================================
class GithubStorage:
    def __init__(self):
        if "github" in st.secrets:
            self.token = st.secrets["github"]["token"]
            self.owner = st.secrets["github"]["owner"]
            self.repo = st.secrets["github"]["repo"]
            self.branch = st.secrets["github"]["branch"]
            self.path = st.secrets["github"]["filepath"]
            self.api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/contents/{self.path}"
            self.headers = {"Authorization": f"token {self.token}"}
            self.can_connect = True
        else:
            self.can_connect = False

    def load_data(self):
        if not self.can_connect:
            return None
        r = requests.get(self.api_url, headers=self.headers, params={"ref": self.branch})
        if r.status_code == 200:
            content = r.json()
            st.session_state["github_sha"] = content["sha"]
            return json.loads(base64.b64decode(content["content"]).decode("utf-8"))
        return None

    def save_data(self, data):
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
# 3. HELPERS
# ==================================================
def get_option_label(item):
    return f"{item['code']} : {item['name']}"

def normalize_fields_structure(cat_data):
    fields = cat_data.get("fields", {})
    normalized = {}
    for i, (fname, fval) in enumerate(fields.items(), start=1):
        if isinstance(fval, dict) and "options" in fval:
            normalized[fname] = fval
        else:
            normalized[fname] = {"order": i, "options": fval}
    cat_data["fields"] = normalized

def ordered_fields(fields):
    return [k for k, v in sorted(fields.items(), key=lambda x: x[1].get("order", 999))]

def normalize_options_df(data):
    if not data:
        df = pd.DataFrame(columns=["code", "name", "order"])
    else:
        df = pd.DataFrame(data)
    for c in ["code", "name", "order"]:
        if c not in df.columns:
            df[c] = ""
    df = df[["code", "name", "order"]]
    if df["order"].isnull().all() or df["order"].eq("").all():
        df["order"] = range(1, len(df) + 1)
    return df

def generate_matrix():
    rows = []
    inventory = st.session_state["sku_data"]["inventory"]

    for cat, cat_data in inventory.items():
        normalize_fields_structure(cat_data)
        fields = cat_data["fields"]
        extras = cat_data.get("extras", [])
        sep = cat_data.get("settings", {}).get("separator", "")
        mode = cat_data.get("settings", {}).get("extras_mode", "Multiple")

        core_lists = []
        for f in ordered_fields(fields):
            opts = fields[f]["options"]
            is_text = opts and isinstance(opts[0], dict) and opts[0].get("type") == "text"
            core_lists.append([{"code": ""}] if is_text else opts)

        cores = list(itertools.product(*core_lists))
        extras_sets = [{"code": ""}]

        if extras:
            if mode == "Single":
                extras_sets += [{"code": e["code"]} for e in extras if e.get("code")]
            else:
                valid = [e for e in extras if e.get("code")]
                for r in range(1, len(valid) + 1):
                    for c in itertools.combinations(valid, r):
                        extras_sets.append({"code": "".join([x["code"] for x in c])})

        for core in cores:
            base = sep.join([c["code"] for c in core if c.get("code")])
            for ex in extras_sets:
                sku = base + (sep if base and ex["code"] else "") + ex["code"]
                rows.append({"Category": cat, "Generated SKU": sku})

    return pd.DataFrame(rows)

def big_copy_sku(sku):
    return f"""
    <div onclick="copySKU()" style="
        cursor:pointer;
        background:#111;
        border:2px solid #4CAF50;
        border-radius:14px;
        padding:24px;
        text-align:center;
    ">
        <div style="
            font-size:42px;
            font-family:monospace;
            color:#4CAF50;
            font-weight:700;
        ">{sku}</div>
        <div id="msg" style="margin-top:8px;color:#aaa;">📋 Click to copy</div>
    </div>

    <script>
    function copySKU() {{
        navigator.clipboard.writeText("{sku}");
        const msg = document.getElementById("msg");
        msg.innerText = "✅ Copied to clipboard";
        msg.style.color = "#4CAF50";
        setTimeout(() => {{
            msg.innerText = "📋 Click to copy";
            msg.style.color = "#aaa";
        }}, 2000);
    }}
    </script>
    """

# ==================================================
# 4. INIT
# ==================================================
if "sku_data" not in st.session_state:
    gh = GithubStorage()
    st.session_state["sku_data"] = gh.load_data() or {"inventory": {}}

if "page" not in st.session_state:
    st.session_state["page"] = "home"

def go(p):
    st.session_state["page"] = p
    st.rerun()

# ==================================================
# 5. HOME
# ==================================================
def home():
    with st.sidebar:
        if st.button("⚙️ Settings", use_container_width=True):
            go("login")

    st.title("Blastline SKU Configurator")
    st.markdown("---")

    inventory = st.session_state["sku_data"]["inventory"]
    if not inventory:
        st.warning("No categories available")
        return

    cat = st.selectbox("Product Category", list(inventory.keys()))
    cat_data = inventory[cat]
    normalize_fields_structure(cat_data)

    fields = cat_data["fields"]
    extras = cat_data.get("extras", [])
    sep = cat_data.get("settings", {}).get("separator", "")

    c1, c2 = st.columns(2)
    selections = {}

    with c1:
        st.subheader("Configuration")
        for f in ordered_fields(fields):
            opts = fields[f]["options"]
            is_text = opts and isinstance(opts[0], dict) and opts[0].get("type") == "text"
            if is_text:
                selections[f] = st.text_input(f)
            else:
                if opts:
                    o = st.selectbox(f, opts, format_func=get_option_label)
                    selections[f] = o["code"]

    with c2:
        st.subheader("Extras / Add-ons")
        selected = []
        for e in extras:
            if st.checkbox(e["name"]):
                if e.get("code"):
                    selected.append(e["code"])

        st.markdown("---")
        st.subheader("Generated SKU")

        base = sep.join([selections[k] for k in ordered_fields(fields) if selections.get(k)])
        sku = base + (sep if base and selected else "") + "".join(selected)

        if sku:
            st.components.v1.html(big_copy_sku(sku), height=150)
        else:
            st.info("Select configuration to generate SKU")

# ==================================================
# 6. LOGIN
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
# 7. ADMIN
# ==================================================
def admin():
    st.title("⚙️ Admin Settings")

    inventory = st.session_state["sku_data"]["inventory"]

    col1, col2 = st.columns([3, 1])
    with col1:
        cat = st.selectbox("Product Category", list(inventory.keys()))
    with col2:
        with st.form("add_cat"):
            new_cat = st.text_input("New Category", placeholder="Name", label_visibility="collapsed")
            if st.form_submit_button("➕ Add") and new_cat and new_cat not in inventory:
                inventory[new_cat] = {
                    "fields": {},
                    "extras": [],
                    "settings": {"separator": "-", "extras_mode": "Multiple"}
                }
                st.rerun()

    if st.button("🗑️ Delete Category"):
        del inventory[cat]
        st.rerun()

    tab1, tab2 = st.tabs(["🛠️ Configuration", "💾 Data I/O"])

    with tab1:
        cat_data = inventory[cat]
        normalize_fields_structure(cat_data)
        fields = cat_data["fields"]

        st.subheader("➕ Add Field")
        with st.form("add_field"):
            a, b, c = st.columns([2, 1, 1])
            fname = a.text_input("Field Name")
            ftype = c.selectbox("Type", ["Dropdown", "Text Input"])
            if b.form_submit_button("Add"):
                fields[fname] = {
                    "order": len(fields) + 1,
                    "options": [{"code": "", "name": "Text", "type": "text"}] if ftype == "Text Input" else []
                }
                st.rerun()

        st.subheader("🔀 Field Order")
        df = pd.DataFrame([{"Field": k, "Order": v["order"]} for k, v in fields.items()])
        edited = st.data_editor(df, hide_index=True)
        if st.button("Apply Field Order"):
            for _, r in edited.iterrows():
                fields[r["Field"]]["order"] = int(r["Order"])
            st.rerun()

        st.subheader("🛠️ Field Options")
        field = st.selectbox("Select Field", ordered_fields(fields))
        if st.button("🗑️ Delete Field"):
            del fields[field]
            st.rerun()

        opts = fields[field]["options"]
        if opts and isinstance(opts[0], dict) and opts[0].get("type") == "text":
            st.info("Text field")
        else:
            df2 = normalize_options_df(opts)
            edited_df = st.data_editor(df2, num_rows="dynamic", hide_index=True)
            if st.button("Update Options"):
                fields[field]["options"] = edited_df.to_dict("records")

    with tab2:
        st.subheader("Export")
        st.download_button("Download Config JSON",
            json.dumps(st.session_state["sku_data"], indent=2),
            "sku_config.json",
            "application/json"
        )

        if st.button("Generate Full Matrix CSV"):
            df = generate_matrix()
            st.download_button("Download Matrix.csv", df.to_csv(index=False), "matrix.csv", "text/csv")

        st.subheader("Import")
        f = st.file_uploader("Upload Config JSON", type=["json"])
        if f and st.button("Load Config"):
            st.session_state["sku_data"] = json.load(f)
            st.rerun()

    if st.button("☁️ Save to Cloud"):
        GithubStorage().save_data(st.session_state["sku_data"])
        go("home")

# ==================================================
# 8. ROUTER
# ==================================================
if st.session_state["page"] == "home":
    home()
elif st.session_state["page"] == "login":
    login()
elif st.session_state["page"] == "admin":
    admin()
