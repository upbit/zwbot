# zwbot project on GAE
# -*- coding: utf-8 -*-
import os
import sys
import base64
import urllib
import csv
import logging
import string
from sets import Set
from datetime import datetime, timedelta

import webapp2
from google.appengine.api import urlfetch
# 2013.04 move to jinja2.template
import jinja2
JINJA_ENVIRONMENT = jinja2.Environment(autoescape=True, extensions=['jinja2.ext.autoescape'],
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

import config             # r14 add @20101215 独立bot的配置文件
from db_util import *     # r2 add  @20101026 将数据库相关操作独立出来

sys.path.insert(0, 'tweepy.zip')
import tweepy

# r2 add @20101026 替换csv为xls文件，加速读取
sys.path.insert(0, 'xlrd-0.6.1.zip')
import xlrd

# When this is true, some things go to the screen as text and templates aren't always generated. Error message are more verbose.
_DEBUG = True


# OAuth认证并发推
def OAuth_UpdateTweet(msg):
  if msg != '':
    auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
    auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_SECRET)
    api = tweepy.API(auth)
    return(api.update_status(msg))


# 读取词典文件中的下一个单词
def GetNextTweetword_from_Dict():
  udb = DB_Utility()
  
  index = udb.GetIncCounter(config.DICT_LINES)
  xlswb = xlrd.open_workbook(config.DICT_NAME)
  
  sheet1 = xlswb.sheet_by_index(0)
  title_line = 0
  
  try:
    if (sheet1.cell_value(index, 0) == ''):
      str = sheet1.cell_value(index, 1)
      title_line = 1
    else:
      if (sheet1.cell_value(index, 1) == ''):
        str = '%s' % ( sheet1.cell_value(index, 0) )     # 第二列没有内容，不附加连词符
      else:
        str = '%s%s%s' % ( sheet1.cell_value(index, 0), config.TW_WORD_LINK, sheet1.cell_value(index, 1) )
    
    if (len(sheet1.row_values(index)) > 2):     # 如果有第三列，取出来附加上
      if (sheet1.cell_value(index, 2) != ''):
        str = '%s%s%s' % ( str, config.TW_WORD_SP, sheet1.cell_value(index, 2) )
    
    tweet = str
    udb.SetTitleFlag(title_line, tweet)
    
    if title_line == 0:
      ssp = sheet1.cell_value(index, 0).split()
      udb.SetRollingWords(ssp[0])                 # 取出开始的单词，用于复习
      udb.SetCurrentWord(tweet)
    else:
      tweet = '%s%s' % (tweet, config.BOT_HASHTAG)
    
  except:
    tweet = ''
  
  return(tweet)


# 请求 /
class MainPage(webapp2.RequestHandler):
  def get(self):
    template_values = { 'msg': 'It work!' }
    template = JINJA_ENVIRONMENT.get_template('template/msg.html')
    self.response.out.write(template.render(template_values))

# 请求 /t
class ShowCurrentWord(webapp2.RequestHandler):
  def get(self):
    mydate = datetime.utcnow() + timedelta(hours=+8)
    ts_hour = mydate.time().hour
    ts_min = mydate.time().minute / 5
    
    udb = DB_Utility()
    
    if (ts_hour < 7):
      words = '%s' % config.GAE_PAGE_TIPS
    else:
      words = '%s<BR>%s' % ( udb.GetTitleString(), udb.GetCurrentWord() )
      logging.debug('ShowCurrentWord(): "%s"' % words)
    
    template = JINJA_ENVIRONMENT.get_template('template/words.html')
    self.response.out.write(template.render({ 'words': words }))

# [ADMIN] 请求提及页面，显示最近的15条@消息
class GetMentions(webapp2.RequestHandler):
  def get(self):
    auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
    auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_SECRET)
    api = tweepy.API(auth)
    mentions = tweepy.Cursor(api.mentions).items(config.MENTIONS_COUNT)
    
    logging.info('Check Mentions')
    
    template = JINJA_ENVIRONMENT.get_template('template/mentions.html')
    self.response.out.write(template.render({ 'mentions': mentions }))


# 自动回Fo所有新的Followers
class FollowAllNewcomers(webapp2.RequestHandler):
  def get(self):
    auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
    auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_SECRET)
    api = tweepy.API(auth)
    
    followers_ids = tweepy.Cursor(api.followers_ids).items()
    followers_set = Set(followers_ids)
    friends_ids = tweepy.Cursor(api.friends_ids).items()
    friends_set = Set(friends_ids)
    
    suc_count = 0             # 成功建立关系的个数
    err_count = 0             # 可能已经发出申请的保护用户
    
    for user_id in (followers_set-friends_set):
      try:
        api.create_friendship(id=user_id)
        suc_count += 1
      except:
        err_count += 1
    
    logging.info('Follow %d user, skip %d.' % (suc_count, err_count))
    
    self.response.out.write('Success create_friendship() with %d user, %d skiped.' % (suc_count, err_count))



#
# r17 新增计划任务支持
#
def ProcessScheduleTask(now):
  # 取当前1小时内的到期任务
  tdb = Db_TaskHelper()
  tasklist = tdb.get_tasks(now)
  
  # 附加上一小时没有完成的任务
  last_hour = now + timedelta(hours=-1)
  tasklist_last = tdb.get_tasks(last_hour)
  tasklist += tasklist_last
  
  if (tasklist):
    for task in tasklist:
      task_time = datetime(task.year, task.month, task.day, task.hour, task.minute)
      
      if (task_time < now):                       # 说明是以前失败的任务
        if ((now-task_time).seconds > 900):       # 超过15分钟的任务，终止尝试
          logging.warning('Scheduled task timeout: [%s] %s' % (task_time.strftime("%Y-%m-%d %H:%M"), task.msg.encode('utf8')))
          tdb.clean_task(task_time)
        else:
          logging.info('retry last task: [%s] %s' % (task_time.strftime("%Y-%m-%d %H:%M"), task.msg.encode('utf8')))
          try:
            OAuth_UpdateTweet(task.msg.encode('utf8'))
            tdb.clean_task(task_time)
            logging.debug('task execute complete')
          except Exception, e:
            logging.error('task execute failed')

      else:                                       # 未来1小时内的任务
        if ((task_time-now).seconds < 300):       # 只处理距当前不足5分钟的
          logging.info('execute task: [%s] %s' % (task_time.strftime("%Y-%m-%d %H:%M"), task.msg.encode('utf8')))
          try:
            OAuth_UpdateTweet(task.msg.encode('utf8'))
            tdb.clean_task(task_time)
            logging.debug('task execute complete')
          except Exception, e:
            logging.error('task execute failed')
        else:
          logging.debug('future task: [%s:L=%s] %s' % (task_time.strftime("%Y-%m-%d %H:%M"), (task_time-now).seconds, task.msg.encode('utf8')))

#
# Cron Job
#
class CronJobCheck(webapp2.RequestHandler):
  def get(self):
    # r14 add @20101130 增加请求来源的判断，只接受由CronJob发起的请求
    Access_CronJob = False
    headers = self.request.headers.items()
    
    for key, value in headers:
      if (key == 'X-Appengine-Cron') and (value == 'true'):
        Access_CronJob = True
        break
    # 如果不是CronJob来源的请求，记录日志并放弃操作
    if (not Access_CronJob):
      logging.debug('CronJobCheck() access denied!')
      logging.critical('如果这个请求不是由你手动触发的话，这意味者你的CronJobKey已经泄漏！请立即修改CronJobKey以防被他人利用')
      return
    
    mydate = datetime.utcnow() + timedelta(hours=+8)
    ts_hour = mydate.time().hour
    ts_min = mydate.time().minute / 5

    try:
      ProcessScheduleTask(mydate)     # r17 检查数据库中的计划任务并推送
    except Exception, e:
      logging.error('Process ScheduleTask() error! %s' % e)

    udb = DB_Utility()

    # 7:00 ~ 23:59 是工作时间，不满足工作时间的直接返回
    if (ts_hour < 7):
      return
    
    # 检查之前是否有失败发生
    if (not ts_min in [0, 3, 6, 9, 11]):          # 分钟为 00/15/30/45/55 的周期才继续处理
      if (udb.GetFatalMin() != -1):               # 或者上次有失败发生，重设周期数继续
        ts_min = udb.GetFatalMin()
        if (udb.GetTitleFlag() == 0):
          logging.warning('上次失败发生在 %d 分，尝试进行恢复...' % (ts_min*5))
          if (ts_min in [0, 3, 6]):
            udb.DecCounter()                      # 退回到上一次的count处
      else:                                       # 没有失败，直接返回
        return
    
    if ((ts_hour == 7) and (ts_min == 0)):        # 7:00
      msg = '%s%s' % (config.MSG_GET_UP, config.BOT_HASHTAG)
    elif ((ts_hour == 23) and (ts_min == 11)):    # 23:55
      msg = '%s%s' % (config.MSG_SLEEP, config.BOT_HASHTAG)
    elif (ts_min in [0, 3, 6]):                   # every 00/15/30 推单词
      msg = GetNextTweetword_from_Dict()
    elif (ts_min == 9):                           # every 45 (复习)
      msg = '%s%s%s%s' % (config.MSG_REVIEW_1, udb.GetRollingWords(), config.MSG_REVIEW_2, config.BOT_HASHTAG)
    else:                                         # every 55 (不是23:55，不处理)
      return
    
    logging.info('Send Tweet: %s' % msg)
    
    try:
      OAuth_UpdateTweet(msg)                        # 发送到Twitter
      udb.SetFatalMin(-1)                           # 如果执行成功，将失败周期数改回-1
      
      # 检查刚才发送的是否为标题，如果是则设置失败min，让下个5分钟继续推一条
      if (udb.GetTitleFlag() == 1):
        udb.SetFatalMin(ts_min)
      
      #logging.debug('Auto tweet success complete.')
    except tweepy.TweepError, e:
      if ('duplicate' in e):                      # [无效?] Tweet已经发出去了，清除掉这个失败
        udb.SetFatalMin(-1)
        msg = '[WARN] 尝试恢复 %d 时刻的Tweet，但该Tweet已存在: %s' % (ts_min*5, e)
        logging.warring(msg)
      else:
        udb.SetFatalMin(ts_min)
        msg = '[Tweepy错误] 错误发生在 %d 分, %s' % (ts_min*5, e)
        logging.error(msg)
    except Exception, e:
      msg = '[未知错误] 错误发生在 %d 分, %s' % (ts_min*5, e)
      logging.error(msg)
    
    template = JINJA_ENVIRONMENT.get_template('template/msg.html')
    self.response.out.write(template.render({ 'msg': msg }))

# 查看计划任务列表
class Manage_ScheduleTask(webapp2.RequestHandler):
  def get(self):
    schedule_task = Db_TaskHelper().list_tasks()
    
    template_values = {
      'schedule_task': schedule_task,
      'taskadd_url': config.KEY_MANAGETASK,
    }

    template = JINJA_ENVIRONMENT.get_template('template/schedule_task.html')
    self.response.out.write(template.render(template_values))

  def post(self):
    try:
      st_year = string.atoi(self.request.get('year'))
      st_month = string.atoi(self.request.get('month'))
      st_day = string.atoi(self.request.get('day'))
      st_hour = string.atoi(self.request.get('hour'))
      st_minute = string.atoi(self.request.get('minute'))
      st_msg = self.request.get('msg')
      
      if (st_msg == ""):
        raise TypeError, "Can't accept null parameters!"
      
      # 新增任务
      task_date = datetime(st_year, st_month, st_day, st_hour, st_minute)
      Db_TaskHelper().add_task(task_date, st_msg.encode('utf-8'))
      
      self.redirect(config.KEY_MANAGETASK)
    except Exception, e:
      self.response.out.write("Input error: %s" % e)



app = webapp2.WSGIApplication([('/', MainPage),
                                (config.URL_CURWORD, ShowCurrentWord),
                                (config.URL_MENTIONS, GetMentions),
                                (config.KEY_FOBACK_ALL, FollowAllNewcomers),
                                (config.KEY_CRONJOB, CronJobCheck),
                                (config.KEY_MANAGETASK, Manage_ScheduleTask)
                               ], debug=True)

"""
def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
"""