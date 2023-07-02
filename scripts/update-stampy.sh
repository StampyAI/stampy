echo "Rebooting Stampy $(date +"%F-%T")"

# These for loops kill the existing stampy processes
# they check to make sure that they only kill processes
# that have been running for 60 seconds so that this
# update process does not kill itself.
for i in $(pgrep -f runstampy)
do
    TIME=$(ps --no-headers -o etimes $i)
    if [ "$TIME" -ge 60 ] ; then
        kill $i
    fi
done
for i in $(pgrep -f stam.py)
do
    TIME=$(ps --no-headers -o etimes $i)
    if [ "$TIME" -ge 60 ] ; then
        kill $i
    fi
done

for i in $(pgrep -f bash)
do
    TIME=$(ps --no-headers -o etimes $i)
    if [ "$TIME" -ge 60 ] ; then
        kill $i
    fi
done

# NOTE: safe to delete?
export DISCORD_TOKEN="$(cat ~/.discordtoken)"
export DISCORD_GUILD="$(cat ~/.discordguild)"
export YOUTUBE_API_KEY="$(cat ~/.youtubeapikey)"
export CLIENT_SECRET_PATH="$(cat ~/.clientsecretpath)"
export WOLFRAM_TOKEN=$(cat ~/.wolframtoken);

export IS_ROB_SERVER="TRUE"

cd ~/stampy
conda activate stampy
python -m scripts.notify-discord-stampy-offline
git pull
conda deactivate
conda env remove -n stampy
conda env create -f environment.yml
conda activate stampy
mkdir -p ~/stampy.local/logs/
export log_file=~/stampy.local/logs/stampy-log-$(date +"%F-%T.log")
./runstampy > $log_file 2>&1 &
ln -s -f $log_file ~/stampy.local/logs/stampy-latest.log
conda deactivate
