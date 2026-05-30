@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 激活虚拟环境
call .venv\Scripts\activate.bat

:: 如果没有参数，默认显示用法
if "%~1"=="" (
    python src/main.py
) else (
    python src/main.py %*
)

:: 保持窗口打开
echo.
echo 按任意键关闭...
pause >nul
