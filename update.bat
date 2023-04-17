@echo off 

git reset --hard origin/main
git pull
Python310\python.exe -m pip -r requirements.txt
