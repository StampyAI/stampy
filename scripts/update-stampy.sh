pkill -f stam.py
cd ~/stampy
python3 -m scripts.notify-discord-stampy-offline
git pull
conda env remove -n stampy
conda env create -f environment.yml
conda activate stampy
python3 stam.py