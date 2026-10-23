"""QuantaGuard Chat - WhatsApp-style messenger secured by BB84 keys.

Run on one laptop with `streamlit run src/app.py`; every phone on the same
Wi-Fi opens the Network URL, signs in with its own number, and chats.
Key exchange, trust classification and encryption come from src.pipeline,
unchanged. Accounts, chats and ciphertext live in src.store (SQLite).
"""
import hashlib
import html
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root

import streamlit as st

from src import store
from src.pipeline import run_exchange, get_expected_qber, encrypt_msg, decrypt_msg

QBER_LIMIT = 0.11   # BB84 security limit
GAUGE_MAX = 0.30    # right edge of the QBER gauge
VERDICT = {
    "safe": ("Secure", "#10b981"),
    "noisy": ("Noisy but usable", "#f59e0b"),
    "compromised": ("Eavesdropper detected", "#ef4444"),
}

st.set_page_config(page_title="QuantaGuard Chat", page_icon="🛡️",
                   layout="centered", initial_sidebar_state="collapsed")
store.init()

SHIELD = ('<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
          '<path d="M12 2.5 4 5.6v6.1c0 4.9 3.4 9.1 8 10.3 4.6-1.2 8-5.4 8-10.3V5.6L12 2.5Z" fill="url(#qg)" '
          'stroke="#67e8f9" stroke-width="1.2"/><circle cx="12" cy="11.5" r="2.2" fill="#0b1220"/>'
          '<ellipse cx="12" cy="11.5" rx="5.2" ry="2" stroke="#0b1220" stroke-width="1.1"/><defs>'
          '<linearGradient id="qg" x1="4" y1="3" x2="20" y2="21"><stop stop-color="#22d3ee"/>'
          '<stop offset="1" stop-color="#6366f1"/></linearGradient></defs></svg>')

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
:root { --bg:#0b1220; --panel:#111a2e; --panel-2:#0e1628; --line:#1f2b45; --text:#e6ebf5; --muted:#8a97b1; }
html, body, .stApp, .stApp p, .stApp label, .stApp input, .stApp button, .stApp textarea { font-family:'Inter', sans-serif; }
.stApp { background: radial-gradient(900px 500px at 80% -10%, #16224099 0%, transparent 60%), var(--bg); color:var(--text); }
[data-testid="stHeader"] { background:transparent; height:0; }
[data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu, footer,
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] { display:none !important; }
.block-container { max-width:540px; padding:1.2rem 1rem 6rem; }
[data-testid="InputInstructions"] { display:none; }
[data-testid="stTextInputRootElement"], [data-baseweb="input"] { border:1px solid #2a3a5c !important; border-radius:10px !important; background:#0b1220 !important; }
[data-baseweb="base-input"] { background:#0b1220 !important; }
div[data-testid="stForm"] { background:var(--panel); border:1px solid var(--line); border-radius:14px; }
.stButton > button, div[data-testid="stFormSubmitButton"] > button { border-radius:10px; font-weight:600; }
button[data-testid^="stBaseButton-primary"] { background:linear-gradient(135deg,#06b6d4,#6366f1); border:0; color:white; }
[data-testid="stExpander"] details { background:var(--panel); border:1px solid var(--line); border-radius:12px; }
[data-testid="stBottom"] > div { background:transparent; }
[data-testid="stBottomBlockContainer"] { max-width:540px; padding-bottom:1rem; background:var(--bg); }

.qg-top { display:flex; align-items:center; gap:12px; padding:6px 0 14px; border-bottom:1px solid var(--line); margin-bottom:14px; }
.qg-top .name { font-weight:700; font-size:1.05rem; line-height:1.2; }
.qg-top .sub { color:var(--muted); font-size:.78rem; }
.qg-avatar { width:40px; height:40px; border-radius:50%; flex:none; display:flex; align-items:center; justify-content:center;
  font-weight:700; color:#0b1220; font-size:.95rem; }
.qg-chip { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px; font-size:.72rem;
  font-weight:600; border:1px solid; white-space:nowrap; margin-left:auto; }
.qg-label { color:var(--muted); font-size:.7rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase; }

.st-key-chatlist button { justify-content:flex-start; text-align:left; padding:12px 14px; background:var(--panel);
  border:1px solid var(--line); border-radius:12px; min-height:64px; }
.st-key-chatlist button:hover { border-color:#22d3ee88; }
.st-key-chatlist button p { text-align:left; font-size:.9rem; line-height:1.35; }

.qg-thread { height:52vh; overflow-y:auto; display:flex; flex-direction:column-reverse; gap:2px;
  background:linear-gradient(180deg,#0d1526,#0b1220); border:1px solid var(--line); border-radius:14px; padding:12px; }
.qg-msg { max-width:80%; width:fit-content; padding:8px 12px; border-radius:12px; margin:3px 0; font-size:.92rem;
  line-height:1.4; overflow-wrap:anywhere; }
.qg-msg.me { margin-left:auto; background:linear-gradient(135deg,#0891b2,#4f46e5); color:white; border-bottom-right-radius:4px; }
.qg-msg.them { background:#1a2540; border:1px solid var(--line); border-bottom-left-radius:4px; }
.qg-meta { font-size:.66rem; opacity:.7; margin-top:2px; text-align:right; }
.qg-note { align-self:center; text-align:center; font-size:.74rem; color:#cbd5e1; background:#1e293b; border:1px solid var(--line);
  border-radius:8px; padding:6px 10px; margin:8px 0; max-width:92%; }
.qg-empty { margin:auto; color:var(--muted); font-size:.85rem; text-align:center; }

.qg-grid { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:10px 0; }
.qg-cell { background:var(--panel-2); border:1px solid var(--line); border-radius:10px; padding:10px 12px; }
.qg-cell .v { font-size:1.15rem; font-weight:700; margin-top:2px; }
.qg-cell .v.mono { font-family:'JetBrains Mono',monospace; font-size:.9rem; letter-spacing:.03em; }
.qg-gauge-wrap { position:relative; margin:34px 0 30px; }
.qg-gauge { height:12px; border-radius:6px; overflow:hidden; display:flex; }
.qg-gauge .ok { background:linear-gradient(90deg,#10b98144,#10b981aa); }
.qg-gauge .bad { background:linear-gradient(90deg,#ef444466,#ef4444aa); }
.qg-marker { position:absolute; display:flex; flex-direction:column; }
.qg-marker.up { bottom:-6px; } .qg-marker.down { top:-6px; }
.qg-marker .stem { width:3px; height:24px; border-radius:2px; }
.qg-marker .tag { font-size:.66rem; font-weight:600; white-space:nowrap; padding:2px 5px; border-radius:4px; }
.qg-ticks { display:flex; justify-content:space-between; color:var(--muted); font-size:.66rem; font-family:'JetBrains Mono',monospace; }
.qg-steps { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:6px; margin-top:8px; }
.qg-step { border-radius:8px; padding:7px 8px; border:1px solid var(--line); background:var(--panel-2); min-width:0; }
.qg-step .n { font-family:'JetBrains Mono',monospace; font-size:.62rem; color:var(--muted); }
.qg-step .t { font-size:.7rem; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.qg-step.done { border-color:#10b98155; } .qg-step.done .t { color:#6ee7b7; }
.qg-step.fail { border-color:#ef444477; background:#ef444414; } .qg-step.fail .t { color:#fca5a5; }
.qg-step.skip { opacity:.45; }
.qg-cipher { font-family:'JetBrains Mono',monospace; font-size:.72rem; color:#94a3b8; background:var(--panel-2);
  border:1px solid var(--line); border-radius:8px; padding:6px 10px; margin:4px 0; overflow-x:auto; white-space:nowrap; }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def fmt_id(uid):
    return f"{uid[:5]} {uid[5:]}"


def avatar(uid, name, size=40):
    hue = int(hashlib.sha256(uid.encode()).hexdigest()[:4], 16) % 360
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    return (f'<div class="qg-avatar" style="width:{size}px;height:{size}px;background:hsl({hue},75%,68%)">'
            f'{html.escape(initials)}</div>')


def hhmm(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%H:%M")
    except (TypeError, ValueError):
        return ""


def fingerprint(key):
    h = hashlib.sha256(key).hexdigest()[:12].upper()
    return " ".join(h[i:i + 4] for i in range(0, 12, 4))


def decrypt_row(m, keys):
    key = keys.get(m["epoch"])
    if key is None or m["blob"] is None:
        return None
    try:
        return decrypt_msg(key, m["blob"])
    except Exception:
        return None


def status_chip(k):
    if k is None:
        return '<span class="qg-chip" style="color:#94a3b8;border-color:#334155">No quantum key</span>'
    if k["key"] is None:
        label, col = ("Locked: eavesdropper" if k["verdict"] == "compromised" else "No key", "#ef4444")
    else:
        label, col = VERDICT[k["verdict"]][0], VERDICT[k["verdict"]][1]
    return f'<span class="qg-chip" style="color:{col};border-color:{col}66;background:{col}14">&#9679; {label}</span>'


def gauge_html(qber, expected):
    def at(v):
        p = max(0.0, min(v, GAUGE_MAX)) / GAUGE_MAX * 100
        shift = "0%" if p < 8 else "-100%" if p > 92 else "-50%"
        align = "flex-start" if p < 8 else "flex-end" if p > 92 else "center"
        return f"left:{p}%; transform:translateX({shift}); align-items:{align}"

    ok_w = QBER_LIMIT / GAUGE_MAX * 100
    obs = "#ef4444" if qber > QBER_LIMIT else "#e6ebf5"
    ticks = "".join(f"<span>{t}%</span>" for t in range(0, 31, 10))
    return (f'<div class="qg-gauge-wrap"><div class="qg-gauge"><div class="ok" style="width:{ok_w}%"></div>'
            f'<div class="bad" style="width:{100 - ok_w}%"></div></div>'
            f'<div class="qg-marker up" style="{at(qber)}"><span class="tag" style="color:#0b1220;background:{obs}">'
            f'observed {qber:.1%}</span><span class="stem" style="background:{obs}"></span></div>'
            f'<div class="qg-marker down" style="{at(expected)}"><span class="stem" style="background:'
            'repeating-linear-gradient(#60a5fa 0 4px,transparent 4px 7px)"></span><span class="tag" '
            f'style="color:#60a5fa;background:#60a5fa1f">expected {expected:.1%}</span></div>'
            f'<div class="qg-marker down" style="{at(QBER_LIMIT)}"><span class="stem" style="background:#ef4444aa;'
            'width:2px"></span><span class="tag" style="color:#fca5a5;background:#ef44441f">11% limit</span></div>'
            f'</div><div class="qg-ticks">{ticks}</div>')


def steps_html(verdict, has_key):
    names = ["BB84", "Sifting", "QBER", "Trust Meter", "Reconcile", "Privacy amp.", "HKDF", "AES-GCM"]
    states = []
    for i in range(len(names)):
        if verdict == "compromised":
            states.append("done" if i < 3 else "fail" if i == 3 else "skip")
        elif not has_key:
            states.append("done" if i < 4 else "fail" if i == 4 else "skip")
        else:
            states.append("done")
    icon = {"done": "&#10003;", "fail": "&#10005;", "skip": "&ndash;"}
    return '<div class="qg-steps">' + "".join(
        f'<div class="qg-step {s}"><div class="n">{i + 1:02d} {icon[s]}</div><div class="t">{n}</div></div>'
        for i, (n, s) in enumerate(zip(names, states))) + "</div>"


def go(chat=None):
    """Switch between the chat list (chat=None) and a chat."""
    st.session_state.chat = chat
    if chat:
        st.query_params["c"] = chat
    else:
        st.query_params.pop("c", None)
    st.rerun()


# --------------------------------------------------------------------------- #
# sign in / create account
# --------------------------------------------------------------------------- #
def sign_in(uid):
    token = store.new_token(uid)
    st.session_state.uid, st.session_state.token = uid, token
    st.query_params["s"] = token
    st.rerun()


def auth_page():
    st.markdown(f'<div style="text-align:center;margin:6vh 0 22px">{SHIELD.format(s=60)}'
                '<div style="font-size:1.8rem;font-weight:700;margin-top:12px">QuantaGuard Chat</div>'
                '<div style="color:var(--muted);font-size:.92rem;margin-top:4px">'
                'Messages protected by quantum-generated keys</div></div>', unsafe_allow_html=True)
    tab_in, tab_up = st.tabs(["Sign in", "Create account"])
    with tab_in:
        with st.form("signin"):
            uid = st.text_input("QuantaGuard number", max_chars=10, placeholder="10-digit number")
            pw = st.text_input("Password", type="password")
            ok = st.form_submit_button("Sign in", type="primary", use_container_width=True)
        if ok:
            if store.check_login(uid, pw):
                sign_in(uid.strip())
            else:
                st.error("Wrong number or password.")
    with tab_up:
        with st.form("signup"):
            name = st.text_input("Your name", max_chars=30)
            uid = st.text_input("Choose a QuantaGuard number", max_chars=10,
                                placeholder="10 digits, like a phone number")
            pw = st.text_input("Password", type="password", help="At least 6 characters")
            pw2 = st.text_input("Confirm password", type="password")
            ok = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if ok:
            err = "Passwords do not match." if pw != pw2 else store.register(uid, name, pw)
            if err:
                st.error(err)
            else:
                sign_in(uid.strip())
    st.caption("Your password is stored only as a salted PBKDF2-SHA256 hash.")


# --------------------------------------------------------------------------- #
# chat list
# --------------------------------------------------------------------------- #
def home(uid):
    me = store.user_name(uid)
    st.markdown(f'<div class="qg-top">{avatar(uid, me)}<div><div class="name">{html.escape(me)}</div>'
                f'<div class="sub">Your number: {fmt_id(uid)}</div></div>'
                f'<span style="margin-left:auto">{SHIELD.format(s=30)}</span></div>', unsafe_allow_html=True)

    with st.form("newchat", clear_on_submit=True):
        st.markdown('<div class="qg-label">New chat</div>', unsafe_allow_html=True)
        other = st.text_input("Number", max_chars=10, placeholder="Enter their 10-digit number",
                              label_visibility="collapsed")
        start = st.form_submit_button("Start chat", type="primary", use_container_width=True)
    if start:
        other = other.strip()
        if other == uid:
            st.error("That's your own number.")
        elif not store.user_name(other):
            st.error("No account with that number. Ask them to create one first.")
        else:
            store.start_chat(uid, other)
            go(other)

    st.markdown('<div class="qg-label" style="margin:18px 0 8px">Chats</div>', unsafe_allow_html=True)
    chat_list(uid)

    st.write("")
    if st.button("Sign out", use_container_width=True):
        store.drop_token(st.session_state.get("token", ""))
        for k in ("uid", "token", "chat"):
            st.session_state.pop(k, None)
        st.query_params.clear()
        st.rerun()


@st.fragment(run_every=3)
def chat_list(uid):
    chats = store.chats_for(uid)
    if not chats:
        st.caption("No chats yet. Enter a friend's number above to start one.")
        return
    with st.container(key="chatlist"):
        for c in chats:
            last = store.messages(c["id"], limit=1)
            k = store.latest_key(c["id"])
            dot = "⚪" if k is None else "🔴" if k["key"] is None else "🟢" if k["verdict"] == "safe" else "🟡"
            if not last:
                preview = "Tap to open and run a quantum key exchange"
            elif last[0]["note"]:
                preview = last[0]["note"]
            else:
                text = decrypt_row(last[0], store.keys_by_epoch(c["id"])) or "Encrypted message"
                preview = ("You: " if last[0]["sender"] == uid else "") + text
            preview = preview if len(preview) <= 48 else preview[:47] + "…"
            when = hhmm(last[0]["ts"]) if last else ""
            label = f"{dot} **{c['name']}**  ·  {when}  \n{preview}"
            if st.button(label, key=f"open_{c['other']}", use_container_width=True):
                go(c["other"])


# --------------------------------------------------------------------------- #
# chat screen
# --------------------------------------------------------------------------- #
def chat_page(uid, other):
    oname = store.user_name(other)
    if not oname:
        go(None)
    cid = store.start_chat(uid, other)
    me = store.user_name(uid)

    if st.button("← Chats"):
        go(None)
    k = store.latest_key(cid)
    st.markdown(f'<div class="qg-top">{avatar(other, oname)}<div><div class="name">{html.escape(oname)}</div>'
                f'<div class="sub">{fmt_id(other)}</div></div>{status_chip(k)}</div>', unsafe_allow_html=True)

    title = "Quantum key: none yet" if k is None else \
        f"Quantum key #{k['epoch']}: {k['verdict'].upper()} · {k['key_len']:,} bits"
    just_ran = st.session_state.pop(f"ran_{cid}", False)
    with st.expander("🔐 " + title, expanded=k is None or just_ran):
        noise = st.slider("Channel noise", 0.0, 1.0, 0.1, 0.05, key=f"noise_{cid}",
                          help="Higher noise raises QBER and shortens the key.")
        eve = st.toggle("Simulate eavesdropper (intercept-resend)", key=f"eve_{cid}")
        if st.button("Run BB84 key exchange", type="primary", use_container_width=True):
            with st.spinner("Exchanging qubits..."):
                ex = run_exchange(noise, eve)
                for _ in range(5):  # empty key on a borderline exchange: run another
                    if ex["key"] is not None or ex["verdict"] == "compromised":
                        break
                    ex = run_exchange(noise, eve)
            if ex["verdict"] == "compromised":
                note = (f"⚠️ {me} ran a key exchange: eavesdropper detected (QBER {ex['qber']:.1%}). "
                        "Key discarded, chat locked until a clean exchange.")
            elif ex["key"] is None:
                note = f"⚠️ {me} ran a key exchange, but no secure key could be derived."
            else:
                note = (f"🔑 {me} set up a new quantum key: {ex['verdict'].upper()}, "
                        f"QBER {ex['qber']:.1%}, {ex['final_key_len']:,} bits")
            store.add_key(cid, ex["key"], ex["verdict"], ex["qber"], ex["final_key_len"],
                          noise, eve, uid, note)
            st.session_state[f"ran_{cid}"] = True
            st.rerun()
        if k is not None:
            expected = get_expected_qber(k["noise"])
            fp = fingerprint(k["key"]) if k["key"] else "DISCARDED"
            st.markdown(
                '<div class="qg-grid">'
                f'<div class="qg-cell"><div class="qg-label">Observed QBER</div><div class="v">{k["qber"]:.1%}</div></div>'
                f'<div class="qg-cell"><div class="qg-label">Expected QBER</div><div class="v">{expected:.1%}</div></div>'
                f'<div class="qg-cell"><div class="qg-label">Final key</div><div class="v">{k["key_len"]:,} bits</div></div>'
                f'<div class="qg-cell"><div class="qg-label">Key fingerprint</div><div class="v mono">{fp}</div></div>'
                f'</div>{gauge_html(k["qber"], expected)}{steps_html(k["verdict"], k["key"] is not None)}',
                unsafe_allow_html=True)
            st.caption("Compare the key fingerprint on both phones: if it matches, you share the same key. "
                       "Demo note: this server holds the key for both phones; real QKD delivers it to "
                       "each device over a quantum link.")

    thread(cid, uid)

    blocked = k is None or k["key"] is None
    hint = ("Run a key exchange to start chatting" if k is None else
            "Chat locked: run a clean key exchange" if blocked else f"Message {oname}")
    text = st.chat_input(hint, disabled=blocked, max_chars=1000)
    if text and text.strip():
        cur = store.latest_key(cid)  # the other phone may have rotated the key
        if cur and cur["key"] is not None:
            store.add_msg(cid, uid, cur["epoch"], encrypt_msg(cur["key"], text.strip()))
        st.rerun()

    with st.expander("🕵️ What an eavesdropper sees on the network"):
        rows = [m for m in store.messages(cid, limit=50) if m["blob"]][-5:]
        if not rows:
            st.caption("No messages yet. Each message is a random 12-byte nonce plus AES-GCM ciphertext.")
        for m in rows:
            st.markdown(f'<div class="qg-cipher">{m["blob"].hex()[:96]}…</div>', unsafe_allow_html=True)


@st.fragment(run_every=2)
def thread(cid, uid):
    msgs = store.messages(cid)
    keys = store.keys_by_epoch(cid)
    parts = []
    for m in msgs:
        if m["note"]:
            parts.append(f'<div class="qg-note">{html.escape(m["note"])}</div>')
            continue
        text = decrypt_row(m, keys)
        body = html.escape(text) if text is not None else "<i>Unable to decrypt</i>"
        mine = m["sender"] == uid
        tick = " ✓✓" if mine else ""
        parts.append(f'<div class="qg-msg {"me" if mine else "them"}">{body}'
                     f'<div class="qg-meta">{hhmm(m["ts"])} · AES-GCM{tick}</div></div>')
    if not parts:
        parts = ['<div class="qg-empty">No messages yet.<br>Run a BB84 key exchange, then say hi.</div>']
    # column-reverse keeps the newest message in view, like a phone chat
    st.markdown('<div class="qg-thread">' + "".join(reversed(parts)) + "</div>",
                unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# router
# --------------------------------------------------------------------------- #
if "uid" not in st.session_state:
    tok = st.query_params.get("s")
    uid = store.token_user(tok) if tok else None
    if uid:
        st.session_state.uid, st.session_state.token = uid, tok
        st.session_state.chat = st.query_params.get("c")

if "uid" not in st.session_state:
    auth_page()
elif st.session_state.get("chat"):
    chat_page(st.session_state.uid, st.session_state.chat)
else:
    home(st.session_state.uid)
