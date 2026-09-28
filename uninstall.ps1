$ErrorActionPreference = 'Stop'
$registryPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\AppKey\18'
$backupPath = Join-Path $PSScriptRoot 'calculator-key-backup.clixml'
if (-not (Test-Path -LiteralPath $backupPath)) { throw 'No backup found; registry was not changed.' }
$backup = Import-Clixml -LiteralPath $backupPath
# Restore only the two values this installer changes, leaving other settings intact.
foreach ($name in @('ShellExecute', 'Association')) {
    Remove-ItemProperty -Path $registryPath -Name $name -ErrorAction SilentlyContinue
    if ($backup.Values.ContainsKey($name)) {
        $value = $backup.Values[$name]
        New-ItemProperty -Path $registryPath -Name $name -Value $value.Value -PropertyType $value.Kind -Force | Out-Null
    }
}
Write-Output 'Original calculator-key values restored. The translator files are kept.'
