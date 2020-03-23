#!/bin/bash
python updatebot.py >> output.txt
git add . 
git commit -m "update who.db" 
git push 
