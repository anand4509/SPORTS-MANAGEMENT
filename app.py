from pathlib import Path
import uuid
import streamlit as st
import time
import pandas as pd
import plotly.express as px
from ui_theme import apply_theme, render_theme_controls
from datetime import date, timedelta
from database import init_db, query_df, execute, get_connection
from auth import (
    user_count, create_first_admin, authenticate, add_user,
    list_users, set_user_active, change_password, password_policy_errors
)
from reports import make_pdf_report

st.set_page_config(page_title="Sports Coordinator", page_icon="🏆", layout="wide")
theme_colors = render_theme_controls()
apply_theme(theme_colors)

# Basic login throttling for the current Streamlit session.
if "login_failures" not in st.session_state:
    st.session_state.login_failures = 0
if "login_blocked_until" not in st.session_state:
    st.session_state.login_blocked_until = 0
if "user" not in st.session_state:
    st.session_state.user = None

SESSION_TIMEOUT_SECONDS = 1800  # 30 minutes of inactivity
if st.session_state.get("user") is not None:
    last_activity = st.session_state.get("last_activity", time.time())
    if time.time() - last_activity > SESSION_TIMEOUT_SECONDS:
        st.session_state.user = None
        st.session_state.pop("last_activity", None)
        st.warning("Your session expired after 30 minutes of inactivity. Please sign in again.")
        st.stop()
    st.session_state.last_activity = time.time()

try:
    init_db()
except Exception as e:
    st.title("🏆 Sports Coordinator Management System")
    st.error("Could not connect to MySQL. Check MySQL service and .streamlit/secrets.toml.")
    st.code(str(e))
    st.stop()

if user_count() == 0:
    st.title("🔐 Initial Admin Setup")
    st.warning("Create the first administrator account. This setup is disabled after the first account exists.")
    with st.form("initial_admin_form"):
        username = st.text_input("Admin username")
        password = st.text_input("Password (minimum 12 characters)", type="password")
        confirm = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create first admin")
        st.caption("Password rules: at least 8 characters, uppercase and lowercase letters, a number, and a symbol. A longer passphrase is strongly recommended.")
        if submitted:
            if password != confirm:
                st.error("Passwords do not match.")
            else:
                try:
                    create_first_admin(username, password)
                    st.success("Admin account created. Sign in below.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    st.stop()

if st.session_state.user is None:
    st.title("🔐 Sports Coordinator Login")
    st.caption("Sign in with an account created by the administrator.")
    if st.session_state.login_failures >= 5:
        st.error("Too many failed attempts in this session. Reloading the app will not necessarily reset server-side controls; contact your admin if access remains blocked.")
        st.stop()
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login", type="primary")
        if submitted:
            user = authenticate(username, password)
            if user:
                st.session_state.user = user
                st.session_state.last_activity = time.time()
                st.session_state.login_failures = 0
                st.rerun()
            else:
                st.session_state.login_failures += 1
                st.error("Invalid username or password, or the account is inactive.")
    st.info("Use a unique password. Never reuse your college, email, or personal account password.")
    st.stop()

user = st.session_state.user
role = user["role"]

with st.sidebar:
    st.title("🏆 Sports Coordinator")
    st.write(f"Signed in: **{user['username']}**")
    st.caption(f"Role: {role}")
    st.divider()
    available_pages = ["Dashboard", "Players", "Events", "Attendance", "Achievements", "Reports", "My Account"]
    if role == "Admin":
        available_pages.append("User Management")
    page = st.radio("Navigation", available_pages)
    if st.button("Log out"):
        st.session_state.user = None
        st.session_state.pop("last_activity", None)
        st.rerun()

# Role access: Secretary can view/report; Coordinator manages sports records; Admin manages all.
view_only = role == "Secretary"
if view_only and page in ["Players", "Events", "Attendance", "Achievements"]:
    st.error("Your Secretary role is read-only. Use Dashboard or Reports.")
    st.stop()

def load_players():
    return query_df("""SELECT id,enrollment,name,department,sport,team_name,phone,
        selection_status,created_at FROM players ORDER BY name""")

def load_events():
    return query_df("""SELECT id,event_name,sport,event_date,venue,status,result,notes
        FROM events ORDER BY event_date DESC,id DESC""")

def load_achievements(start=None, end=None):
    if start and end:
        return query_df("""SELECT achievement_date,player_name,sport,achievement,competition,notes
            FROM achievements WHERE achievement_date BETWEEN %s AND %s
            ORDER BY achievement_date DESC""", (start,end))
    return query_df("""SELECT achievement_date,player_name,sport,achievement,competition,notes
        FROM achievements ORDER BY achievement_date DESC""")

if page == "Dashboard":
    players, events, achievements = load_players(), load_events(), load_achievements()
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Registered players",len(players))
    c2.metric("Sports events",len(events))
    c3.metric("Completed events",int((events["status"]=="Completed").sum()) if not events.empty else 0)
    c4.metric("Achievements",len(achievements))
    left,right = st.columns(2)
    with left:
        st.subheader("Players by sport")
        if not players.empty:
            counts=players.groupby("sport",as_index=False).size()
            st.plotly_chart(px.bar(counts,x="sport",y="size",labels={"size":"Players","sport":"Sport"}),use_container_width=True)
        else: st.info("Add players to see charts.")
    with right:
        st.subheader("Events by status")
        if not events.empty:
            counts=events.groupby("status",as_index=False).size()
            st.plotly_chart(px.pie(counts,names="status",values="size",hole=.45),use_container_width=True)
        else: st.info("Add events to see charts.")
    st.subheader("Upcoming events")
    upcoming=events[events["event_date"].astype(str)>=date.today().isoformat()] if not events.empty else events
    st.dataframe(upcoming.head(10),use_container_width=True,hide_index=True)
    st.subheader("Recent achievements")
    st.dataframe(achievements.head(10),use_container_width=True,hide_index=True)

elif page == "Players":
    st.subheader("Register a player")
    with st.form("player_form",clear_on_submit=True):
        c1,c2=st.columns(2)
        enrollment=c1.text_input("Enrollment number *").strip()
        name=c2.text_input("Full name *").strip()
        department=c1.text_input("Department *").strip()
        sport=c2.selectbox("Sport",["Cricket","Football","Basketball","Badminton","Volleyball","Athletics","Kabaddi","Other"])
        team_name=c1.text_input("Team name").strip()
        phone=c2.text_input("Phone (optional)").strip()
        selection=st.selectbox("Selection status",["Trial","Selected","Reserve","Not Selected"])
        submitted=st.form_submit_button("Save player")
        if submitted:
            if not enrollment or not name or not department: st.error("Enrollment, name, and department are required.")
            else:
                try:
                    execute("""INSERT INTO players(enrollment,name,department,sport,team_name,phone,selection_status)
                        VALUES(%s,%s,%s,%s,%s,%s,%s)""",(enrollment,name,department,sport,team_name,phone,selection))
                    st.success("Player saved."); st.rerun()
                except Exception as e: st.error("Could not save player; check duplicate enrollment number."); st.code(str(e))
    players=load_players()
    st.dataframe(players,use_container_width=True,hide_index=True)
    if not players.empty:
        st.download_button("Download players CSV",players.to_csv(index=False).encode("utf-8-sig"),"players.csv","text/csv")
        with st.expander("Delete a player (Admin only)"):
            if role != "Admin": st.warning("Only Admin can delete players.")
            else:
                choices={f'{r["enrollment"]} — {r["name"]} (ID {r["id"]})':int(r["id"]) for _,r in players.iterrows()}
                label=st.selectbox("Select player",list(choices))
                if st.button("Delete player"):
                    execute("DELETE FROM players WHERE id=%s",(choices[label],))
                    st.success("Player deleted."); st.rerun()

elif page == "Events":
    st.subheader("Create a sports event")
    with st.form("event_form",clear_on_submit=True):
        event_name=st.text_input("Event name *").strip()
        sport=st.selectbox("Sport",["Cricket","Football","Basketball","Badminton","Volleyball","Athletics","Kabaddi","Other"])
        event_date=st.date_input("Event date",value=date.today())
        venue=st.text_input("Venue").strip()
        status=st.selectbox("Status",["Planned","Ongoing","Completed","Postponed","Cancelled"])
        result=st.text_input("Result / score").strip()
        notes=st.text_area("Notes").strip()
        if st.form_submit_button("Save event"):
            if not event_name: st.error("Event name is required.")
            else:
                execute("""INSERT INTO events(event_name,sport,event_date,venue,status,result,notes)
                    VALUES(%s,%s,%s,%s,%s,%s,%s)""",(event_name,sport,event_date,venue,status,result,notes))
                st.success("Event saved."); st.rerun()
    events=load_events()
    st.dataframe(events,use_container_width=True,hide_index=True)
    if not events.empty:
        st.download_button("Download events CSV",events.to_csv(index=False).encode("utf-8-sig"),"events.csv","text/csv")
        with st.expander("Update event status/result"):
            event_map={f'{r["event_date"]} — {r["event_name"]} (ID {r["id"]})':r for _,r in events.iterrows()}
            label=st.selectbox("Choose event",list(event_map)); chosen=event_map[label]
            statuses=["Planned","Ongoing","Completed","Postponed","Cancelled"]
            new_status=st.selectbox("New status",statuses,index=statuses.index(chosen["status"]))
            new_result=st.text_input("Update result",value=str(chosen["result"] or ""))
            if st.button("Update event"):
                execute("UPDATE events SET status=%s,result=%s WHERE id=%s",(new_status,new_result.strip(),int(chosen["id"])))
                st.success("Event updated."); st.rerun()

elif page == "Attendance":
    st.subheader("Record attendance")
    players,events=load_players(),load_events()
    if players.empty: st.info("Add players first.")
    else:
        p_opts={f'{r["enrollment"]} — {r["name"]} ({r["sport"]})':int(r["id"]) for _,r in players.iterrows()}
        e_opts={"Training / general attendance":None}
        if not events.empty: e_opts.update({f'{r["event_date"]} — {r["event_name"]} (ID {r["id"]})':int(r["id"]) for _,r in events.iterrows()})
        with st.form("attendance_form",clear_on_submit=True):
            pl=st.selectbox("Player",list(p_opts)); ev=st.selectbox("Event",list(e_opts))
            ad=date.today(); ad=st.date_input("Attendance date",value=ad)
            status=st.selectbox("Attendance status",["Present","Absent","Late","Excused"])
            notes=st.text_input("Notes")
            if st.form_submit_button("Save attendance"):
                try:
                    execute("""INSERT INTO attendance(player_id,event_id,attendance_date,status,notes)
                        VALUES(%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE status=VALUES(status),notes=VALUES(notes)""",
                        (p_opts[pl],e_opts[ev],ad,status,notes.strip()))
                    st.success("Attendance saved."); st.rerun()
                except Exception as e: st.error("Could not save attendance."); st.code(str(e))
    att=query_df("""SELECT a.id,a.attendance_date,p.enrollment,p.name,p.sport,e.event_name,a.status,a.notes
        FROM attendance a JOIN players p ON p.id=a.player_id LEFT JOIN events e ON e.id=a.event_id
        ORDER BY a.attendance_date DESC,a.id DESC""")
    st.dataframe(att,use_container_width=True,hide_index=True)
    if not att.empty: st.download_button("Download attendance CSV",att.to_csv(index=False).encode("utf-8-sig"),"attendance.csv","text/csv")


elif page == "Achievements":
    st.subheader("Record an achievement")
    st.caption("Attach certificates, award documents, photos, or other supporting files.")

    players = load_players()
    p_opts = {"External / team achievement": None}

    if not players.empty:
        p_opts.update({
            f'{r["enrollment"]} — {r["name"]}': int(r["id"])
            for _, r in players.iterrows()
        })

    allowed_extensions = {
        ".pdf", ".doc", ".docx", ".xml",
        ".jpg", ".jpeg", ".png"
    }
    max_file_size = 10 * 1024 * 1024  # 10 MB per file

    upload_dir = Path(__file__).resolve().parent / "achievement_uploads"

    with st.form("achievement_form", clear_on_submit=True):
        pl = st.selectbox("Linked player (optional)", list(p_opts))
        player_name = st.text_input("Player or team name *").strip()

        sport_options = [
            "Cricket", "Football", "Basketball", "Badminton",
            "Volleyball", "Athletics", "Kabaddi", "Other"
        ]
        sport = st.selectbox("Sport", sport_options)

        achievement = st.text_input("Achievement *").strip()
        competition = st.text_input("Competition / tournament").strip()
        achievement_date = st.date_input(
            "Achievement date", value=date.today()
        )
        notes = st.text_area("Notes")

        uploaded_files = st.file_uploader(
            "Upload certificates / photos / documents",
            type=[
                "pdf", "doc", "docx", "xml",
                "jpg", "jpeg", "png"
            ],
            accept_multiple_files=True,
            help="Allowed: PDF, DOC, DOCX, XML, JPG, JPEG, PNG. "
                 "Maximum 10 MB per file."
        )

        submitted = st.form_submit_button("Save achievement")

        if submitted:
            if not player_name or not achievement:
                st.error("Player/team name and achievement are required.")

            elif any(
                Path(f.name).suffix.lower() not in allowed_extensions
                for f in uploaded_files
            ):
                st.error("One or more files have an unsupported extension.")

            elif any(f.size > max_file_size for f in uploaded_files):
                st.error("Each uploaded file must be 10 MB or smaller.")

            else:
                try:
                    achievement_id = execute(
                        """
                        INSERT INTO achievements (
                            player_id, player_name, sport, achievement,
                            competition, achievement_date, notes
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            p_opts[pl], player_name, sport, achievement,
                            competition, achievement_date, notes.strip()
                        )
                    )

                    upload_dir.mkdir(parents=True, exist_ok=True)

                    for uploaded in uploaded_files:
                        extension = Path(uploaded.name).suffix.lower()
                        stored_name = f"{uuid.uuid4().hex}{extension}"
                        target = upload_dir / stored_name

                        target.write_bytes(uploaded.getvalue())

                        try:
                            execute(
                                """
                                INSERT INTO achievement_files (
                                    achievement_id, original_filename,
                                    stored_filename, file_path, file_type
                                )
                                VALUES (%s, %s, %s, %s, %s)
                                """,
                                (
                                    achievement_id,
                                    Path(uploaded.name).name,
                                    stored_name,
                                    str(target),
                                    extension
                                )
                            )
                        except Exception:
                            target.unlink(missing_ok=True)
                            raise

                    st.success(
                        f"Achievement saved with {len(uploaded_files)} "
                        "attached file(s)."
                    )
                    st.rerun()

                except Exception as e:
                    st.error("Could not save the achievement or its files.")
                    st.code(str(e))

    st.subheader("Saved achievements")

    achievements = load_achievements()
    st.dataframe(
        achievements,
        use_container_width=True,
        hide_index=True
    )

    if not achievements.empty:
        st.download_button(
            "Download achievements CSV",
            achievements.to_csv(index=False).encode("utf-8-sig"),
            "achievements.csv",
            "text/csv"
        )

    st.subheader("Certificates and uploaded files")

    files_df = query_df("""
        SELECT
            f.id,
            a.player_name,
            a.achievement,
            f.original_filename,
            f.file_type,
            f.file_path,
            f.uploaded_at
        FROM achievement_files f
        JOIN achievements a ON a.id = f.achievement_id
        ORDER BY f.uploaded_at DESC
    """)

    if files_df.empty:
        st.info("No achievement files have been uploaded yet.")
    else:
        for _, file_row in files_df.iterrows():
            with st.container(border=True):
                st.write(f'**{file_row["original_filename"]}**')
                st.caption(
                    f'{file_row["player_name"]} — '
                    f'{file_row["achievement"]} '
                    f'({file_row["file_type"]})'
                )

                file_path = Path(file_row["file_path"])

                if file_path.is_file():
                    st.download_button(
                        label="Download file",
                        data=file_path.read_bytes(),
                        file_name=file_row["original_filename"],
                        key=f'achievement_file_{file_row["id"]}'
                    )
                else:
                    st.warning(
                        "The file is missing from the upload folder."
                    )

    st.subheader("Record an achievement")
    players=load_players()
    p_opts={"External / team achievement":None}
    if not players.empty: p_opts.update({f'{r["enrollment"]} — {r["name"]}':int(r["id"]) for _,r in players.iterrows()})
    with st.form("achievement_upload_form", clear_on_submit=True):
        pl=st.selectbox("Linked player (optional)",list(p_opts))
        player_name=st.text_input("Player or team name *").strip()
        sport=st.selectbox("Sport",["Cricket","Football","Basketball","Badminton","Volleyball","Athletics","Kabaddi","Other"])
        achievement=st.text_input("Achievement *").strip()
        competition=st.text_input("Competition / tournament").strip()
        achievement_date=st.date_input("Achievement date",value=date.today())
        notes=st.text_area("Notes")
        if st.form_submit_button("Save achievement"):
            if not player_name or not achievement: st.error("Player/team name and achievement are required.")
            else:
                execute("""INSERT INTO achievements(player_id,player_name,sport,achievement,competition,achievement_date,notes)
                    VALUES(%s,%s,%s,%s,%s,%s,%s)""",(p_opts[pl],player_name,sport,achievement,competition,achievement_date,notes.strip()))
                st.success("Achievement saved."); st.rerun()
    achievements=load_achievements()
    st.dataframe(achievements,use_container_width=True,hide_index=True)
    if not achievements.empty:
     st.download_button(
        "Download achievements CSV",
        achievements.to_csv(index=False).encode("utf-8-sig"),
        "achievements.csv",
        "text/csv",
        key="achievements_csv_download"
    )

elif page == "Reports":
    st.subheader("Secretary report")
    today=date.today(); c1,c2=st.columns(2)
    start_date=c1.date_input("Start date",value=today-timedelta(days=30))
    end_date=c2.date_input("End date",value=today)
    if start_date>end_date: st.error("Start date must be on or before end date."); st.stop()
    events_period=query_df("""SELECT event_date,event_name,sport,venue,status,result FROM events
        WHERE event_date BETWEEN %s AND %s ORDER BY event_date""",(start_date,end_date))
    achievements_period=query_df("""SELECT achievement_date,player_name,sport,achievement,competition,notes
        FROM achievements WHERE achievement_date BETWEEN %s AND %s ORDER BY achievement_date DESC""",(start_date,end_date))
    attendance_period=query_df("SELECT status FROM attendance WHERE attendance_date BETWEEN %s AND %s",(start_date,end_date))
    summary={
        "Total registered players":len(load_players()),
        "Events in reporting period":len(events_period),
        "Completed events in period":int((events_period["status"]=="Completed").sum()) if not events_period.empty else 0,
        "Achievements in period":len(achievements_period),
        "Attendance records in period":len(attendance_period),
        "Present attendance records":int((attendance_period["status"]=="Present").sum()) if not attendance_period.empty else 0
    }
    for k,v in summary.items(): st.write(f"**{k}:** {v}")
    pdf=make_pdf_report(summary,events_period,achievements_period,start_date,end_date)
    st.download_button("📄 Download Secretary PDF report",pdf,f"sports_report_{start_date}_{end_date}.pdf","application/pdf",type="primary")
    st.download_button("Download events CSV",events_period.to_csv(index=False).encode("utf-8-sig"),f"events_{start_date}_{end_date}.csv","text/csv")
    st.download_button("Download achievements CSV",achievements_period.to_csv(index=False).encode("utf-8-sig"),f"achievements_{start_date}_{end_date}.csv","text/csv")

elif page == "My Account":
    st.subheader("Change your password")
    st.info("Password tip: a unique 14–16+ character passphrase is stronger and easier to remember than a short complex password.")
    with st.form("change_password_form"):
        old=st.text_input("Current password",type="password")
        new=st.text_input("New password (8+ characters with upper/lowercase, number and symbol)",type="password")
        confirm=st.text_input("Confirm new password",type="password")
        if st.form_submit_button("Change password"):
            if new != confirm: st.error("New passwords do not match.")
            else:
                try:
                    change_password(user["id"],old,new)
                    st.success("Password changed. Please log out and sign in again.")
                except Exception as e: st.error(str(e))

elif page == "User Management" and role == "Admin":
    st.subheader("User management")
    st.caption("Create accounts for Coordinators and Secretaries. Give Admin access only when necessary.")
    with st.form("add_user_form",clear_on_submit=True):
        username=st.text_input("Username (4–60 characters)")
        password=st.text_input("Temporary password (8+ characters; stronger is better)",type="password")
        confirm=st.text_input("Confirm password",type="password")
        new_role=st.selectbox("Role",["Coordinator","Secretary","Admin"])
        if st.form_submit_button("Create user"):
            if password!=confirm: st.error("Passwords do not match.")
            else:
                try:
                    add_user(username,password,new_role)
                    st.success("User created. Share credentials securely and ask the user to change their password.")
                    st.rerun()
                except Exception as e: st.error(f"Could not create user: {e}")
    st.subheader("Existing accounts")
    users=list_users()
    st.dataframe(pd.DataFrame(users),use_container_width=True,hide_index=True)
    for item in users:
        with st.container(border=True):
            c1,c2,c3=st.columns([3,2,2])
            c1.write(f'**{item["username"]}** — {item["role"]}')
            c2.write("Active" if item["active"] else "Disabled")
            if item["id"] != user["id"]:
                if item["active"] and c3.button("Disable",key=f'disable_{item["id"]}'):
                    set_user_active(item["id"],False); st.rerun()
                elif not item["active"] and c3.button("Enable",key=f'enable_{item["id"]}'):
                    set_user_active(item["id"],True); st.rerun()

st.caption("Security note: use HTTPS and institutional approval before deployment. Keep secrets private and back up MySQL.")
