import services
import shopRoster
import shopCalendar
import shopConfig

import bisect
import argparse
import datetime

from ortools.sat.python import cp_model

class ShopScheduler():
    def __init__(self, args):
        
        self.args = args

        provider = services.ServiceProvider(
            services.GMAIL, 
            services.CALENDAR, 
            services.SHEETS)

        self.gmail = provider.get_service('gmail')
        self.gsheets = provider.get_service('sheets')
        self.gcalendar = provider.get_service('calendar')

        self.anchor = shopConfig.anchor

        self.calendar = shopCalendar.ShopCalendar(
            self.gcalendar, 
            shopConfig.calendars, 
            self.anchor, 
            self.args.week)

        self.roster = shopRoster.ShopRoster(
            self.gsheets, 
            self.gmail, 
            shopConfig.spreadsheet,
            self.anchor)
        
    def parseAvailability(self, shifts, techs):
        ''' Determines which shifts each tech can work '''

        def canWork(tech, shift):
            ''' Determines which shifts a tech can work '''

            permitted = {
                'Rookie Tech': [
                    'Maintenance - Mustang 60', 
                    'Maintenance - Hangar', 
                    'Schedule - Rookies'],
                'Junior Tech': [
                    'Schedule - Red Tags', 
                    'Schedule - Yellow Tags', 
                    'Schedule - Mustang 60', 
                    'Schedule - Hangar', 
                    'Maintenance - Mustang 60', 
                    'Maintenance - Hangar'],
                'Senior Tech': [
                    'Schedule - Red Tags', 
                    'Schedule - Yellow Tags', 
                    'Schedule - Mustang 60', 
                    'Schedule - Hangar', 
                    'Maintenance - Mustang 60', 
                    'Maintenance - Hangar'],
                'Supervisor': [
                    'Schedule - Red Tags', 
                    'Schedule - Yellow Tags', 
                    'Schedule - Mustang 60', 
                    'Schedule - Hangar']
            }

            if shift.cal not in permitted[tech.level]:
                return False
            
            # Maintenance supervisors work in their own shop
            if tech.last == 'Fedor' and 'Mustang' in shift.cal:
                return False
            
            if tech.last == 'Schmidt' and 'Hangar' in shift.cal:
                return False
            
            start = shift.start.hour
            end = shift.end - datetime.timedelta(microseconds=1)
            end = end.replace(minute=0, second=0, microsecond=0)
            end = (end + datetime.timedelta(hours=1)).hour

            for h in range(start, end):
                if tech.by_hour[shift.start.weekday()][h]:
                    return False

            return True

        return [[canWork(tech, shift) for tech in techs] for shift in shifts]

    def parseConflicts(self, shifts):
        ''' Determine which shifts overlap with one another '''
    
        roundDay = lambda dt: dt.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        
        shifts.sort(key=lambda shift: shift.start)     
        starts = [shift.start for shift in shifts]

        # Shifts that actually overlap
        overlaps = [bisect.bisect_left(starts, shift.end) for shift in shifts]
        overlaps = [(cur, max_ov) for cur, max_ov in enumerate(overlaps)]

        # Shifts that are on the same day
        conflicts = [bisect.bisect_left(starts, roundDay(shift.end)) for shift in shifts]
       
        return overlaps, conflicts

    def schedule(self):

        techs = self.roster.techs
        shifts = self.calendar.shifts

        for tech in techs:
            tech.hours = int((tech.hours * (7 - sum(tech.by_day[self.args.week-1]))) // 7)
        
        overlaps, conflicts = self.parseConflicts(shifts)
        availability = self.parseAvailability(shifts, techs)

        for s in range(len(self.calendar.shifts)):
            for c in range(s, conflicts[s]):
                if shifts[c].tech is not None:
                    availability[s][shifts[c].tech] = False

        for s in range(len(self.calendar.shifts)-1, -1, -1):
            if shifts[s].old:
                del shifts[s]
                del availability[s]
    
        overlaps, conflicts = self.parseConflicts(shifts)

        model = cp_model.CpModel()
        all_vars = []
        tech_vars = [[] for _ in techs]
        shift_vars = [[] for _ in shifts]
        abs_vars = []
        abs_abs_vars = []
        
        for t, tech in enumerate(techs):
            for s, shift in enumerate(shifts):
                if availability[s][t] == 0 or shift.tech is not None:
                    var = model.NewIntVar(0, 0, 'v[%i,%i]' % (t, s))
                else:
                    var = model.NewIntVar(0, 1, 'v[%i,%i]' % (t, s))

                all_vars.append(var)
                tech_vars[t].append(var)    # Track variables for each tech
                shift_vars[s].append(var)   # Track variables for each shift

        for t, tech in enumerate(techs):

            terms = [(tech_vars[t][s], shift.hours) for s, shift in enumerate(shifts)]
            model.AddLinearConstraint(terms, 0, 20)
            
            hour_var = model.NewIntVar(-20, 20, 'h[%i]' % t)
            hours = sum([tech_vars[t][s] * shift.hours for s, shift in enumerate(shifts)])
            model.Add(hour_var == tech.hours - hours)
            if tech.hours == 0:
                model.Add(hour_var == 0)
            
            abs_var = model.NewIntVar(0, 20, 'a[%i]' % t)
            abs_vars.append(abs_var)
            model.AddAbsEquality(abs_var, hour_var)

        for s, shift in enumerate(shifts):
            model.AddSumConstraint(shift_vars[s], 0, 1)
        
        for t, tech in enumerate(techs):
            for s, shift in enumerate(shifts):
                model.AddSumConstraint(tech_vars[t][s:conflicts[s]], 0, 1)
        
        # Optimize the number of shifts filled
        model.Maximize(sum(all_vars)) 
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        print(solver.ObjectiveValue())
        model.Add(sum(all_vars) >= int(solver.ObjectiveValue()))

        # Optimize the sum of differences
        model.Minimize(sum(abs_vars))
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        print(solver.ObjectiveValue())
        model.Add(sum(abs_vars) <= int(solver.ObjectiveValue()))
       
        pain = int(solver.ObjectiveValue() // len(techs))

        for t, tech in enumerate(techs):
            pain_var = model.NewIntVar(-20, 20, 'p[%i]' % t)
            abs_abs_var = model.NewIntVar(0, 20, 'aa[%i]' % t)
            abs_abs_vars.append(abs_abs_var)
            model.Add(pain_var == pain - abs_vars[t])
            model.AddAbsEquality(abs_abs_var, pain_var)
        
        # Evenly distribute pain
        model.Minimize(sum(abs_abs_vars))
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        print(solver.ObjectiveValue())
        model.Add(sum(abs_abs_vars) <= int(solver.ObjectiveValue()))
     
        # Parse solution
        for t, tech in enumerate(techs):
            for s, shift in enumerate(shifts):
                if solver.Value(tech_vars[t][s]):
                    shift.tech = t
                    tech.shifts.append(shift)

        for s, shift in enumerate(shifts):
            for c in range(s, conflicts[s]):
                if shifts[c].tech is not None:
                    availability[s][shifts[c].tech] = False

        for s, shift in enumerate(shifts):
            for t, tech in enumerate(techs):
                name = '{} {:1.1}'.format(tech.first, tech.last)
                name = tech.nick if tech.nick else name
                if availability[s][t]:
                    shift.covers.append(name)

        # Print solution
        for tech in techs:
            print(tech)
        for shift in shifts:
            if not shift.tech:
                print('Not filled: {}'.format(shift))

        # Dry run, exit after printing
        if self.args.dry:
            exit(1)
    
        # Update calendars
        print('Post? y/N')
        x = input()
        if x != 'y':
            exit(1)
        self.calendar.postEvents(techs)

        # Send notifications
        print('Email? y/N')
        x = input()
        if x != 'y':
            exit(1)
        self.roster.sendEmails()

if __name__ == '__main__':
    
    # Parse command-line flags and arguments
    parser = argparse.ArgumentParser(
        description='Schedules shop techs', 
        epilog='Brought to you by Scarborough'
    )
    parser.add_argument('week', type=int, help='week of the quarter')
    parser.add_argument('-n', '--nuke', action='store_true', help='unassign all shifts for the week')
    parser.add_argument('-d', '--dry', action='store_true', help='print the schedule, but do not update the calendars')
    args = parser.parse_args()
    
    s = ShopScheduler(args)
    
    if args.nuke:
        print('Nuke week {}? y/N'.format(args.week))
        x = input()
        if x != 'y':
            exit(1)
        if not args.dry:
            s.calendar.nukeEvents()

    s.schedule()
