import streamlit as st
import pandas as pd
import json
import itertools
import math

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(page_title="Blastline SKU Configurator", layout="wide")

# =====================================================
# SESSION INIT
# =====================================================
if "sku_data" not in st.session_state:
    st.session_state["sku_data"] = {
        "inventory": {
            "Blast Machine": {
                "settings": {
                    "separator": "-",
                    "extras_mode": "Single"
                },
                "fields": {
                    "Brand": {
                        "order": 1,
                        "options": [
                            {"code": "BL", "name": "Blastline", "order": 1}
                        ]
                    },
                    "Capacity": {
                        "order": 2,
                        "options": []
                    }
                },
                "extras": [
                    {"name": "Moisture Separator", "code": "01", "order": 1},
                    {"name": "PG + RV", "code": "02", "order": 2}
                ]
            }
        }
    }

if "page" not in st.session_state:
    st.session_state["page"] = "home"

if "extras_page" not in st.session_state:
    st.session_state["extras_page"] = 0

# =====================================================
# HELPERS
# =====================================================
def ordered_fields(fields):
    return sorted(fields.keys(), key=lambda k: fields[k]["order"])

def option_label(o):
    return f"{o['code']} : {o['name']}"

def sku_box(text):
    return f"""
    <div onclick="copySKU()" style="
        background:#111;
        border:2px solid #4CAF50;
        border-radius:16px;
        padding:28px;
        cursor:pointer;
        text-align:center;">
        <div style="
            font-size:46px;
            font-family:monospace;
            font-weight:700;
            color:#4CAF50;">{text}</div>
        <div id="msg" style="color:#aaa;margin-top:6px;">
            📋 Click to copy
        </div>
    </div>
    <script>
    function copySKU(){{
        navigator.clipboard.writeText("{text}");
        let m=document.getElementById("msg");
        m.innerText="✅ Copied";
        m.style.color="#4CAF50";
        setTimeout(()=>{{
            m.innerText="📋 Click to copy";
            m.style.color="#aaa";
        }},2000);
    }}
    </script>
    """

def generate_matrix(data):
    rows = []

    for cat_name, cat in data["inventory"].items():
        sep = cat["settings"]["separator"]
        mode = cat["settings"]["extras_mode"]
        fields = cat["fields"]
        extras = cat["extras"]

        field_lists = []
        for f in ordered_fields(fields):
            opts = fields[f]["options"]
            if not opts:
                field_lists.append([{"code": ""}])
            else:
                field_lists.append(opts)

        base_combos = itertools.product(*field_lists)

        if mode == "Single":
            extra_sets = [""] + [e["code"] for e in extras]
        else:
            valid = [e["code"] for e in extras]
            extra_sets = [""]
            for r in range(1, len(valid) + 1):
                for c in itertools.combinations(valid, r):
                    extra_sets.append("".join(c))

        for combo in base_combos:
            base = sep.join([c["code"] for c in combo if c["code"]])
            for ex in extra_sets:
                sku = base + (sep if base and ex else "") + ex
                rows.append({"Category": cat_name, "SKU": sku})

    return pd.DataFrame(rows)

# =====================================================
# HOME
# =====================================================
def home():
    st.title("Blastline SKU Configurator")
    st.markdown("---")
        with st.sidebar:
        st.markdown("### Navigation")
        if st.button("⚙️ Admin Settings", use_container_width=True):
            st.session_state["page"] = "admin"
            st.experimental_rerun()


    inventory = st.session_state["sku_data"]["inventory"]
    category = st.selectbox("Product Category", list(inventory.keys()))
    cat = inventory[category]

    fields = cat["fields"]
    extras = sorted(cat["extras"], key=lambda x: x["order"])
    sep = cat["settings"]["separator"]
    mode = cat["settings"]["extras_mode"]

    col1, col2 = st.columns(2)
    selections = {}

    # ---------- CONFIGURATION ----------
    with col1:
        st.subheader("Configuration")

        for f in ordered_fields(fields):
            opts = fields[f]["options"]

            if not opts:
                st.selectbox(f, ["No options available"], disabled=True)
                selections[f] = ""
            else:
                sel = st.selectbox(f, opts, format_func=option_label)
                selections[f] = sel["code"]

    # ---------- EXTRAS ----------
    with col2:
        st.subheader("Extras / Add-ons")

        ITEMS = 12
        page = st.session_state["extras_page"]
        total_pages = max(1, math.ceil(len(extras) / ITEMS))
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
                st.experimental_rerun()
            c2.markdown(f"<center>{page+1} / {total_pages}</center>", unsafe_allow_html=True)
            if c3.button("▶", disabled=page == total_pages - 1):
                st.session_state["extras_page"] += 1
                st.experimental_rerun()

        st.markdown("---")
        base = sep.join([selections[k] for k in ordered_fields(fields) if selections[k]])
        sku = base + (sep if base and selected else "") + "".join(selected)
        st.components.v1.html(sku_box(sku), height=190)

# =====================================================
# ADMIN
# =====================================================
def admin():
    st.title("Admin Settings")

    data = st.session_state["sku_data"]
    inv = data["inventory"]

    tabs = st.tabs(["Configuration", "Data I/O"])

    # ---------- CONFIG ----------
    with tabs[0]:
        category = st.selectbox("Product Category", list(inv.keys()))
        cat = inv[category]

        st.markdown("### Fields")
        field_df = pd.DataFrame(
            [{"Field": k, "Order": v["order"]} for k, v in cat["fields"].items()]
        )

        field_df = st.data_editor(field_df, num_rows="dynamic", hide_index=True)

        if st.button("Apply Field Changes"):
            new_fields = {}
            for _, r in field_df.iterrows():
                old = cat["fields"].get(r["Field"], {"options": []})
                new_fields[r["Field"]] = {
                    "order": int(r["Order"]),
                    "options": old["options"]
                }
            cat["fields"] = new_fields

        st.markdown("### Field Options")
        fsel = st.selectbox("Select Field", list(cat["fields"].keys()))
        opts_df = st.data_editor(
            pd.DataFrame(cat["fields"][fsel]["options"]),
            num_rows="dynamic",
            hide_index=True
        )
        if st.button("Update Options"):
            cat["fields"][fsel]["options"] = opts_df.to_dict("records")

        st.markdown("### Extras")
        mode = st.radio("Extras Selection Mode", ["Single", "Multiple"])
        cat["settings"]["extras_mode"] = mode

        extras_df = st.data_editor(
            pd.DataFrame(cat["extras"]),
            num_rows="dynamic",
            hide_index=True
        )
        if st.button("Update Extras"):
            cat["extras"] = extras_df.sort_values("order").to_dict("records")

    # ---------- DATA I/O ----------
    with tabs[1]:
        st.download_button(
            "Export JSON",
            json.dumps(data, indent=2),
            "sku_config.json",
            "application/json"
        )

        upload = st.file_uploader("Import JSON", type=["json"])
        if upload and st.button("Load JSON"):
            st.session_state["sku_data"] = json.load(upload)
            st.experimental_rerun()

        if st.button("Generate Full Matrix CSV"):
            df = generate_matrix(data)
            st.download_button(
                "Download CSV",
                df.to_csv(index=False),
                "sku_matrix.csv",
                "text/csv"
            )

# =====================================================
# ROUTER
# =====================================================
if st.session_state["page"] == "home":
    home()
elif st.session_state["page"] == "admin":
    admin()

