set /P DISCORD_TOKEN=<%USERPROFILE%\.discordtoken
set /P DISCORD_GUILD=<%USERPROFILE%\.discordguild
set /P YOUTUBE_API_KEY=<%USERPROFILE%\.youtubeapikey
set /P CLIENT_SECRET_PATH=<%USERPROFILE%\.clientsecretpath
set DATABASE_PATH=C:\Users\james\OneDrive\Projects\Stampy\stampy\database\stampy.db
set ENVIRONMENT_TYPE=development
:while
python stam.py
rem timeout /t 10 /nobreak
rem GOTO :while
