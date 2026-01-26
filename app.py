import streamlit as st
import pandas as pd
import json
import itertools
import requests
import base64
import qrcode
from io import BytesIO
import os

# ==================================================
# CONSTANTS
# ==================================================
COPY_BOX_HEIGHT = 160
DEFAULT_SEPARATOR = "-"
DEFAULT_EXTRAS_MODE = "Single"
EXTRAS_PER_PAGE = 8

# ==================================================
# SETUP
# ==================================================
st.set_page_config(page_title="Blastline SKU Configurator", layout="wide")

# ==================================================
# GITHUB STORAGE
# ==================================================
class GithubStorage:
    """Handles data persistence to GitHub repository."""
    

DATA_FILE = "/data/sku_data.json"

class GithubStorage:
    """
    Disk-backed persistent storage.
    Class name intentionally preserved so the rest of the
    971-line application remains completely untouched.
    """

    def __init__(self):
        self.path = DATA_FILE
        self.can_connect = True  # preserve existing logic paths

    def load(self):
        if not os.path.exists(self.path):
            return {"inventory": {}}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"inventory": {}}

    def save(self, data):
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
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
    Features responsive font sizing for mobile devices.
    
    Args:
        text: The SKU text to display and copy
        
    Returns:
        HTML string with embedded JavaScript and responsive CSS
    """
    return f"""
    <style>
        .sku-container {{
            cursor: pointer;
            background: #111;
            border: 2px solid #4CAF50;
            border-radius: 14px;
            padding: 26px 15px;
            text-align: center;
            overflow: hidden;
        }}
        .sku-text {{
            font-family: monospace;
            color: #4CAF50;
            font-weight: 700;
            word-break: break-all;
            overflow-wrap: break-word;
            /* Dynamic font sizing based on viewport and text length */
            font-size: clamp(16px, 5vw, 44px);
        }}
        .sku-msg {{
            margin-top: 8px;
            color: #aaa;
            font-size: 14px;
        }}
        /* Adjust for very long SKUs */
        @media (max-width: 768px) {{
            .sku-container {{
                padding: 20px 10px;
            }}
            .sku-text {{
                font-size: clamp(14px, 4vw, 28px);
            }}
        }}
        @media (max-width: 480px) {{
            .sku-text {{
                font-size: clamp(12px, 3.5vw, 22px);
            }}
        }}
    </style>
    <div class="sku-container" onclick="copySKU()">
        <div class="sku-text">{text}</div>
        <div id="msg" class="sku-msg">📋 Click to copy</div>
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


def generate_qr_code(text, size=200):
    """
    Generate a QR code image for the given text.
    
    Args:
        text: The text to encode in the QR code
        size: Size of the QR code image in pixels
        
    Returns:
        BytesIO object containing the PNG image
    """
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
    """
    Generate a QR code and return as base64 string for HTML embedding.
    
    Args:
        text: The text to encode in the QR code
        
    Returns:
        Base64 encoded string of the QR code PNG
    """
    buffer = generate_qr_code(text)
    return base64.b64encode(buffer.getvalue()).decode()


def generate_qr_svg(text):
    """
    Generate a QR code as SVG string.
    
    Args:
        text: The text to encode in the QR code
        
    Returns:
        SVG string of the QR code
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(text)
    qr.make(fit=True)
    
    # Get the QR code matrix
    matrix = qr.get_matrix()
    size = len(matrix)
    scale = 10
    
    # Build SVG
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

if "confirm_delete_cat" not in st.session_state:
    st.session_state["confirm_delete_cat"] = None

if "confirm_delete_field" not in st.session_state:
    st.session_state["confirm_delete_field"] = None

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

    # Centered Header
    st.markdown("<h2 style='text-align: center; margin-bottom: 5px; font-family: -apple-system, BlinkMacSystemFont, sans-serif;'>Blastline SKU Configurator</h2>", unsafe_allow_html=True)

    inv = st.session_state["sku_data"]["inventory"]
    if not inv:
        st.warning("No categories available. Please contact admin to set up product categories.")
        return

    # Centered Product Category dropdown - compact width
    cat_spacer1, cat_col, cat_spacer2 = st.columns([2, 1.5, 2])
    with cat_col:
        cat = st.selectbox("Product Category", list(inv.keys()), label_visibility="collapsed")
    
    cat_data = inv[cat]
    normalize_fields(cat_data)

    fields = cat_data["fields"]
    extras = cat_data.get("extras", [])
    sep = cat_data.get("settings", {}).get("separator", DEFAULT_SEPARATOR)
    extras_mode = cat_data.get("settings", {}).get("extras_mode", DEFAULT_EXTRAS_MODE)

    sel = {}
    chosen = []
    
    st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)

    # Main two-column layout with divider
    left_col, divider_col, right_col = st.columns([10, 0.5, 10])

    with left_col:
        # Configuration Section
        st.markdown("**Configuration**")
        
        # Create a narrower container for dropdowns
        config_inner, config_spacer = st.columns([3, 1])
        with config_inner:
            for f in ordered_fields(fields):
                opts = fields[f]["options"]
                is_text = opts and opts[0].get("type") == "text"
                if is_text:
                    text_val = st.text_input(f, help=f"Enter {f}", placeholder=f"Enter {f}", label_visibility="collapsed")
                    sel[f] = {"code": text_val, "name": text_val}
                else:
                    if opts:
                        o = st.selectbox(
                            f, 
                            opts, 
                            format_func=lambda x, field=f: f"{field}: {x['code']} - {x['name']}", 
                            help=f"Select {f}",
                            label_visibility="collapsed"
                        )
                        sel[f] = {"code": o["code"], "name": o["name"]}
        
        st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
        
        # Extras Section
        st.markdown("**Extras**")
        
        if extras:
            sorted_extras = sorted(extras, key=lambda x: x.get("order", 999))
            
            total_extras = len(sorted_extras)
            total_pages = (total_extras - 1) // EXTRAS_PER_PAGE + 1 if total_extras > 0 else 1
            current_page = st.session_state.get("extras_page", 0)
            
            if current_page >= total_pages:
                current_page = total_pages - 1
                st.session_state["extras_page"] = current_page
            
            start_idx = current_page * EXTRAS_PER_PAGE
            end_idx = min(start_idx + EXTRAS_PER_PAGE, total_extras)
            page_extras = sorted_extras[start_idx:end_idx]
            
            if extras_mode == "Single":
                extra_options = [{"name": "None", "code": ""}] + page_extras
                extra_labels = [e["name"] for e in extra_options]
                
                selected = st.radio(
                    "Select extra:",
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
            
            # Pagination arrows at bottom
            if total_pages > 1:
                prev_col, next_col, spacer = st.columns([1, 1, 4])
                with prev_col:
                    if st.button("‹", disabled=(current_page == 0), key="prev_page"):
                        st.session_state["extras_page"] = current_page - 1
                        st.rerun()
                with next_col:
                    if st.button("›", disabled=(current_page == total_pages - 1), key="next_page"):
                        st.session_state["extras_page"] = current_page + 1
                        st.rerun()
        else:
            st.info("No extras configured")

    # Calculate SKU
    base = sep.join([sel[k]["code"] for k in ordered_fields(fields) if sel.get(k) and sel[k]["code"]])
    extras_codes = "".join([c["code"] for c in chosen])
    sku = base + (sep if base and extras_codes else "") + extras_codes
    
    config_names = [sel[k]["name"] for k in ordered_fields(fields) if sel.get(k) and sel[k]["name"]]
    extras_names = [c["name"] for c in chosen]
    all_names = config_names + extras_names
    sku_description = " - ".join(all_names) if all_names else ""

    # Vertical divider
    with divider_col:
        pass

    with right_col:
        # Right panel with card-style background using container
        with st.container():
            # Generated SKU Section
            st.markdown("**Generated SKU**")
            
            if sku:
                # SKU box - fixed width 260px to match QR box
                sku_html = f"""
                <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />
                <style>
                    * {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                    html, body {{ margin: 0; padding: 0; overflow: visible; }}
                </style>
                <div id="sku-container" onclick="copySKU()" style="
                    background: #e8f4fd;
                    border: 1px solid #c5dff0;
                    border-radius: 12px;
                    padding: 16px 20px;
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    cursor: pointer;
                    width: 260px;
                    margin: 8px;
                    box-sizing: border-box;
                ">
                    <span style="
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        font-size: 17px;
                        font-weight: 600;
                        color: #1a73e8;
                    ">{sku}</span>
                    <div id="copy-area" style="text-align: center; color: #1a73e8;">
                        <span id="copy-icon" class="material-symbols-outlined" style="font-size: 20px;">content_copy</span>
                        <p id="copy-text" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 9px; color: #5a9bd5; margin: 2px 0 0 0;">Click to Copy</p>
                    </div>
                </div>
                <script>
                function copySKU() {{
                    navigator.clipboard.writeText("{sku}").then(function() {{
                        document.getElementById('copy-icon').innerText = 'check_circle';
                        document.getElementById('copy-icon').style.color = '#34a853';
                        document.getElementById('copy-text').innerText = 'Copied!';
                        document.getElementById('copy-text').style.color = '#34a853';
                        setTimeout(function() {{
                            document.getElementById('copy-icon').innerText = 'content_copy';
                            document.getElementById('copy-icon').style.color = '#1a73e8';
                            document.getElementById('copy-text').innerText = 'Click to Copy';
                            document.getElementById('copy-text').style.color = '#5a9bd5';
                        }}, 2000);
                    }});
                }}
                </script>
                """
                st.components.v1.html(sku_html, height=95)
                
                # SKU Breakdown - with proper text wrapping
                st.markdown("**SKU Breakdown**")
                st.markdown(f"<p style='font-family: -apple-system, BlinkMacSystemFont, sans-serif; font-size: 13px; color: #555; line-height: 1.5; word-wrap: break-word; max-width: 100%;'>{sku_description}</p>", unsafe_allow_html=True)
                
                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                
                # Generated QR Code Section - same width 260px as SKU box
                st.markdown("**Generated QR Code**")
                
                qr_base64 = get_qr_code_base64(sku)
                
                # Create downloadable QR PNG data as base64
                qr_buffer = generate_qr_code(sku, size=300)
                qr_download_base64 = base64.b64encode(qr_buffer.getvalue()).decode()
                
                qr_html = f"""
                <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet" />
                <style>
                    * {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                    html, body {{ margin: 0; padding: 0; overflow: visible; }}
                </style>
                <div style="
                    background: white;
                    border: 1px solid #e0e0e0;
                    border-radius: 12px;
                    padding: 16px;
                    display: flex;
                    align-items: center;
                    gap: 16px;
                    width: 260px;
                    margin: 8px;
                    box-sizing: border-box;
                ">
                    <img src="data:image/png;base64,{qr_base64}" style="width: 70px; height: 70px;">
                    <a href="data:image/png;base64,{qr_download_base64}" 
                       download="{sku}_QR.png" 
                       style="
                           display: inline-flex;
                           align-items: center;
                           gap: 5px;
                           background: #f8f9fa;
                           border: 1px solid #e0e0e0;
                           border-radius: 6px;
                           padding: 8px 12px;
                           text-decoration: none;
                           color: #333;
                           font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                           font-size: 12px;
                           font-weight: 500;
                           cursor: pointer;
                       ">
                        <span class="material-symbols-outlined" style="font-size: 16px; color: #1a73e8;">download</span>
                        Download PNG
                    </a>
                </div>
                """
                st.components.v1.html(qr_html, height=130)
                
            else:
                st.info("Select configuration to generate SKU")
    
    # Footer
    st.markdown("<div style='margin-top: 50px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center;color:#aaa;font-size:0.8em;'>"
        "Developed by <strong>Blastline India Pvt Ltd</strong>"
        "</div>",
        unsafe_allow_html=True
    )

# ==================================================
# LOGIN
# ==================================================
def login():
    """Admin login page."""
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h3 style='text-align: center; font-family: Montserrat, Arial, sans-serif;'>Admin Login</h3>", unsafe_allow_html=True)
        st.markdown("")
        pw = st.text_input("Password", type="password")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Login", use_container_width=True):
                if pw == "admin123":
                    go("admin")
                else:
                    show_error("Invalid password. Please try again.")
        with c2:
            if st.button("Cancel", use_container_width=True):
                go("home")

# ==================================================
# ADMIN
# ==================================================
def admin():
    """Admin configuration page."""
    st.title("⚙️ Admin Settings")
    
    # Back to home button - constrained width
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
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

    # Delete Category with confirmation
    if st.session_state.get("confirm_delete_cat") == cat:
        st.warning(f"⚠️ Are you sure you want to delete category '{cat}'? This cannot be undone!")
        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            if st.button("✓ Yes, Delete", type="primary"):
                del inv[cat]
                st.session_state["confirm_delete_cat"] = None
                show_success(f"Category '{cat}' deleted successfully!")
                st.rerun()
        with col2:
            if st.button("✗ Cancel"):
                st.session_state["confirm_delete_cat"] = None
                st.rerun()
    else:
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if st.button("🗑️ Delete Category", help="Permanently delete this category"):
                st.session_state["confirm_delete_cat"] = cat
                st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["🛠️ Fields Configuration", "🎁 Extras Management", "⚙️ Category Settings", "📊 Export Matrix"])

    # ---------- FIELDS CONFIG ----------
    with tab1:
        cat_data = inv[cat]
        normalize_fields(cat_data)
        fields = cat_data["fields"]

        # Add Field - Collapsible
        with st.expander("➕ Add Field", expanded=False):
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
            # Field Order - Collapsible
            with st.expander("🔀 Field Order", expanded=False):
                df = pd.DataFrame([{"Field": k, "Order": v["order"]} for k, v in fields.items()])
                edited = st.data_editor(df, hide_index=True, use_container_width=True)
                
                if st.button("Apply Field Order"):
                    for _, r in edited.iterrows():
                        fields[r["Field"]]["order"] = int(r["Order"])
                    show_success("Field order updated successfully!")
                    st.rerun()

            # Rename / Delete Field - Collapsible
            with st.expander("✏️ Rename / Delete Field", expanded=False):
                field = st.selectbox("Select Field", ordered_fields(fields))
                new_name = st.text_input("Rename Field To", value=field)
                
                # Delete Field with confirmation
                if st.session_state.get("confirm_delete_field") == field:
                    st.warning(f"⚠️ Are you sure you want to delete field '{field}'? This cannot be undone!")
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        if st.button("✓ Yes, Delete", type="primary", key="confirm_delete_field_btn"):
                            del fields[field]
                            st.session_state["confirm_delete_field"] = None
                            show_success(f"Field '{field}' deleted successfully!")
                            st.rerun()
                    with col2:
                        if st.button("✗ Cancel", key="cancel_delete_field_btn"):
                            st.session_state["confirm_delete_field"] = None
                            st.rerun()
                else:
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
                        st.session_state["confirm_delete_field"] = field
                        st.rerun()

            # Field Options - Collapsible
            with st.expander("🛠️ Field Options", expanded=False):
                field_for_options = st.selectbox("Select Field to Edit Options", ordered_fields(fields), key="field_options_select")
                opts = fields[field_for_options]["options"]
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
                        fields[field_for_options]["options"] = edited_df.to_dict("records")
                        show_success(f"Options for '{field_for_options}' updated successfully!")
                        st.rerun()
        else:
            st.info("No fields configured yet. Add a field above to get started.")

    # ---------- EXTRAS MANAGEMENT ----------
    with tab2:
        cat_data = inv[cat]
        extras = cat_data.get("extras", [])
        
        with st.expander("🎁 Manage Extras / Add-ons", expanded=False):
            st.info(f"Extras will be displayed as a list (8 per page) in the configurator with pagination controls.")
            
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
            
            if st.button("💾 Save Extras", type="primary"):
                cat_data["extras"] = edited_extras.to_dict("records")
                show_success(f"Extras updated successfully! Total: {len(edited_extras)}")
                st.rerun()
        
        if len(extras) > 0:
            with st.expander("📋 Preview", expanded=False):
                st.write(f"**Total Extras:** {len(extras)}")
                total_pages = (len(extras) - 1) // EXTRAS_PER_PAGE + 1 if len(extras) > 0 else 1
                st.write(f"**Pages in Configurator:** {total_pages}")
                st.write(f"**Layout:** 8 items per page")

    # ---------- CATEGORY SETTINGS ----------
    with tab3:
        cat_data = inv[cat]
        settings = cat_data.get("settings", {})
        
        with st.expander("🔧 SKU Format Options", expanded=False):
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
            
            if st.button("💾 Save Settings", type="primary"):
                settings["separator"] = separator
                settings["extras_mode"] = extras_mode_setting
                cat_data["settings"] = settings
                show_success("Category settings saved successfully!")
                st.rerun()
        
        with st.expander("📋 Current Settings Preview", expanded=False):
            st.write(f"**Separator:** `{settings.get('separator', DEFAULT_SEPARATOR)}`")
            st.write(f"**Extras Mode:** {settings.get('extras_mode', DEFAULT_EXTRAS_MODE)}")
            if settings.get('extras_mode', DEFAULT_EXTRAS_MODE) == "Single":
                st.info("ℹ️ Users will see radio buttons to select one extra at a time")
            else:
                st.info("ℹ️ Users will see checkboxes to select multiple extras")

    # ---------- EXPORT MATRIX ----------
    with tab4:
        cat_data = inv[cat]
        normalize_fields(cat_data)
        
        with st.expander("📊 Full Matrix SKU Export", expanded=False):
            st.write("Generate a CSV file containing all possible SKU combinations for this category.")
            
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
                    
                    if st.button("🔄 Generate Matrix"):
                        with st.spinner("Generating SKU matrix..."):
                            matrix_df = generate_full_matrix(cat_data)
                            st.session_state["matrix_preview"] = matrix_df
                            show_success(f"Generated {len(matrix_df):,} SKU combinations!")
                            st.rerun()
                    
                    if "matrix_preview" in st.session_state:
                        st.markdown("---")
                        st.write("**Preview:**")
                        st.dataframe(st.session_state["matrix_preview"].head(50), use_container_width=True)
                        if len(st.session_state["matrix_preview"]) > 50:
                            st.caption(f"Showing first 50 of {len(st.session_state['matrix_preview']):,} rows")
                        
                        csv = st.session_state["matrix_preview"].to_csv(index=False)
                        
                        st.download_button(
                            "📥 Download CSV",
                            csv,
                            f"{cat}_full_matrix.csv",
                            "text/csv",
                            type="primary"
                        )
                else:
                    st.warning("No dropdown fields configured. Text input fields are excluded from matrix generation.")
            else:
                st.warning("No fields configured yet. Add fields in the Fields Configuration tab.")

    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("☁️ Save to Cloud", type="primary"):
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


