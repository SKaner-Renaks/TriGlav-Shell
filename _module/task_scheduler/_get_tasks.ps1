
$ErrorActionPreference = 'SilentlyContinue'
$tasks = Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\Microsoft\Windows\*' }
$results = @()
foreach ($task in $tasks) {
    $info = $task | Get-ScheduledTaskInfo -ErrorAction SilentlyContinue
    $schedule = ''
    if ($task.Triggers.Count -gt 0) {
        $triggers = @()
        foreach ($tr in $task.Triggers) {
            $cn = $tr.CimClass.CimClassName
            $rep = ''
            if ($tr.Repetition -and $tr.Repetition.Interval) {
                $rep = ' [' + $tr.Repetition.Interval + ']'
            }
            if ($cn -like '*TimeTrigger*') {
                $time = ''
                if ($tr.StartBoundary) { $time = [datetime]::Parse($tr.StartBoundary).ToString('HH:mm') }
                $triggers += ('Every ' + $time + $rep)
            } elseif ($cn -like '*DailyTrigger*') {
                $time = ''
                if ($tr.StartBoundary) { $time = [datetime]::Parse($tr.StartBoundary).ToString('HH:mm') }
                $triggers += ('Daily at ' + $time + $rep)
            } elseif ($cn -like '*WeeklyTrigger*') {
                $time = ''
                if ($tr.StartBoundary) { $time = [datetime]::Parse($tr.StartBoundary).ToString('HH:mm') }
                $days = @()
                $dw = [int]$tr.DaysOfWeek
                if ($dw -band 1) { $days += 'Mon' }
                if ($dw -band 2) { $days += 'Tue' }
                if ($dw -band 4) { $days += 'Wed' }
                if ($dw -band 8) { $days += 'Thu' }
                if ($dw -band 16) { $days += 'Fri' }
                if ($dw -band 32) { $days += 'Sat' }
                if ($dw -band 64) { $days += 'Sun' }
                $triggers += ('Weekly ' + ($days -join ',') + ' ' + $time + $rep)
            } elseif ($cn -like '*MonthlyTrigger*') {
                $time = ''
                if ($tr.StartBoundary) { $time = [datetime]::Parse($tr.StartBoundary).ToString('HH:mm') }
                $triggers += ('Monthly ' + $time + $rep)
            } else {
                $triggers += ('Other' + $rep)
            }
        }
        $schedule = $triggers -join '; '
    }
    $lastRun = ''
    $nextRun = ''
    $lastResult = ''
    if ($info) {
        if ($info.LastRunTime -and $info.LastRunTime.Year -gt 1999) { $lastRun = $info.LastRunTime.ToString('dd-MM-yyyy HH:mm') }
        if ($info.NextRunTime -and $info.NextRunTime.Year -gt 1999) { $nextRun = $info.NextRunTime.ToString('dd-MM-yyyy HH:mm') }
        $lastResult = $info.LastTaskResult
    }
    $results += @{
        Name = $task.TaskName
        Path = $task.TaskPath
        Status = $task.State.ToString()
        Schedule = $schedule
        LastRun = $lastRun
        NextRun = $nextRun
        LastResult = $lastResult
    }
}
$results | ConvertTo-Json -Compress
