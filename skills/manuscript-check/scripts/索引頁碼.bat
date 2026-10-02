@echo off
rem Drag the index term list (.txt/.csv/.xlsx) and the typeset .pdf onto this file together (any order).
rem Python lookup order: PYTHON_EXE env var, py launcher, python on PATH.
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
  echo Python with python-docx, openpyxl and pdfplumber was not found. See 使用說明.md in this folder.
  pause
  exit /b 1
)

if "%~2"=="" (
  echo Drag the term list and the .pdf onto this .bat file together.
  pause
  exit /b 1
)

%PY% "%HERE%索引頁碼.py" %*
echo.
pause
