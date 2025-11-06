
import os
from pathlib import Path
from datetime import datetime, date, time, timedelta

import pandas as pd
import streamlit as st
import plotly.express as px

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from pathlib import Path

from sqlalchemy import create_engine, text


# =============================
# 基本配置（根据你的需求）
# =============================
ROOMS = ["101", "102"]
ALLOWED_DURS = [30, 45, 60, 90, 120]  # 分钟
CLEANING_MIN = 30

START_TIME = time(12, 0)  # 固定 12:00
END_TIME   = time(20, 0)  # 固定 20:00
TIME_STEP_MIN = 15        # 15分钟一档

st.set_page_config(page_title="房间预定管理", layout="wide")

#st.write("driver:", st.secrets["db"]["driver"])
#st.write("host:", st.secrets["db"]["host"])
#st.write("user:", st.secrets["db"]["user"])

# =============================
# 数据库引擎：优先 Secrets 的 Postgres；否则本地 SQLite
# 并包含：连接自检 + 方言区分建表
# =============================

@st.cache_resource(show_spinner=False)
def get_engine():
    # 1) 构造连接（优先云端 Postgres；无 secrets 则本地 SQLite）
    if "db" in st.secrets:
        s = st.secrets["db"]
        driver = s.get("driver", "postgresql+psycopg")  # ← 默认走 psycopg
        url = URL.create(
            drivername=driver,
            username=s["user"],
            password=s["password"],
            host=s["host"],
            port=int(str(s.get("port", "5432"))),
            database=s["database"],
        )
        # psycopg v3：SSL 用 sslmode 即可
        connect_args = {"sslmode": s.get("sslmode", "require")}
        engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)

    else:
        # 本地回退：SQLite（云端会丢失，仅本地调试用）
        base_dir = Path(__file__).resolve().parent
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{data_dir / 'bookings.db'}", pool_pre_ping=True)

    # 2) 连接自检（通过则继续；失败就提示并中止）
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        st.caption(f"✅ 数据库连接正常：{engine.dialect.name} / driver={engine.url.drivername}")
    except Exception as e:
        st.error("❌ 数据库连接失败：请检查 Secrets（driver/host/port/database/user/password/SSL）。")
        if "db" in st.secrets:
            s = st.secrets["db"]
            st.caption(f"driver={s.get('driver')} host={s.get('host')} port={s.get('port')} db={s.get('database')} user={s.get('user')}")
        # 打印错误类型与简要信息（不包含密码）
        st.caption(f"hint: {type(e).__name__}: {getattr(e, 'args', [''])[0]}")
        st.stop()


    # 3) 初始化表结构（Postgres/SQLite 兼容）
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS bookings(
                    id BIGSERIAL PRIMARY KEY,
                    room TEXT NOT NULL,
                    start_ts TIMESTAMP NOT NULL,
                    end_ts TIMESTAMP NOT NULL,
                    clean_end_ts TIMESTAMP NOT NULL,
                    duration_min INTEGER NOT NULL,
                    customer TEXT,
                    note TEXT,
                    status TEXT DEFAULT 'booked',
                    created_at TIMESTAMP
                );
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bookings_room_start ON bookings (room, start_ts);"))
        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS bookings(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT NOT NULL,
                    start_ts TEXT NOT NULL,
                    end_ts TEXT NOT NULL,
                    clean_end_ts TEXT NOT NULL,
                    duration_min INTEGER NOT NULL,
                    customer TEXT,
                    note TEXT,
                    status TEXT DEFAULT 'booked',
                    created_at TEXT
                );
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bookings_room_start ON bookings (room, start_ts);"))

    return engine

# 使用
engine = get_engine()


# =============================
# 工具函数
# =============================
def combine(d: date, t: time) -> datetime:
    return datetime.combine(d, t)

def gen_time_slots(start_t: time, end_t: time, step_min: int = 15):
    base = datetime(2000,1,1, start_t.hour, start_t.minute)
    end  = datetime(2000,1,1, end_t.hour, end_t.minute)
    cur = base
    slots = []
    while cur <= end:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return slots

TIME_SLOTS = gen_time_slots(START_TIME, END_TIME, TIME_STEP_MIN)

def within_business(start_dt: datetime, clean_end_dt: datetime) -> bool:
    # 起点 >= 12:00，清洁结束 <= 20:00（同一天内）
    s_ok = START_TIME <= start_dt.time() <= END_TIME
    e_ok = START_TIME <= clean_end_dt.time() <= END_TIME
    return (start_dt.date() == clean_end_dt.date()) and s_ok and e_ok

def overlap(a_start, a_end, b_start, b_end) -> bool:
    # 半开区间重叠判定
    return (a_start < b_end) and (b_start < a_end)



def query_between(s, e, room: str | None = None):
    params = {"s": s, "e": e}
    sql = "SELECT * FROM bookings WHERE status='booked' AND start_ts>=:s AND start_ts<:e"
    if room:
        sql += " AND room=:room"
        params["room"] = room

    stmt = text(sql)  # ← 包成 text()，让 SQLAlchemy 负责绑定 :s/:e/:room
    df = pd.read_sql(stmt, engine, params=params)
    if not df.empty:
        for c in ["start_ts", "end_ts", "clean_end_ts", "created_at"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c])
    return df


def query_day(d: date, room: str | None = None):
    d0 = pd.Timestamp(d).normalize()
    d1 = d0 + pd.Timedelta(days=1)
    return query_between(d0, d1, room)

def query_upcoming_from_today(room: str | None = None):
    today0 = pd.Timestamp(date.today()).normalize()
    far = today0 + pd.Timedelta(days=365*3)
    return query_between(today0, far, room)

def query_history_before_today():
    today0 = pd.Timestamp(date.today()).normalize()
    sql = "SELECT * FROM bookings WHERE start_ts<:t0 ORDER BY start_ts DESC LIMIT 200"
    stmt = text(sql)  # ★ 必须：用 text() 包装
    df = pd.read_sql(stmt, engine, params={"t0": today0})
    if not df.empty:
        for c in ["start_ts", "end_ts", "clean_end_ts", "created_at"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c])
    return df


def conflicts(room: str, start_dt: datetime, clean_end_dt: datetime, exclude_id: int | None = None):
    df = query_day(start_dt.date(), room)
    if df.empty:
        return df
    if exclude_id is not None:
        df = df[df["id"] != exclude_id]
    mask = df.apply(lambda r: overlap(start_dt, clean_end_dt, r["start_ts"], r["clean_end_ts"]), axis=1)
    return df[mask]

def insert_booking(room: str, start_dt: datetime, duration_min: int, customer: str, note: str):
    end_dt = start_dt + timedelta(minutes=duration_min)
    clean_end_dt = end_dt + timedelta(minutes=CLEANING_MIN)

    # 业务规则
    if start_dt.date() < date.today():
        return False, "预约日期必须为今天或之后。"
    if duration_min not in ALLOWED_DURS:
        return False, "时长不在允许范围。"
    if not within_business(start_dt, clean_end_dt):
        return False, "预约需在 12:00 之后开始，且清洁结束不晚于 20:00。"

    cfs = conflicts(room, start_dt, clean_end_dt)
    if not cfs.empty:
        return False, "与现有预约或清洁冲突。"

    sql = """
    INSERT INTO bookings(room, start_ts, end_ts, clean_end_ts, duration_min, customer, note, created_at)
    VALUES (:room, :start_ts, :end_ts, :clean_end_ts, :duration_min, :customer, :note, :created_at)
    """
    with engine.begin() as conn:
        conn.execute(text(sql), dict(
            room=room,
            start_ts=start_dt,
            end_ts=end_dt,
            clean_end_ts=clean_end_dt,
            duration_min=int(duration_min),
            customer=customer,
            note=note,
            created_at=datetime.now()
        ))
    return True, "创建成功。"

def delete_booking(row_id: int):
    with engine.begin() as conn:
        conn.execute(text("UPDATE bookings SET status='cancelled' WHERE id=:id"), {"id": row_id})


# =============================
# 页面：无侧边栏
# =============================
#st.markdown("## 🏨 房间预定管理")

# ---- 创建预定表单 ----
# st.markdown("### 📋 创建预定")
# col1, col2, col3, col4 = st.columns([1,1,1,2])
# with col1:
#     room = st.selectbox("房间号", ROOMS, index=0)
# with col2:
#     min_date = date.today()
#     book_date = st.date_input("预约日期", value=min_date, min_value=min_date)
# with col3:
#     start_slot = st.selectbox("开始时间", gen_time_slots(START_TIME, END_TIME, TIME_STEP_MIN), index=0)
# with col4:
#     dur = st.selectbox("预约时长", ALLOWED_DURS, index=ALLOWED_DURS.index(60))

# col5, col6 = st.columns([1,3])
# with col5:
#     customer = st.text_input("预定人（可空）", value="")
# with col6:
#     note = st.text_input("备注（可空）", value="")

# if st.button("✅ 创建预定"):
#     hh, mm = map(int, start_slot.split(":"))
#     start_dt = datetime.combine(book_date, time(hh, mm))
#     ok, msg = insert_booking(room, start_dt, int(dur), customer.strip(), note.strip())
#     (st.success if ok else st.error)(msg)
st.markdown("## 🏨 房间预定管理")

# ---- 侧边栏 · 创建预定表单 ----
st.sidebar.markdown("### 📋 创建预定")

room = st.sidebar.selectbox("房间号", ROOMS, index=0)

min_date = date.today()
book_date = st.sidebar.date_input("预约日期", value=min_date, min_value=min_date)

start_slot = st.sidebar.selectbox(
    "开始时间",
    gen_time_slots(START_TIME, END_TIME, TIME_STEP_MIN),
    index=0
)

dur = st.sidebar.selectbox(
    "预约时长（分钟）",
    ALLOWED_DURS,
    index=ALLOWED_DURS.index(60)
)

customer = st.sidebar.text_input("预定人（可空）", value="")
note = st.sidebar.text_input("备注（可空）", value="")

if st.sidebar.button("✅ 创建预定", use_container_width=True):
    hh, mm = map(int, start_slot.split(":"))
    start_dt = datetime.combine(book_date, time(hh, mm))
    ok, msg = insert_booking(room, start_dt, int(dur), customer.strip(), note.strip())
    (st.sidebar.success if ok else st.sidebar.error)(msg)






st.markdown("---")

# ---- 预约记录（从今天开始） ----
st.markdown("### 📅 预约记录")
df_upcoming = query_upcoming_from_today()
if df_upcoming.empty:
    st.info("从今天开始暂无预约记录。")
else:
    show = df_upcoming[["id","room","start_ts","end_ts","clean_end_ts","duration_min","customer","note","status"]].copy()
    show = show.rename(columns={
        "id":"ID","room":"房间","start_ts":"开始","end_ts":"结束","clean_end_ts":"清洁结束",
        "duration_min":"时长(分)","customer":"预定人","note":"备注","status":"状态"
    })
    st.dataframe(show, use_container_width=True, hide_index=True)

# ---- 撤销 ----
st.markdown("### 🗑️ 撤销预定")
colx, coly = st.columns([3,1])
with colx:
    del_id = st.number_input("输入要撤销的 ID（状态将置为 cancelled）", min_value=0, step=1, value=0)
with coly:
    if st.button("撤销"):
        if del_id > 0:
            delete_booking(int(del_id))
            st.success(f"ID {del_id} 已撤销。点击右上角 Rerun 刷新。")
        else:
            st.error("请输入有效的 ID。")

# ---- 历史记录（昨天及更早） ----
st.markdown("### 🗄️ 历史记录（昨天及更早）")
with st.expander("展开查看历史记录"):
    df_hist = query_history_before_today()
    if df_hist.empty:
        st.write("无历史记录。")
    else:
        show_h = df_hist[["id","room","start_ts","end_ts","clean_end_ts","duration_min","customer","note","status"]].copy()
        show_h = show_h.rename(columns={
            "id":"ID","room":"房间","start_ts":"开始","end_ts":"结束","clean_end_ts":"清洁结束",
            "duration_min":"时长(分)","customer":"预定人","note":"备注","status":"状态"
        })
        st.dataframe(show_h, use_container_width=True, hide_index=True)


st.markdown("---")

# ---- 时间轴（按天） ----
st.markdown("### ⏱️ 时间轴（按天）")
day_sel = st.date_input("选择日期（用于时间轴查看）", value=date.today())

df_day = query_day(day_sel)
timeline_rows = []
if not df_day.empty:
    for _, r in df_day.iterrows():
        # 预约段
        timeline_rows.append(dict(
            房间=r["room"], 开始=r["start_ts"], 结束=r["end_ts"], 状态="预定",
            详情=f"预定：{r['start_ts'].strftime('%H:%M')}~{r['end_ts'].strftime('%H:%M')}｜客户：{r['customer'] or ''}｜备注：{r['note'] or ''}｜ID:{r['id']}"
        ))
        # 清洁段
        timeline_rows.append(dict(
            房间=r["room"], 开始=r["end_ts"], 结束=r["clean_end_ts"], 状态="清洁",
            详情=f"清洁：{r['end_ts'].strftime('%H:%M')}~{r['clean_end_ts'].strftime('%H:%M')}｜ID:{r['id']}"
        ))

if timeline_rows:
    tl_df = pd.DataFrame(timeline_rows)
    fig = px.timeline(
        tl_df, x_start="开始", x_end="结束", y="房间", color="状态", hover_data=["详情"],
        title=f"{day_sel} 时间轴（12:00–20:00）"
    )
    x0 = combine(day_sel, START_TIME)
    x1 = combine(day_sel, END_TIME)
    fig.update_layout(xaxis=dict(range=[x0, x1]))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(f"{day_sel} 暂无记录。时间轴范围固定为 12:00–20:00。")
