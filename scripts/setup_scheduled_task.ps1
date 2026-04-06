$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-Command `".\note\.venv\Scripts\python.exe .\note\scripts\neta_gatherer.py`""
$Trigger = New-ScheduledTaskTrigger -Daily -At 7am
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName "DailyNetaGatherer" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily blog idea generation at 7 AM" -Force

Write-Host "Success: Task 'DailyNetaGatherer' has been registered for 7:00 AM."
Write-Host "Please ensure your .env file is correctly configured."
