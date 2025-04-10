@echo off
:: 替换为你的sqllite3.exe路径
set sqlite_path="E:\develop\sqlite\sqlite3.exe"
set db_file="ProductMonitor.db"
set sql_file="./init_sqlite.sql"

echo Initializing SQLite database...

if not exist "%sqlite_path%" (
    echo SQLite3.exe not found. Please check the path.
    exit /b 1
)

if not exist "%sql_file%" (
    echo SQL script file not found.
    exit /b 1
)

"%sqlite_path%" "%db_file%" < "%sql_file%"

echo SQLite database initialization completed.
pause
