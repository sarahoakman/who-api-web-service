#!/bin/sh
heroku ps:stop run -a teletubbies-who-api >> output.txt
python updatebot.py >> output.txt
git add . >> output.txt
git commit -m "update who.db" >> output.txt
git push >> output.txt
heroku dyno:restart -a teletubbies-who-api >> output.txt