#!/bin/sh
heroku ps:stop run -a teletubbies-who-api
updatebot.py
git add .
git commit -m "update who.db"
git push
heroku dyno:restart -a teletubbies-who-api