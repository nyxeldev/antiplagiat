param([int]$Port = 8000, [string]$Origin = 'http://127.0.0.1:3000')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$names = @('ANTIPLAGIAT_DB_HOST','ANTIPLAGIAT_DB_PORT','ANTIPLAGIAT_DB_NAME','ANTIPLAGIAT_DB_USER','ANTIPLAGIAT_DB_PASSWORD','ANTIPLAGIAT_PUBLIC_ORIGIN')
$previous = @{}
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $defaults = @{ HOST = '127.0.0.1'; PORT = '5432'; NAME = 'antiplagiat'; USER = 'antiplagiat_app' }
    foreach ($key in @('HOST','PORT','NAME','USER')) {
        $value = Read-Host "Runtime DB $key [$($defaults[$key])]"
        if ([string]::IsNullOrWhiteSpace($value)) { $value = $defaults[$key] }
        [Environment]::SetEnvironmentVariable("ANTIPLAGIAT_DB_$key", $value, 'Process')
    }
    $secret = Read-Host 'Runtime DB paroli' -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try { $env:ANTIPLAGIAT_DB_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secret.Dispose() }
    $env:ANTIPLAGIAT_PUBLIC_ORIGIN = $Origin
    & .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port $Port --no-access-log
}
finally {
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
}
