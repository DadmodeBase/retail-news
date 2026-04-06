$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-Command `".\note\.venv\Scripts\python.exe .\note\scripts\neta_gatherer.py`""
$Trigger = New-ScheduledTaskTrigger -Daily -At 5am
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "DailyNetaGatherer" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily blog idea generation at 5 AM" -Force

Write-Host "Success: Task 'DailyNetaGatherer' has been registered for 5:00 AM."
Write-Host "Please ensure your .env file is correctly configured."
