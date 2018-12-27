@echo off

set CUR_DIR=%cd%
rem Call setting config
call "%CUR_DIR%\config.bat"

rem Destroy previus session
call "%ADB_PATH%\adb.exe" shell am force-stop %ANDROID_PACKAGE%
rem Run session
call "%ADB_PATH%\adb.exe" shell am start -n "%ANDROID_PACKAGE%/%MAIN_ACTIVITY%" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -D
