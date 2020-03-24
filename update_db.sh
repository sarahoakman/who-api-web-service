#!/bin/bash
cd 'C:\Users\Sarah Oakman\Documents\GitHub\who-api-web-service'
python updatebot.py
git add . 
git commit -m "update who.db" 
git push 
