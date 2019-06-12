import datetime

class Shift(object):

   __slots__ = ['start', 'end', 'hours', 'cal', 
                'event', 'old', 'tech', 'covers']

   def __init__(self, event, **kwargs):

      strptime = datetime.datetime.strptime
      hour = datetime.timedelta(hours = 1)
      fmt = '%Y-%m-%dT%H:%M:%S'

      self.event = event
      self.start = strptime(event['start']['dateTime'][:19], fmt)
      self.end = strptime(event['end']['dateTime'][:19], fmt)
      self.hours = (self.end - self.start) // hour
      self.cal = event['organizer']['displayName']
      self.covers = []

      self.tech = kwargs.get('tech', None)
      cutoff = kwargs.get('cutoff', None)
      self.old = self.start < cutoff if cutoff else True

   def __str__(self): 
      return '{:<25.25} {:>11} {:>5} {:>5}'.format(
         self.cal, 
         self.start.strftime('%a %m/%d'), 
         self.start.strftime('%H:%M'), 
         self.end.strftime('%H:%M'))

   def postEvent(self, gcalendar, techs):

      if self.old:
         return None
      
      if self.tech is None:
         return None

      tech = techs[self.tech]
      name = '{} {:1.1}'.format(tech.first, tech.last)
      name = tech.nick if tech.nick else name 
      self.event['summary'] = name
      self.event['description'] = '\n'.join(self.covers)

      return gcalendar.events().update(
         calendarId=self.event['organizer']['email'],
         eventId=self.event['id'],
         body=self.event)
