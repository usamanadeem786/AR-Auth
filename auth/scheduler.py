from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from auth import tasks


def schedule():
    scheduler = BlockingScheduler()
    scheduler.add_job(
        tasks.cleanup.send,
        CronTrigger.from_crontab("0 0 * * *"),
    )
    scheduler.add_job(
        tasks.heartbeat.send,
        CronTrigger.from_crontab("0 0 * * *"),
    )
    scheduler.add_job(
        tasks.subscription_reminder.send,
        CronTrigger.from_crontab("0 0 * * *"),
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.shutdown()
