# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

from webnotes.utils import getdate, cint, add_months, date_diff, add_days, nowdate
#from __future__ import unicode_literals
#import webnotes
import gflags
import httplib2
import os
import MySQLdb
from webnotes import msgprint, _
sql = webnotes.conn.sql
from webnotes.model.bean import getlist
import gdata
from apiclient.discovery import build
from oauth2client.file import Storage
#import os
#import httplib2
#from apiclient.discovery import build
#from oauth2client.client import OAuth2WebServerFlow
from oauth2client.client import Credentials
 
from oauth2client.tools import run
#from webnotes.utils import getdate, cint, add_months, date_diff, add_days, nowdate
import oauth2client.client
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import logging
import os
import signal
import time
import sys
import re
import string
import requests
import subprocess
import json
import simplejson as json
#import time
logging.basicConfig()            

weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def validate(self):
		if self.doc.starts_on and self.doc.ends_on and self.doc.starts_on > self.doc.ends_on:
			webnotes.msgprint(webnotes._("Event End must be after Start"), raise_exception=True)
	
	
	def on_update(self):
		webnotes.errprint("In on Update")
		name=webnotes.session.user
		qry= webnotes.conn.sql(""" select token_credentials from 	`tabCredentials` where user='%s'"""%name)
		webnotes.errprint(qry[0])
		if len(qry) == 0:
			webnotes.msgprint("Create Credentials for current user")
		if self.doc.event_id:
			self.update_event()
		else:
			dic=self.create_dict()
			event=self.create_event(dic)
			service=self.create_service()
			recurring_event= self.create_recurringevent(event,service)
			self.doc.event_id=recurring_event['id']
			self.doc.save()

			

	def create_dict(self):
		webnotes.errprint("in dict")
		name=webnotes.session.user
		webnotes.errprint(name)
		list1=[]
		for p in getlist(self.doclist,'event_individuals'):
			list1.append(p.person)
		   	
		dic = {'summary': self.doc.subject,'location': 'pune','start': self.doc.starts_on,'end': self.doc.ends_on,'attendees': list1 }
		return dic
	def create_service(self):
		webnotes.errprint("in create service")
		name=webnotes.session.user
		qry= webnotes.conn.sql(""" select token_credentials from 	`tabCredentials` where user='%s'"""%name)
		#credentials_json = webnotes.conn.get_value("Credentials", None, "token_credentials")
		
		credentials_json=qry[0]
		webnotes.errprint(credentials_json)
		credentials = oauth2client.client.Credentials.new_from_json(credentials_json)
		#json_object = json.load(response)
		#json_object = json.loads(response.read())
		#webnotes.errprint(json_object)
		http = httplib2.Http()
		http = credentials.autorize(http)
		service = build('calendar', 'v3', http=http)	
		return service
	def create_recurringevent(self,event,service):
		webnotes.errprint("in recurring event")
		recurring_event = service.events().insert(calendarId='primary', body=event).execute()
		return recurring_event

	def create_event(self,dic):
		webnotes.errprint("in create event")
		
		event = { 
				'summary': dic['summary'],
				'location': dic['location'],
				'start': {
					'dateTime': dic['start'].replace(' ','T')+'.00+05:30'
				},
				'end': {
					'dateTime': dic['end'].replace(' ','T')+'.00+05:30'
				},
				'attendees': [
					{
						'email': dic['attendees']
					}	
				]
			}
				
		
		return event
	def update_event(self):
		webnotes.errprint("in update")
		#self.create_dict()
		dic=self.create_dict()
		
		#self.create_service()
		service=self.create_service()
		event = service.events().get(calendarId='primary', eventId=self.doc.event_id).execute()
		
		#self.create_event(dic)
		event=self.create_event(dic)
				
		updated_event = service.events().update(calendarId='primary', eventId=self.doc.event_id, body=event).execute()

		#return updated_event
def get_match_conditions():
	return """(tabEvent.event_type='Public' or tabEvent.owner='%(user)s'
		or exists(select * from `tabEvent User` where 
			`tabEvent User`.parent=tabEvent.name and `tabEvent User`.person='%(user)s')
		or exists(select * from `tabEvent Role` where 
			`tabEvent Role`.parent=tabEvent.name 
			and `tabEvent Role`.role in ('%(roles)s')))
		""" % {
			"user": webnotes.session.user,
			"roles": "', '".join(webnotes.get_roles(webnotes.session.user))
		}
			
def send_event_digest():
	today = nowdate()
	for user in webnotes.conn.sql("""select name, email, language 
		from tabProfile where ifnull(enabled,0)=1 
		and user_type='System User' and name not in ('Guest', 'Administrator')""", as_dict=1):
		events = get_events(today, today, user.name, for_reminder=True)
		if events:
			text = ""
			webnotes.set_user_lang(user.name, user.language)
			webnotes.load_translations("core", "doctype", "event")

			text = "<h3>" + webnotes._("Events In Today's Calendar") + "</h3>"
			for e in events:
				if e.all_day:
					e.starts_on = "All Day"
				text += "<h4>%(starts_on)s: %(subject)s</h4><p>%(description)s</p>" % e

			text += '<p style="color: #888; font-size: 80%; margin-top: 20px; padding-top: 10px; border-top: 1px solid #eee;">'\
				+ webnotes._("Daily Event Digest is sent for Calendar Events where reminders are set.")+'</p>'

			from webnotes.utils.email_lib import sendmail
			sendmail(recipients=user.email, subject=webnotes._("Upcoming Events for Today"),
				msg = text)
				
@webnotes.whitelist()
def get_events(start, end, user=None, for_reminder=False):
	if not user:
		user = webnotes.session.user
	roles = webnotes.get_roles(user)
	events = webnotes.conn.sql("""select name, subject, description,
		starts_on, ends_on, owner, all_day, event_type, repeat_this_event, repeat_on,
		monday, tuesday, wednesday, thursday, friday, saturday, sunday
		from tabEvent where ((
			(date(starts_on) between date('%(start)s') and date('%(end)s'))
			or (date(ends_on) between date('%(start)s') and date('%(end)s'))
			or (date(starts_on) <= date('%(start)s') and date(ends_on) >= date('%(end)s'))
		) or (
			date(starts_on) <= date('%(start)s') and ifnull(repeat_this_event,0)=1 and
			ifnull(repeat_till, "3000-01-01") > date('%(start)s')
		))
		%(reminder_condition)s
		and (event_type='Public' or owner='%(user)s'
		or exists(select * from `tabEvent User` where 
			`tabEvent User`.parent=tabEvent.name and person='%(user)s')
		or exists(select * from `tabEvent Role` where 
			`tabEvent Role`.parent=tabEvent.name 
			and `tabEvent Role`.role in ('%(roles)s')))
		order by starts_on""" % {
			"start": start,
			"end": end,
			"reminder_condition": "and ifnull(send_reminder,0)=1" if for_reminder else "",
			"user": user,
			"roles": "', '".join(roles)
		}, as_dict=1)
			
	# process recurring events
	start = start.split(" ")[0]
	end = end.split(" ")[0]
	add_events = []
	remove_events = []
	
	def add_event(e, date):
		new_event = e.copy()
		new_event.starts_on = date + " " + e.starts_on.split(" ")[1]
		if e.ends_on:
			new_event.ends_on = date + " " + e.ends_on.split(" ")[1]
		add_events.append(new_event)
	
	for e in events:
		if e.repeat_this_event:
			event_start, time_str = e.starts_on.split(" ")
			if e.repeat_on=="Every Year":
				start_year = cint(start.split("-")[0])
				end_year = cint(end.split("-")[0])
				event_start = "-".join(event_start.split("-")[1:])
				
				# repeat for all years in period
				for year in range(start_year, end_year+1):
					date = str(year) + "-" + event_start
					if date >= start and date <= end:
						add_event(e, date)
						
				remove_events.append(e)

			if e.repeat_on=="Every Month":
				date = start.split("-")[0] + "-" + start.split("-")[1] + "-" + event_start.split("-")[2]
				
				# last day of month issue, start from prev month!
				try:
					getdate(date)
				except ValueError:
					date = date.split("-")
					date = date[0] + "-" + str(cint(date[1]) - 1) + "-" + date[2]
					
				start_from = date
				for i in xrange(int(date_diff(end, start) / 30) + 3):
					if date >= start and date <= end and date >= event_start:
						add_event(e, date)
					date = add_months(start_from, i+1)

				remove_events.append(e)

			if e.repeat_on=="Every Week":
				weekday = getdate(event_start).weekday()
				# monday is 0
				start_weekday = getdate(start).weekday()
				
				# start from nearest weeday after last monday
				date = add_days(start, weekday - start_weekday)
				
				for cnt in xrange(int(date_diff(end, start) / 7) + 3):
					if date >= start and date <= end and date >= event_start:
						add_event(e, date)

					date = add_days(date, 7)
				
				remove_events.append(e)

			if e.repeat_on=="Every Day":				
				for cnt in xrange(date_diff(end, start) + 1):
					date = add_days(start, cnt)
					if date >= event_start and date <= end \
						and e[weekdays[getdate(date).weekday()]]:
						add_event(e, date)
				remove_events.append(e)

	for e in remove_events:
		events.remove(e)
		
	events = events + add_events
	
	for e in events:
		# remove weekday properties (to reduce message size)
		for w in weekdays:
			del e[w]
			
	return events
