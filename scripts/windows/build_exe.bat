@echo off
setlocal

REM 在 Windows 下执行：scripts\windows\build_exe.bat

if not exist .venv (
  py -3 -m venv .venv
)
call .venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
pip install -e .

pyinstaller --clean --noconfirm packaging\cs_caller_gui.spec

echo.
echo Build done. Output: dist\cs_caller\cs_caller.exe
endlocal
