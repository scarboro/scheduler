import bisect
import datetime

import shopShift

class ShopCalendar(object):

    def __init__(self, gcalendar, cal_ids, anchor, week):

        self.gcalendar = gcalendar
        self.cal_ids = cal_ids
        self.anchor = anchor
        self.week = week

        self.cutoff = datetime.datetime.strptime(self.anchor, '%Y-%m-%d')
        self.cutoff += datetime.timedelta(days = 7 * week) 
        self.getAllShifts(cal_ids, anchor, week)

    def getAllShifts(self, cal_ids, anchor, week):
        ''' Retrieves all shifts from Google Calendar '''

        min_time = self.getWeek(week)
        max_time = self.getWeek(week + 1)

        shifts = []
        for cal_id in cal_ids:
            
            request = self.gcalendar.events().list(
                calendarId=cal_id,
                timeMin=min_time,
                timeMax=max_time,
                singleEvents=True)
        
            result = request.execute()

            for item in result['items']:
                try: 
                    shift = shopShift.Shift(item, cutoff=self.cutoff)
                    shifts.append(shift)
                # All-day events throw KeyErrors and are not shifts
                except KeyError:
                    continue
        
        self.shifts = shifts
        
        return shifts

    def getWeek(self, num_weeks):
        ''' Returns a date offset from self.anchor by num_weeks '''

        anchor_date = datetime.datetime.strptime(self.anchor, '%Y-%m-%d')
        week = anchor_date + datetime.timedelta(days = 7 * num_weeks) 
        return week.strftime('%Y-%m-%dT%H:%M:%S-07:00')

    def postEvents(self, techs):
        ''' Posts all shifts to Google Calendar '''

        requests = [shift.postEvent(self.gcalendar, techs) for shift in self.shifts]
        #batch = self.gcalendar.new_batch_http_request()
        for request in requests:
            if request:
                request.execute()
                #batch.add(request)
        #batch.execute()

    def nukeEvents(self):
        ''' Resets all shifts in the specified week '''

        for shift in self.shifts:
            if shift.old:
                continue
            
            event = shift.event
            event['summary'] = ''
            event['description'] = ''

            self.gcalendar.events().update(
                calendarId=event['organizer']['email'],
                eventId=event['id'],
                body=event).execute()
