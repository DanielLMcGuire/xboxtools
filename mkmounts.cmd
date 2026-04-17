@echo off
setlocal enabledelayedexpansion

set "base_path=D:\DevelopmentFiles"

if not exist "%base_path%" mkdir "%base_path%"

echo Scanning registry for mounted devices...

for /f "tokens=3 delims=\" %%A in ('reg query "HKEY_LOCAL_MACHINE\SYSTEM\MountedDevices" ^| findstr /C:"\\DosDevices\\"') do (
    
    set "entry=%%A"
    
    set "letter=!entry:~0,1!"

    set "target=!letter!:\ "
    set "link=%base_path%\!letter!"

    if exist "!target!" (
        if not exist "!link!" (
            echo Creating junction for drive !letter!: at !link!
            mklink /J "!link!" "!target!"
        ) else (
            echo Junction for !letter!: already exists. Skipping.
        )
    )
)

echo Done.
pause