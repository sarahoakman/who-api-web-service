from crontab import CronTab

cron = CronTab(tab="""* * * * * updatebot.py""")
job = cron.new(command='python updatebot.py')
job.minute.every(1)

for item in cron:
    print (item)

cron.write()