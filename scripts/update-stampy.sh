pkill -f stam.py
pkill -f runstampy
cd ~/stampy
python3 -m scripts.notify-discord-stampy-offline
git pull
conda deactivate
conda env remove -n stampy
conda env create -f environment.yml
conda activate stampy
./runstampy > ~/"stampy-log-$(date +"%F-%T")" 2>&1 &