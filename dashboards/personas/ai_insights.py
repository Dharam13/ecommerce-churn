"""
personas/ai_insights.py
═══════════════════════
AI Insights chat panel — rendered at the bottom of every persona view.
Users can ask natural-language questions about churn data.
Features a polished contained chatbox with scrollable message area.
"""

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from config import PALETTE, RISK_COLORS, CHART_COLORS, PLOTLY_TEMPLATE
from components import section_header

# Lazy-initialised chatbot (cached so it survives reruns)
@st.cache_resource
def _get_chatbot():
    """Initialise the chatbot engine once and cache it."""
    from database import connect_db
    from src.genai.chatbot_engine import ChurnChatbot
    engine = connect_db()
    return ChurnChatbot(engine)


# ════════════════════════════════════════════════════════════
# CHAT UI STYLES
# ════════════════════════════════════════════════════════════

def _inject_chat_css():
    """Inject CSS for the polished chatbox UI."""
    st.markdown("""
    <style>
        /* ── Chat wrapper — the outer card ──────────────── */
        .chatbox-wrapper {
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06),
                        0 1px 4px rgba(0, 0, 0, 0.03);
            overflow: hidden;
            margin: 0.5rem 0 1rem;
        }

        /* ── Header bar ────────────────────────────────── */
        .chat-header {
            background: linear-gradient(135deg, #2563EB, #7C3AED);
            padding: 0.9rem 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .chat-header-icon {
            width: 38px; height: 38px;
            background: rgba(255,255,255,0.18);
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 1.15rem;
            backdrop-filter: blur(10px);
        }

        .chat-header-title {
            color: #FFF; font-size: 0.95rem; font-weight: 700;
            letter-spacing: -0.3px; margin: 0;
        }

        .chat-header-sub {
            color: rgba(255,255,255,0.7); font-size: 0.68rem;
            font-weight: 500; margin: 0.1rem 0 0;
        }

        .chat-header-dot {
            margin-left: auto; display: flex; align-items: center;
            gap: 0.35rem; font-size: 0.65rem; color: rgba(255,255,255,0.8);
            font-weight: 500;
        }

        .status-dot {
            width: 7px; height: 7px; background: #34D399;
            border-radius: 50%;
            animation: pulse-dot 2s ease-in-out infinite;
        }

        @keyframes pulse-dot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50%      { opacity: 0.6; transform: scale(1.3); }
        }

        /* ── Scrollable message area (via st.container) ── */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.chat-scroll-marker) {
            border: none !important;
            border-radius: 0 !important;
        }

        /* ── User message bubble ──────────────────────── */
        .user-bubble-row {
            display: flex; justify-content: flex-end;
            margin-bottom: 0.65rem;
        }

        .user-bubble {
            max-width: 72%;
            background: linear-gradient(135deg, #2563EB, #3B82F6);
            color: #FFF;
            padding: 0.75rem 1.1rem;
            border-radius: 14px 14px 4px 14px;
            font-size: 0.84rem; line-height: 1.5; font-weight: 500;
            box-shadow: 0 2px 8px rgba(37,99,235,0.2);
        }

        /* ── AI message bubble ────────────────────────── */
        .ai-bubble-row {
            display: flex; justify-content: flex-start;
            margin-bottom: 0.65rem; gap: 0.55rem;
        }

        .ai-avatar {
            width: 30px; height: 30px;
            background: linear-gradient(135deg, #2563EB, #7C3AED);
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.85rem; flex-shrink: 0; margin-top: 2px;
        }

        .ai-bubble {
            max-width: 82%;
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            padding: 0.85rem 1.1rem;
            border-radius: 4px 14px 14px 14px;
            font-size: 0.83rem; line-height: 1.65;
            color: #111827;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        }

        .ai-bubble strong, .ai-bubble b { color: #2563EB; }
        .ai-bubble p { margin: 0.25rem 0; }
        .ai-bubble ul, .ai-bubble ol { padding-left: 1.2rem; margin: 0.25rem 0; }
        .ai-bubble li { margin-bottom: 0.2rem; }

        /* ── Welcome panel ────────────────────────────── */
        .welcome-panel {
            text-align: center; padding: 1.75rem 1.25rem 1rem;
        }

        .welcome-panel .wi { font-size: 2.5rem; margin-bottom: 0.5rem; }

        .welcome-panel .wt {
            font-size: 1rem; font-weight: 700; color: #111827;
            margin-bottom: 0.3rem;
        }

        .welcome-panel .ws {
            font-size: 0.78rem; color: #6B7280; max-width: 400px;
            margin: 0 auto 1rem; line-height: 1.45;
        }

        .welcome-panel .wl {
            font-size: 0.6rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 1.2px; color: #9CA3AF; margin-bottom: 0.6rem;
        }

        /* ── Detail cards ─────────────────────────────── */
        .detail-card {
            background: #F9FAFB; border: 1px solid #E5E7EB;
            border-radius: 8px; padding: 0.6rem 0.9rem;
            margin: 0.45rem 0;
        }

        .detail-card-label {
            font-size: 0.62rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.8px; color: #9CA3AF; margin-bottom: 0.3rem;
        }
    </style>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# CHART RENDERER
# ════════════════════════════════════════════════════════════

def _render_chart(df: pd.DataFrame, chart_info: dict):
    """Render a Plotly chart based on chatbot chart suggestion."""
    if chart_info is None or df is None or df.empty:
        return

    x = chart_info.get("x")
    y = chart_info.get("y")
    chart_type = chart_info.get("type", "bar")

    if x not in df.columns or y not in df.columns:
        return

    try:
        if chart_type == "bar":
            fig = px.bar(df, x=x, y=y, color_discrete_sequence=CHART_COLORS, template=PLOTLY_TEMPLATE)
        elif chart_type == "line":
            fig = px.line(df, x=x, y=y, color_discrete_sequence=CHART_COLORS, template=PLOTLY_TEMPLATE, markers=True)
        elif chart_type == "pie":
            fig = px.pie(df, names=x, values=y, color_discrete_sequence=CHART_COLORS, template=PLOTLY_TEMPLATE, hole=0.45)
        elif chart_type == "histogram":
            fig = px.histogram(df, x=x, color_discrete_sequence=CHART_COLORS, template=PLOTLY_TEMPLATE)
        else:
            fig = px.bar(df, x=x, y=y, color_discrete_sequence=CHART_COLORS, template=PLOTLY_TEMPLATE)

        fig.update_layout(
            margin=dict(t=30, b=30, l=30, r=30),
            height=280,
            font=dict(family="Inter, sans-serif", size=11),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(gridcolor="#F3F4F6"),
            yaxis=dict(gridcolor="#F3F4F6"),
        )
        if chart_type == "bar":
            fig.update_traces(marker_cornerradius=6)

        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════
# SUGGESTION CHIPS
# ════════════════════════════════════════════════════════════

SUGGESTED_QUESTIONS = [
    {"icon": "📉", "text": "How many customers churned?"},
    {"icon": "🏙️", "text": "What is the churn rate by city tier?"},
    {"icon": "⚠️", "text": "Top 10 high risk customers"},
    {"icon": "💰", "text": "Avg cashback for churned vs retained"},
    {"icon": "📦", "text": "Which product category has most churn?"},
    {"icon": "👥", "text": "Churn rate by gender and marital status"},
]


# ════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ════════════════════════════════════════════════════════════

def render_ai_insights():
    """Render the AI Insights chat panel (placed at bottom of every persona)."""

    _inject_chat_css()

    # ── Session state ─────────────────────────────────────
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    if "chatbot_ready" not in st.session_state:
        st.session_state.chatbot_ready = False

    # ── Chatbot init ──────────────────────────────────────
    try:
        chatbot = _get_chatbot()
        st.session_state.chatbot_ready = True
    except Exception as e:
        st.error(
            f"**Chatbot Initialization Error**\n\n"
            f"Could not start the AI engine:\n\n"
            f"```\n{e}\n```\n\n"
            f"Make sure `GEMINI_API_KEY` is set in `.env` and "
            f"`google-genai` is installed."
        )
        return

    # ════════════════════════════════════════════════════════
    # CHAT HEADER (static HTML, always visible)
    # ════════════════════════════════════════════════════════

    st.markdown("""
    <div class="chatbox-wrapper">
        <div class="chat-header">
            <div class="chat-header-icon">🤖</div>
            <div>
                <div class="chat-header-title">ChurnGuard AI</div>
                <div class="chat-header-sub">Retention Strategy Assistant</div>
            </div>
            <div class="chat-header-dot">
                <div class="status-dot"></div>
                Online
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # SCROLLABLE CHAT AREA (fixed height container)
    # ════════════════════════════════════════════════════════

    chat_area = st.container(height=420, border=False)

    with chat_area:
        # invisible marker for CSS targeting
        st.markdown('<div class="chat-scroll-marker" style="display:none;"></div>', unsafe_allow_html=True)

        # ── Welcome state ─────────────────────────────────
        if not st.session_state.chat_messages:
            st.markdown("""
            <div class="welcome-panel">
                <div class="wi">🧠</div>
                <div class="wt">Ask me anything about customer churn</div>
                <div class="ws">
                    I analyse your data, generate insights, and provide
                    actionable retention strategies to reduce churn.
                </div>
                <div class="wl">Suggested Questions</div>
            </div>
            """, unsafe_allow_html=True)

            # Suggestion chips as buttons
            chip_cols = st.columns(2)
            for i, q in enumerate(SUGGESTED_QUESTIONS):
                with chip_cols[i % 2]:
                    if st.button(
                        f"{q['icon']}  {q['text']}",
                        key=f"suggestion_{i}",
                        use_container_width=True,
                    ):
                        st.session_state.pending_question = q["text"]
                        st.rerun()

        # ── Chat history ──────────────────────────────────
        for idx, msg in enumerate(st.session_state.chat_messages):
            if msg["role"] == "user":
                st.markdown(f"""
                <div class="user-bubble-row">
                    <div class="user-bubble">{msg["content"]}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # AI response — use native st.markdown for rich formatting
                st.markdown("""
                <div class="ai-bubble-row">
                    <div class="ai-avatar">🤖</div>
                    <div class="ai-bubble">
                """, unsafe_allow_html=True)

                st.markdown(msg["content"])

                st.markdown("</div></div>", unsafe_allow_html=True)

                # Data, chart, SQL toggles
                _render_response_details(msg, f"h_{idx}")

    # ════════════════════════════════════════════════════════
    # CHAT INPUT (always at the bottom, outside scroll area)
    # ════════════════════════════════════════════════════════

    pending_q = st.session_state.pop("pending_question", None)
    user_input = st.chat_input(
        "Ask about churn, customers, retention strategies...",
        key="ai_chat_input",
    )

    question = pending_q or user_input

    if question:
        # Add user message
        st.session_state.chat_messages.append({
            "role": "user",
            "content": question,
        })

        # Get AI response
        with st.spinner("🔍 Analysing..."):
            response = chatbot.ask(question)

        # Save assistant message
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": response["summary"],
            "data": response.get("data"),
            "chart": response.get("chart"),
            "sql": response.get("sql"),
        })

        st.rerun()

    # ── Clear chat ────────────────────────────────────────
    if st.session_state.chat_messages:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("🗑️ Clear conversation", use_container_width=True, key="clear_chat"):
                st.session_state.chat_messages = []
                chatbot.clear_history()
                st.rerun()


# ════════════════════════════════════════════════════════════
# RESPONSE DETAIL CARDS (data table, chart, SQL)
# ════════════════════════════════════════════════════════════

def _render_response_details(msg: dict, key_prefix: str):
    """Render data table, chart, and SQL as togglable sections."""
    has_data = msg.get("data") is not None and not msg["data"].empty
    has_sql = bool(msg.get("sql"))
    has_chart = msg.get("chart") is not None and msg.get("data") is not None

    if not has_data and not has_sql and not has_chart:
        return

    # Chart
    if has_chart:
        _render_chart(msg["data"], msg["chart"])

    # Toggle buttons
    if has_data or has_sql:
        n_cols = (1 if has_data else 0) + (1 if has_sql else 0)
        btn_cols = st.columns(n_cols)
        col_idx = 0

        if has_data:
            with btn_cols[col_idx]:
                data_key = f"sd_{key_prefix}"
                lbl = "📊 Hide Data" if st.session_state.get(data_key) else "📊 View Data"
                if st.button(lbl, key=f"bd_{key_prefix}", use_container_width=True):
                    st.session_state[data_key] = not st.session_state.get(data_key, False)
                    st.rerun()
            col_idx += 1

        if has_sql:
            with btn_cols[col_idx]:
                sql_key = f"ss_{key_prefix}"
                lbl = "🔍 Hide SQL" if st.session_state.get(sql_key) else "🔍 View SQL"
                if st.button(lbl, key=f"bs_{key_prefix}", use_container_width=True):
                    st.session_state[sql_key] = not st.session_state.get(sql_key, False)
                    st.rerun()

    # Data table
    if has_data and st.session_state.get(f"sd_{key_prefix}"):
        st.markdown(f"""
        <div class="detail-card">
            <div class="detail-card-label">📊 Query Results — {len(msg["data"])} row(s)</div>
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(
            msg["data"],
            use_container_width=True,
            height=min(len(msg["data"]) * 38 + 50, 300),
        )

    # SQL
    if has_sql and st.session_state.get(f"ss_{key_prefix}"):
        st.markdown("""
        <div class="detail-card">
            <div class="detail-card-label">🔍 Generated SQL</div>
        </div>
        """, unsafe_allow_html=True)
        st.code(msg["sql"], language="sql")
