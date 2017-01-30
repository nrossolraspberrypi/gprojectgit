#!/usr/bin/python
import RPi.GPIO as GPIO
import time
from xml.etree import ElementTree
import datetime
from pytz import timezone
import pytz
from xml.dom import minidom
import os
import sys

#Important constant declarations
xmlFilename = 'recentActivity.xml'
serverTimezone = timezone('America/Edmonton')
SWITCH_READER_GPIO_INPUT_PIN = int(22) # GPIO pin for reading the state of the switch

GOOD_LED_GPIO_OUTPUT_PIN = int(27) #GPIO output pins for the various LEDs
WARNING_LED_GPIO_OUTPUT_PIN = int(17)
BAD_LED_GPIO_OUTPUT_PIN = int(4)

SECONDS_BETWEEN_UPDATE_PINGS = 200.0 #i.e. automatic updates every ping
MAX_SECONDS_BEFORE_OPEN_DOOR_ALERT = 610 #How long the door can be open before it's time to broadcast an alert
WEB_CALLS_TIMEOUT_IN_SECONDS = int(55) # How long to wait for a web call (such as a dropbox upload) to finish before giving up on it

def addNewEventToEventLog(eventLogNode, event_type, event_time, MAX_EVENTS_ALLOWED = 50):
    
    doorEventElements = eventLogNode.findall('doorEvent')
    if(len(doorEventElements) >= MAX_EVENTS_ALLOWED): #We need to purge excess items from oldest to newest
        doorEventElements.sort(key=lambda x: x.attrib['timestamp'], reverse=False) #First sort all events from oldest to newest
        del doorEventElements[:(len(doorEventElements) - MAX_EVENTS_ALLOWED + 1)]#Delete the excess element(s) + 1  for the new element.

    dateAsUTC_ISOstring = event_time.utcnow().isoformat() + 'Z' #Client side wants this
    eventLogNode.clear()
    eventLogNode.set('lastModified', dateAsUTC_ISOstring)
    eventLogNode.extend(doorEventElements)


    #Now we add a new doorEventElement
    newElement = ElementTree.Element('doorEvent', {'type': event_type, 'timestamp': dateAsUTC_ISOstring})
    eventLogNode.append(newElement)

    return

#Return a pretty-printed XML string for the Element.
def writeOutXMLTree(xmlTree, filename):
    rough_string = ElementTree.tostring(xmlTree.getroot(), 'utf-8')
    #reparsed = minidom.parseString(rough_string)
    #prettyXMLString = reparsed.toprettyxml(indent="\t")

    #Actually write the file
    f = open(filename,'w')
    f.write('<?xml version="1.0" ?>')
    f.write(rough_string)
    f.close() # you can omit in most cases as the destructor will call if

#Setting up initial GPIO states
def setupGPIOs():
    GPIO.setmode(GPIO.BCM)
    GPIO.cleanup()

    #First, setup the GPIO port that will read the input switch status
    GPIO.setup(SWITCH_READER_GPIO_INPUT_PIN, GPIO.IN)

    #Next, set up all the output pins
    GPIO.setup(GOOD_LED_GPIO_OUTPUT_PIN, GPIO.OUT)
    GPIO.setup(WARNING_LED_GPIO_OUTPUT_PIN, GPIO.OUT)
    GPIO.setup(BAD_LED_GPIO_OUTPUT_PIN, GPIO.OUT)

    GPIO.output(BAD_LED_GPIO_OUTPUT_PIN, False)
    GPIO.output(WARNING_LED_GPIO_OUTPUT_PIN, False)    
    GPIO.output(GOOD_LED_GPIO_OUTPUT_PIN, False)
    print "GPIOs set up sucessfully."

def setLEDsToShowSystemError():
    GPIO.output(WARNING_LED_GPIO_OUTPUT_PIN, False)    
    GPIO.output(GOOD_LED_GPIO_OUTPUT_PIN, False)
    GPIO.output(BAD_LED_GPIO_OUTPUT_PIN, True)

def setLEDsToShowSystemGood():
    GPIO.output(WARNING_LED_GPIO_OUTPUT_PIN, False)    
    GPIO.output(GOOD_LED_GPIO_OUTPUT_PIN, True)
    
def setLEDsToShowSystemWarning():
    GPIO.output(WARNING_LED_GPIO_OUTPUT_PIN, True)    
    GPIO.output(GOOD_LED_GPIO_OUTPUT_PIN, False)

def uploadRecentActivity():
    os.system('timeout ' + str(WEB_CALLS_TIMEOUT_IN_SECONDS) + ' ./gitupload.sh &')

def uploadRecentActivityToDropbox(): #Old deprecated technique using the open source dropbox-uploader script 
    os.system('timeout ' + str(WEB_CALLS_TIMEOUT_IN_SECONDS) + ' ./dropbox_uploader.sh upload '+xmlFilename+' Public/sites/gproject/' + xmlFilename + ' &')
	
def sendAlertEmails():
    os.system('timeout ' + str(WEB_CALLS_TIMEOUT_IN_SECONDS) + ' python emailAlerts.py &')

def uploadPing():
    xmlTree = ElementTree.parse(xmlFilename)# Open the XML file
    xmlTree.getroot().set( 'lastModified', (serverTimezone.localize(datetime.datetime.now())).utcnow().isoformat() + 'Z')
    writeOutXMLTree(xmlTree, xmlFilename)# Output the updated XML file
    uploadRecentActivity()

def uploadNewEvent(eventType):
    xmlTree = ElementTree.parse(xmlFilename)# Open the XML file
    addNewEventToEventLog(xmlTree.getroot(), eventType, serverTimezone.localize(datetime.datetime.now()))
    writeOutXMLTree(xmlTree, xmlFilename)# Output the updated XML file
    uploadRecentActivity()

def enterManualDebuggingMode():
    #Debug code
    nextEvent = 'open'

    while(True):
        text = raw_input('Type "q" to quit: ')
        if(text == 'q' or text == 'u'):
            xmlTree = ElementTree.parse(xmlFilename)# Open the XML file
            xmlTree.getroot().set( 'lastModified', (serverTimezone.localize(datetime.datetime.now())).utcnow().isoformat() + 'Z')
            writeOutXMLTree(xmlTree, xmlFilename)# Output the updated XML file
            if(text == 'u'):
                print('Performing upload...')
                uploadRecentActivity()
            break

        xmlTree = ElementTree.parse(xmlFilename)# Open the XML file
        addNewEventToEventLog(xmlTree.getroot(), nextEvent, serverTimezone.localize(datetime.datetime.now()))
        writeOutXMLTree(xmlTree, xmlFilename)# Output the updated XML file

        print(nextEvent+' ')

        if nextEvent == 'open':
            nextEvent = 'close'
        else:
            nextEvent = 'open'

    print('Qutting')

######################################
#MAIN Entry Point

setupGPIOs()

inputPinHighLastTime = GPIO.input(SWITCH_READER_GPIO_INPUT_PIN)
doorWasClosedLastTime = inputPinHighLastTime
timeOfLastUpdateOrPing = time.time()
timeDoorWasLastOpenned = timeOfLastUpdateOrPing
alertEmailAlreadySent = False

if doorWasClosedLastTime:
    setLEDsToShowSystemGood()
else:
    setLEDsToShowSystemWarning()

try:
    while(True):
        currentTime = time.time()
        inputPinIsHigh = GPIO.input(SWITCH_READER_GPIO_INPUT_PIN)
        doorIsNowClosed = inputPinIsHigh

        if(doorIsNowClosed and not doorWasClosedLastTime): #door CLOSED Event
            print "Door is now CLOSED! ("+str(currentTime)+")\n"
            setLEDsToShowSystemGood()
            uploadNewEvent('close')
            timeOfLastUpdateOrPing = time.time()

        elif(not doorIsNowClosed and doorWasClosedLastTime): #door OPEN Event
            print "Door is now OPEN! ("+str(currentTime)+")\n"
            timeDoorWasLastOpenned = currentTime
            alertEmailAlreadySent = False #Get ready in case we need to send an alert email
            setLEDsToShowSystemWarning()
            uploadNewEvent('open')
            timeOfLastUpdateOrPing = time.time()
        
        # Check to see if we need to send an alert email yet
        if(not doorIsNowClosed and ((currentTime - timeDoorWasLastOpenned) > MAX_SECONDS_BEFORE_OPEN_DOOR_ALERT) and not alertEmailAlreadySent):
            sendAlertEmails()
            alertEmailAlreadySent = True

        #Check to see if it's been long enough that we need to send another automated ping.
        if((currentTime - timeOfLastUpdateOrPing) > SECONDS_BETWEEN_UPDATE_PINGS):
            #print('Performing update after being idle for '+str(currentTime - timeOfLastUpdateOrPing) + ' seconds.')
            uploadPing()
            timeOfLastUpdateOrPing = time.time()


        inputPinHighLastTime = inputPinIsHigh
        doorWasClosedLastTime = doorIsNowClosed

        time.sleep( 0.25 )

except KeyboardInterrupt:
    GPIO.cleanup()
    print "Shutting down due to Keyboad command."
    sys.exit(0)

except SystemExit:
    GPIO.cleanup()
    print "Shutting down due to System Exit call."
    sys.exit(0)

except SystemError:
    setLEDsToShowSystemError()
    print "Shutting down due to System Error!."
    sys.exit(0)
