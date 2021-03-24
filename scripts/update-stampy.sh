for i in $(pgrep -f stam.py)
do
    TIME=$(ps --no-headers -o etimes $i)
    if [ "$TIME" -ge 60 ] ; then
        kill $i
    fi
done
for i in $(pgrep -f runstampy)
do
    TIME=$(ps --no-headers -o etimes $i)
    if [ "$TIME" -ge 60 ] ; then
        kill $i
    fi
done
cd ~/stampy
conda activate stampy
python -m scripts.notify-discord-stampy-offline
git pull
conda deactivate
conda env remove -n stampy
conda env create -f environment.yml
conda activate stampy
./runstampy > ~/"stampy-log-$(date +"%F-%T")" 2>&1 &
conda deactivate