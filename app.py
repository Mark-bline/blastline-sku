import streamlit as st
import pandas as pd
import json
import itertools
import requests
import base64

# ==================================================
# CONSTANTS
# ==================================================
COPY_BOX_HEIGHT = 160
DEFAULT_SEPARATOR = "-"
DEFAULT_EXTRAS_MODE = "Single"
EXTRAS_PER_PAGE = 10

# ==================================================
# SETUP
# ==================================================
st.set_page_config(page_title="Blastline SKU Configurator", layout="wide")

# ==================================================
# GITHUB STORAGE
# ==================================================
class GithubStorage:
    """Handles data persistence to GitHub repository."""
    
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
        """Load configuration data from GitHub."""
        if not self.can_connect:
            return None
        r = requests.get(self.api_url, headers=self.headers, params={"ref": self.branch})
        if r.status_code == 200:
            st.session_state["github_sha"] = r.json()["sha"]
            return json.loads(base64.b64decode(r.json()["content"]).decode())
        return None

    def save(self, data):
        """Save configuration data to GitHub."""
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
    """Format option for display in selectbox."""
    return f"{o['code']} : {o['name']}"

def normalize_fields(cat):
    """
    Normalize category fields structure to ensure consistent format.
    Converts legacy field formats to new structure with 'order' and 'options'.
    
    Args:
        cat: Category dictionary (modified in place)
    """
    fields = {}
    for i, (k, v) in enumerate(cat.get("fields", {}).items(), start=1):
        if isinstance(v, dict):
            fields[k] = v
        else:
            fields[k] = {"order": i, "options": v}
    cat["fields"] = fields

def ordered_fields(fields):
    """
    Return field names sorted by their order value.
    
    Args:
        fields: Dictionary of field configurations
        
    Returns:
        List of field names in order
    """
    return sorted(fields.keys(), key=lambda k: fields[k].get("order", 999))

def normalize_option_df(data):
    """
    Convert options list to normalized DataFrame for editing.
    
    Args:
        data: List of option dictionaries
        
    Returns:
        DataFrame with code, name, order columns
    """
    df = pd.DataFrame(data or [], columns=["code", "name", "order"])
    if df.empty:
        df = pd.DataFrame(columns=["code", "name", "order"])
    if df["order"].isnull().all():
        df["order"] = range(1, len(df) + 1)
    return df[["code", "name", "order"]]

def normalize_extras_df(data):
    """
    Convert extras list to normalized DataFrame for editing.
    
    Args:
        data: List of extra dictionaries
        
    Returns:
        DataFrame with code, name, and order columns
    """
    df = pd.DataFrame(data or [], columns=["code", "name", "order"])
    if df.empty:
        df = pd.DataFrame(columns=["code", "name", "order"])
    if "order" not in df.columns or df["order"].isnull().all():
        df["order"] = range(1, len(df) + 1)
    return df[["code", "name", "order"]]

def generate_full_matrix(cat_data):
    """
    Generate all possible SKU combinations for a category.
    
    Args:
        cat_data: Category configuration dictionary
        
    Returns:
        pandas DataFrame with all SKU combinations
    """
    normalize_fields(cat_data)
    fields = cat_data["fields"]
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)
    
    # Get all field combinations (excluding text input fields)
    field_combos = []
    field_names = []
    
    for f in ordered_fields(fields):
        opts = fields[f]["options"]
        is_text = opts and opts[0].get("type") == "text"
        if not is_text and opts:
            field_names.append(f)
            field_combos.append([o["code"] for o in opts])
    
    # Generate all combinations
    if not field_combos:
        return pd.DataFrame(columns=["SKU"] + field_names)
    
    combinations = list(itertools.product(*field_combos))
    
    # Create DataFrame
    rows = []
    for combo in combinations:
        sku = sep.join(combo)
        row = {"SKU": sku}
        for i, fname in enumerate(field_names):
            row[fname] = combo[i]
        rows.append(row)
    
    return pd.DataFrame(rows)

def big_copy_box(text):
    """
    Generate HTML for large, clickable SKU display with copy functionality.
    
    Args:
        text: The SKU text to display and copy
        
    Returns:
        HTML string with embedded JavaScript
    """
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

def show_success(message):
    """Display success message."""
    st.success(message)

def show_error(message):
    """Display error message."""
    st.error(message)

def show_info(message):
    """Display info message."""
    st.info(message)

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
    """Navigate to a different page."""
    st.session_state["page"] = p
    st.rerun()

# ==================================================
# HOME
# ==================================================
def home():
    """Main SKU configuration page."""
    with st.sidebar:
        if st.button("⚙️ Settings", use_container_width=True):
            go("login")

    st.title("Blastline SKU Configurator")
    st.markdown("---")

    inv = st.session_state["sku_data"]["inventory"]
    if not inv:
        st.warning("No categories available. Please contact admin to set up product categories.")
        st.markdown("---")
        st.markdown(
            "<div style='text-align:center;color:#888;padding:20px;font-size:0.9em'>"
            "This application is developed by <strong>Blastline India Pvt Ltd</strong>."
            "</div>",
            unsafe_allow_html=True
        )
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

    # Generated SKU section at top
    st.subheader("Generated SKU")
    
    # Placeholders for SKU display
    sku_placeholder = st.empty()
    breakdown_placeholder = st.empty()
    
    st.markdown("---")

    # Configuration section in 2 columns
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Configuration")
        for f in ordered_fields(fields):
            opts = fields[f]["options"]
            is_text = opts and opts[0].get("type") == "text"
            if is_text:
                sel[f] = st.text_input(f, help=f"Enter {f}")
            else:
                if opts:
                    o = st.selectbox(f, opts, format_func=get_option_label, help=f"Select {f}")
                    sel[f] = o["code"]

    with c2:
        st.subheader("Extras / Add-ons")
        
        if extras:
            # Sort extras by order before displaying
            sorted_extras = sorted(extras, key=lambda x: x.get("order", 999))
            
            # Calculate pagination
            total_extras = len(sorted_extras)
            total_pages = (total_extras - 1) // EXTRAS_PER_PAGE + 1 if total_extras > 0 else 1
            current_page = st.session_state.get("extras_page", 0)
            
            # Ensure current page is within bounds
            if current_page >= total_pages:
                current_page = total_pages - 1
                st.session_state["extras_page"] = current_page
            
            start_idx = current_page * EXTRAS_PER_PAGE
            end_idx = min(start_idx + EXTRAS_PER_PAGE, total_extras)
            
            # Show pagination controls if needed
            if total_pages > 1:
                col1, col2, col3 = st.columns([1, 2, 1])
                with col1:
                    if st.button("← Prev", disabled=(current_page == 0), use_container_width=True):
                        st.session_state["extras_page"] = current_page - 1
                        st.rerun()
                with col2:
                    st.markdown(f"<div style='text-align:center;padding:8px'>Page {current_page + 1} of {total_pages}</div>", unsafe_allow_html=True)
                with col3:
                    if st.button("Next →", disabled=(current_page == total_pages - 1), use_container_width=True):
                        st.session_state["extras_page"] = current_page + 1
                        st.rerun()
            
            # Show extras based on mode
            page_extras = sorted_extras[start_idx:end_idx]
            
            if extras_mode == "Single":
                # Radio button for single selection
                extra_options = [{"name": "None", "code": ""}] + page_extras
                extra_labels = [e["name"] for e in extra_options]
                
                selected = st.radio(
                    "Select one extra:",
                    options=range(len(extra_options)),
                    format_func=lambda i: extra_labels[i],
                    key="single_extra_selector"
                )
                
                if selected > 0 and extra_options[selected].get("code"):
                    chosen.append(extra_options[selected]["code"])
            else:
                # Multiple selection with checkboxes (5x2 grid)
                for row in range(5):
                    left_idx = row
                    right_idx = row + 5
                    
                    col1, col2 = st.columns(2)
                    
                    # Left column item
                    if left_idx < len(page_extras):
                        with col1:
                            e = page_extras[left_idx]
                            actual_idx = start_idx + left_idx
                            if st.checkbox(e["name"], key=f"extra_{actual_idx}", help=f"Add {e['name']} to SKU"):
                                if e.get("code"):
                                    chosen.append(e["code"])
                    
                    # Right column item
                    if right_idx < len(page_extras):
                        with col2:
                            e = page_extras[right_idx]
                            actual_idx = start_idx + right_idx
                            if st.checkbox(e["name"], key=f"extra_{actual_idx}", help=f"Add {e['name']} to SKU"):
                                if e.get("code"):
                                    chosen.append(e["code"])
        else:
            st.info("No extras configured for this category")

    # Now calculate and display the SKU at the top
    base = sep.join([sel[k] for k in ordered_fields(fields) if sel.get(k)])
    sku = base + (sep if base and chosen else "") + "".join(chosen)

    with sku_placeholder.container():
        if sku:
            st.components.v1.html(big_copy_box(sku), height=COPY_BOX_HEIGHT)
        else:
            st.info("Select options to generate SKU")
    
    with breakdown_placeholder.container():
        if sku:
            # Show SKU breakdown
            with st.expander("SKU Breakdown"):
                st.write("**Base Configuration:**")
                for f in ordered_fields(fields):
                    if sel.get(f):
                        st.write(f"- {f}: `{sel[f]}`")
                if chosen:
                    st.write("**Extras:**")
                    for e in extras:
                        if e.get("code") in chosen:
                            st.write(f"- {e['name']}: `{e['code']}`")
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align:center;color:#888;padding:20px;font-size:0.9em'>"
        "This application is developed by <strong>Blastline India Pvt Ltd</strong>."
        "</div>",
        unsafe_allow_html=True
    )

# ==================================================
# LOGIN
# ==================================================
def login():
    """Admin login page."""
    st.subheader("Admin Login")
    pw = st.text_input("Password", type="password")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login", use_container_width=True):
            if pw == "admin123":
                go("admin")
            else:
                show_error("Invalid password. Please try again.")
    with col2:
        if st.button("Cancel", use_container_width=True):
            go("home")

# ==================================================
# ADMIN
# ==================================================
def admin():
    """Admin configuration page."""
    st.title("⚙️ Admin Settings")
    
    # Back to home button
    if st.button("← Back to Home"):
        go("home")
    
    st.markdown("---")

    inv = st.session_state["sku_data"]["inventory"]

    c1, c2 = st.columns([3, 1])
    with c1:
        if inv:
            cat = st.selectbox("Product Category", list(inv.keys()))
        else:
            cat = None
            st.info("No categories yet. Create one below.")
            
    with c2:
        with st.form("add_cat"):
            n = st.text_input("New Category", label_visibility="collapsed", placeholder="Category name")
            if st.form_submit_button("➕ Add") and n:
                if n in inv:
                    show_error(f"Category '{n}' already exists!")
                else:
                    inv[n] = {
                        "fields": {}, 
                        "extras": [], 
                        "settings": {
                            "separator": DEFAULT_SEPARATOR, 
                            "extras_mode": DEFAULT_EXTRAS_MODE
                        }
                    }
                    show_success(f"Category '{n}' created successfully!")
                    st.rerun()

    if not cat:
        return

    if st.button("🗑️ Delete Category", help="Permanently delete this category"):
        del inv[cat]
        show_success(f"Category '{cat}' deleted successfully!")
        st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🛠️ Fields Configuration", "🎁 Extras Management", "⚙️ Category Settings", "📊 Export Matrix"])

    # ---------- FIELDS CONFIG ----------
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
                if name in fields:
                    show_error(f"Field '{name}' already exists!")
                else:
                    fields[name] = {
                        "order": len(fields) + 1,
                        "options": [{"type": "text", "code": "", "name": ""}] if ftype == "Text Input" else []
                    }
                    show_success(f"Field '{name}' added successfully!")
                    st.rerun()

        if fields:
            st.subheader("🔀 Field Order")
            df = pd.DataFrame([{"Field": k, "Order": v["order"]} for k, v in fields.items()])
            edited = st.data_editor(df, hide_index=True, use_container_width=True)
            if st.button("Apply Field Order"):
                for _, r in edited.iterrows():
                    fields[r["Field"]]["order"] = int(r["Order"])
                show_success("Field order updated successfully!")
                st.rerun()

            st.subheader("✏️ Rename / Delete Field")
            field = st.selectbox("Select Field", ordered_fields(fields))
            new_name = st.text_input("Rename Field To", value=field)
            c1, c2 = st.columns(2)
            if c1.button("Rename", use_container_width=True):
                if new_name == field:
                    show_info("Field name unchanged.")
                elif new_name and new_name not in fields:
                    fields[new_name] = fields.pop(field)
                    show_success(f"Field renamed from '{field}' to '{new_name}'")
                    st.rerun()
                elif new_name in fields:
                    show_error(f"Field '{new_name}' already exists!")
                    
            if c2.button("Delete", use_container_width=True):
                del fields[field]
                show_success(f"Field '{field}' deleted successfully!")
                st.rerun()

            st.subheader("🛠️ Field Options")
            opts = fields[field]["options"]
            if opts and opts[0].get("type") == "text":
                st.info("This is a text input field - users will enter values manually.")
            else:
                df2 = normalize_option_df(opts)
                edited_df = st.data_editor(
                    df2, 
                    num_rows="dynamic", 
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "code": st.column_config.TextColumn("Code", help="SKU code segment"),
                        "name": st.column_config.TextColumn("Name", help="Display name"),
                        "order": st.column_config.NumberColumn("Order", help="Display order")
                    }
                )
                if st.button("Update Options"):
                    fields[field]["options"] = edited_df.to_dict("records")
                    show_success(f"Options for '{field}' updated successfully!")
                    st.rerun()
        else:
            st.info("No fields configured yet. Add a field above to get started.")

    # ---------- EXTRAS MANAGEMENT ----------
    with tab2:
        cat_data = inv[cat]
        extras = cat_data.get("extras", [])
        
        st.subheader("🎁 Manage Extras / Add-ons")
        st.info(f"Extras will be displayed in a 5×2 grid (10 per page) in the configurator with pagination controls.")
        
        extras_df = normalize_extras_df(extras)
        edited_extras = st.data_editor(
            extras_df,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            column_config={
                "code": st.column_config.TextColumn("Code", help="SKU code for this extra (will be appended to SKU)"),
                "name": st.column_config.TextColumn("Name", help="Display name shown to users"),
                "order": st.column_config.NumberColumn("Order", help="Display order (lower numbers appear first)")
            }
        )
        
        if st.button("💾 Save Extras", type="primary", use_container_width=True):
            cat_data["extras"] = edited_extras.to_dict("records")
            show_success(f"Extras updated successfully! Total: {len(edited_extras)}")
            st.rerun()
        
        if len(extras) > 0:
            st.markdown("---")
            st.subheader("Preview")
            st.write(f"**Total Extras:** {len(extras)}")
            total_pages = (len(extras) - 1) // EXTRAS_PER_PAGE + 1 if len(extras) > 0 else 1
            st.write(f"**Pages in Configurator:** {total_pages}")
            st.write(f"**Layout:** 5 rows × 2 columns per page")

    # ---------- CATEGORY SETTINGS ----------
    with tab3:
        cat_data = inv[cat]
        settings = cat_data.get("settings", {})
        
        st.subheader("⚙️ Category Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### SKU Separator")
            separator = st.text_input(
                "Separator Character",
                value=settings.get("separator", DEFAULT_SEPARATOR),
                help="Character used to separate SKU components",
                max_chars=5,
                key="separator_input"
            )
        
        with col2:
            st.markdown("##### Extras Selection Mode")
            extras_mode_setting = st.radio(
                "Allow users to select:",
                options=["Single", "Multiple"],
                index=0 if settings.get("extras_mode", DEFAULT_EXTRAS_MODE) == "Single" else 1,
                help="Single: Users can select only one extra (radio buttons)\nMultiple: Users can select multiple extras (checkboxes)",
                key="extras_mode_input"
            )
        
        st.markdown("---")
        
        if st.button("💾 Save Settings", type="primary", use_container_width=True):
            settings["separator"] = separator
            settings["extras_mode"] = extras_mode_setting
            cat_data["settings"] = settings
            show_success("Category settings saved successfully!")
            st.rerun()
        
        st.markdown("---")
        st.subheader("Current Settings Preview")
        st.write(f"**Separator:** `{separator}`")
        st.write(f"**Extras Mode:** {extras_mode_setting}")
        if extras_mode_setting == "Single":
            st.info("ℹ️ Users will see radio buttons to select one extra at a time")
        else:
            st.info("ℹ️ Users will see checkboxes to select multiple extras")

    # ---------- EXPORT MATRIX ----------
    with tab4:
        st.subheader("📊 Full Matrix SKU Export")
        st.write("Generate a CSV file containing all possible SKU combinations for this category.")
        
        cat_data = inv[cat]
        normalize_fields(cat_data)
        
        if cat_data["fields"]:
            # Preview count
            field_combos = []
            for f in ordered_fields(cat_data["fields"]):
                opts = cat_data["fields"][f]["options"]
                is_text = opts and opts[0].get("type") == "text"
                if not is_text and opts:
                    field_combos.append(len(opts))
            
            if field_combos:
                total_combinations = 1
                for count in field_combos:
                    total_combinations *= count
                
                st.info(f"This will generate **{total_combinations:,}** SKU combinations")
                
                if st.button("🔄 Generate Matrix", use_container_width=True):
                    with st.spinner("Generating SKU matrix..."):
                        matrix_df = generate_full_matrix(cat_data)
                        st.session_state["matrix_preview"] = matrix_df
                        show_success(f"Generated {len(matrix_df):,} SKU combinations!")
                
                if "matrix_preview" in st.session_state:
                    st.markdown("---")
                    st.subheader("Preview")
                    st.dataframe(st.session_state["matrix_preview"].head(50), use_container_width=True)
                    if len(st.session_state["matrix_preview"]) > 50:
                        st.caption(f"Showing first 50 of {len(st.session_state['matrix_preview']):,} rows")
                    
                    csv = st.session_state["matrix_preview"].to_csv(index=False)
                    st.download_button(
                        "📥 Download Full Matrix CSV",
                        csv,
                        f"{cat}_full_matrix.csv",
                        "text/csv",
                        use_container_width=True,
                        type="primary"
                    )
            else:
                st.warning("No dropdown fields configured. Text input fields are excluded from matrix generation.")
        else:
            st.warning("No fields configured yet. Add fields in the Fields Configuration tab.")

    st.markdown("---")
    if st.button("☁️ Save to Cloud", use_container_width=True, type="primary"):
        with st.spinner("Saving to cloud..."):
            if GithubStorage().save(st.session_state["sku_data"]):
                show_success("Configuration saved to cloud successfully!")
            else:
                show_error("Failed to save to cloud. Check your connection and credentials.")
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
