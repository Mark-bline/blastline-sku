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
EXTRAS_PER_PAGE = 5  # Reduced slightly to fit card layout better

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

def generate_qr_svg(text):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    size = len(matrix)
    scale = 10
    svg_size = size * scale
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_size}" height="{svg_size}" viewBox="0 0 {svg_size} {svg_size}">',
        f'<rect width="100%" height="100%" fill="white"/>',
    ]
    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                svg_parts.append(
                    f'<rect x="{x * scale}" y="{y * scale}" width="{scale}" height="{scale}" fill="black"/>'
                )
    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)

def show_success(message):
    st.success(message)

def show_error(message):
    st.error(message)

def show_info(message):
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

if "confirm_delete_cat" not in st.session_state:
    st.session_state["confirm_delete_cat"] = None

if "confirm_delete_field" not in st.session_state:
    st.session_state["confirm_delete_field"] = None

def go(p):
    st.session_state["page"] = p
    st.rerun()

# ==================================================
# HOME
# ==================================================
def home():
    """Main SKU configuration page with Card UI."""
    
    # 1. CSS Styling for the "Card" Layout
    st.markdown("""
        <style>
        /* Main background */
        .stApp {
            background-color: #f8f9fa;
        }
        
        /* Card Container Styling */
        div[data-testid="stVerticalBlock"] > div.element-container {
            width: 100%;
        }
        
        /* Create the "Card" look for the columns */
        /* Note: This targets the specific vertical blocks in the columns. 
           It might need adjustment if Streamlit structure changes. */
        div[data-testid="column"] {
            background-color: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
            border: 1px solid #e9ecef;
        }

        /* Headers inside cards */
        h4 {
            font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            font-weight: 700;
            color: #1a1a1a;
            margin-bottom: 20px;
        }

        /* Form elements styling */
        .stSelectbox label, .stTextInput label, .stRadio label {
            font-weight: 500;
            color: #4a4a4a;
        }
        
        /* Divider */
        hr {
            margin: 25px 0;
            border-color: #eee;
        }
        
        /* Center the top header */
        .main-header {
            text-align: center; 
            margin-bottom: 20px;
        }
        .main-header h1 {
            font-weight: 800;
            font-size: 2.2rem;
            color: #000;
        }
        
        /* Hide sidebar navigation on mobile for cleaner look if desired */
        </style>
    """, unsafe_allow_html=True)

    # 2. Top Header & Settings Access
    with st.sidebar:
        if st.button("⚙️ Settings", use_container_width=True):
            go("login")

    st.markdown("<div class='main-header'><h1>Blastline SKU Configurator</h1></div>", unsafe_allow_html=True)

    # 3. Category Selection (Centered)
    inv = st.session_state["sku_data"]["inventory"]
    if not inv:
        st.warning("No categories available. Please contact admin.")
        return

    # Center the category dropdown
    col_l, col_c, col_r = st.columns([1, 2, 1])
    with col_c:
        cat = st.selectbox("Product Category", list(inv.keys()), label_visibility="collapsed")
    
    # Data Setup
    cat_data = inv[cat]
    normalize_fields(cat_data)
    fields = cat_data["fields"]
    extras = cat_data.get("extras", [])
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)
    extras_mode = cat_data.get("settings", {}).get("extras_mode", DEFAULT_EXTRAS_MODE)

    sel = {}
    chosen = []

    st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)

    # 4. Main Two-Column Layout
    col_config, col_results = st.columns([1, 1], gap="large")

    # --- LEFT COLUMN: CONFIGURATION ---
    with col_config:
        st.markdown("#### Configuration")
        
        # Dynamic Fields
        for f in ordered_fields(fields):
            opts = fields[f]["options"]
            is_text = opts and opts[0].get("type") == "text"
            
            if is_text:
                text_val = st.text_input(f, help=f"Enter {f}", placeholder=f"Enter {f}")
                sel[f] = {"code": text_val, "name": text_val}
            else:
                if opts:
                    # Format: "Machine: BL - Blast Machine" style in dropdown
                    o = st.selectbox(
                        f, 
                        opts, 
                        format_func=lambda x, field=f: f"{field}: {x['code']} - {x['name']}",
                    )
                    sel[f] = {"code": o["code"], "name": o["name"]}
        
        st.markdown("---")
        
        # Extras Section
        st.markdown("#### Extras")
        if extras:
            sorted_extras = sorted(extras, key=lambda x: x.get("order", 999))
            
            # Pagination
            total_extras = len(sorted_extras)
            total_pages = (total_extras - 1) // EXTRAS_PER_PAGE + 1 if total_extras > 0 else 1
            current_page = st.session_state.get("extras_page", 0)
            
            if current_page >= total_pages:
                current_page = total_pages - 1
                st.session_state["extras_page"] = current_page
            
            start_idx = current_page * EXTRAS_PER_PAGE
            end_idx = min(start_idx + EXTRAS_PER_PAGE, total_extras)
            page_extras = sorted_extras[start_idx:end_idx]

            # Render Extras
            if extras_mode == "Single":
                extra_options = [{"name": "None", "code": ""}] + page_extras
                extra_labels = [e["name"] for e in extra_options]
                selected = st.radio(
                    "Select Extra:",
                    options=range(len(extra_options)),
                    format_func=lambda i: extra_labels[i],
                    key="single_extra_selector",
                    label_visibility="collapsed"
                )
                if selected > 0 and extra_options[selected].get("code"):
                    chosen.append({"code": extra_options[selected]["code"], "name": extra_options[selected]["name"]})
            else:
                for idx in range(len(page_extras)):
                    e = page_extras[idx]
                    actual_idx = start_idx + idx
                    if st.checkbox(e["name"], key=f"extra_{actual_idx}"):
                        if e.get("code"):
                            chosen.append({"code": e["code"], "name": e["name"]})

            # Pagination Controls
            if total_pages > 1:
                st.markdown("<br>", unsafe_allow_html=True)
                c_prev, c_info, c_next = st.columns([1, 2, 1])
                with c_prev:
                    if st.button("❮", disabled=(current_page == 0)):
                        st.session_state["extras_page"] = current_page - 1
                        st.rerun()
                with c_next:
                    if st.button("❯", disabled=(current_page == total_pages - 1)):
                        st.session_state["extras_page"] = current_page + 1
                        st.rerun()
        else:
            st.caption("No extras available.")

    # Calculate SKU Logic
    base = sep.join([sel[k]["code"] for k in ordered_fields(fields) if sel.get(k) and sel[k]["code"]])
    extras_codes = "".join([c["code"] for c in chosen])
    sku = base + (sep if base and extras_codes else "") + extras_codes
    
    config_names = [sel[k]["name"] for k in ordered_fields(fields) if sel.get(k) and sel[k]["name"]]
    extras_names = [c["name"] for c in chosen]
    all_names = config_names + extras_names
    sku_description = " - ".join(all_names) if all_names else "Select options to view breakdown"

    # --- RIGHT COLUMN: RESULTS ---
    with col_results:
        st.markdown("#### Generated SKU")
        
        # Light Theme SKU Box
        if sku:
            sku_html = f"""
            <div onclick="copySKUText()" style="
                background: #F0F7FF;
                border: 1px solid #CCE4FF;
                border-radius: 8px;
                padding: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                cursor: pointer;
                margin-bottom: 15px;
            ">
                <span style="color: #0066CC; font-weight: 700; font-family: monospace; font-size: 24px;">{sku}</span>
                <div style="text-align: center;">
                    <span id="copy-icon" style="font-size: 20px;">📋</span>
                    <div style="font-size: 10px; color: #666;">Click to Copy</div>
                </div>
            </div>
            <div id="copy-msg" style="height: 20px; text-align: right; font-size: 12px; color: #28a745;"></div>
            
            <script>
            function copySKUText() {{
                navigator.clipboard.writeText("{sku}");
                document.getElementById('copy-msg').innerText = "Copied!";
                setTimeout(() => {{ document.getElementById('copy-msg').innerText = ""; }}, 2000);
            }}
            </script>
            """
            st.components.v1.html(sku_html, height=120)
        else:
            st.info("Pending selection...")

        # Breakdown
        st.markdown("**SKU Breakdown**")
        st.caption(sku_description)

        st.markdown("---")
        
        st.markdown("#### Generated QR Code")
        if sku:
            qr_base64 = get_qr_code_base64(sku)
            
            # QR Code Display
            st.markdown(
                f"""
                <div style="
                    background: #F8F9FA;
                    border: 1px dashed #DEE2E6;
                    border-radius: 8px;
                    padding: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                ">
                    <img src="data:image/png;base64,{qr_base64}" width="100">
                    <div style="text-align: right;">
                        <span style="font-size: 24px;">📱</span>
                        <div style="font-size: 10px; color: #666;">Scan or DL</div>
                    </div>
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Download Button
            col_dl, _ = st.columns([1, 1])
            with col_dl:
                qr_buffer_png = generate_qr_code(sku, size=300)
                st.download_button(
                    label="⬇️ Download PNG",
                    data=qr_buffer_png,
                    file_name=f"{sku}_QR.png",
                    mime="image/png",
                )
        else:
            st.caption("QR Code will appear here")

# ==================================================
# LOGIN
# ==================================================
def login():
    """Admin login page."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Admin Login")
        pw = st.text_input("Password", type="password")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Login", use_container_width=True):
                # Security Note: Consider moving this password to st.secrets
                if pw == "admin123":
                    go("admin")
                else:
                    show_error("Invalid password.")
        with c2:
            if st.button("Cancel", use_container_width=True):
                go("home")

# ==================================================
# ADMIN
# ==================================================
def admin():
    """Admin configuration page."""
    st.title("⚙️ Admin Settings")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("← Back"):
            go("home")
    
    st.markdown("---")
    inv = st.session_state["sku_data"]["inventory"]

    # Category Creation
    c1, c2 = st.columns([3, 1])
    with c1:
        cat = st.selectbox("Product Category", list(inv.keys()) if inv else [])
    with c2:
        with st.form("add_cat"):
            n = st.text_input("New Cat", label_visibility="collapsed", placeholder="New Category")
            if st.form_submit_button("➕ Add") and n:
                if n not in inv:
                    inv[n] = {"fields": {}, "extras": [], "settings": {}}
                    st.rerun()

    if not cat: return

    # Admin Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Fields", "Extras", "Settings", "Export"])

    # FIELDS
    with tab1:
        cat_data = inv[cat]
        normalize_fields(cat_data)
        fields = cat_data["fields"]
        
        with st.expander("Add Field"):
            with st.form("new_f"):
                fn = st.text_input("Name")
                ft = st.selectbox("Type", ["Dropdown", "Text Input"])
                if st.form_submit_button("Create") and fn:
                    fields[fn] = {"order": len(fields)+1, "options": [{"type":"text"}] if ft == "Text Input" else []}
                    st.rerun()
        
        if fields:
            f_edit = st.selectbox("Edit Field", ordered_fields(fields))
            opts = fields[f_edit]["options"]
            if opts and opts[0].get("type") != "text":
                df = normalize_option_df(opts)
                edited = st.data_editor(df, num_rows="dynamic", use_container_width=True)
                if st.button("Save Options"):
                    fields[f_edit]["options"] = edited.to_dict("records")
                    st.rerun()
            
            if st.button("Delete Field"):
                del fields[f_edit]
                st.rerun()

    # EXTRAS
    with tab2:
        cat_data = inv[cat]
        extras = cat_data.get("extras", [])
        df_ex = normalize_extras_df(extras)
        ed_ex = st.data_editor(df_ex, num_rows="dynamic", use_container_width=True)
        if st.button("Save Extras"):
            cat_data["extras"] = ed_ex.to_dict("records")
            st.rerun()

    # SETTINGS
    with tab3:
        cat_data = inv[cat]
        settings = cat_data.get("settings", {})
        sep = st.text_input("Separator", settings.get("separator", DEFAULT_SEPARATOR))
        mode = st.radio("Extras Mode", ["Single", "Multiple"], index=0 if settings.get("extras_mode") == "Single" else 1)
        if st.button("Save Settings"):
            settings["separator"] = sep
            settings["extras_mode"] = mode
            cat_data["settings"] = settings
            st.rerun()

    # EXPORT
    with tab4:
        if st.button("Generate Matrix"):
            df = generate_full_matrix(inv[cat])
            st.dataframe(df.head())
            st.download_button("Download CSV", df.to_csv(index=False), f"{cat}_matrix.csv")

    st.markdown("---")
    if st.button("☁️ Save Changes to Cloud", type="primary"):
        if GithubStorage().save(st.session_state["sku_data"]):
            show_success("Saved!")
        else:
            show_error("Save failed.")

# ==================================================
# ROUTER
# ==================================================
if st.session_state["page"] == "home":
    home()
elif st.session_state["page"] == "login":
    login()
elif st.session_state["page"] == "admin":
    admin()
