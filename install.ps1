$ErrorActionPreference = 'Stop'
$registryPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\AppKey\18'
$backupPath = Join-Path $PSScriptRoot 'calculator-key-backup.clixml'
if (-not (Test-Path -LiteralPath $backupPath)) {
    $values = @{}
    if (Test-Path $registryPath) {
        $key = Get-Item $registryPath
        foreach ($name in $key.GetValueNames()) {
            $values[$name] = @{ Value = $key.GetValue($name); Kind = $key.GetValueKind($name).ToString() }
        }
    }
    @{ Exists = (Test-Path $registryPath); Values = $values } | Export-Clixml -LiteralPath $backupPath
}
New-Item -Path $registryPath -Force | Out-Null
$command = 'wscript.exe "' + (Join-Path $PSScriptRoot 'launch.vbs') + '"'
New-ItemProperty -Path $registryPath -Name ShellExecute -Value $command -PropertyType String -Force | Out-Null
Remove-ItemProperty -Path $registryPath -Name Association -ErrorAction SilentlyContinue
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Programs')) 'Quick Translator.lnk'))
$portable = Join-Path $PSScriptRoot 'QuickTranslator.exe'
if (Test-Path -LiteralPath $portable) {
    $shortcut.TargetPath = $portable
} else {
    $shortcut.TargetPath = Join-Path $env:WINDIR 'System32\wscript.exe'
    $shortcut.Arguments = '"' + (Join-Path $PSScriptRoot 'launch.vbs') + '"'
}
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Save()
Write-Output 'Installed calculator-key mapping for the current user. Restore with uninstall.ps1.'
