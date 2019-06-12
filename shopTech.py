import base64
import datetime

from functools import reduce
from email.mime.text import MIMEText

class Tech(object):

   __slots__ = ['first', 'last', 'nick', 'email', 'edit', 
                 'level', 'hours', 'shifts', 'by_hour', 'by_day']

   def __init__(self, row, params, **kwargs):
      ''' Initializes the Tech from a row of the results spreadsheet '''

      self.first    = row[params['col_index']['First Name']]
      self.last     = row[params['col_index']['Last Name']]
      self.nick     = row[params['col_index']['Nickname']]
      self.email    = row[params['col_index']['Google Email Address']]
      self.edit     = row[params['col_index']['Edit URL']]
      self.level    = row[params['col_index']['Position']]
      self.hours    = int(row[params['col_index']['Hours per Week']])
      self.shifts   = []
      self.by_hour, self.by_day = self.parseConflicts(row, params)
    
   def __str__(self):
      ''' Pretty-prints information about the tech '''

      return '{:>12s} {:1.1s} {:>2} {:>2} {:>2} {:>2} {:>2}'.format(
         self.first, 
         self.last,
         self.hours,
         self.getHours(old=False),
         self.getHours(),
         len(self.getShifts(filter='Red')),
         len(self.getShifts(filter='Yellow')))
   
   def parseConflicts(self, row, params):
      ''' Determines when the Tech is unavailabile '''

      by_hour = [[True for h in range(24)] for day in params['day_names']]
      by_day = [[True for d in range(7)] for week in params['week_names']]

      for h, index in enumerate(params['hour_cols'], start=params['first_hour']):
         for d, day in enumerate(params['day_names']):
            by_hour[d][h] = day in row[index]

      for w, index in enumerate(params['week_cols']):
         for d, day in enumerate(params['day_names']):
            by_day[w][d] = day in row[index]

      return by_hour, by_day

   def getShifts(self, **kwargs):
      ''' Returns a subset of the Tech's shifts '''
      
      def match(shift):
         if 'filter' in kwargs and kwargs['filter'] not in shift.cal:
            return False
         if 'old' in kwargs and kwargs['old'] != shift.old:
            return False
         return True

      return [shift for shift in self.shifts if match(shift)]
   
   def getHours(self, **kwargs):
      ''' Returns the total length of a subset of the Techs's shifts '''

      return sum([shift.hours for shift in self.getShifts(**kwargs)])

   def sendEmail(self, gmail):
      ''' Notifies the Tech of their shift assignment '''

      name = self.nick if self.nick else self.first

      shift_string = 'Zip, zilch, zero...'
      if self.shifts:
         self.shifts.sort(key=lambda shift: shift.start)
         shift_strings = [str(shift) for shift in self.shifts if not shift.old]
         shift_string = '<br>'.join(shift_strings)

      text = '<br><br>'.join([
         'Hi {},',
         'You have been assigned the following shifts this week:',
         '{}'
         '<br><br>Click <a href="{}">here</a> to edit your schedule.',
         'Have a great week!',
         '<small>This message brought to you by Scarborough</small>'
      ]).format(name, shift_string, self.edit)

      mime = MIMEText(text, 'html')
      mime['to'] = self.email
      mime['subject'] = 'Schedule for Next Week'
      encoded = base64.urlsafe_b64encode(mime.as_string().encode('utf-8'))
      message = {'raw': encoded.decode()} 

      return gmail.users().messages().send(userId="me", body=message)
