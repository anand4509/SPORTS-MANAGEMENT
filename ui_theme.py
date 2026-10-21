"""Customizable visual theme helpers for the Sports Coordinator Streamlit app."""
import streamlit as st

THEMES = {
    "Light": {"background":"#F4F7FB","surface":"#FFFFFF","sidebar":"#14243A","text":"#172033","muted":"#64748B","accent":"#1769AA","border":"#E2E8F0"},
    "Dark": {"background":"#0B1220","surface":"#111C2E","sidebar":"#080E19","text":"#E5EDF7","muted":"#9AAAC0","accent":"#60A5FA","border":"#29364A"},
    "Stadium": {"background":"#101820","surface":"#182630","sidebar":"#09131A","text":"#F3F7F4","muted":"#B3C2BC","accent":"#F5B700","border":"#30434A"},
    "Emerald": {"background":"#F1F8F4","surface":"#FFFFFF","sidebar":"#103B32","text":"#16352E","muted":"#5F7D73","accent":"#16845B","border":"#D5E8DE"},
}

def render_theme_controls():
    """Show preset themes and optional custom color pickers in the sidebar."""
    if "sc_theme_name" not in st.session_state:
        st.session_state.sc_theme_name = "Light"
    if "sc_use_custom_colors" not in st.session_state:
        st.session_state.sc_use_custom_colors = False
    if "sc_picker_preset" not in st.session_state:
        st.session_state.sc_picker_preset = st.session_state.sc_theme_name

    with st.sidebar:
        with st.expander("🎨 Customize appearance", expanded=False):
            selected = st.selectbox("Preset theme", list(THEMES), key="sc_theme_name")
            preset = dict(THEMES[selected])

            # When the preset changes, reset the color picker values to that preset.
            if st.session_state.sc_picker_preset != selected:
                for short, color_key in [
                    ("bg", "background"), ("surface", "surface"),
                    ("sidebar", "sidebar"), ("text", "text"),
                    ("muted", "muted"), ("accent", "accent"), ("border", "border")
                ]:
                    st.session_state[f"sc_{short}_picker"] = preset[color_key]
                st.session_state.sc_picker_preset = selected

            use_custom = st.checkbox(
                "Use custom colors",
                key="sc_use_custom_colors",
                help="Enable this to choose your own colors."
            )
            if not use_custom:
                return preset

            st.caption("Choose your own colors")
            return {
                "background": st.color_picker("Page background", preset["background"], key="sc_bg_picker"),
                "surface": st.color_picker("Cards and panels", preset["surface"], key="sc_surface_picker"),
                "sidebar": st.color_picker("Sidebar", preset["sidebar"], key="sc_sidebar_picker"),
                "text": st.color_picker("Main text", preset["text"], key="sc_text_picker"),
                "muted": st.color_picker("Secondary text", preset["muted"], key="sc_muted_picker"),
                "accent": st.color_picker("Accent / buttons", preset["accent"], key="sc_accent_picker"),
                "border": st.color_picker("Borders", preset["border"], key="sc_border_picker"),
            }

def apply_theme(colors):
    """Apply the selected palette using CSS."""
    bg, surface, sidebar = colors["background"], colors["surface"], colors["sidebar"]
    fg, muted, accent, border = colors["text"], colors["muted"], colors["accent"], colors["border"]
    st.markdown(f"""
    <style>
    :root {{
      --sc-bg:{bg}; --sc-surface:{surface}; --sc-sidebar:{sidebar};
      --sc-text:{fg}; --sc-muted:{muted}; --sc-accent:{accent}; --sc-border:{border};
    }}
    .stApp {{ background:var(--sc-bg); color:var(--sc-text); }}
    [data-testid="stHeader"] {{ background:transparent; }}
    .block-container {{ max-width:1500px; padding-top:1.5rem; padding-bottom:2.5rem; }}
    section[data-testid="stSidebar"] {{ background:var(--sc-sidebar); border-right:1px solid var(--sc-border); }}
    section[data-testid="stSidebar"] * {{ color:#F8FAFC; }}
    h1,h2,h3,h4 {{ color:var(--sc-text); letter-spacing:-.025em; }}
    [data-testid="stCaptionContainer"] {{ color:var(--sc-muted); }}
    div[data-testid="stMetric"] {{
      background:var(--sc-surface); border:1px solid var(--sc-border);
      border-radius:16px; padding:1.1rem 1.2rem;
      box-shadow:0 5px 18px rgba(15,23,42,.06); min-height:118px;
    }}
    div[data-testid="stMetricLabel"] {{ color:var(--sc-muted); font-weight:600; }}
    div[data-testid="stMetricValue"] {{ color:var(--sc-text); font-weight:750; }}
    div[data-testid="stForm"],div[data-testid="stVerticalBlockBorderWrapper"] {{
      background:var(--sc-surface); border:1px solid var(--sc-border); border-radius:14px;
    }}
    .stButton>button,.stDownloadButton>button,button[kind="primary"] {{
      background:var(--sc-accent); color:#FFFFFF; border:1px solid var(--sc-accent);
      border-radius:10px; font-weight:650; min-height:2.55rem;
      transition:filter 120ms ease,transform 120ms ease;
    }}
    .stButton>button:hover,.stDownloadButton>button:hover,button[kind="primary"]:hover {{
      filter:brightness(.92); color:#FFFFFF; border-color:var(--sc-accent); transform:translateY(-1px);
    }}
    input,textarea,div[data-baseweb="select"]>div {{ border-radius:9px !important; }}
    div[data-testid="stDataFrame"],div[data-testid="stTable"] {{
      border:1px solid var(--sc-border); border-radius:12px; overflow:hidden;
    }}
    hr {{ border-color:var(--sc-border); }}
    div[data-testid="stAlert"] {{ border-radius:12px; }}
    </style>
    """, unsafe_allow_html=True)
