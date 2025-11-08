@echo off
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt
flask initdb
echo Setup complete! Run: flask run
pause
