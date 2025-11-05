@echo off
setlocal
cd /d %~dp0
echo ===== 房间预定系统（GitHub/本地运行） =====
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
pause
endlocal
