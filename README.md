
# 房间预定与空置展示（GitHub / Streamlit Cloud 版）

本项目支持：
- 一键部署到 **Streamlit Community Cloud**（从 GitHub 仓库）
- 使用 **Supabase/Neon Postgres** 持久化；若未配置 secrets，自动回退到本地 **SQLite**
- 无侧边栏；预约日期 ≥ 今天；开始时间固定为 12:00–20:00（每 15 分钟一档）
- “预约记录”显示 **从今天开始的全部预约**；历史记录（昨天及更早）放在“历史记录”折叠区
- 时间轴按天查看，默认当天；范围固定为 **12:00–20:00**；鼠标悬停显示预定时间与信息

## 本地运行
1. 安装 Python 3.9+
2. 双击 `run.bat`（Windows）或在命令行执行：
   ```bash
   pip install -r requirements.txt
   streamlit run app.py
   ```

## GitHub + Streamlit Cloud 部署
1. 将本目录推送到 GitHub 仓库
2. 打开 https://share.streamlit.io → “New app” → 选择仓库 → 部署
3. 在 Streamlit Cloud 的 **Settings → Secrets** 设置数据库连接（可选，但推荐），格式如下：
   ```toml
   [db]
   driver   = "postgresql+psycopg2"
   host     = "YOUR_HOST"
   port     = "5432"
   database = "YOUR_DB"
   user     = "YOUR_USER"
   password = "YOUR_PASSWORD"
   sslmode  = "require"
   ```
   > 如果不配置 `secrets`，应用会自动使用本地 `data/bookings.db`（仅限你在本地运行时生效；在云端文件系统不持久，不建议）。

### 选择云数据库（推荐）
- **Supabase**（Postgres）：注册新项目，复制连接参数到 Cloud Secrets。
- **Neon**（Postgres）：适合免费层和自动休眠，复制连接参数到 Cloud Secrets。

## 使用说明
- “创建预定”：选择房间、预约日期（≥ 今天）、开始时间（15 分钟档位）、时长（30/45/60/90/120），可填写预定人和备注。
- 系统自动判定结束时间与清洁结束时间（+30 分钟），并进行冲突校验（预约段与清洁段均参与冲突）。
- “预约记录”：展示从 **今天开始** 的全部记录。
- “历史记录”：展示 **昨天及更早** 的记录（折叠区）。
- “时间轴”：按天查看 12:00–20:00 的预约与清洁时间条；鼠标悬停显示详情（时间、客户、备注、ID）。

## 结构
```
room_booking_app_github/
├─ app.py
├─ requirements.txt
├─ run.bat
├─ data/                 # 本地 SQLite 数据库目录（云端不会持久）
└─ .streamlit/
   └─ secrets.toml.example
```

## 注意
- 为保证准确与长期持久化，强烈建议配置 **Postgres**（Supabase/Neon 等）。
- 时区建议统一存储 UTC，由前端本地化；当前演示版直接使用服务器时区。
