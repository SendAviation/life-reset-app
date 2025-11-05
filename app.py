import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Life Reset App", layout="wide")

# ---- Session state ----
if "tasks" not in st.session_state:
    st.session_state.tasks = []
if "planner" not in st.session_state:
    st.session_state.planner = {"time_available": 30}

# ---- Helper functions ----
FREQUENCIES = ["once", "daily", "weekly", "biweekly", "monthly", "quarterly"]

def next_due_from(freq: str, base: datetime=None):
    base = base or datetime.now()
    if freq == "once":
        return base
    if freq == "daily":
        return base + timedelta(days=1)
    if freq == "weekly":
        return base + timedelta(weeks=1)
    if freq == "biweekly":
        return base + timedelta(weeks=2)
    if freq == "monthly":
        # naive month add
        month = base.month + 1
        year = base.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        return base.replace(year=year, month=month)
    if freq == "quarterly":
        month = base.month + 3
        year = base.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        return base.replace(year=year, month=month)
    return base

# ---- Sidebar: Time & Focus ----
st.sidebar.header("🧭 Planner")
st.session_state.planner["time_available"] = st.sidebar.slider("How many minutes do you have right now?", 10, 180, st.session_state.planner["time_available"], step=5)
energy = st.sidebar.select_slider("Energy level", options=["low","medium","high"], value="medium")

st.title("Life Reset — ADHD Friendly Planner (MVP)")
st.caption("Add tasks, set your available time, and get a short, ADHD‑friendly list of what to do now. New: email/SMS summary + .ics download.")

# ---- Task Entry ----
with st.expander("➕ Add a Task"):
    c1, c2, c3 = st.columns([3,2,2])
    with c1:
        title = st.text_input("Task title", placeholder="e.g., Declutter kitchen counters")
    with c2:
        effort = st.number_input("Effort (minutes)", min_value=5, max_value=240, step=5, value=20)
    with c3:
        freq = st.selectbox("Frequency", FREQUENCIES, index=2)
    c4, c5 = st.columns([2,2])
    with c4:
        tag = st.selectbox("Tag", ["money","home","health","admin","other"], index=0)
    with c5:
        due = st.date_input("Due date (optional)")
    note = st.text_area("Notes", placeholder="Context, link, or steps…")
    if st.button("Add task", type="primary"):
        st.session_state.tasks.append({
            "title": title.strip(),
            "effort": int(effort),
            "freq": freq,
            "tag": tag,
            "energy": energy,
            "due": due.strftime("%Y-%m-%d") if due else "",
            "next_due": next_due_from(freq).strftime("%Y-%m-%d"),
            "notes": note
        })
        st.success("Task added.")

# ---- Task Table ----
if st.session_state.tasks:
    df = pd.DataFrame(st.session_state.tasks)
    st.subheader("📋 Your Tasks")
    st.dataframe(df, use_container_width=True)
else:
    st.info("No tasks yet. Add a few above.")

# ---- Suggestion Engine ----
st.subheader("⚡ What should I do with my time?")
time_available = st.session_state.planner["time_available"]
summary_text = ""
ics_content = ""
if st.session_state.tasks:
    df = pd.DataFrame(st.session_state.tasks)
    candidates = df[df["effort"] <= time_available].copy()
    def urgency(row):
        try:
            nd = datetime.strptime(row["next_due"], "%Y-%m-%d")
            days = (nd - datetime.now()).days
        except Exception:
            days = 7
        return max(0, 14 - days)
    candidates["urgency"] = candidates.apply(urgency, axis=1)
    energy_weight = {"low": 0.8, "medium": 1.0, "high": 1.2}
    candidates["score"] = (candidates["urgency"] + 1) * energy_weight.get(energy,1.0)
    tag_boost = candidates["tag"].map({"money": 2, "admin": 1.5, "home": 1.2, "health": 1.1}).fillna(1.0)
    candidates["score"] = candidates["score"] * tag_boost
    plan = candidates.sort_values(["score","effort"], ascending=[False, True]).head(5)

    st.write(f"Top picks for the next **{time_available} min**:")
    lines = []
    for i, row in plan.reset_index(drop=True).iterrows():
        with st.container(border=True):
            st.markdown(f"**{i+1}. {row['title']}** — {row['effort']} min · *{row['tag']}* · due {row['next_due']}")
            if row["notes"]:
                st.caption(row["notes"])
        lines.append(f"{i+1}. {row['title']} — {row['effort']} min [{row['tag']}] (due {row['next_due']})")

    # ---- Build summary for email/SMS ----
    summary_text = (
        f"Life Reset — Today
Time now: {datetime.now().strftime('%I:%M %p')}

"
        f"You told me you have {time_available} minutes and energy = {energy}.

"
        + "Do these next:" + "
" + "
".join(lines)
    )
    st.divider()
    st.subheader("📧 / 📱 Send yourself a summary")
    st.text_area("Preview", summary_text, height=180)

    # mailto link
    email = st.text_input("Send to email (optional)", value="")
    subject = "Life Reset — Today" 
    if email:
        mailto = f"mailto:{email}?subject={subject}&body=" + summary_text.replace("
","%0D%0A")
        st.markdown(f"[Open your email app with the summary prefilled]({mailto})")

    # sms share hint
    st.caption("Tip: Copy the preview and paste into your own text thread or notes app. SMS deep links vary by device.")

    # ---- .ics download for the top task ----
    st.subheader("🗓️ Add the top task to your calendar (.ics)")
    if not plan.empty:
        top = plan.iloc[0]
        start = datetime.now() + timedelta(minutes=5)
        end = start + timedelta(minutes=int(top['effort']))
        def ics_datetime(dt):
            return dt.strftime('%Y%m%dT%H%M%S')
        ics_content = ("BEGIN:VCALENDAR
"
                       "VERSION:2.0
"
                       "PRODID:-//Life Reset//EN
"
                       "BEGIN:VEVENT
"
                       f"DTSTART:{ics_datetime(start)}
"
                       f"DTEND:{ics_datetime(end)}
"
                       f"SUMMARY:{top['title']}
"
                       f"DESCRIPTION:{top['notes'] if top['notes'] else 'Life Reset task'}
"
                       "END:VEVENT
END:VCALENDAR
")
        st.download_button("Download .ics for top task", data=ics_content, file_name="life_reset_top_task.ics", mime="text/calendar")

    # ---- One-tap Sprint (bundle tasks into a schedule) ----
    st.subheader("🚀 One‑tap Sprint (bundle tasks)")
    sprint_minutes = st.number_input("Sprint length (minutes)", min_value=30, max_value=240, step=15, value=90)
    if st.button("Build 90‑minute Sprint", type="secondary"):
        # Greedy select highest score tasks that fit within sprint_minutes
        pool = candidates.sort_values(["score","effort"], ascending=[False, True]).copy()
        remaining = sprint_minutes
        chosen = []
        for _, r in pool.iterrows():
            if r["effort"] <= remaining:
                chosen.append(r)
                remaining -= int(r["effort"])
        if not chosen:
            # Fallback at least one task
            chosen = [pool.iloc[0]] if not pool.empty else []

        # Build schedule blocks starting 5 min from now
        start0 = datetime.now() + timedelta(minutes=5)
        blocks = []
        cur = start0
        for r in chosen:
            s = cur
            e = s + timedelta(minutes=int(r["effort"]))
            blocks.append({"title": r["title"], "start": s, "end": e, "tag": r["tag"], "notes": r.get("notes","")})
            cur = e

        if blocks:
            st.markdown("**Sprint plan:**")
            for i, b in enumerate(blocks, 1):
                st.markdown(f"{i}. {b['start'].strftime('%I:%M %p')}–{b['end'].strftime('%I:%M %p')} — **{b['title']}** · *{b['tag']}*")

            # Build multi‑event ICS
            def ics_datetime(dt):
                return dt.strftime('%Y%m%dT%H%M%S')
            ics_multi = ["BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Life Reset//EN
"]
            for b in blocks:
                ics_multi.append("BEGIN:VEVENT
" +
                                 f"DTSTART:{ics_datetime(b['start'])}
" +
                                 f"DTEND:{ics_datetime(b['end'])}
" +
                                 f"SUMMARY:{b['title']}
" +
                                 f"DESCRIPTION:{b['notes'] if b['notes'] else 'Life Reset sprint task'}
" +
                                 "END:VEVENT
")
            ics_multi.append("END:VCALENDAR
")
            ics_data = "".join(ics_multi)
            st.download_button("Download .ics for sprint (all tasks)", data=ics_data, file_name="life_reset_sprint.ics", mime="text/calendar")

            # Shareable sprint summary
            sprint_summary = "Life Reset — Sprint

" + "
".join([f"{i+1}. {b['title']} — {b['start'].strftime('%I:%M %p')} to {b['end'].strftime('%I:%M %p')}" for i,b in enumerate(blocks)])
            st.text_area("Copy/paste sprint summary", sprint_summary, height=140)
else:
    st.info("Add tasks to get suggestions.")

st.caption("MVP v2: Email/text summary and .ics export. Future: push notifications, scheduled emails, and calendar sync.")
