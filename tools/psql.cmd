@echo off
REM FlightSim has no Windows psql on PATH. Postgres is Docker container memorybox-pg.
where docker >nul 2>&1
if errorlevel 1 (
  echo docker not found. Start Docker Desktop, then retry.
  exit /b 1
)
docker inspect -f "{{.State.Running}}" memorybox-pg 2>nul | findstr /i "true" >nul
if errorlevel 1 (
  echo memorybox-pg is not running. From the repo: startmb.cmd
  exit /b 1
)
if "%~1"=="" (
  docker exec -it memorybox-pg psql -U memorybox -d memorybox
) else (
  docker exec -i memorybox-pg psql -U memorybox -d memorybox %*
)
