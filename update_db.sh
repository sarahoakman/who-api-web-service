#!/bin/bash
python updatebot.py >> testing_output.txt
git add . 
git commit -m "update who.db" 
git push 
