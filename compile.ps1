# Clean up previous build and dist directories
Remove-Item -Recurse -Force -Path ".\dist" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force -Path ".\build" -ErrorAction SilentlyContinue

# Run PyInstaller with Poetry
poetry run python -m PyInstaller master115.spec --clean