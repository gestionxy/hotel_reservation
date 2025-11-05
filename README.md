# 房间预定与空置展示（Streamlit Cloud 子目录部署版）

## 目录结构
```
hotel_reservation/
├─ app.py
├─ requirements.txt
├─ runtime.txt
└─ .streamlit/
   └─ secrets.toml.example
```

> 在 Streamlit Cloud 上把 **Main file path** 设为：`hotel_reservation/app.py`

## 云端部署步骤（Streamlit Community Cloud）
1. 将整个仓库（含 `hotel_reservation/`）推到 GitHub。
2. 打开 https://share.streamlit.io → New app → 选择你的仓库。
3. 在 **Advanced settings** 或 App 设置中确认 **Main file path** 为：`hotel_reservation/app.py`。
4. App 页面右上角 **⋯ → Settings → Secrets**，粘贴（替换自己的值）：
   ```toml
   [db]
   driver="postgresql+psycopg2"
   host="db.jkefdvhhfnxpzlglmnvg.supabase.co"
   port="5432"
   database="postgres"
   user="postgres"
   password="YOUR_DATABASE_PASSWORD"
   sslmode="require"
   ```
5. 回到 App 页面，**Rerun**。

## 功能
- 无侧边栏。
- 预约日期必须 ≥ 今天；开始时间固定为 **12:00–20:00，每 15 分钟一档**；时长：30/45/60/90/120。
- 预约后自动加 **+30 分钟清洁** 并参与冲突校验（预约段与清洁段均纳入占用）。
- “预约记录”：展示 **从今天开始** 的全部记录。
- “历史记录”：展示 **昨天及更早** 的记录（折叠）。
- “时间轴”：按天展示（默认今天），范围固定 **12:00–20:00**，悬停显示预定/清洁详情。

## 本地运行（可选）
```bash
cd hotel_reservation
pip install -r requirements.txt
streamlit run app.py
```
若未配置 Secrets，本地将自动使用 `data/bookings.db` 的 SQLite（仅本地持久）。
