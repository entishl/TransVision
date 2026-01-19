@echo off
start powershell -NoExit -Command "& {conda activate videolingo; streamlit run E:\git\VideoLingo\st.py}"
timeout /t 5
start "" "http://localhost:8501"
