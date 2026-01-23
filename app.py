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
    out = {}
    for i, (k, v) in enumerate(cat.get("fields", {}).items(), start=1):
        out[k] = v if isinstance(v, dict) else {"order": i, "options": v}
    cat["fields"] = out

def ordered_fields(fields):
    return sorted(fields.keys(), key=lambda k: fields[k].get("order", 999))

def big_copy_box(text):
    return f"""
    <div onclick="copySKU()" style="
        cursor:pointer;background:#0f0f0f;
        border:2px solid #4CAF50;border-radius:16px;
        padding:28px;text-align:center">
        <div style="font-size:44px;font-family:monospace;
        color:#4CAF50;font-weight:700">{text}</div>
        <div id="msg" style="margin-top:8px;color:#aaa">📋 Click to copy</div>
    </div>
    <script>
    function copySKU(){{
        navigator.clipboard.writeText("{text}");
        let m=document.getElementById("msg");
        m.innerText="✅ Copied";
        m.style.color="#4CAF50";
        setTimeout(()=>{{m.innerText="📋 Click to copy";m.style.color="#aaa";}},2000);
    }}
    </script>
    """

def generate_full_matrix():
    rows = []
    inv = st.session_state["sku_data"]["inventory"]

    for cat, cdata in inv.items():
        normalize_fields(cdata)
        fields = cdata["fields"]
        extras = cdata.get("extras", [])
        sep = cdata.get("settings", {}).get("separator", "")
        mode = cdata.get("settings", {}).get("extras_mode", "Single")

        core_lists = []
        for f in ordered_fields(fields):
            opts = fields[f]["options"]
            is_text = opts and opts[0].get("type") == "text"
            core_lists.append([{"code": ""}] if is_text else opts)

        core_combos = itertools.product(*core_lists)

        if mode == "Single":
            extra_sets = [""] + [e["code"] for e in extras if e.get("code")]
        else:
            valid = [e["code"] for e in extras if e.get("code")]
            extra_sets = [""]
            for r in range(1, len(valid) + 1):
                for c in itertools.combinations(valid, r):
                    extra_sets.append("".join(c))

        for core in core_combos:
            base = sep.join([c["code"] for c in core if c["code"]])
            for ex in extra_sets:
                sku = base + (sep if base and ex else "") + ex
                rows.append({"Category": cat, "SKU": sku})

    return pd.DataFrame(rows)

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

    st.title("Blastline SKU Configurator")
    st.markdown("---")

    inv = st.session_state["sku_data"]["inventory"]
    cat_name = st.selectbox("Product Category", list(inv.keys()))
    cat = inv[cat_name]

    normalize_fields(cat)
    fields = cat["fields"]
    extras = cat.get("extras", [])
    settings = cat.get("settings", {})
    sep = settings.get("separator", "")
    mode = settings.get("extras_mode", "Single")

    col1, col2 = st.columns(2)
    sel = {}

    with col1:
        st.subheader("Configuration")
        for f in ordered_fields(fields):
            opts = fields[f]["options"]
            is_text = opts and opts[0].get("type") == "text"
            sel[f] = st.text_input(f) if is_text else (
                st.selectbox(f, opts, format_func=get_option_label)["code"]
                if opts else ""
            )

    with col2:
        st.subheader("Extras / Add-ons")

        ITEMS = 12
        total_pages = max(1, math.ceil(len(extras) / ITEMS))
        page = st.session_state["extras_page"]
        page_items = extras[page * ITEMS:(page + 1) * ITEMS]

        selected = []

        if mode == "Single":
            choice = st.radio(
                "Extras (Select One)",
                ["None"] + [e["name"] for e in page_items]
            )
            if choice != "None":
                selected.append(
                    next(e["code"] for e in extras if e["name"] == choice)
                )
        else:
            for e in page_items:
                if st.checkbox(e["name"], key=f"ex_{page}_{e['name']}"):
                    selected.append(e["code"])

        if total_pages > 1:
            c1, c2, c3 = st.columns([1,2,1])
            if c1.button("◀", disabled=page == 0):
                st.session_state["extras_page"] -= 1
                st.rerun()
            c2.markdown(f"<center>{page+1} / {total_pages}</center>", unsafe_allow_html=True)
            if c3.button("▶", disabled=page == total_pages - 1):
                st.session_state["extras_page"] += 1
                st.rerun()

        st.markdown("---")
        base = sep.join([sel[k] for k in ordered_fields(fields) if sel[k]])
        sku = base + (sep if base and selected else "") + "".join(selected)
        st.components.v1.html(big_copy_box(sku), height=180)

# ==================================================
# LOGIN
# ==================================================
def login():
    pw = st.text_input("Admin Password", type="password")
    if st.button("Login") and pw == "admin123":
        go("admin")
    if st.button("Cancel"):
        go("home")

# ==================================================
# ADMIN
# ==================================================
def admin():
    st.title("⚙️ Admin Settings")
    inv = st.session_state["sku_data"]["inventory"]

    cat = st.selectbox("Product Category", list(inv.keys()))
    cat_data = inv[cat]

    normalize_fields(cat_data)
    fields = cat_data["fields"]

    st.subheader("➕ Extras Configuration")

    mode = st.radio(
        "Extras Selection Mode",
        ["Single", "Multiple"],
        index=0 if cat_data.get("settings", {}).get("extras_mode", "Single") == "Single" else 1
    )
    cat_data.setdefault("settings", {})["extras_mode"] = mode

    extras_df = pd.DataFrame(cat_data.get("extras", []),
        columns=["name", "code", "order"]
    )

    extras_df = st.data_editor(
        extras_df,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn("Item Name", required=True),
            "code": st.column_config.TextColumn("Code", required=True),
            "order": st.column_config.NumberColumn("Sort Order")
        }
    )

    if st.button("Update Extras"):
        cat_data["extras"] = extras_df.sort_values("order").to_dict("records")

    st.markdown("---")
    st.subheader("💾 Data I/O")

    st.download_button(
        "Export Config JSON",
        json.dumps(st.session_state["sku_data"], indent=2),
        "sku_config.json",
        "application/json"
    )

    upload = st.file_uploader("Import Config JSON", type=["json"])
    if upload and st.button("Load Config"):
        st.session_state["sku_data"] = json.load(upload)
        st.rerun()

    if st.button("Generate Full Matrix CSV"):
        df = generate_full_matrix()
        st.download_button(
            "Download Matrix.csv",
            df.to_csv(index=False),
            "sku_matrix.csv",
            "text/csv"
        )

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
