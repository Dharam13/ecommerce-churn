"""
chatbot_engine.py
═════════════════
Core AI engine for the Churn Insights chatbot.

Pipeline:
    1. User asks a natural-language question
    2. Gemini generates a safe SELECT query using Gold/Silver schema
    3. Query executes against PostgreSQL (read-only)
    4. Gemini summarises the results in plain English
    5. Returns structured response with summary, data, SQL, chart suggestion
"""

import os
import re
import logging
from datetime import date

import pandas as pd
from sqlalchemy import text
from google import genai

from src.genai.schema_context import (
    SCHEMA_CONTEXT,
    SQL_GENERATION_PROMPT,
    SUMMARIZATION_PROMPT,
)

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# SAFETY GUARDS
# ════════════════════════════════════════════════════════════

_FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXECUTE", "COPY", "VACUUM",
    "SET ", "COMMIT", "ROLLBACK", "BEGIN",
]

_MAX_RESULT_ROWS = 500
_QUERY_TIMEOUT_SECONDS = 10

# ════════════════════════════════════════════════════════════
# CASUAL / GREETING DETECTION
# ════════════════════════════════════════════════════════════

_CASUAL_PATTERNS = [
    "hi", "hii", "hiii", "hello", "hey", "yo", "sup",
    "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "thank u", "thx",
    "bye", "goodbye", "see you", "ok", "okay", "cool",
    "nice", "great", "awesome", "got it", "sure",
    "help", "what can you do", "who are you",
]

_CASUAL_RESPONSES = {
    "greeting": (
        "Hey there! 👋 I'm **ChurnGuard AI**, your retention strategy assistant. "
        "Ask me anything about your customer churn data — like churn rates, "
        "high-risk customers, or retention strategies. "
        "Try one of the suggestions above to get started!"
    ),
    "thanks": (
        "You're welcome! 😊 Let me know if you have more questions about your churn data."
    ),
    "bye": (
        "Goodbye! 👋 Come back anytime you need churn insights."
    ),
    "help": (
        "I can help you analyse your e-commerce churn data! Here are some things I can do:\n\n"
        "→ **Churn metrics** — \"How many customers churned?\"\n"
        "→ **Segment analysis** — \"Churn rate by city tier\"\n"
        "→ **Risk profiling** — \"Top 10 high risk customers\"\n"
        "→ **Comparisons** — \"Avg cashback churned vs retained\"\n\n"
        "Just type your question and I'll query the database and give you insights!"
    ),
    "acknowledgement": (
        "Got it! Let me know if you'd like to explore anything else about your churn data. 📊"
    ),
}


def _detect_casual(question: str) -> str | None:
    """
    Return a casual response category if the question is a greeting/casual
    message, or None if it's a real data question.
    """
    q = question.strip().lower().rstrip("!?.")
    # Must be short to be casual (long messages are likely real questions)
    if len(q.split()) > 8:
        return None
    
    greetings = {"hi", "hii", "hiii", "hello", "hey", "yo", "sup",
                 "good morning", "good afternoon", "good evening",
                 "howdy", "what's up", "whats up"}
    thanks = {"thanks", "thank you", "thank u", "thx", "ty", "appreciated"}
    byes = {"bye", "goodbye", "see you", "see ya", "cya", "later"}
    helps = {"help", "what can you do", "who are you", "what are you",
             "how do you work", "what do you do"}
    acks = {"ok", "okay", "cool", "nice", "great", "awesome", "got it",
            "sure", "alright", "fine", "good", "perfect", "understood"}
    
    if q in greetings or any(q.startswith(g) for g in greetings):
        return "greeting"
    if q in thanks or any(t in q for t in thanks):
        return "thanks"
    if q in byes or any(b in q for b in byes):
        return "bye"
    if q in helps or any(h in q for h in helps):
        return "help"
    if q in acks:
        return "acknowledgement"
    return None


def _sanitise_sql(sql: str) -> str:
    """
    Strip markdown fences and whitespace from LLM output.
    """
    # Remove ```sql ... ``` fences if present
    sql = re.sub(r"```(?:sql)?\s*", "", sql).strip()
    sql = sql.rstrip(";").strip()
    return sql


def _is_safe_query(sql: str) -> bool:
    """
    Return True only if the query is a read-only SELECT.
    Rejects any DML/DDL commands.
    """
    upper = sql.upper().strip()
    if not upper.startswith("SELECT"):
        return False
    for kw in _FORBIDDEN_KEYWORDS:
        # Match as whole word to avoid false positives (e.g. 'updated_at')
        if re.search(rf"\b{kw}\b", upper):
            return False
    return True


# ════════════════════════════════════════════════════════════
# CHART SUGGESTION HEURISTICS
# ════════════════════════════════════════════════════════════

def _suggest_chart(df: pd.DataFrame, question: str) -> dict | None:
    """
    Simple heuristic to suggest a chart type based on result shape.
    Returns a dict like {"type": "bar", "x": "col1", "y": "col2"} or None.
    """
    if df is None or df.empty or len(df) < 2:
        return None

    cols = list(df.columns)
    if len(cols) < 2:
        return None

    # If exactly 2 columns and one looks numeric → bar chart
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    non_numeric_cols = [c for c in cols if c not in numeric_cols]

    if len(numeric_cols) >= 1 and len(non_numeric_cols) >= 1:
        x_col = non_numeric_cols[0]
        y_col = numeric_cols[0]

        # Decide chart type
        q_lower = question.lower()
        if any(w in q_lower for w in ["trend", "over time", "monthly", "weekly"]):
            chart_type = "line"
        elif any(w in q_lower for w in ["distribution", "histogram"]):
            chart_type = "histogram"
        elif any(w in q_lower for w in ["compare", "vs", "versus", "breakdown"]):
            chart_type = "bar"
        elif len(df) <= 6:
            chart_type = "pie"
        else:
            chart_type = "bar"

        return {"type": chart_type, "x": x_col, "y": y_col}

    return None


# ════════════════════════════════════════════════════════════
# CHATBOT ENGINE
# ════════════════════════════════════════════════════════════

class ChurnChatbot:
    """
    Natural-language → SQL → results → summary pipeline.

    Usage:
        bot = ChurnChatbot(engine)
        response = bot.ask("How many customers churned last month?")
        # response = {
        #     "summary": "There were 47 customers who churned...",
        #     "sql": "SELECT COUNT(*) ...",
        #     "data": pd.DataFrame(...),
        #     "chart": {"type": "bar", "x": ..., "y": ...} or None,
        #     "error": None
        # }
    """

    def __init__(self, engine, api_key: str | None = None):
        self.engine = engine
        _key = api_key or os.getenv("GEMINI_API_KEY")
        if not _key:
            raise ValueError(
                "GEMINI_API_KEY not found. Set it in .env or pass it directly."
            )
        self.client = genai.Client(api_key=_key)
        # Try models in order of preference (confirmed available)
        self._model_candidates = [
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash",
        ]
        self.model = self._model_candidates[0]
        self.conversation_history: list[dict] = []

    # ── LLM Call with Fallback ────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """
        Call Gemini with automatic model fallback.
        Tries each model in _model_candidates until one succeeds.
        """
        last_error = None
        for model_name in self._model_candidates:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                # If this model worked, make it the default going forward
                self.model = model_name
                return response.text
            except Exception as e:
                last_error = e
                error_str = str(e).upper()
                # Only fall back on quota/rate-limit or model-not-found errors
                if any(code in error_str for code in [
                    "RESOURCE_EXHAUSTED", "429", "NOT_FOUND", "404",
                ]):
                    logger.warning(
                        "Model %s failed (%s), trying next...",
                        model_name, str(e)[:80],
                    )
                    continue
                # For other errors, don't fall back — raise immediately
                raise
        # If all models failed
        raise last_error  # type: ignore[misc]

    # ── SQL Generation ────────────────────────────────────

    def _generate_sql(self, question: str) -> str:
        """Ask Gemini to produce a SELECT query for the user question."""

        prompt = SQL_GENERATION_PROMPT.format(
            schema_context=SCHEMA_CONTEXT,
            current_date=date.today().isoformat(),
            question=question,
        )

        # Include last few Q&A pairs for follow-up context
        history_context = ""
        for entry in self.conversation_history[-4:]:
            history_context += (
                f"\nPREVIOUS Q: {entry['question']}\n"
                f"PREVIOUS SQL: {entry.get('sql', 'N/A')}\n"
            )
        if history_context:
            prompt += f"\n\nCONVERSATION HISTORY (for follow-up context):{history_context}"

        raw = self._call_llm(prompt)
        sql = _sanitise_sql(raw)
        return sql

    # ── SQL Execution ─────────────────────────────────────

    def _execute_sql(self, sql: str) -> pd.DataFrame:
        """Execute a read-only SQL query against the database."""

        if not _is_safe_query(sql):
            raise ValueError(
                "Unsafe query detected. Only SELECT statements are allowed."
            )

        # Add LIMIT if not present
        if "LIMIT" not in sql.upper():
            sql = f"{sql} LIMIT {_MAX_RESULT_ROWS}"

        with self.engine.connect() as conn:
            conn = conn.execution_options(
                timeout=_QUERY_TIMEOUT_SECONDS
            )
            result = pd.read_sql(text(sql), conn)

        return result

    # ── Result Summarisation ─────────────────────────────

    def _summarise_results(
        self, question: str, sql: str, results_df: pd.DataFrame
    ) -> str:
        """Ask Gemini to summarise query results in plain English."""

        # Format results as a readable table (cap at 30 rows for prompt space)
        if results_df.empty:
            results_str = "(No rows returned)"
        else:
            results_str = results_df.head(30).to_string(index=False)
            if len(results_df) > 30:
                results_str += f"\n... and {len(results_df) - 30} more rows"

        prompt = SUMMARIZATION_PROMPT.format(
            question=question,
            sql=sql,
            results=results_str,
        )

        return self._call_llm(prompt).strip()

    # ── Main Pipeline ────────────────────────────────────

    def ask(self, question: str) -> dict:
        """
        Full pipeline: question → SQL → execute → summarise.

        Returns a dict with keys:
            summary  (str)   — Human-readable answer
            sql      (str)   — The generated SQL query
            data     (DataFrame | None) — Raw query results
            chart    (dict | None) — Chart suggestion
            error    (str | None) — Error message if something failed
        """
        result = {
            "summary": "",
            "sql": "",
            "data": None,
            "chart": None,
            "error": None,
        }

        # Check for casual/greeting messages first
        casual_type = _detect_casual(question)
        if casual_type:
            result["summary"] = _CASUAL_RESPONSES.get(casual_type, _CASUAL_RESPONSES["greeting"])
            return result

        try:
            # Step 1: Generate SQL
            sql = self._generate_sql(question)
            result["sql"] = sql
            logger.info("Generated SQL: %s", sql)

            # Step 2: Execute
            df = self._execute_sql(sql)
            result["data"] = df

            # Step 3: Summarise
            summary = self._summarise_results(question, sql, df)
            result["summary"] = summary

            # Step 4: Chart suggestion
            result["chart"] = _suggest_chart(df, question)

            # Save to history for follow-ups
            self.conversation_history.append({
                "question": question,
                "sql": sql,
                "row_count": len(df),
            })

        except ValueError as e:
            # Safety guard triggered
            result["error"] = str(e)
            result["summary"] = (
                f"⚠️ I couldn't process that query safely: {e}\n\n"
                "Please try rephrasing your question."
            )

        except Exception as e:
            logger.exception("Chatbot error for question: %s", question)
            result["error"] = str(e)
            result["summary"] = (
                f"❌ Something went wrong while analysing your question:\n\n"
                f"`{e}`\n\n"
                "This might be a data issue — try rephrasing your question."
            )

        return result

    def clear_history(self):
        """Reset conversation history."""
        self.conversation_history = []
