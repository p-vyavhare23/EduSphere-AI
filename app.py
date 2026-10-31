import os
import json
import hmac
import hashlib
import secrets
import sqlite3
import time
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

# =========================================================
# CONFIGURATION
# =========================================================

load_dotenv()

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "edusphere.db"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
LOCAL_MODEL = "llama3.2:1b"

st.set_page_config(
    page_title="EduSphere AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# DATABASE
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                theme TEXT DEFAULT 'Dark',
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                messages TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)


initialize_database()

# =========================================================
# PASSWORD SECURITY
# =========================================================

def hash_password(password, salt=None):

    if salt is None:
        salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310000
    )

    return password_hash.hex(), salt.hex()


def verify_password(password, salt_hex, saved_hash):

    salt = bytes.fromhex(salt_hex)
    calculated_hash, _ = hash_password(password, salt)

    return hmac.compare_digest(calculated_hash, saved_hash)

# =========================================================
# USER FUNCTIONS
# =========================================================

def get_user(email):

    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),)
        ).fetchone()


def register_user(name, email, password):

    password_hash, salt = hash_password(password)

    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO users
                (name, email, password_hash, salt, theme, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                name.strip(),
                email.strip().lower(),
                password_hash,
                salt,
                "Dark",
                datetime.now().isoformat(timespec="seconds")
            ))

        return True, "Account created successfully!"

    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."


def update_profile(user_id, name):

    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET name = ? WHERE id = ?",
            (name.strip(), user_id)
        )


def update_user_theme(user_id, theme):

    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET theme = ? WHERE id = ?",
            (theme, user_id)
        )


def change_user_password(user_id, password):

    password_hash, salt = hash_password(password)

    with get_connection() as conn:
        conn.execute("""
            UPDATE users
            SET password_hash = ?, salt = ?
            WHERE id = ?
        """, (password_hash, salt, user_id))


# =========================================================
# CHAT HISTORY FUNCTIONS
# =========================================================

def get_conversations(user_id):

    with get_connection() as conn:
        return conn.execute("""
            SELECT id, title, updated_at
            FROM conversations
            WHERE user_id = ?
            ORDER BY updated_at DESC
        """, (user_id,)).fetchall()


def get_conversation(user_id, conversation_id):

    with get_connection() as conn:
        return conn.execute("""
            SELECT *
            FROM conversations
            WHERE id = ? AND user_id = ?
        """, (conversation_id, user_id)).fetchone()


def save_conversation(user_id, conversation_id, title, messages):

    timestamp = datetime.now().isoformat(timespec="seconds")
    messages_json = json.dumps(messages, ensure_ascii=False)

    with get_connection() as conn:

        if conversation_id is not None:

            result = conn.execute("""
                UPDATE conversations
                SET title = ?, messages = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
            """, (
                title,
                messages_json,
                timestamp,
                conversation_id,
                user_id
            ))

            if result.rowcount:
                return conversation_id

        cursor = conn.execute("""
            INSERT INTO conversations
            (user_id, title, messages, updated_at)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            title,
            messages_json,
            timestamp
        ))

        return cursor.lastrowid


# =========================================================
# SESSION STATE
# =========================================================

defaults = {
    "logged_in": False,
    "user_id": None,
    "user_name": "",
    "user_email": "",
    "theme": "Dark",
    "page": "Dashboard",
    "conversation_id": None,
    "conversation_title": "New Chat",
    "messages": []
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# Refresh account details from the database.
if st.session_state.logged_in:

    account = get_user(st.session_state.user_email)

    if account:

        st.session_state.user_name = account["name"]
        st.session_state.theme = account["theme"]

    else:
        st.session_state.logged_in = False

# =========================================================
# THEME AND CSS
# =========================================================

def apply_theme(theme):

    if theme == "Light":
        background = "#f4f6fb"
        panel = "#ffffff"
        text = "#172033"
        muted = "#64748b"
        border = "#e2e8f0"
        accent = "#4f46e5"

        input_bg = "#ffffff"
        button_text = "#ffffff"

    else:
        background = "#0b1020"
        panel = "#121a2b"
        text = "#eef2ff"
        muted = "#b4bfd8"
        border = "#26324a"
        accent = "#8b9cff"

        input_bg = "#ffffff"
        button_text = "#172033"

    st.markdown(f"""
    <style>

    /* ===== MAIN APP ===== */

    .stApp {{
        background-color: {background};
        color: {text};
    }}

    .stApp h1,
    .stApp h2,
    .stApp h3,
    .stApp h4,
    .stApp p,
    .stApp li,
    .stApp label,
    .stApp .stMarkdown {{
        color: {text};
    }}

    /* ===== SIDEBAR ===== */

    [data-testid="stSidebar"] {{
        background-color: {panel};
        border-right: 1px solid {border};
    }}

    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {{
        color: {text};
    }}

    /* ===== PAGE LAYOUT ===== */

    .block-container {{
        padding-top: 1.8rem;
        max-width: 1250px;
    }}

    /* ===== HERO SECTION ===== */

    .hero {{
        background: {panel};
        border: 1px solid {border};
        border-radius: 20px;
        padding: 28px;
        margin-bottom: 22px;
    }}

    .hero h1 {{
        color: {text};
        font-size: 2.2rem;
        margin-bottom: 8px;
    }}

    .hero p {{
        color: {muted};
        font-size: 1rem;
    }}

    /* ===== FEATURE CARDS ===== */

    .feature-card {{
        background: {panel};
        border: 1px solid {border};
        border-radius: 16px;
        padding: 20px;
        min-height: 145px;
        margin-bottom: 12px;
    }}

    .feature-card h3 {{
        color: {text};
        font-size: 1.1rem;
    }}

    .feature-card p {{
        color: {muted};
        font-size: 0.92rem;
    }}

    /* ===== METRICS ===== */

    div[data-testid="stMetric"] {{
        background: {panel};
        border: 1px solid {border};
        padding: 15px;
        border-radius: 14px;
    }}

    div[data-testid="stMetric"] label,
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
        color: {text};
    }}

    /* ===== CHAT MESSAGES ===== */

    [data-testid="stChatMessage"] {{
        background-color: {panel};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 14px;
    }}

    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] h1,
    [data-testid="stChatMessage"] h2,
    [data-testid="stChatMessage"] h3,
    [data-testid="stChatMessage"] strong,
    [data-testid="stChatMessage"] em {{
        color: {text} !important;
    }}

    [data-testid="stChatMessage"] a {{
        color: {accent} !important;
    }}

    /* ===== CHAT INPUT AND TEXT FIELDS ===== */

    [data-testid="stChatInput"] textarea,
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div[data-baseweb="select"] {{
        background-color: {input_bg} !important;
        color: #172033 !important;
        -webkit-text-fill-color: #172033 !important;
        border-color: {border} !important;
    }}

    [data-testid="stChatInput"] textarea::placeholder,
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder {{
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
        opacity: 1 !important;
    }}

    /* ===== BUTTONS ===== */

    .stButton button {{
        border-radius: 10px;
        min-height: 40px;
        border: 1px solid {border};
    }}

    .stButton button p,
    .stButton button span {{
        color: {button_text} !important;
    }}

    /* ===== DIVIDERS ===== */

    hr {{
        border-color: {border};
    }}

    /* ===== LINKS ===== */

    .stApp a {{
        color: {accent};
    }}

    /* ===== EXPANDERS ===== */

    [data-testid="stExpander"] {{
        border-color: {border};
    }}

    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p {{
        color: {text} !important;
    }}

    </style>
    """, unsafe_allow_html=True)


apply_theme(st.session_state.theme)

# =========================================================
# AI CONFIGURATION: LOCAL AI + GEMINI BACKUP
# =========================================================

@st.cache_resource
def get_gemini_client(api_key):
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=15000)
    )


# ---------------------------------------------------------
# 1. PRIMARY MODEL: LOCAL AI (OLLAMA)
# ---------------------------------------------------------

def ask_local_ai(prompt, history=None, system_instruction=None):

    import ollama

    messages = [
        {
            "role": "system",
            "content": (
                "You are EduSphere AI, a helpful educational assistant. "
                "Answer in simple, clear English. "
                "Be accurate and concise. "
                "Explain step by step only when needed. "
                "Never invent facts, scholarship amounts, eligibility rules, "
                "deadlines, or official website links. "
                "If you do not know something, clearly say so."
            )
        }
    ]

    if system_instruction:
        messages.append({
            "role": "system",
            "content": system_instruction
        })

    # Keep only the latest 4 conversation messages
    recent_history = (history or [])[-4:]

    for message in recent_history:

        if message.get("role") not in ("user", "assistant"):
            continue

        content = message.get("content", "")

        if isinstance(content, str) and content.strip():
            messages.append({
                "role": message["role"],
                "content": content
            })

    messages.append({
        "role": "user",
        "content": prompt
    })

    response = ollama.chat(
        model=LOCAL_MODEL,
        messages=messages,
        options={
            "num_predict": 512,
            "temperature": 0.3
        }
    )

    answer = response["message"]["content"]

    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Local AI returned an empty response.")

    return answer.strip()

# ---------------------------------------------------------
# 2. BACKUP MODEL: GEMINI
# ---------------------------------------------------------

def ask_gemini_ai(prompt, history=None, system_instruction=None):

    from google.genai import types

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "Gemini API key is missing. Check your .env file."
        )

    client = get_gemini_client(GEMINI_API_KEY)

    contents = []

    for message in history or []:

        if message.get("role") not in ("user", "assistant"):
            continue

        message_text = message.get("content", "")

        if not isinstance(message_text, str) or not message_text.strip():
            continue

        role = "user" if message["role"] == "user" else "model"

        contents.append({
            "role": role,
            "parts": [{"text": message_text}]
        })

    contents.append({
        "role": "user",
        "parts": [{"text": prompt}]
    })

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        max_output_tokens=256
    )

    def is_quota_error(error):

        error_text = str(error).lower()
        error_code = getattr(error, "code", None)

        return (
            error_code == 429
            or "resource_exhausted" in error_text
            or "quota exceeded" in error_text
            or "rate limit" in error_text
        )

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=config
        )

    except Exception as e:

        print("PRIMARY GEMINI ERROR:", repr(e))

        if is_quota_error(e):
            raise RuntimeError(
                "Gemini API quota has been exhausted."
            ) from e

        if getattr(e, "code", None) == 503 or "503" in str(e):

            print("Trying Gemini fallback model...")

            try:

                response = client.models.generate_content(
                    model="gemini-2.5-flash-lite",
                    contents=contents,
                    config=config
                )

            except Exception as fallback_error:

                print(
                    "GEMINI FALLBACK ERROR:",
                    repr(fallback_error)
                )

                if is_quota_error(fallback_error):
                    raise RuntimeError(
                        "Gemini API quota has been exhausted."
                    ) from fallback_error

                raise RuntimeError(
                    "Gemini is temporarily unavailable."
                ) from fallback_error

        else:
            raise

    answer = response.text

    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Gemini returned an empty response.")

    return answer.strip()

# ---------------------------------------------------------
# 3. MAIN AI FUNCTION: GEMINI FIRST, OLLAMA BACKUP
# ---------------------------------------------------------

def ask_ai(prompt, history=None, system_instruction=None):
    import time

    gemini_error_message = "Gemini was not attempted."
    ollama_error_message = "Ollama was not attempted."

    # Try Gemini first
    gemini_start = time.perf_counter()

    try:
        print("Using Gemini AI (Primary)...")

        answer = ask_gemini_ai(
            prompt=prompt,
            history=history,
            system_instruction=system_instruction
        )

        elapsed = time.perf_counter() - gemini_start
        st.session_state["last_ai_provider"] = "Gemini"

        print(f"GEMINI TIME: {elapsed:.2f} seconds")
        return answer

    except Exception as error:
        gemini_error_message = str(error)
        elapsed = time.perf_counter() - gemini_start

        print(f"GEMINI ERROR: {gemini_error_message}")
        print(f"GEMINI FAILED AFTER: {elapsed:.2f} seconds")
        print("Switching to Ollama backup...")

    # Try Ollama if Gemini fails
    ollama_start = time.perf_counter()

    try:
        answer = ask_local_ai(
            prompt=prompt,
            history=history,
            system_instruction=system_instruction
        )

        elapsed = time.perf_counter() - ollama_start
        st.session_state["last_ai_provider"] = "Local AI (Ollama)"

        print(f"OLLAMA TIME: {elapsed:.2f} seconds")
        return answer

    except Exception as error:
        ollama_error_message = str(error)

        print(f"OLLAMA ERROR: {ollama_error_message}")

        raise RuntimeError(
            "Both AI providers failed. "
            f"Gemini error: {gemini_error_message}; "
            f"Ollama error: {ollama_error_message}"
        ) from error

# =========================================================
# LOGOUT AND NEW CHAT
# =========================================================


def new_chat():

    st.session_state.conversation_id = None
    st.session_state.conversation_title = "New Chat"
    st.session_state.messages = []
    st.session_state.page = "AI Chat"


def logout():

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.rerun()


# =========================================================
# LOGIN / SIGNUP
# =========================================================

if not st.session_state.logged_in:

    left, right = st.columns([1.1, 1], gap="large")

    with left:

        st.markdown("""
        <div class="hero" style="margin-top:35px">
            <div style="font-size:55px">🎓</div>
            <h1>EduSphere AI</h1>
            <p>Your personal AI-powered learning workspace.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### Learn. Practise. Improve.")

        st.markdown("""
        - 🤖 AI-powered study assistance
        - 📄 Ask questions about your documents
        - 📝 Generate practice quizzes
        - 💬 Save your conversations
        - 🎨 Personalise your workspace
        """)

    with right:

        st.markdown("## Welcome")

        auth_choice = st.radio(
            "Account",
            ["Login", "Sign up"],
            horizontal=True,
            label_visibility="collapsed"
        )

        if auth_choice == "Login":

            with st.form("login_form"):

                email = st.text_input("Email address")
                password = st.text_input(
                    "Password",
                    type="password"
                )

                submitted = st.form_submit_button(
                    "Login",
                    use_container_width=True,
                    type="primary"
                )

            if submitted:

                account = get_user(email)

                if (
                    account
                    and verify_password(
                        password,
                        account["salt"],
                        account["password_hash"]
                    )
                ):

                    st.session_state.logged_in = True
                    st.session_state.user_id = account["id"]
                    st.session_state.user_name = account["name"]
                    st.session_state.user_email = account["email"]
                    st.session_state.theme = account["theme"]
                    st.session_state.page = "Dashboard"

                    st.rerun()

                else:
                    st.error("Incorrect email address or password.")

        else:

            with st.form("signup_form"):

                name = st.text_input("Full name")
                email = st.text_input("Email address")
                password = st.text_input(
                    "Password",
                    type="password",
                    help="Use at least 8 characters."
                )
                confirm_password = st.text_input(
                    "Confirm password",
                    type="password"
                )

                submitted = st.form_submit_button(
                    "Create account",
                    use_container_width=True,
                    type="primary"
                )

            if submitted:

                if not name.strip():
                    st.error("Please enter your name.")

                elif (
                    "@" not in email
                    or "." not in email.split("@")[-1]
                ):
                    st.error("Please enter a valid email address.")

                elif len(password) < 8:
                    st.error("Password must contain at least 8 characters.")

                elif password != confirm_password:
                    st.error("Passwords do not match.")

                else:

                    success, message = register_user(
                        name,
                        email,
                        password
                    )

                    if success:
                        st.success(message)
                    else:
                        st.error(message)

    st.stop()


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## 🎓 EduSphere AI")

    st.caption(f"Welcome, {st.session_state.user_name}")

    st.divider()

    navigation = {
        "🏠 Dashboard": "Dashboard",
        "💬 AI Chat": "AI Chat",
        "📄 Document Assistant": "Document Assistant",
        "📝 Quiz Generator": "Quiz Generator",
        "🕘 Chat History": "Chat History",
        "⚙️ Settings": "Settings"
    }

    for label, page_name in navigation.items():

        if st.button(
            label,
            key=f"nav_{page_name}",
            use_container_width=True
        ):

            st.session_state.page = page_name
            st.rerun()

    st.divider()

    if st.button(
        "➕ New Chat",
        type="primary",
        use_container_width=True
    ):

        new_chat()
        st.rerun()

    if st.button(
        "🚪 Logout",
        use_container_width=True
    ):

        logout()


page = st.session_state.page


# =========================================================
# DASHBOARD
# =========================================================

if page == "Dashboard":

    first_name = st.session_state.user_name.split()[0]

    st.markdown(f"""
    <div class="hero">
        <h1>Welcome back, {first_name} 👋</h1>
        <p>Your personal learning space is ready.</p>
    </div>
    """, unsafe_allow_html=True)

    conversations = get_conversations(
        st.session_state.user_id
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Saved conversations",
        len(conversations)
    )

    col2.metric(
        "Learning tools",
        3
    )

    col3.metric(
        "Current theme",
        st.session_state.theme
    )

    st.markdown("## Explore your workspace")

    features = [
        (
            "💬 AI Chat",
            "Ask questions and understand difficult concepts.",
            "AI Chat"
        ),
        (
            "📄 Document Assistant",
            "Upload notes and ask questions about them.",
            "Document Assistant"
        ),
        (
            "📝 Quiz Generator",
            "Create practice questions for revision.",
            "Quiz Generator"
        )
    ]

    columns = st.columns(3)

    for column, (title, description, target) in zip(
        columns, features
    ):

        with column:

            st.markdown(f"""
            <div class="feature-card">
                <h3>{title}</h3>
                <p>{description}</p>
            </div>
            """, unsafe_allow_html=True)

            if st.button(
                f"Open {target}",
                key=f"dashboard_{target}",
                use_container_width=True
            ):

                st.session_state.page = target
                st.rerun()

    st.markdown("## Recent conversations")

    if conversations:

        for conversation in conversations[:5]:

            col1, col2 = st.columns([4, 1])

            col1.write(f"**{conversation['title']}**")

            col1.caption(
                conversation["updated_at"].replace("T", " ")
            )

            if col2.button(
                "Open",
                key=f"dashboard_open_{conversation['id']}"
            ):

                record = get_conversation(
                    st.session_state.user_id,
                    conversation["id"]
                )

                if record:

                    st.session_state.conversation_id = record["id"]
                    st.session_state.conversation_title = record["title"]
                    st.session_state.messages = json.loads(
                        record["messages"]
                    )
                    st.session_state.page = "AI Chat"

                    st.rerun()

    else:
        st.info("Your saved chats will appear here.")


# =========================================================
# AI CHAT
# =========================================================

elif st.session_state.page == "AI Chat":

    st.title("💬 EduSphere AI Chat")

    # Make sure the message list exists
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display existing conversation
    for message in st.session_state.messages:

        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Get user's question
    user_prompt = st.chat_input(
        "Ask EduSphere AI anything..."
    )

    if user_prompt:

        # Display and save user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_prompt
        })

        with st.chat_message("user"):
            st.markdown(user_prompt)

        # Generate AI response
        with st.chat_message("assistant"):
            with st.spinner("EduSphere AI is thinking..."):
                try:
                    start_time = time.perf_counter()

                    answer = ask_ai(
                        prompt=user_prompt,
                        history=st.session_state.messages[-5:-1]
                    )

                    generation_time = time.perf_counter() - start_time

                    print(
                    f"AI GENERATION TIME: {generation_time:.2f} seconds"
                    )
                    # Validate response
                    if not isinstance(answer, str):
                        answer = str(answer)

                    if not answer.strip() or answer.strip().lower() == "none":
                        answer = (
                            "No valid response was received. "
                            "Please try again."
                        )

                except Exception as e:
                    print("FULL AI ERROR:", repr(e))
                    error_message = str(e)

                    if "Daily AI usage limit reached" in error_message:
                        st.warning(error_message)
                        answer = (
                            "Your daily AI usage limit has been reached. "
                            "Please try again after the quota resets."
                        )

                    elif "quota" in error_message.lower():
                        st.warning(error_message)
                        answer = (
                            "The available AI quota has been exhausted. "
                            "Please try again later."
                        )

                    else:
                        st.error(error_message)
                        answer = (
                            "EduSphere AI could not generate a response. "
                            "Please try again later."
                        )

                # Display AI response
                st.markdown(answer)

                provider = st.session_state.get(
                    "last_ai_provider",
                    "AI"
                )

                st.caption(f"Generated using: {provider}") 

        # Save assistant response
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer
        })

        # Generate conversation title
        first_question = next(
            (
                item["content"]
                for item in st.session_state.messages
                if item["role"] == "user"
            ),
            "New Chat"
        )

        title = first_question.replace(
            "\n", " "
        ).strip()[:50]

        if not title:
            title = "New Chat"

        st.session_state.conversation_title = title

        # Save conversation to database
        st.session_state.conversation_id = save_conversation(
            st.session_state.user_id,
            st.session_state.conversation_id,
            title,
            st.session_state.messages
        )

        # Refresh chat
        st.rerun()

# =========================================================
# DOCUMENT ASSISTANT
# =========================================================

elif page == "Document Assistant":

    st.title("📄 Document Assistant")
    st.write(
        "Upload a PDF or TXT file and ask questions about its contents."
    )

    uploaded_file = st.file_uploader(
        "Upload your document",
        type=["pdf", "txt"]
    )

    if uploaded_file:

        document_text = ""

        if uploaded_file.name.lower().endswith(".pdf"):

            try:

                import fitz

                pdf = fitz.open(
                    stream=uploaded_file.getvalue(),
                    filetype="pdf"
                )

                document_text = "\n".join(
                    page.get_text() for page in pdf
                )

            except Exception as error:
                st.error(f"Could not read PDF: {error}")

        else:

            document_text = uploaded_file.getvalue().decode(
                "utf-8",
                errors="replace"
            )

        if not document_text.strip():

            st.warning(
                "No readable text found. Scanned PDFs may require OCR."
            )

        else:

            st.success(
                f"Document loaded: {uploaded_file.name}"
            )

            question = st.text_area(
                "Ask a question about this document",
                placeholder="Summarise the main points..."
            )

            if st.button(
                "Ask about document",
                type="primary"
            ):

                if not question.strip():

                    st.warning("Please enter a question.")

                else:

                    with st.spinner("Analysing document..."):

                        try:

                            answer = ask_ai(
                                f"""
                                Answer the question using the document below.
                                If the document does not contain the answer,
                                clearly say so.

                                DOCUMENT:
                                {document_text[:25000]}

                                QUESTION:
                                {question}
                                """,
                                system_instruction=(
                                    "You are a careful document assistant. "
                                    "Ground your answer in the supplied text."
                                )
                            )

                            st.markdown("### Answer")
                            st.markdown(answer)

                        except Exception as error:
                            st.error(str(error))


# =========================================================
# QUIZ GENERATOR
# =========================================================

elif page == "Quiz Generator":

    st.title("📝 Quiz Generator")

    st.write(
        "Create practice questions to test your understanding."
    )

    topic = st.text_input(
        "Topic",
        placeholder="e.g. Finite Automata"
    )

    difficulty = st.selectbox(
        "Difficulty",
        ["Easy", "Medium", "Hard"]
    )

    question_count = st.slider(
        "Number of questions",
        min_value=3,
        max_value=15,
        value=5
    )

    notes = st.text_area(
        "Optional notes or syllabus",
        placeholder="Paste your notes here..."
    )

    if st.button(
        "Generate quiz",
        type="primary"
    ):

        if not topic.strip():

            st.warning("Enter a topic first.")

        else:

            prompt = f"""
            Create {question_count} {difficulty.lower()} practice
            questions about {topic}.

            Include four options for multiple-choice questions,
            identify the correct answer, and briefly explain it.

            Additional notes:
            {notes[:12000] if notes else "No notes supplied."}
            """

            with st.spinner("Generating quiz..."):

                try:

                    quiz = ask_ai(
                        prompt,
                        system_instruction=(
                            "You are an accurate educational quiz writer. "
                            "Use clear, age-appropriate explanations."
                        )
                    )

                    st.markdown("### Your practice quiz")
                    st.markdown(quiz)

                except Exception as error:
                    st.error(str(error))


# =========================================================
# CHAT HISTORY
# =========================================================

elif page == "Chat History":

    st.title("🕘 Chat History")

    st.write("Open or delete your saved conversations.")

    conversations = get_conversations(
        st.session_state.user_id
    )

    if not conversations:

        st.info(
            "No conversations saved yet. Start a chat first."
        )

    else:

        for conversation in conversations:

            with st.container(border=True):

                col1, col2, col3 = st.columns([4, 1, 1])

                col1.markdown(
                    f"**{conversation['title']}**"
                )

                col1.caption(
                    conversation["updated_at"].replace("T", " ")
                )

                if col2.button(
                    "Open",
                    key=f"history_open_{conversation['id']}"
                ):

                    record = get_conversation(
                        st.session_state.user_id,
                        conversation["id"]
                    )

                    if record:

                        st.session_state.conversation_id = record["id"]
                        st.session_state.conversation_title = record["title"]
                        st.session_state.messages = json.loads(
                            record["messages"]
                        )
                        st.session_state.page = "AI Chat"

                        st.rerun()

                if col3.button(
                    "Delete",
                    key=f"history_delete_{conversation['id']}"
                ):

                    with get_connection() as conn:

                        conn.execute("""
                            DELETE FROM conversations
                            WHERE id = ? AND user_id = ?
                        """, (
                            conversation["id"],
                            st.session_state.user_id
                        ))

                    if (
                        st.session_state.conversation_id
                        == conversation["id"]
                    ):

                        st.session_state.conversation_id = None
                        st.session_state.conversation_title = "New Chat"
                        st.session_state.messages = []

                    st.rerun()


# =========================================================
# SETTINGS
# =========================================================

elif page == "Settings":

    st.title("⚙️ Settings")

    profile_tab, appearance_tab, security_tab = st.tabs([
        "👤 Profile",
        "🎨 Appearance",
        "🔐 Security"
    ])

    # ---------------- PROFILE ----------------

    with profile_tab:

        st.subheader("Account details")

        st.text_input(
            "Email address",
            value=st.session_state.user_email,
            disabled=True
        )

        new_name = st.text_input(
            "Display name",
            value=st.session_state.user_name
        )

        if st.button(
            "Save profile",
            type="primary"
        ):

            if not new_name.strip():

                st.error("Name cannot be empty.")

            else:

                update_profile(
                    st.session_state.user_id,
                    new_name
                )

                st.session_state.user_name = new_name.strip()

                st.success("Profile updated.")
                st.rerun()

        account = get_user(st.session_state.user_email)

        if account:

            st.caption(
                f"Member since {account['created_at'][:10]}"
            )

    # ---------------- APPEARANCE ----------------

    with appearance_tab:

        st.subheader("Appearance")

        chosen_theme = st.radio(
            "Choose your theme",
            ["Light", "Dark"],
            index=(
                0 if st.session_state.theme == "Light"
                else 1
            ),
            horizontal=True
        )

        if chosen_theme == "Light":

            st.info("☀️ Light theme selected")

        else:

            st.info("🌙 Dark theme selected")

        if st.button(
            "Apply theme",
            type="primary"
        ):

            update_user_theme(
                st.session_state.user_id,
                chosen_theme
            )

            st.session_state.theme = chosen_theme

            st.rerun()

    # ---------------- SECURITY ----------------

    with security_tab:

        st.subheader("Change password")

        with st.form("password_change_form"):

            current_password = st.text_input(
                "Current password",
                type="password"
            )

            new_password = st.text_input(
                "New password",
                type="password"
            )

            confirm_password = st.text_input(
                "Confirm new password",
                type="password"
            )

            submitted = st.form_submit_button(
                "Update password",
                type="primary"
            )

        if submitted:

            account = get_user(
                st.session_state.user_email
            )

            if not verify_password(
                current_password,
                account["salt"],
                account["password_hash"]
            ):

                st.error("Current password is incorrect.")

            elif len(new_password) < 8:

                st.error(
                    "New password must contain at least 8 characters."
                )

            elif new_password != confirm_password:

                st.error("New passwords do not match.")

            else:

                change_user_password(
                    st.session_state.user_id,
                    new_password
                )

                st.success("Password updated successfully.")

    st.divider()

    st.caption(
        "EduSphere AI stores account details and chat history in a "
        "local SQLite database. This starter app is not production-ready "
        "authentication and should not be exposed publicly without "
        "additional security."
    )