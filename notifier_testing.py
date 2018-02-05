#!/usr/bin/env python3

# Google calendars polling script + audio reminders
# File used for testing in standard Linux environment, not Raspi.
# Edit the RPi packages and the GPIO stuff.
# Author: Matthew Cheng
# 

import gflags
import httplib2
import requests
import time
import os
import logging
import logging.handlers
import sys, traceback
import unicodedata
import pytz
# import RPi.GPIO as GPIO

from datetime import datetime, timedelta

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.tools import run_flow
from oauth2client.client import flow_from_clientsecrets

from ConfigParser import SafeConfigParser

#############
# GPIO CONFIG
#############
# GPIO.setmode(GPIO.BCM)
# GPIO.setup(14,GPIO.OUT)

###########################
# PERSONAL CONFIG FILE READ
###########################

parser = SafeConfigParser()
parser.read('information.ini')

# Read private developer for access to the google API
developerKeyString = parser.get('config', 'developerKey')

# Read list of calendars to be managed concurrently
# NOTE: there is a main calendar, the one with which the credentials have been generated
# Additional calendars must be configured as shared with this main calendar.
calendars = parser.get('config', 'calendars').split(',')

# Read path to log file
LOG_FILENAME = parser.get('config', 'log_filename')

# Read how much time in advance the spoken reminder should be played, if no reminder is specified in gcalendar.
REMINDER_DELTA_DEFAULT = parser.getint('config', 'reminder_minutes_default')


#################
#  LOGGING SETUP
#################
LOG_LEVEL = logging.INFO  

# Configure logging to log to a file, making a new file at midnight and keeping the last 3 day's data
# Give the logger a unique name (good practice)
logger = logging.getLogger(__name__)
# Set the log level to LOG_LEVEL
logger.setLevel(LOG_LEVEL)
# Make a handler that writes to a file, making a new file at midnight and keeping 3 backups
handler = logging.handlers.TimedRotatingFileHandler(LOG_FILENAME, when="midnight", backupCount=3)
# Format each log message like this
formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
# Attach the formatter to the handler
handler.setFormatter(formatter)
# Attach the handler to the logger
logger.addHandler(handler)

# Make a class we can use to capture stdout and sterr in the log
class MyLogger(object):
	def __init__(self, logger, level):
		#Needs a logger and a logger level.
		self.logger = logger
		self.level = level

	def write(self, message):
		# Only log if there is a message (not just a new line)
		if message.rstrip() != "":
			self.logger.log(self.level, message.rstrip())

# Replace stdout with logging to file at INFO level
sys.stdout = MyLogger(logger, logging.INFO)
# Replace stderr with logging to file at ERROR level
sys.stderr = MyLogger(logger, logging.ERROR)

logger.info('Starting Google Calendar Polling and Notification Service')
logger.info('Using google developerkey %s' % developerKeyString)
logger.info('Using calendar list: ' + str(calendars))
logger.info("Beginning authentication...")


logger.info('Starting GCal Polling')
logger.info('using devkey %s' % developerKeyString)

###############################
# GOOGLE CALENDAR ACCESS SETUP
###############################

scope = 'https://www.googleapis.com/auth/calendar'
flow = flow_from_clientsecrets('client_secret.json', scope=scope)

storage = Storage('credentials.dat')
credentials = storage.get()

class fakeargparse(object):  # fake argparse.Namespace
 	noauth_local_webserver = True
 	logging_level = "ERROR"
flags = fakeargparse()

if credentials is None or credentials.invalid:
	credentials = run_flow(flow, storage,flags)

# Create an httplib2.Http object to handle our HTTP requests and authorize it
# with our good Credentials.
http = httplib2.Http()
http = credentials.authorize(http)

#logger.info
logger.info("Authentication completed")

# Build a service object for accessing the API
service = build(serviceName='calendar', version='v3', http=http,developerKey=developerKeyString)

###############################
# GOOGLE CALENDAR POLLING LOOP
###############################
logger.info("Starting calendars polling & notification loop...")

while True:

	try:
		logger.info("Checking calendars...")

		# get events from calendar, set for the next 30 days
		tzone = pytz.timezone('US/Pacific')
		now = datetime.now(tz=tzone)

		timeMin = now
		timeMin = timeMin.isoformat()
		timeMax = now + timedelta(days=5)
		timeMax = timeMax.isoformat()

		eventlist = []
		defaultReminderDelta = REMINDER_DELTA_DEFAULT

		# Merge events from all configured calendars
		for calendar in calendars:
				events = service.events().list(singleEvents=True, timeMin=timeMin, timeMax=timeMax, calendarId=calendar).execute()
				if 'items' in events:
					eventlist += events['items']

				# Grab default reminder time value from calendar settings
				if ('defaultReminders' in events) and (len(events['defaultReminders'])>0) :
					defaultReminderDelta = events['defaultReminders'][0]['minutes']
		
		# Check for each collected event if it is about to start
		for i, event in enumerate(eventlist):

			if 'summary' in event and 'start' in event and 'dateTime' in event['start']:
				# Use this calendar event's summary text as the text to be spoken
				# Also, remove any accentuated characters from the name (too lazy to handle text encoding properly)
				name = unicodedata.normalize('NFKD', event['summary'].lower()).encode('ascii', 'ignore')
				end = event['end']['dateTime'][:-9]
				description = event.get('description', '')
				repeat = True if description.lower() == 'repeat' else False

				# By default, set announce time to (event start time) - (default value from config or from calendar itself)
				# Unless some specific reminders are specified in the event
				reminder_deltatime = defaultReminderDelta
				if 'reminders' in event:
					reminders = event['reminders']

					if reminders['useDefault'] == False:
						# Parse overridden reminders to get time value
						if 'overrides' in reminders:
							for override in reminders['overrides']:
								if 	override['method'] == 'popup':
									reminder_deltatime = override['minutes']
									break;

				logger.info('Event Number %s, Name: %s, End: %s, Reminder at %d minutes', i, name, end, reminder_deltatime)
				
				# If the start time of the event is reached, play out a speech synthesis corresponding to the event
				expiration = now + timedelta(minutes=reminder_deltatime)
				if end == expiration.strftime('%Y-%m-%dT%H:%M'):
					
					print "it's time "
					"""
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)
					# Play sound
					logger.info('Playing sounds!')
					# os.system('omxplayer 5star.mp3 &') @TODO: This is a remnant from the Relay Robot. Delete ASAP
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)
					GPIO.output(14,GPIO.HIGH)
					time.sleep(.5)
					GPIO.output(14,GPIO.LOW)
					time.sleep(.5)					
					if repeat == False:
						# wait until the current minute ends, so as not to re-trigger this event, if no repeat condition is specified
						time.sleep(60)
					"""

		# Poll calendar every 30 seconds
		time.sleep(30)

	except:
		print("*****Exception in main loop, retrying in 30 seconds ******")
		exc_type, exc_value, exc_traceback = sys.exc_info()
		traceback.print_exception(exc_type, exc_value, exc_traceback,limit=2, file=sys.stdout)	
		del exc_traceback
		time.sleep(30)
		continue
