@echo off
REM Windows batch script to apply snapshots and create git commits with specified dates.
SETLOCAL ENABLEDELAYEDEXPANSION
set "ROOT=%~dp0"
set "SNAP_DIR=%ROOT%snapshots"
set "REPO_DIR=%ROOT%edu_payment_portal_repo"

if exist "%REPO_DIR%" rd /s /q "%REPO_DIR%"
mkdir "%REPO_DIR%"
cd /d "%REPO_DIR%"
git init -b main

for /f "delims=" %%S in ('dir /b /a:d "%SNAP_DIR%" ^| sort') do (
  echo Applying %%S
  robocopy "%SNAP_DIR%\%%S" "%REPO_DIR%" /MIR >nul
  REM read commit message and date from snapshots_note.txt
  set "CM="
  set "DATE="
  for /f "usebackq tokens=1* delims=:" %%A in ("%SNAP_DIR%\%%S\snapshots_note.txt") do (
    if not defined CM (
      set "CM=%%B"
    ) else if not defined DATE (
      set "DATE=%%B"
    )
  )
  REM trim leading spaces
  for /f "tokens=* delims= " %%x in ("!CM!") do set "CM=%%x"
  for /f "tokens=* delims= " %%x in ("!DATE!") do set "DATE=%%x"
  REM set Git author/committer date and commit
  set GIT_AUTHOR_DATE=!DATE!
  set GIT_COMMITTER_DATE=!DATE!
  git add -A
  git commit -m "!CM!"
)
echo Repository created at %REPO_DIR% with %cd%
echo Add remote and push when ready.
ENDLOCAL
pause
