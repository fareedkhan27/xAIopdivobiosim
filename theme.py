"""Theme CSS definitions for the Opdivo Biosimilar Surveillance dashboard.

Two modes:
  - presentation  (light, high-contrast, screen-share friendly)
  - dark          (updated dark theme with accessibility fixes)
"""

# ═══════════════════════════════════════════════════════════════════════════════
# PRESENTATION MODE — Light, executive-friendly, screen-share optimised
# ═══════════════════════════════════════════════════════════════════════════════
_PRESENTATION_CSS = """
<style>
/* ── RESET & BASE ── */
html, body {
    background-color: #F8F9FA !important;
    color: #1A202C !important;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
.stApp, .appview-container, .main {
    background-color: #F8F9FA !important;
    color: #1A202C !important;
}

[data-testid="stApp"] p,
[data-testid="stApp"] span,
[data-testid="stApp"] div,
[data-testid="stApp"] li,
[data-testid="stApp"] td,
[data-testid="stApp"] th,
[data-testid="stApp"] label {
    color: #1A202C !important;
}

[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] a {
    color: #1A202C !important;
}

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
    color: #4A5568 !important;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-left: clamp(0.75rem, 3vw, 3rem) !important;
    padding-right: clamp(0.75rem, 3vw, 3rem) !important;
    max-width: 100% !important;
    background-color: #F8F9FA !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {
    background-color: #FFFFFF !important;
    border-right: 1px solid #E2E8F0;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label {
    color: #1A202C !important;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #1A202C !important; }
[data-testid="stSidebarNav"] span { color: #1A202C !important; }

/* ── Form labels ── */
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label,
[data-testid="stTextInput"] label,
[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label,
.stSelectbox label, .stMultiSelect label {
    color: #4A5568 !important;
    font-weight: 500;
}

/* ── Dropdowns ── */
[data-baseweb="select"] [data-testid="stMarkdownContainer"],
[data-baseweb="select"] span,
[data-baseweb="select"] div,
[data-baseweb="tag"] span {
    color: #1A202C !important;
    background-color: #FFFFFF !important;
}
[data-baseweb="menu"] { background-color: #FFFFFF !important; }
[data-baseweb="menu"] li { color: #1A202C !important; background-color: #FFFFFF !important; }
[data-baseweb="menu"] li:hover { background-color: #EDF2F7 !important; }

/* ── Inputs ── */
[data-baseweb="input"] input,
[data-baseweb="input"] textarea,
[data-testid="stTextInput"] input {
    background-color: #FFFFFF !important;
    color: #1A202C !important;
    border-color: #CBD5E0 !important;
    font-size: 16px !important;
    min-height: 44px !important;
}

/* ── Alerts ── */
[data-testid="stAlert"],
[data-testid="stAlert"] p,
[data-testid="stAlert"] span,
[data-testid="stAlert"] div {
    color: #1A202C !important;
}
[data-testid="stAlert"][kind="info"],
.stAlert[data-baseweb="notification"][kind="info"] {
    background-color: #EBF8FF !important;
    border-color: #3182CE !important;
}

/* ── KPI cards ── */
.kpi-card {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: clamp(16px, 3vw, 24px) clamp(14px, 3vw, 24px);
    text-align: center;
    min-width: 0;
    word-break: break-word;
    color: #1A202C !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.kpi-value {
    font-size: clamp(1.8rem, 4vw, 2.8rem) !important;
    font-weight: 700 !important;
    color: #0F766E !important;
    line-height: 1.2;
}
.kpi-label {
    font-size: clamp(0.78rem, 2vw, 0.9rem) !important;
    color: #4A5568 !important;
    margin-top: 4px;
    font-weight: 500;
}

/* ── Update cards ── */
.update-card {
    background: #FFFFFF !important;
    border-left: 4px solid #0F766E;
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 12px;
    word-break: break-word;
    color: #1A202C !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.update-card .source { font-size: 0.82rem; color: #4A5568 !important; font-weight: 500; }
.update-card .title  { font-weight: 600; margin: 4px 0; color: #1A202C !important; }
.update-card .body   { font-size: 0.95rem; color: #4A5568 !important; line-height: 1.5; }

/* ── Social post cards ── */
.post-card {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
    word-break: break-word;
    color: #1A202C !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.post-card .user  { font-weight: 600; color: #1E40AF !important; }
.post-card .time  { font-size: 0.82rem; color: #718096 !important; margin-left: 8px; }
.post-card .text  { margin-top: 8px; font-size: 0.95rem; color: #1A202C !important; line-height: 1.5; }
.post-card .platform-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #F7FAFC;
    border: 1px solid #E2E8F0;
    color: #4A5568 !important;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.01em;
}
.post-card .post-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #1E40AF !important;
    font-size: 0.88rem;
    font-weight: 600;
    text-decoration: none;
}
.post-card .post-link:hover { color: #1E3A8A !important; text-decoration: underline; }

/* ── Badges ── */
.badge-pos { background:#D1FAE5 !important; color:#065F46 !important; padding:3px 12px; border-radius:99px; font-size:0.82rem; white-space:nowrap; font-weight:600; }
.badge-neu { background:#FEF3C7 !important; color:#92400E !important; padding:3px 12px; border-radius:99px; font-size:0.82rem; white-space:nowrap; font-weight:600; }
.badge-neg { background:#FEE2E2 !important; color:#991B1B !important; padding:3px 12px; border-radius:99px; font-size:0.82rem; white-space:nowrap; font-weight:600; }

/* ── Headings ── */
h1, h2, h3, h4, h5, h6 {
    color: #1A202C !important;
}
h1 { font-size: clamp(1.6rem, 5vw, 2.2rem) !important; font-weight: 600 !important; }
h2 { font-size: clamp(1.3rem, 4vw, 1.7rem) !important; font-weight: 600 !important; }
h3 { font-size: clamp(1.1rem, 3vw, 1.35rem) !important; font-weight: 600 !important; }

/* ── Buttons ── */
.stButton > button {
    background: #0F766E !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
    min-height: 44px !important;
    font-size: clamp(0.9rem, 2.5vw, 1rem) !important;
}
.stButton > button:hover { background: #115E59 !important; }

/* ── Dataframe ── */
.stDataFrame {
    border-radius: 8px;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
}
.stDataFrame table { background-color: #FFFFFF !important; }
.stDataFrame th {
    background-color: #F7FAFC !important;
    color: #1A202C !important;
    border-bottom: 2px solid #E2E8F0 !important;
    font-weight: 600;
}
.stDataFrame td {
    background-color: #FFFFFF !important;
    color: #1A202C !important;
    border-color: #E2E8F0 !important;
}
[data-testid="stDataFrame"] * { color: #1A202C !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #FFFFFF !important;
    border-radius: 8px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    flex-wrap: nowrap;
    border-bottom: 2px solid #E2E8F0;
}
.stTabs [data-baseweb="tab"] {
    color: #718096 !important;
    white-space: nowrap;
    min-width: fit-content;
    padding: 10px 14px !important;
    font-size: clamp(0.85rem, 2vw, 0.95rem) !important;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    color: #0F766E !important;
    border-bottom-color: #0F766E !important;
    font-weight: 600;
}

/* ── Plotly charts ── */
.js-plotly-plot, .plotly { max-width: 100% !important; }

/* ── Progress banner grid ── */
.banner-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

/* ── MOBILE ── */
@media (max-width: 640px) {
    .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 0.75rem !important;
    }
    .kpi-value { font-size: 1.6rem !important; }
    .kpi-label { font-size: 0.78rem !important; }
    .kpi-card  { padding: 12px 10px; border-radius: 8px; }
    .banner-grid { grid-template-columns: 1fr !important; }
    .stSelectbox, .stRadio { width: 100% !important; }
    .js-plotly-plot .main-svg { width: 100% !important; }
    p, li, td, th { font-size: 0.95rem !important; }
}

/* ── SMALL TABLET ── */
@media (min-width: 641px) and (max-width: 900px) {
    .kpi-value { font-size: 2rem !important; }
    .block-container {
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
    }
}
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# DARK MODE — Updated for accessibility (high contrast, no thin fonts)
# ═══════════════════════════════════════════════════════════════════════════════
_DARK_CSS = """
<style>
/* ── RESET & BASE ── */
html, body {
    background-color: #0F172A !important;
    color: #F1F5F9 !important;
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
.stApp, .appview-container, .main {
    background-color: #0F172A !important;
    color: #F1F5F9 !important;
}

[data-testid="stApp"] p,
[data-testid="stApp"] span,
[data-testid="stApp"] div,
[data-testid="stApp"] li,
[data-testid="stApp"] td,
[data-testid="stApp"] th,
[data-testid="stApp"] label {
    color: #F1F5F9 !important;
}

[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] a {
    color: #F1F5F9 !important;
}

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
    color: #94A3B8 !important;
}

.block-container {
    padding-top: 1.5rem !important;
    padding-left: clamp(0.75rem, 3vw, 3rem) !important;
    padding-right: clamp(0.75rem, 3vw, 3rem) !important;
    max-width: 100% !important;
    background-color: #0F172A !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {
    background-color: #1E293B !important;
    border-right: 1px solid #334155;
}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label {
    color: #F1F5F9 !important;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #F1F5F9 !important; }
[data-testid="stSidebarNav"] span { color: #F1F5F9 !important; }

/* ── Form labels ── */
[data-testid="stSelectbox"] label,
[data-testid="stMultiSelect"] label,
[data-testid="stTextInput"] label,
[data-testid="stRadio"] label,
[data-testid="stCheckbox"] label,
.stSelectbox label, .stMultiSelect label {
    color: #CBD5E1 !important;
    font-weight: 500;
}

/* ── Dropdowns ── */
[data-baseweb="select"] [data-testid="stMarkdownContainer"],
[data-baseweb="select"] span,
[data-baseweb="select"] div,
[data-baseweb="tag"] span {
    color: #F1F5F9 !important;
    background-color: #1E293B !important;
}
[data-baseweb="menu"] { background-color: #1E293B !important; }
[data-baseweb="menu"] li { color: #F1F5F9 !important; background-color: #1E293B !important; }
[data-baseweb="menu"] li:hover { background-color: #334155 !important; }

/* ── Inputs ── */
[data-baseweb="input"] input,
[data-baseweb="input"] textarea,
[data-testid="stTextInput"] input {
    background-color: #1E293B !important;
    color: #F1F5F9 !important;
    border-color: #475569 !important;
    font-size: 16px !important;
    min-height: 44px !important;
}

/* ── Alerts ── */
[data-testid="stAlert"],
[data-testid="stAlert"] p,
[data-testid="stAlert"] span,
[data-testid="stAlert"] div {
    color: #F1F5F9 !important;
}
[data-testid="stAlert"][kind="info"],
.stAlert[data-baseweb="notification"][kind="info"] {
    background-color: #1E3A5F !important;
    border-color: #3B82F6 !important;
}

/* ── KPI cards ── */
.kpi-card {
    background: #1E293B !important;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: clamp(14px, 3vw, 22px) clamp(12px, 3vw, 24px);
    text-align: center;
    min-width: 0;
    word-break: break-word;
    color: #F1F5F9 !important;
}
.kpi-value {
    font-size: clamp(1.6rem, 4vw, 2.4rem) !important;
    font-weight: 700 !important;
    color: #2DD4BF !important;
    line-height: 1.2;
}
.kpi-label {
    font-size: clamp(0.78rem, 2vw, 0.88rem) !important;
    color: #94A3B8 !important;
    margin-top: 4px;
    font-weight: 500;
}

/* ── Update cards ── */
.update-card {
    background: #1E293B !important;
    border-left: 4px solid #2DD4BF;
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 12px;
    word-break: break-word;
    color: #F1F5F9 !important;
}
.update-card .source { font-size: 0.82rem; color: #94A3B8 !important; font-weight: 500; }
.update-card .title  { font-weight: 600; margin: 4px 0; color: #F8FAFC !important; }
.update-card .body   { font-size: 0.95rem; color: #CBD5E1 !important; line-height: 1.5; }

/* ── Social post cards ── */
.post-card {
    background: #1E293B !important;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 10px;
    word-break: break-word;
    color: #F1F5F9 !important;
}
.post-card .user  { font-weight: 600; color: #60A5FA !important; }
.post-card .time  { font-size: 0.82rem; color: #64748B !important; margin-left: 8px; }
.post-card .text  { margin-top: 8px; font-size: 0.95rem; color: #F1F5F9 !important; line-height: 1.5; }
.post-card .platform-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #0F172A;
    border: 1px solid #334155;
    color: #CBD5E1 !important;
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.01em;
}
.post-card .post-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #93C5FD !important;
    font-size: 0.88rem;
    font-weight: 600;
    text-decoration: none;
}
.post-card .post-link:hover { color: #BFDBFE !important; text-decoration: underline; }

/* ── Badges ── */
.badge-pos { background:#064E3B !important; color:#6EE7B7 !important; padding:3px 12px; border-radius:99px; font-size:0.82rem; white-space:nowrap; font-weight:600; }
.badge-neu { background:#451A03 !important; color:#FDE68A !important; padding:3px 12px; border-radius:99px; font-size:0.82rem; white-space:nowrap; font-weight:600; }
.badge-neg { background:#7F1D1D !important; color:#FCA5A5 !important; padding:3px 12px; border-radius:99px; font-size:0.82rem; white-space:nowrap; font-weight:600; }

/* ── Headings ── */
h1, h2, h3, h4, h5, h6 {
    color: #F8FAFC !important;
}
h1 { font-size: clamp(1.5rem, 5vw, 2.1rem) !important; font-weight: 600 !important; }
h2 { font-size: clamp(1.2rem, 4vw, 1.6rem) !important; font-weight: 600 !important; }
h3 { font-size: clamp(1.05rem, 3vw, 1.3rem) !important; font-weight: 600 !important; }

/* ── Buttons ── */
.stButton > button {
    background: #2DD4BF !important;
    color: #0F172A !important;
    font-weight: 600 !important;
    border-radius: 8px !important;
    border: none !important;
    min-height: 44px !important;
    font-size: clamp(0.9rem, 2.5vw, 1rem) !important;
}
.stButton > button:hover { background: #14B8A6 !important; }

/* ── Dataframe ── */
.stDataFrame {
    border-radius: 8px;
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
}
.stDataFrame table { background-color: #1E293B !important; }
.stDataFrame th {
    background-color: #0F172A !important;
    color: #F8FAFC !important;
    border-bottom: 2px solid #334155 !important;
    font-weight: 600;
}
.stDataFrame td {
    background-color: #1E293B !important;
    color: #F1F5F9 !important;
    border-color: #334155 !important;
}
[data-testid="stDataFrame"] * { color: #F1F5F9 !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #1E293B !important;
    border-radius: 8px;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    flex-wrap: nowrap;
}
.stTabs [data-baseweb="tab"] {
    color: #94A3B8 !important;
    white-space: nowrap;
    min-width: fit-content;
    padding: 10px 14px !important;
    font-size: clamp(0.85rem, 2vw, 0.95rem) !important;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    color: #2DD4BF !important;
    border-bottom-color: #2DD4BF !important;
    font-weight: 600;
}

/* ── Plotly charts ── */
.js-plotly-plot, .plotly { max-width: 100% !important; }

/* ── Progress banner grid ── */
.banner-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

/* ── MOBILE ── */
@media (max-width: 640px) {
    .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 0.75rem !important;
    }
    .kpi-value { font-size: 1.6rem !important; }
    .kpi-label { font-size: 0.78rem !important; }
    .kpi-card  { padding: 12px 10px; border-radius: 8px; }
    .banner-grid { grid-template-columns: 1fr !important; }
    .stSelectbox, .stRadio { width: 100% !important; }
    .js-plotly-plot .main-svg { width: 100% !important; }
    p, li, td, th { font-size: 0.95rem !important; }
}

/* ── SMALL TABLET ── */
@media (min-width: 641px) and (max-width: 900px) {
    .kpi-value { font-size: 2rem !important; }
    .block-container {
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
    }
}
</style>
"""
