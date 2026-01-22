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

# --- INITIALIZE DATA (FROM MASTER PDF) ---
if "sku_data" not in st.session_state:
    gh = GithubStorage()
    remote_data = gh.load_data()
    
    if remote_data:
        st.session_state["sku_data"] = remote_data
        st.toast("Data loaded from GitHub!", icon="☁️")
    else:
        # === MASTER DATA PRE-LOAD ===
        st.session_state["sku_data"] = {
            "inventory": {
                # 1. BLAST MACHINE (Separated by hyphens)
                "Blast Machine": {
                    "settings": {"extras_mode": "Multiple", "separator": "-"},
                    "fields": {
                        "Brand": [{"code": "BL", "name": "Blastline", "order": 1}],
                        "Capacity": [
                            {"code": "20", "name": "1080 (20L)", "order": 1},
                            {"code": "30", "name": "1090 (30L)", "order": 2},
                            {"code": "200", "name": "24650 (200L)", "order": 3}
                        ],
                        "Configuration": [
                            {"code": "M", "name": "Manual", "order": 1},
                            {"code": "C", "name": "Contractor", "order": 2}
                        ],
                        "Certification": [
                            {"code": "S", "name": "Standard", "order": 1},
                            {"code": "CE", "name": "CE Certified", "order": 2}
                        ],
                        "Valve": [
                            {"code": "F", "name": "Flat Sand", "order": 1},
                            {"code": "T", "name": "Thompson", "order": 2}
                        ]
                    },
                    "extras": [
                        {"name": "Moisture Separator", "code": "01", "selected": False},
                        {"name": "PG + RV", "code": "02", "selected": False}
                    ]
                },
                # 2. HOSE - AIR (No separator, concatenated)
                "Hose - Air": {
                    "settings": {"extras_mode": "Single", "separator": ""},
                    "fields": {
                        "Main Category": [{"code": "H", "name": "Hose", "order": 1}],
                        "Application": [{"code": "A", "name": "Air", "order": 1}],
                        "Material": [
                            {"code": "P", "name": "NBR/PVC", "order": 1},
                            {"code": "R", "name": "Rubber", "order": 2}
                        ],
                        "Size": [
                            {"code": "08", "name": "1/2 inch", "order": 1},
                            {"code": "16", "name": "1 inch", "order": 2}
                        ],
                        "Roll Length": [
                            {"code": "020", "name": "20 mtr", "order": 1},
                            {"code": "040", "name": "40 mtr", "order": 2}
                        ],
                        "Pressure": [
                            {"code": "20", "name": "20 Bar / 300 Psi", "order": 1}
                        ]
                    },
                    "extras": []
                },
                 # 3. COUPLINGS (Chicago/Crowfoot)
                "Couplings": {
                    "settings": {"extras_mode": "Single", "separator": ""},
                    "fields": {
                        "Main Category": [{"code": "C", "name": "Couplings", "order": 1}],
                        "Lug Type": [
                            {"code": "2L", "name": "Chicago 2 Lug", "order": 1},
                            {"code": "4L", "name": "Crowfoot 4 Lug", "order": 2}
                        ],
                        "End Type": [
                            {"code": "HE", "name": "Hose End", "order": 1},
                            {"code": "ME", "name": "Male End", "order": 2},
                            {"code": "FE", "name": "Female End", "order": 3}
                        ],
                        "Size": [
                            {"code": "04", "name": "1/4 inch", "order": 1},
                            {"code": "12", "name": "3/4 inch", "order": 2},
                            {"code": "16", "name": "1 inch", "order": 3}
                        ],
                         "Supplier": [
                            {"code": "TFG", "name": "Tuticorin Finished", "order": 1},
                            {"code": "YC", "name": "Yangcheng", "order": 2}
                        ]
                    },
                    "extras": []
                },
                # 4. GRACO (Text Input Example)
                "Graco": {
                    "settings": {"extras_mode": "Single", "separator": ""},
                    "fields": {
                        "Prefix": [{"code": "PG", "name": "Graco Part", "order": 1}],
                        # Special flag 'is_text_input' for manual entry
                        "Part Number": [{"code": "", "name": "Enter No.", "order": 1, "type": "text"}]
                    },
                    "extras": []
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
        separator = cat_data.get("settings", {}).get("separator", "")
        
        if not fields_dict and not extras_list: continue
        
        core_lists = []
        field_keys = list(fields_dict.keys())
        
        # We only generate matrix for Dropdown fields. Text fields complicate matrix generation.
        # We will assume empty string for text fields in matrix.
        for key in field_keys:
            # check if text input
            is_text = False
            if fields_dict[key] and isinstance(fields_dict[key][0], dict):
                 if fields_dict[key][0].get("type") == "text":
                     is_text = True
            
            if is_text:
                # Add a dummy placeholder for text fields in matrix
                core_lists.append([{"code": "###", "name": "[Manual Input]"}])
            else:
                core_lists.append(fields_dict[key])
            
        if not core_lists: core_combinations = [([],)]
        else: core_combinations = list(itertools.product(*core_lists))

        extras_combinations = []
        if mode == "Single":
            extras_combinations.append({"code": "", "name": "None"})
            for ex in extras_list:
                code = ex.get("code")
                if code and str(code).strip():
                    extras_combinations.append({"code": str(code), "name": ex["name"]})
        else:
            valid_extras = [e for e in extras_list if e.get("code") and str(e.get("code")).strip()]
            for r in range(len(valid_extras) + 1):
                for combo in itertools.combinations(valid_extras, r):
                    if not combo:
                        extras_combinations.append({"code": "", "name": "None"})
                    else:
                        c_code = "".join([str(i["code"]) for i in combo])
                        c_name = " | ".join([i["name"] for i in combo])
                        extras_combinations.append({"code": c_code, "name": c_name})
        
        for core in core_combinations:
            base_sku = separator.join([item["code"] for item in core]) if core and core[0] else ""
            base_desc = " | ".join([item["name"] for item in core]) if core and core[0] else ""
            
            for extra in extras_combinations:
                # Add separator before extra if needed, or just append based on logic
                # Usually extras are appended with separator if the main sku used one
                full_sku = base_sku + (separator if separator and extra["code"] else "") + extra["code"]
                
                desc_sep = " | " if base_desc and extra["name"] != "None" else ""
                extra_desc = extra["name"] if extra["name"] != "None" else ""
                full_desc = f"{base_desc}{desc_sep}{extra_desc}"
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

    c_cat1, c_cat2 = st.columns([1, 1])
    with c_cat1:
        category = st.selectbox("Product Category", available_cats, on_change=reset_pagination)
    
    cat_data = inventory.get(category, {})
    fields_dict = cat_data.get("fields", {})
    extras_list = cat_data.get("extras", [])
    extras_mode = cat_data.get("settings", {}).get("extras_mode", "Multiple")
    separator = cat_data.get("settings", {}).get("separator", "")

    col1, col2 = st.columns([1, 1])
    selections = {}
    
    with col1:
        st.subheader("Configuration")
        field_keys = list(fields_dict.keys())
        # No specific priority hardcoded, use insertion order or 'order' key if needed
        # Just use list order for now
        
        if not field_keys:
            st.info("No fields configured for this category.")
            
        for key in field_keys:
            opts = fields_dict[key]
            
            # Check if this field is a TEXT INPUT field
            is_text_input = False
            if opts and isinstance(opts[0], dict):
                 if opts[0].get("type") == "text":
                     is_text_input = True
            
            if is_text_input:
                # Render Text Input
                val = st.text_input(key, key=f"home_{category}_{key}")
                selections[key] = val # Use typed value directly
            else:
                # Render Dropdown
                try:
                    opts = sorted(opts, key=safe_int_sort)
                except Exception: pass
                
                if opts:
                    choice = st.selectbox(key, opts, format_func=get_option_label, key=f"home_{category}_{key}")
                    selections[key] = choice['code']
                else:
                    selections[key] = ""
                    st.warning(f"No options in {key}")

    with col2:
        st.subheader("Extras / Add-ons")
        selected_extras_codes = []
        missing_code_names = []

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
                            code = e.get("code")
                            if code and str(code).strip():
                                selected_extras_codes.append(str(code))
                            else:
                                missing_code_names.append(e["name"])
                            break
            else:
                c_ex1, c_ex2 = st.columns(2)
                for i, extra in enumerate(current_page_extras):
                    col = c_ex1 if i % 2 == 0 else c_ex2
                    if col.checkbox(extra["name"], key=f"ex_{category}_{current_idx}_{i}"):
                        code = extra.get("code")
                        if code and str(code).strip():
                            selected_extras_codes.append(str(code))
                        else:
                            missing_code_names.append(extra["name"])

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
        
        if missing_code_names:
            st.error(f"⚠️ **Configuration Error:** The following items have no SKU Code: {', '.join(missing_code_names)}.")

        # JOIN SKU USING THE CATEGORY SEPARATOR
        # Filter out empty values (unless text input was intentionally left blank, handled by join)
        parts = [str(selections.get(k, "")) for k in field_keys]
        # Remove empty strings from parts only if we want to avoid double separators
        # But for text inputs, empty might mean missing data. We'll stick to joining.
        base_sku = separator.join(parts)
        
        # Append extras. Usually extras are just appended, or separated? 
        # Standard logic: Append to end. If separator exists, maybe add it?
        # For hoses (no sep), just append. For Machines (sep), usually separated.
        extras_sku = "".join(selected_extras_codes) # Extras usually combined
        
        if separator and base_sku and extras_sku:
             full_sku = base_sku + separator + extras_sku
        else:
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
                            "fields": {}, "extras": [], "settings": {"extras_mode": "Multiple", "separator": "-"}
                        }
                        st.success(f"Created {new_cat_name}")
                        st.rerun()

        st.markdown("---")

        if selected_cat:
            cat_data = inventory[selected_cat]
            col_conf_main, col_conf_extras = st.columns([1, 1], gap="large")
            
            with col_conf_main:
                st.markdown(f"### 1. Configuration Fields")
                
                # SEPARATOR SETTING
                curr_sep = cat_data.get("settings", {}).get("separator", "-")
                new_sep = st.text_input("SKU Separator (e.g. '-' or leave empty)", value=curr_sep, key=f"sep_{selected_cat}")
                if new_sep != curr_sep:
                    if "settings" not in cat_data: cat_data["settings"] = {}
                    cat_data["settings"]["separator"] = new_sep
                    # Force update in session state? It's ref passed so should be ok, but let's be safe
                    st.session_state["sku_data"]["inventory"][selected_cat]["settings"]["separator"] = new_sep

                current_fields = cat_data["fields"]
                field_list = list(current_fields.keys())
                
                with st.form("form_new_field"):
                    c_f1, c_f2, c_f3 = st.columns([2, 1, 1])
                    new_field_name = c_f1.text_input("New Field Name", placeholder="e.g. Thread", label_visibility="collapsed")
                    field_type = c_f3.selectbox("Type", ["Dropdown", "Text Input"], label_visibility="collapsed")
                    
                    if c_f2.form_submit_button("Add Field"):
                        if new_field_name and new_field_name not in current_fields:
                            # Initialize with a dummy record that defines the type
                            f_type_code = "text" if field_type == "Text Input" else "select"
                            if f_type_code == "text":
                                # Initialize text fields with a marker
                                st.session_state["sku_data"]["inventory"][selected_cat]["fields"][new_field_name] = [
                                    {"code": "", "name": "Text Input", "type": "text"}
                                ]
                            else:
                                st.session_state["sku_data"]["inventory"][selected_cat]["fields"][new_field_name] = []
                            st.rerun()

                if field_list:
                    field_to_edit = st.selectbox("Select Field to Edit Options", field_list)
                    
                    # CHECK TYPE
                    is_text_field = False
                    if current_fields[field_to_edit] and isinstance(current_fields[field_to_edit][0], dict):
                         if current_fields[field_to_edit][0].get("type") == "text":
                             is_text_field = True
                    
                    if is_text_field:
                        st.info(f"Field '{field_to_edit}' is a **Text Input**. No options to configure.")
                        if st.button("🗑️ Delete Field", key="del_text_field"):
                             del st.session_state["sku_data"]["inventory"][selected_cat]["fields"][field_to_edit]
                             st.rerun()
                    else:
                        st.markdown(f"**Options for '{field_to_edit}'**")
                        data_source = current_fields[field_to_edit]
                        if not data_source:
                            df = pd.DataFrame(columns=["order", "code", "name"])
                        else:
                            df = pd.DataFrame(data_source)
                        
                        if 'order' not in df.columns: df['order'] = range(1, len(df)+1)
                        if 'code' not in df.columns: df['code'] = ""
                        if 'name' not in df.columns: df['name'] = ""

                        with st.form(key=f"form_fields_{selected_cat}_{field_to_edit}"):
                            edited_df = st.data_editor(
                                df,
                                num_rows="dynamic",
                                column_config={
                                    "order": st.column_config.NumberColumn("Sort Order", width="small", default=1),
                                    "code": st.column_config.TextColumn("SKU Code", required=True),
                                    "name": st.column_config.TextColumn("Display Name", required=True),
                                },
                                hide_index=True,
                                use_container_width=True
                            )
                            c_sub1, c_sub2 = st.columns([1, 4])
                            if c_sub1.form_submit_button("✅ Update"):
                                st.session_state["sku_data"]["inventory"][selected_cat]["fields"][field_to_edit] = edited_df.to_dict('records')
                                st.success("Updated!")
                            
                            # Hacky delete button outside form logic usually preferred, but for now:
                            # User can delete all rows in editor to 'clear', but to delete field itself:
                        
                        if st.button("🗑️ Delete Field", key=f"del_field_{field_to_edit}"):
                             del st.session_state["sku_data"]["inventory"][selected_cat]["fields"][field_to_edit]
                             st.rerun()
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
                
                if not extras_data:
                    df_extras = pd.DataFrame(columns=["name", "code", "selected"])
                else:
                    df_extras = pd.DataFrame(extras_data)
                
                if 'name' not in df_extras.columns: df_extras['name'] = ""
                if 'code' not in df_extras.columns: df_extras['code'] = ""
                
                with st.form(key=f"form_extras_{selected_cat}"):
                    edited_extras = st.data_editor(
                        df_extras,
                        num_rows="dynamic",
                        column_config={
                            "name": st.column_config.TextColumn("Extra Name", required=True),
                            "code": st.column_config.TextColumn("Code", required=True),
                            "selected": None 
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    if st.form_submit_button("✅ Update Extras"):
                        st.session_state["sku_data"]["inventory"][selected_cat]["extras"] = edited_extras.to_dict('records')
                        st.success("Extras updated! Click 'Save to Cloud' to persist.")

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
