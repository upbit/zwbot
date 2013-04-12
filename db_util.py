# DB function for zwbot
# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timedelta
from google.appengine.ext import db

# DB����������
class Counter(db.Model):
  count = db.IntegerProperty()
  is_title = db.IntegerProperty()
  current_title = db.StringProperty(multiline=False)
  current_word = db.StringProperty(multiline=False)
  rol_word1 = db.StringProperty(multiline=False)
  rol_word2 = db.StringProperty(multiline=False)
  rol_word3 = db.StringProperty(multiline=False)
  fatal_min = db.IntegerProperty()

class DB_Utility():
  def __init__(self):
    query = db.GqlQuery("select * from Counter")
    counter = query.get()
    
    if (not counter):
      counter = Counter()
      counter.count = 0
      counter.is_title = 0
      counter.current_title = ''
      counter.current_word = ''
      counter.rol_word1 = ''
      counter.rol_word2 = ''
      counter.rol_word3 = ''
      counter.fatal_min = -1
      counter.put()
  
  # max ��xls�ļ�������������ﵽ���ͷ��ʼ
  def GetIncCounter(self, max):
    query = db.GqlQuery("select * from Counter")
    counter = query.get()
    
    result = counter.count                        # ȡ�õ�ǰ�ļ���(��0��ʼ)
    counter.count += 1
    counter.count = counter.count % max;          # �� (0) - (max-1)
    
    counter.put()
    return(result)
  
  def GetCounter(self):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    return(counter.count)
  
  def DecCounter(self):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    if (counter.count > 0):
      counter.count -= 1
      counter.put()
  
  
  def GetTitleFlag(self):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    return(counter.is_title)
  
  def SetTitleFlag(self, title, title_str):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    counter.is_title = title
    if (title == 1):
      counter.current_title = title_str
    counter.put()
  
  def GetTitleString(self):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    return(counter.current_title.encode('utf-8'))
  
  
  def GetCurrentWord(self):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    return(counter.current_word.encode('utf-8'))
  
  def SetCurrentWord(self, str_word):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    counter.current_word = str_word
    counter.put()
  
  def GetRollingWords(self):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    str_word = '%s  %s  %s' % (counter.rol_word3, counter.rol_word2, counter.rol_word1)
    return(str_word.encode('utf-8'))
  
  def SetRollingWords(self, str_word):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    counter.rol_word3 = counter.rol_word2
    counter.rol_word2 = counter.rol_word1
    counter.rol_word1 = str_word
    counter.put()
  
  
  # ��д����ʧ�ܵ�������
  def GetFatalMin(self):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    return(counter.fatal_min)
  
  def SetFatalMin(self, iMin):
    q = db.GqlQuery("select * from Counter")
    counter = q.get()
    if (counter.fatal_min != iMin):
      counter.fatal_min = iMin
      counter.put()

#
# r17 �ƻ�����
#
class ScheduleTaskDb(db.Model):
  year = db.IntegerProperty()
  month = db.IntegerProperty()
  day = db.IntegerProperty()
  hour = db.IntegerProperty()
  minute = db.IntegerProperty()
  msg = db.StringProperty(multiline=True)

class Db_TaskHelper():
  def get_tasks(self, now):
    schedule_task = []
    query = db.GqlQuery("select * from ScheduleTaskDb where year=:1 and month=:2 and day=:3 and hour=:4", now.year, now.month, now.day, now.hour)
    for row in query:
      schedule_task.append(row)
    return (schedule_task)

  def list_tasks(slef):
    schedule_task = []
    query = db.GqlQuery("select * from ScheduleTaskDb")
    for row in query:
      schedule_task.append(row)
    return (schedule_task)

  def add_task(self, task_date, msg):
    schedule_task = ScheduleTaskDb()
    schedule_task.year = task_date.year
    schedule_task.month = task_date.month
    schedule_task.day = task_date.day
    schedule_task.hour = task_date.hour
    schedule_task.minute = task_date.minute
    schedule_task.msg = msg.decode("utf-8")
    
    logging.debug('add new task: [%s] %s' % (task_date.strftime("%Y-%m-%d %H:%M"), msg))
    schedule_task.put()

  def clean_task(self, task_date):
    query = db.GqlQuery("select * from ScheduleTaskDb where year=:1 and month=:2 and day=:3 and hour=:4 and minute=:5", task_date.year, task_date.month, task_date.day, task_date.hour, task_date.minute)
    schedule_task = query.get()
    
    logging.debug('delete task: [%s] %s' % (task_date.strftime("%Y-%m-%d %H:%M"), schedule_task.msg))
    schedule_task.delete()

