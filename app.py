import streamlit as st
import pandas as pd
import json
import itertools
import math
import requests
import base64

# =====================================================
# 1. SETUP
# =====================================================
st.set_page_config(page_title="Blastline SKU Configurator", layout="wide")

# =====================================================
# 2. GITHUB STORAGE
# =====================================================
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

# =====================================================
# 3. DATA NORMALIZATION HELPERS
# =====================================================
def normalize_fields_structure(cat_data):
    """Backward compatible: wrap fields with order + options"""
    fields = cat_data.get("fields", {})
    normalized = {}
    for i, (fname, fval) in enumerate(fields.items(), start=1):
        if isinstance(fval, dict) and "options" in fval:
            normalized[fname] = fval
        else:
            normalized[fname] = {"order": i, "options": fval}
    cat_data["fields"] = normalized

def normalize_option_df(data):
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

def ordered_fields(fields_dict):
    return [
        k for k, v in sorted(
            fields_dict.items(),
            key=lambda x: x[1].get("order", 999)
        )
    ]

# =====================================================
# 4. SKU BUILDER (SINGLE SOURCE OF TRUTH)
# =====================================================
def build_sku(fields_dict, selections, separator, extras_codes=None):
    parts = []
    for fname in ordered_fields(fields_dict):
        val = selections.get(fname)
        if val:
            parts.append(str(val))
    base = separator.join(parts)
    extras = "".join(extras_codes or [])
    if separator and base and extras:
        return base + separator + extras
    return base + extras

# =====================================================
# 5. INIT DATA
# =====================================================
if "sku_data" not in st.session_state:
    gh = GithubStorage()
    data = gh.load_data()
    if data:
        st.session_state["sku_data"] = data
    else:
        st.session_state["sku_data"] = {"inventory": {}}

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "home"

def navigate(page):
    st.session_state["current_page"] = page
    st.rerun()

# =====================================================
# 6. HOME PAGE
# =====================================================
def render_home():
    st.title("Blastline SKU Configurator")

    inventory = st.session_state["sku_data"]["inventory"]
    if not inventory:
        st.info("No categories configured")
        return

    category = st.selectbox("Product Category", list(inventory.keys()))
    cat_data = inventory[category]
    normalize_fields_structure(cat_data)

    fields = cat_data["fields"]
    extras = cat_data.get("extras", [])
    separator = cat_data.get("settings", {}).get("separator", "")

    selections = {}
    for fname in ordered_fields(fields):
        opts = fields[fname]["options"]
        is_text = opts and isinstance(opts[0], dict) and opts[0].get("type") == "text"
        if is_text:
            selections[fname] = st.text_input(fname)
        else:
            if opts:
                choice = st.selectbox(
                    fname,
                    sorted(opts, key=lambda x: int(x.get("order", 99))),
                    format_func=lambda x: f"{x['code']} - {x['name']}"
                )
                selections[fname] = choice["code"]

    selected_extras = []
    for e in extras:
        if st.checkbox(e["name"]):
            if e.get("code"):
                selected_extras.append(str(e["code"]))

    sku = build_sku(fields, selections, separator, selected_extras)
    st.subheader("Generated SKU")
    st.code(sku or "—")

    if st.button("⚙️ Admin"):
        navigate("login")

# =====================================================
# 7. LOGIN
# =====================================================
def render_login():
    st.subheader("Admin Login")
    pw = st.text_input("Password", type="password")
    if st.button("Login"):
        if pw == "admin123":
            navigate("admin")
        else:
            st.error("Invalid password")

# =====================================================
# 8. ADMIN PAGE
# =====================================================
def render_admin():
    st.title("⚙️ Admin Configuration")

    inventory = st.session_state["sku_data"]["inventory"]
    cat = st.selectbox("Category", list(inventory.keys()))
    cat_data = inventory[cat]
    normalize_fields_structure(cat_data)

    fields = cat_data["fields"]

    # ---------- FIELD REORDER ----------
    st.subheader("Field Order")
    field_df = pd.DataFrame([
        {"Field": k, "Order": v.get("order", i+1)}
        for i, (k, v) in enumerate(fields.items())
    ])
    edited = st.data_editor(
        field_df,
        hide_index=True,
        column_config={
            "Field": st.column_config.TextColumn(disabled=True),
            "Order": st.column_config.NumberColumn(min_value=1)
        }
    )
    if st.button("Apply Field Order"):
        for _, r in edited.iterrows():
            fields[r["Field"]]["order"] = int(r["Order"])
        st.success("Field order updated")
        st.rerun()

    # ---------- FIELD OPTIONS ----------
    st.subheader("Edit Field Options")
    field_name = st.selectbox("Select Field", ordered_fields(fields))
    field_data = fields[field_name]["options"]

    if field_data and isinstance(field_data[0], dict) and field_data[0].get("type") == "text":
        st.info("Text input field – no options")
    else:
        df = normalize_option_df(field_data)
        edited_df = st.data_editor(
            df,
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "code": st.column_config.TextColumn("SKU Code", required=True),
                "name": st.column_config.TextColumn("Display Name", required=True),
                "order": st.column_config.NumberColumn("Sort Order", min_value=1)
            }
        )
        if st.button("Update Options"):
            fields[field_name]["options"] = edited_df.to_dict("records")
            st.success("Options updated")

    # ---------- LIVE SKU PREVIEW ----------
    st.markdown("---")
    st.subheader("🔍 Live SKU Preview")

    preview_sel = {}
    for fname in ordered_fields(fields):
        opts = fields[fname]["options"]
        is_text = opts and isinstance(opts[0], dict) and opts[0].get("type") == "text"
        if is_text:
            preview_sel[fname] = st.text_input(f"{fname} (Preview)")
        else:
            if opts:
                c = st.selectbox(
                    f"{fname} (Preview)",
                    opts,
                    format_func=lambda x: f"{x['code']} - {x['name']}"
                )
                preview_sel[fname] = c["code"]

    preview_extras = []
    for e in cat_data.get("extras", []):
        if st.checkbox(f"➕ {e['name']}", key=f"prev_{e['name']}"):
            if e.get("code"):
                preview_extras.append(str(e["code"]))

    sep = cat_data.get("settings", {}).get("separator", "")
    preview_sku = build_sku(fields, preview_sel, sep, preview_extras)
    st.code(preview_sku or "—")

    # ---------- SAVE ----------
    st.markdown("---")
    if st.button("☁️ Save to GitHub"):
        if GithubStorage().save_data(st.session_state["sku_data"]):
            st.success("Saved successfully")
            navigate("home")

# =====================================================
# 9. ROUTER
# =====================================================
if st.session_state["current_page"] == "home":
    render_home()
elif st.session_state["current_page"] == "login":
    render_login()
elif st.session_state["current_page"] == "admin":
    render_admin()
