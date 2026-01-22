import streamlit as st
import pandas as pd
import json
import itertools
import math
import requests
import base64

# ==========================================
# 1. SETUP
# ==========================================
st.set_page_config(page_title="Blastline SKU Configurator", layout="wide")

# ==========================================
# 2. GITHUB STORAGE
# ==========================================
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

# ==========================================
# 3. HELPERS
# ==========================================
def get_option_label(item):
    return f"{item['code']}: {item['name']}"

def normalize_fields_structure(cat_data):
    fields = cat_data.get("fields", {})
    normalized = {}
    for i, (fname, fval) in enumerate(fields.items(), start=1):
        if isinstance(fval, dict) and "options" in fval:
            normalized[fname] = fval
        else:
            normalized[fname] = {"order": i, "options": fval}
    cat_data["fields"] = normalized

def get_ordered_field_keys(fields_dict):
    return [
        k for k, v in sorted(
            fields_dict.items(),
            key=lambda x: x[1].get("order", 999)
        )
    ]

def normalize_options_df(data):
    if not data:
        df = pd.DataFrame(columns=["code", "name", "order"])
    else:
        df = pd.DataFrame(data)
    for col in ["code", "name", "order"]:
        if col not in df.columns:
            df[col] = ""
    df = df[["code", "name", "order"]]
    if df["order"].isnull().all() or df["order"].eq("").all():
        df["order"] = range(1, len(df) + 1)
    return df

def generate_full_matrix_df():
    inventory = st.session_state["sku_data"]["inventory"]
    rows = []

    for cat_name, cat_data in inventory.items():
        normalize_fields_structure(cat_data)
        fields = cat_data.get("fields", {})
        extras = cat_data.get("extras", [])
        mode = cat_data.get("settings", {}).get("extras_mode", "Multiple")
        sep = cat_data.get("settings", {}).get("separator", "")

        core_lists = []
        for k in get_ordered_field_keys(fields):
            opts = fields[k]["options"]
            is_text = opts and isinstance(opts[0], dict) and opts[0].get("type") == "text"
            if is_text:
                core_lists.append([{"code": ""}])
            else:
                core_lists.append(opts)

        core_combos = list(itertools.product(*core_lists)) if core_lists else [[]]

        extra_combos = [{"code": ""}]
        if extras:
            if mode == "Single":
                extra_combos += [{"code": e["code"]} for e in extras if e.get("code")]
            else:
                valid = [e for e in extras if e.get("code")]
                for r in range(1, len(valid) + 1):
                    for c in itertools.combinations(valid, r):
                        extra_combos.append({"code": "".join([x["code"] for x in c])})

        for core in core_combos:
            base = sep.join([c["code"] for c in core if c.get("code")])
            for ex in extra_combos:
                sku = base + (sep if base and ex["code"] else "") + ex["code"]
                rows.append({"Category": cat_name, "Generated SKU": sku})

    return pd.DataFrame(rows)

# ==========================================
# 4. INIT STATE
# ==========================================
if "sku_data" not in st.session_state:
    gh = GithubStorage()
    data = gh.load_data()
    st.session_state["sku_data"] = data if data else {"inventory": {}}

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "home"

def navigate(page):
    st.session_state["current_page"] = page
    st.rerun()

# ==========================================
# 5. HOME
# ==========================================
def render_home():
    with st.sidebar:
        if st.button("⚙️ Admin Settings", use_container_width=True):
            navigate("login")

    st.title("Blastline SKU Configurator")
    st.markdown("---")

    inventory = st.session_state["sku_data"]["inventory"]
    if not inventory:
        st.warning("No categories configured.")
        return

    c1, c2 = st.columns(2)
    with c1:
        category = st.selectbox("Product Category", list(inventory.keys()))

    cat_data = inventory[category]
    normalize_fields_structure(cat_data)
    fields = cat_data["fields"]
    extras = cat_data.get("extras", [])
    sep = cat_data.get("settings", {}).get("separator", "")

    col1, col2 = st.columns(2)
    selections = {}

    with col1:
        st.subheader("Configuration")
        for k in get_ordered_field_keys(fields):
            opts = fields[k]["options"]
            is_text = opts and isinstance(opts[0], dict) and opts[0].get("type") == "text"
            if is_text:
                selections[k] = st.text_input(k)
            else:
                if opts:
                    choice = st.selectbox(k, opts, format_func=get_option_label)
                    selections[k] = choice["code"]

    with col2:
        st.subheader("Extras / Add-ons")
        selected_extras = []
        for e in extras:
            if st.checkbox(e["name"]):
                if e.get("code"):
                    selected_extras.append(str(e["code"]))

        st.markdown("---")
        st.subheader("Generated SKU")
        base = sep.join([selections.get(k, "") for k in get_ordered_field_keys(fields) if selections.get(k)])
        sku = base + (sep if base and selected_extras else "") + "".join(selected_extras)
        st.code(sku or "—")

# ==========================================
# 6. LOGIN
# ==========================================
def render_login():
    st.subheader("Admin Login")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        if pw == "admin123":
            navigate("admin")
        else:
            st.error("Invalid password")
    if st.button("Cancel"):
        navigate("home")

# ==========================================
# 7. ADMIN
# ==========================================
def render_admin():
    st.title("⚙️ Admin Settings")

    inventory = st.session_state["sku_data"]["inventory"]

    # CATEGORY ADD / DELETE
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_cat = st.selectbox("Product Category", list(inventory.keys()))
    with col2:
        with st.form("add_cat"):
            new_cat = st.text_input("New Category", placeholder="Category name", label_visibility="collapsed")
            if st.form_submit_button("➕ Add") and new_cat and new_cat not in inventory:
                inventory[new_cat] = {
                    "fields": {},
                    "extras": [],
                    "settings": {"separator": "-", "extras_mode": "Multiple"}
                }
                st.success("Category added")
                st.rerun()

    if st.button("🗑️ Delete Category"):
        del inventory[selected_cat]
        st.success("Category deleted")
        st.rerun()

    tab1, tab2 = st.tabs(["🛠️ Configuration", "💾 Data I/O"])

    # ---------- TAB 1 ----------
    with tab1:
        cat_data = inventory[selected_cat]
        normalize_fields_structure(cat_data)
        fields = cat_data["fields"]

        st.subheader("🔀 Field Order")
        field_df = pd.DataFrame([
            {"Field": k, "Order": v.get("order", i + 1)}
            for i, (k, v) in enumerate(fields.items())
        ])
        edited = st.data_editor(
            field_df,
            hide_index=True,
            column_config={
                "Field": st.column_config.TextColumn(disabled=True),
                "Order": st.column_config.NumberColumn(min_value=1)
            },
            use_container_width=True
        )
        if st.button("Apply Field Order"):
            for _, r in edited.iterrows():
                fields[r["Field"]]["order"] = int(r["Order"])
            st.rerun()

        st.markdown("---")
        st.subheader("🛠️ Field Options")
        if fields:
            field = st.selectbox("Select Field", get_ordered_field_keys(fields))
            data = fields[field]["options"]
            if data and isinstance(data[0], dict) and data[0].get("type") == "text":
                st.info("Text input field")
            else:
                df = normalize_options_df(data)
                edited_df = st.data_editor(
                    df,
                    num_rows="dynamic",
                    hide_index=True,
                    column_config={
                        "code": st.column_config.TextColumn("SKU Code", required=True),
                        "name": st.column_config.TextColumn("Display Name", required=True),
                        "order": st.column_config.NumberColumn("Sort Order")
                    },
                    use_container_width=True
                )
                if st.button("Update Options"):
                    fields[field]["options"] = edited_df.to_dict("records")

        st.markdown("---")
        st.subheader("🔍 Live SKU Preview")

        preview = {}
        for k in get_ordered_field_keys(fields):
            opts = fields[k]["options"]
            is_text = opts and isinstance(opts[0], dict) and opts[0].get("type") == "text"
            if is_text:
                preview[k] = st.text_input(f"{k} (Preview)")
            else:
                if opts:
                    c = st.selectbox(f"{k} (Preview)", opts, format_func=get_option_label)
                    preview[k] = c["code"]

        extras = cat_data.get("extras", [])
        selected_extras = []
        for e in extras:
            if st.checkbox(f"➕ {e['name']}", key=f"pv_{e['name']}"):
                if e.get("code"):
                    selected_extras.append(e["code"])

        sep = cat_data.get("settings", {}).get("separator", "")
        base = sep.join([preview.get(k, "") for k in get_ordered_field_keys(fields) if preview.get(k)])
        sku = base + (sep if base and selected_extras else "") + "".join(selected_extras)
        st.code(sku or "—")

    # ---------- TAB 2 ----------
    with tab2:
        st.subheader("📤 Export")
        json_str = json.dumps(st.session_state["sku_data"], indent=2)
        st.download_button("Download Config (JSON)", json_str, "sku_config.json", "application/json")

        if st.button("Generate Full Matrix CSV"):
            df = generate_full_matrix_df()
            st.download_button(
                "Download Matrix.csv",
                df.to_csv(index=False),
                "sku_matrix.csv",
                "text/csv"
            )

        st.markdown("---")
        st.subheader("📥 Import")
        uploaded = st.file_uploader("Upload Config JSON", type=["json"])
        if uploaded and st.button("Load Config"):
            st.session_state["sku_data"] = json.load(uploaded)
            st.success("Config loaded")

    if st.button("☁️ Save to Cloud"):
        if GithubStorage().save_data(st.session_state["sku_data"]):
            st.success("Saved successfully")
            navigate("home")

# ==========================================
# 8. ROUTER
# ==========================================
if st.session_state["current_page"] == "home":
    render_home()
elif st.session_state["current_page"] == "login":
    render_login()
elif st.session_state["current_page"] == "admin":
    render_admin()
