# Build the catalogue in Docker and render selected PDF pages to PNG.
#
# Usage:
#   .\verify.ps1              # page 1
#   .\verify.ps1 1 4 23       # pages 1, 4 and 23
#
# The images are written to .\verify_out\page-<N>.png and the LaTeX report to
# .\verify_out\report.txt. The image is rebuilt only when the sources changed.

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $Pages = @('1')
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$outDir = Join-Path $root 'verify_out'
$image = 'katalog-verify'

Push-Location $root
try {
    # Rebuild only when a source file is newer than the image.
    $imageTime = (docker image inspect $image --format '{{.Created}}' 2>$null)
    $needsBuild = -not $imageTime
    if (-not $needsBuild) {
        $imageDate = [datetime]::Parse($imageTime).ToUniversalTime()
        $sources = @(
            'src', 'latex_temp\catalog_styling.tex', 'artefakte_export.csv',
            'bilder', 'Dockerfile.verify', 'verify.sh'
        )
        foreach ($source in $sources) {
            $path = Join-Path $root $source
            if (-not (Test-Path $path)) { continue }
            $newest = Get-ChildItem $path -Recurse -File -ErrorAction SilentlyContinue |
                Sort-Object LastWriteTimeUtc -Descending |
                Select-Object -First 1
            if ($newest -and $newest.LastWriteTimeUtc -gt $imageDate) {
                $needsBuild = $true
                break
            }
        }
    }

    if ($needsBuild) {
        Write-Host 'Building image...'
        docker build -q -f Dockerfile.verify -t $image . | Out-Null
    }

    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
    docker rm -f $image 2>$null | Out-Null
    docker run --name $image $image @Pages

    docker cp "${image}:/app/out/." $outDir | Out-Null
    docker cp "${image}:/app/katalog_output.pdf" (Join-Path $root 'katalog_output.pdf') | Out-Null
    docker cp "${image}:/app/latex_temp/catalog.log" (Join-Path $root 'latex_temp\catalog.log') | Out-Null
    docker rm -f $image 2>$null | Out-Null

    Write-Host ''
    Write-Host "Images: $outDir"
    Get-ChildItem $outDir -Filter 'page-*.png' | ForEach-Object { Write-Host "  $($_.Name)" }
}
finally {
    Pop-Location
}
