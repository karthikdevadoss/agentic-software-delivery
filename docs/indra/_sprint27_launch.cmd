@echo off
cd /d "C:\Users\Hemapriya\agentic-software-delivery"
echo === Sprint 27 launch %DATE% %TIME% ===> "C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_RUN.log"
echo claude=C:\Users\Hemapriya\AppData\Local\Microsoft\WinGet\Packages\Anthropic.ClaudeCode_Microsoft.Winget.Source_8wekyb3d8bbwe\claude.exe>> "C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_RUN.log"
echo branch=indra/sprint-27-5h-platform>> "C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_RUN.log"
echo prompt=C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_PROMPT.md>> "C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_RUN.log"
echo --->> "C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_RUN.log"
"C:\Users\Hemapriya\AppData\Local\Microsoft\WinGet\Packages\Anthropic.ClaudeCode_Microsoft.Winget.Source_8wekyb3d8bbwe\claude.exe" -p --dangerously-skip-permissions --model sonnet < "C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_PROMPT.md" >> "C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_RUN.log" 2>&1
echo.>> "C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_RUN.log"
echo === Sprint 27 exit code %ERRORLEVEL% at %DATE% %TIME% ===>> "C:\Users\Hemapriya\agentic-software-delivery\docs\indra\SPRINT_27_5H_RUN.log"
