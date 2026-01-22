import streamlit as st
import pandas as pd
import json
import itertools
import math
import requests
import base64

# ==========================================
# 1. SETUP & GITHUB INTEGRATION
# ==========================================
st.set_page_config(page_title="Blastline SKU Configurator", layout="wide")

# --- GITHUB STORAGE HANDLER ---
class GithubStorage:
    def __init__(self):
        # Check if secrets are set up
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
        """Loads JSON from GitHub. Returns None if file doesn't exist yet."""
        if not self.can_connect: return None
        
        try:
            r = requests.get(self.api_url, headers=self.headers, params={"ref": self.branch})
            if r.status_code == 200:
                content = r.json()
                st.session_state["github_sha"] = content["sha"]
                file_content = base64.b64decode(content["content"]).decode("utf-8")
                return json.loads(file_content)
        except Exception as e:
            st.error(f"Error loading from GitHub: {e}")
        return None

    def save_data(self, data):
        """Updates the file on GitHub."""
        if not self.can_connect:
            st.error("GitHub secrets not configured!")
            return False
            
        try:
            json_str = json.dumps(data, indent=2)
            content_b64 = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
            
            payload = {
                "message": "Update SKU Config (Streamlit App)",
                "content": content_b64,
                "branch": self.branch
            }
            
            if "github_sha" in st.session_state:
                payload["sha"] = st.session_state["github_sha"]
                
            r = requests.put(self.api_url, headers=self.headers, json=payload)
            
            if r.status_code in [200, 201]:
                st.session_state["github_sha"] = r.json()["content"]["sha"]
                return True
            else:
                st.error(f"GitHub Save Failed: {r.status_code} - {r.text}")
                return False
        except Exception as e:
            st.error(f"Error saving to GitHub: {e}")
            return False

# --- INITIALIZE DATA ---
if "sku_data" not in st.session_state:
    gh = GithubStorage()
    remote_data = gh.load_data()
    
    if remote_data:
        st.session_state["sku_data"] = remote_data
        st.toast("Data loaded from GitHub!", icon="☁️")
    else:
        # Fallback Defaults
        st.session_state["sku_data"] = {
            "inventory": {
                "Blast Machine": {
                    "settings": {"extras_mode": "Multiple"},
                    "fields": {
                        "Brand": [{"code": "BL", "name": "Blastline", "order": 1}],
                        "Capacity": [{"code": "20", "name": "1080", "order": 1}]
                    },
                    "extras": [
                        {"name": "Remote Control", "code": "R", "selected": False}
                    ]
                }
            }
        }

if "current_page" not in st.session_state:
    st.session_state["current_page"] = "home"
    
if "extras_page_idx" not in st.session_state:
    st.session_state["extras_page_idx"] = 0

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def navigate_to(page):
    st.session_state["current_page"] = page
    st.rerun()

def get_option_label(item):
    return f"{item['code']}: {item['name']}"

def reset_pagination():
    st.session_state["extras_page_idx"] = 0

def copy_to_clipboard_html(text):
    return f"""
    <div id="sku-box" onclick="copyToClipboard('{text}')" 
         style="cursor: pointer; background-color: #1E1E1E; padding: 20px; border-radius: 10px; border: 1px solid #333; text-align: center; transition: background-color 0.2s;">
        <h1 style="color: #4CAF50; margin:0; font-size: 40px; font-family: monospace;">{text}</h1>
        <p id="copy-msg" style="color: #888; margin:0; font-size: 14px; margin-top: 5px;">📋 Click to Copy</p>
    </div>
    <script>
    function copyToClipboard(text) {{
        navigator.clipboard.writeText(text).then(function() {{
            const msgElement = document.getElementById("copy-msg");
            const boxElement = document.getElementById("sku-box");
            msgElement.innerHTML = "✅ Copied!";
            msgElement.style.color = "#4CAF50";
            boxElement.style.borderColor = "#4CAF50";
            setTimeout(function() {{
                msgElement.innerHTML = "📋 Click to Copy";
                msgElement.style.color = "#888";
                boxElement.style.borderColor = "#333";
            }}, 2000);
        }}, function(err) {{
            console.error('Async: Could not copy text: ', err);
        }});
    }}
    </script>
    """

# Helper to safely convert order to int for sorting
def safe_int_sort(x):
    try:
        return int(x.get('order', 99))
    except (ValueError, TypeError):
        return 999

def generate_full_matrix_df():
    inventory = st.session_state["sku_data"]["inventory"]
    rows = []
    
    for cat_name, cat_data in inventory.items():
        fields_dict = cat_data.get("fields", {})
        extras_list = cat_data.get("extras", [])
        mode = cat_data.get("settings", {}).get("extras_mode", "Multiple")
        
        if not fields_dict and not extras_list: continue
        
        core_lists = []
        field_keys = list(fields_dict.keys())
        priority = ["Brand", "Capacity", "Configuration", "Certification", "Valve", "Screen / Cover"]
        sorted_keys = [k for k in priority if k in field_keys] + [k for k in field_keys if k not in priority]
        
        for key in sorted_keys:
            core_lists.append(fields_dict[key])
            
        if not core_lists: core_combinations = [([],)]
        else: core_combinations = list(itertools.product(*core_lists))

        extras_combinations = []
        if mode == "Single":
            extras_combinations.append({"code": "", "name": "None"})
            for ex in extras_list:
                extras_combinations.append({"code": ex["code"], "name": ex["name"]})
        else:
            for r in range(len(extras_list) + 1):
                for combo in itertools.combinations(extras_list, r):
                    if not combo:
                        extras_combinations.append({"code": "", "name": "None"})
                    else:
                        c_code = "".join([i["code"] for i in combo])
                        c_name = " | ".join([i["name"] for i in combo])
                        extras_combinations.append({"code": c_code, "name": c_name})
        
        for core in core_combinations:
            base_sku = "".join([item["code"] for item in core]) if core and core[0] else ""
            base_desc = " | ".join([item["name"] for item in core]) if core and core[0] else ""
            
            for extra in extras_combinations:
                full_sku = base_sku + extra["code"]
                separator = " | " if base_desc and extra["name"] != "None" else ""
                extra_desc = extra["name"] if extra["name"] != "None" else ""
                full_desc = f"{base_desc}{separator}{extra_desc}"
                rows.append({"Category": cat_name, "Generated SKU": full_sku, "Full Description": full_desc})
            
    return pd.DataFrame(rows)

# ==========================================
# 3. PAGE: HOME
# ==========================================
def render_home():
    with st.sidebar:
        st.markdown("### Admin")
        if st.button("⚙️ Open Settings", use_container_width=True):
            navigate_to("login")

    st.title("Blastline SKU Configurator")
    st.caption("Database: Factory Default" if "github" not in st.secrets else "Database: GitHub (Cloud)")
    st.markdown("---")

    inventory = st.session_state["sku_data"]["inventory"]
    available_cats = list(inventory.keys())
    
    if not available_cats:
        st.warning("No Categories Configured.")
        return

    # Create columns to control the width (e.g., use half the screen width)
    c1, c2 = st.columns([1, 1]) 
    with c1:
        category = st.selectbox("Product Category", available_cats, on_change=reset_pagination)
    
    cat_data = inventory.get(category, {})
    fields_dict = cat_data.get("fields", {})
    extras_list = cat_data.get("extras", [])
    extras_mode = cat_data.get("settings", {}).get("extras_mode", "Multiple")

    col1, col2 = st.columns([1, 1])
    selections = {}
    
    with col1:
        st.subheader("Configuration")
        field_keys = list(fields_dict.keys())
        priority = ["Brand", "Capacity", "Configuration", "Certification", "Valve", "Screen / Cover"]
        sorted_fields = [k for k in priority if k in field_keys] + [k for k in field_keys if k not in priority]
        
        if not sorted_fields:
            st.info("No fields configured for this category.")
            
        for key in sorted_fields:
            opts = fields_dict[key]
            
            # --- SAFE SORTING APPLIED ---
            try:
                opts = sorted(opts, key=safe_int_sort)
            except Exception:
                pass # Use unsorted if catastrophic failure
            # ----------------------------
            
            if opts:
                choice = st.selectbox(key, opts, format_func=get_option_label, key=f"home_{category}_{key}")
                selections[key] = choice['code']
            else:
                selections[key] = ""
                st.warning(f"No options in {key}")

    with col2:
        st.subheader("Extras / Add-ons")
        selected_extras_codes = []

        if not extras_list:
            st.caption("No extras available.")
        else:
            ITEMS_PER_PAGE = 12
            total_items = len(extras_list)
            total_pages = math.ceil(total_items / ITEMS_PER_PAGE)
            
            if st.session_state["extras_page_idx"] >= total_pages:
                st.session_state["extras_page_idx"] = max(0, total_pages - 1)
                
            current_idx = st.session_state["extras_page_idx"]
            start_idx = current_idx * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            current_page_extras = extras_list[start_idx:end_idx]

            if extras_mode == "Single":
                radio_opts = ["None"] + [e["name"] for e in current_page_extras]
                choice = st.radio(f"Select Add-on (Page {current_idx+1})", radio_opts)
                if choice != "None":
                    for e in extras_list:
                        if e["name"] == choice:
                            selected_extras_codes.append(e["code"])
                            break
            else:
                c_ex1, c_ex2 = st.columns(2)
                for i, extra in enumerate(current_page_extras):
                    col = c_ex1 if i % 2 == 0 else c_ex2
                    if col.checkbox(extra["name"], key=f"ex_{category}_{current_idx}_{i}"):
                        selected_extras_codes.append(extra["code"])

            if total_pages > 1:
                st.markdown("---")
                cp1, cp2, cp3, cp4 = st.columns([1, 1, 3, 1])
                if cp1.button("◀️ Prev", disabled=(current_idx == 0)):
                    st.session_state["extras_page_idx"] -= 1
                    st.rerun()
                with cp2:
                    st.markdown(f"<div style='padding-top: 5px; text-align:center'><b>{current_idx + 1} / {total_pages}</b></div>", unsafe_allow_html=True)
                if cp4.button("Next ▶️", disabled=(current_idx == total_pages - 1)):
                    st.session_state["extras_page_idx"] += 1
                    st.rerun()

        st.markdown("---")
        st.subheader("Generated SKU")
        
        base_sku = "".join([selections.get(k, "") for k in sorted_fields])
        extras_sku = "".join(selected_extras_codes)
        full_sku = base_sku + extras_sku
        
        st.components.v1.html(copy_to_clipboard_html(full_sku), height=150)
        
        if st.button("📋 Copy Manually"):
            st.write(f"SKU: `{full_sku}`")

    st.markdown("---")
    st.markdown(
        """<div style="text-align: center; color: #666; font-size: 12px; margin-top: 20px;">
            Application developed by <b>Blastline India Pvt Ltd.</b>
        </div>""", 
        unsafe_allow_html=True
    )

# ==========================================
# 4. PAGE: LOGIN
# ==========================================
def render_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## Admin Access")
        password = st.text_input("Enter Password", type="password")
        c1, c2 = st.columns(2)
        if c1.button("Login", type="primary"):
            if password == "admin123":
                navigate_to("admin")
            else:
                st.error("Invalid Password")
        if c2.button("Cancel"):
            navigate_to("home")

# ==========================================
# 5. PAGE: ADMIN DASHBOARD
# ==========================================
def render_admin():
    st.title("⚙️ Admin Settings")
    c1, c2 = st.columns([6,1])
    with c2:
        if st.button("☁️ Save to Cloud", type="primary", help="Saves data permanently to GitHub"):
            gh = GithubStorage()
            if gh.save_data(st.session_state["sku_data"]):
                st.toast("Saved successfully to GitHub!", icon="✅")
                navigate_to("home")
            else:
                st.toast("Save failed! Check settings.", icon="❌")

    tab1, tab2 = st.tabs(["🛠️ Configuration", "💾 Data I/O"])

    with tab1:
        st.info("Select a Category to configure its Fields and Extras.")
        inventory = st.session_state["sku_data"]["inventory"]
        cat_list = list(inventory.keys())
        
        col_cat1, col_cat2 = st.columns([3, 1])
        with col_cat1:
            selected_cat = st.selectbox("Product Category", cat_list, key="admin_cat_select")
        with col_cat2:
            with st.form("form_new_category"):
                new_cat_name = st.text_input("Create New Category", placeholder="Name...", label_visibility="collapsed")
                if st.form_submit_button("➕ Add"):
                    if new_cat_name and new_cat_name not in inventory:
                        st.session_state["sku_data"]["inventory"][new_cat_name] = {
                            "fields": {}, "extras": [], "settings": {"extras_mode": "Multiple"}
                        }
                        st.success(f"Created {new_cat_name}")
                        st.rerun()

        st.markdown("---")

        if selected_cat:
            cat_data = inventory[selected_cat]
            col_conf_main, col_conf_extras = st.columns([1, 1], gap="large")
            
            with col_conf_main:
                st.markdown(f"### 1. Configuration Fields")
                current_fields = cat_data["fields"]
                field_list = list(current_fields.keys())
                
                with st.form("form_new_field"):
                    c_f1, c_f2 = st.columns([2, 1])
                    new_field_name = c_f1.text_input("New Field Name", placeholder="e.g. Thread", label_visibility="collapsed")
                    if c_f2.form_submit_button("Add Field"):
                        if new_field_name and new_field_name not in current_fields:
                            st.session_state["sku_data"]["inventory"][selected_cat]["fields"][new_field_name] = []
                            st.rerun()

                if field_list:
                    field_to_edit = st.selectbox("Select Field to Edit Options", field_list)
                    st.markdown(f"**Options for '{field_to_edit}'**")
                    df = pd.DataFrame(current_fields[field_to_edit])
                    if 'order' not in df.columns: df['order'] = range(1, len(df)+1)

                    with st.form(key=f"form_fields_{selected_cat}_{field_to_edit}"):
                        edited_df = st.data_editor(
                            df,
                            num_rows="dynamic",
                            column_config={
                                "order": st.column_config.NumberColumn("Order", width="small"),
                                "code": st.column_config.TextColumn("Code"),
                                "name": st.column_config.TextColumn("Name"),
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                        if st.form_submit_button("✅ Update Options"):
                            st.session_state["sku_data"]["inventory"][selected_cat]["fields"][field_to_edit] = edited_df.to_dict('records')
                            st.success("Options updated locally. Click 'Save to Cloud' to persist.")
                else:
                    st.info("No fields created yet.")

            with col_conf_extras:
                st.markdown(f"### 2. Extras & Add-ons")
                curr_mode = cat_data.get("settings", {}).get("extras_mode", "Multiple")
                new_mode = st.radio("Selection Logic", ["Single", "Multiple"], 
                                   index=0 if curr_mode=="Single" else 1, 
                                   horizontal=True,
                                   key=f"mode_{selected_cat}")
                
                if "settings" not in st.session_state["sku_data"]["inventory"][selected_cat]:
                    st.session_state["sku_data"]["inventory"][selected_cat]["settings"] = {}
                st.session_state["sku_data"]["inventory"][selected_cat]["settings"]["extras_mode"] = new_mode

                extras_data = cat_data.get("extras", [])
                df_extras = pd.DataFrame(extras_data)
                
                with st.form(key=f"form_extras_{selected_cat}"):
                    edited_extras = st.data_editor(
                        df_extras,
                        num_rows="dynamic",
                        column_config={
                            "name": st.column_config.TextColumn("Extra Name"),
                            "code": st.column_config.TextColumn("Code"),
                            "selected": None 
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    if st.form_submit_button("✅ Update Extras"):
                        st.session_state["sku_data"]["inventory"][selected_cat]["extras"] = edited_extras.to_dict('records')
                        st.success("Extras updated locally. Click 'Save to Cloud' to persist.")

    with tab2:
        st.subheader("Backup & Matrix Export")
        col_exp, col_imp = st.columns(2)
        with col_exp:
            st.markdown("#### 📤 Export")
            json_str = json.dumps(st.session_state["sku_data"], indent=2)
            st.download_button("Download Config (JSON)", json_str, "blastline_config.json", "application/json")
            if st.button("Generate Full Matrix CSV"):
                with st.spinner("Processing..."):
                    df_matrix = generate_full_matrix_df()
                    csv = df_matrix.to_csv(index=False).encode('utf-8')
                st.success(f"Generated {len(df_matrix)} rows.")
                st.download_button("📥 Download Matrix.csv", csv, "blastline_matrix.csv", "text/csv", type="primary")

        with col_imp:
            st.markdown("#### 📥 Restore")
            uploaded_file = st.file_uploader("Upload Config JSON", type=["json"])
            if uploaded_file and st.button("Load Settings"):
                try:
                    data = json.load(uploaded_file)
                    st.session_state["sku_data"] = data
                    st.success("Loaded! Click 'Save to Cloud' to persist.")
                except:
                    st.error("Invalid File")

if st.session_state["current_page"] == "home":
    render_home()
elif st.session_state["current_page"] == "login":
    render_login()
elif st.session_state["current_page"] == "admin":
    render_admin()

