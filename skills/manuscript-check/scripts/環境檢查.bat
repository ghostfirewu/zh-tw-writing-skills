@echo off
rem Run the three test suites. All three should print ALL PASS.
chcp 65001 >nul
setlocal
set "HERE=%~dp0"
set "PY="
if defined PYTHON_EXE (
  "%PYTHON_EXE%" -c "import docx, openpyxl, pdfplumber" >nul 2>nul && set PY="%PYTHON_EXE%"
)
if not defined PY (
  py -3 -c "import docx, openpyxl, pdfplumber" >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  python -c "import docx, openpyxl, pdfplumber" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python with python-docx, openpyxl and pdfplumber was not found.
  echo Install Python 3, then run:  py -m pip install -r "%HERE%requirements.txt"
  pause
  exit /b 1
)
echo [1/3] manuscript check
%PY% "%HERE%tests\test_all.py" | findstr /C:"ALL PASS" /C:"FAIL"
echo [2/3] typeset comparison
%PY% "%HERE%tests\test_collate.py" | findstr /C:"ALL PASS" /C:"FAIL"
echo [3/3] index pages
%PY% "%HERE%tests\test_index.py" | findstr /C:"ALL PASS" /C:"FAIL"
echo.
pause
