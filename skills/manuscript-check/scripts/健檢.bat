@echo off
rem Drag one or more .docx files onto this file to run the manuscript check.
rem Python lookup order: PYTHON_EXE env var, py launcher, python on PATH.
chcp 65001 >nul
setlocal
set "HERE=%~dp0"
set "PY="

if defined PYTHON_EXE (
  "%PYTHON_EXE%" -c "import docx, openpyxl, lxml" >nul 2>nul && set PY="%PYTHON_EXE%"
)
if not defined PY (
  py -3 -c "import docx, openpyxl, lxml" >nul 2>nul && set "PY=py -3"
)
if not defined PY (
  python -c "import docx, openpyxl, lxml" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python with python-docx, openpyxl and lxml was not found. See 使用說明.md in this folder.
  pause
  exit /b 1
)

if "%~1"=="" (
  echo Drag .docx files onto this .bat file.
  pause
  exit /b 1
)

%PY% "%HERE%稿件健檢.py" %*
echo.
pause
