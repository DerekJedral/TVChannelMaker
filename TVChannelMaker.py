import os
import random
import subprocess
import vlc
import time
import datetime
import math
import threading
from threading import Thread
from threading import Timer
from tkinter import *
import tkinter as tk
from tkinter import filedialog
import sys

# Constants, should never be changed
NUMBER_SLOTS = 48
HALF_HOUR = 1800000
BASE_VOLUME = 70

# Global, set by program
root = 0
vlc_instance = 0
videoPlayer = 0
musicPlayer = 0
numSlots = -1
CHANNEL_THREAD = threading.Event()

# Global, set by user
CHANNEL_PATH = ''
schedule = []

DEFAULT_MODE = True

class Application(Frame):
	def __init__(self, master):
		Frame.__init__(self, master)
		self.grid()
		self.shouldSkip = False
		self.create_widgets()
	
	def create_widgets(self):
		self.addInitialButtons()
		self.text = Text(self, width = 60, height = 20, wrap= WORD)
		self.text.grid(row=1, column =1,rowspan=3, sticky = E)
		
		self.buttonSkip = Button(self)
		self.buttonSkip["text"] = "Skip episodes: " +str(self.shouldSkip)
		self.buttonSkip["command"] = self.toggle_skip
		self.buttonSkip.grid(row=3, column=2, sticky=W)
		
	def open_guide(self):
		self.text.delete(0.0, END)
		counter = 0
		scheduleString = ""
		totalSlots = 0
		currentEpisodeTitle = ""
		for episode in schedule:
			if DEFAULT_MODE:
				temp = time.strftime('%H:%M', time.gmtime(counter*1800))
				scheduleString = scheduleString+temp+":"	
			else:
				scheduleString = scheduleString+ str(counter)+":"
			if totalSlots == 0:
				totalSlots = episode.numSlots - 1
				currentEpisodeTitle = episode.series
				scheduleString=scheduleString+episode.series+"\n"
			else:
				totalSlots=totalSlots-1
				scheduleString=scheduleString+currentEpisodeTitle+"\n"
			counter=counter+1
		
		self.text.insert(0.0, scheduleString)
	def stop_channel(self):
		CHANNEL_THREAD.set()
		
		self.text.delete(0.0, END)
		self.text.insert(0.0, "Stopping Channel")
		
		self.buttonGuide.grid_forget()
		self.buttonStop.grid_forget()
		self.addInitialButtons()
		self.addStoppedButtons()
		
	def pick_channel(self):
		global CHANNEL_PATH
		CHANNEL_PATH = tk.filedialog.askdirectory() + '\\'
		self.text.delete(0.0, END)
		self.text.insert(0.0, "Channel: "+CHANNEL_PATH)
		self.addStoppedButtons()
	
	def startChannel(self):
		self.buttonStart.grid_forget()
		self.buttonToggle.grid_forget()
		self.buttonQuit.grid_forget()
		self.buttonPick.grid_forget()
		self.addPlayingButtons()
		setupChannel(self.shouldSkip)

	def addInitialButtons(self):
		self.buttonQuit = Button(self)
		self.buttonQuit["text"] = "Quit"
		self.buttonQuit["command"] = self.quit_application
		self.buttonQuit.grid(row=0, column=2, sticky=W)
	
		self.buttonPick = Button(self)
		self.buttonPick["text"] = "Pick Channel"
		self.buttonPick["command"] = self.pick_channel
		self.buttonPick.grid(row=1, column=0, sticky=W)
	
	def setToggleText(self):
		if DEFAULT_MODE:
			self.buttonToggle["text"] = "Switch to test mode"
		else:
			self.buttonToggle["text"] = "Switch to default mode"
	
	def addStoppedButtons(self):
		self.buttonStart = Button(self)
		self.buttonStart["text"] = "Start Channel"
		self.buttonStart["command"] = self.startChannel
		self.buttonStart.grid(row=2, column=0, sticky=W)
		
		self.buttonToggle = Button(self)
		self.setToggleText()
		self.buttonToggle["command"] = self.toggle_mode
		self.buttonToggle.grid(row=1, column=2, sticky=E)
	
	def addPlayingButtons(self):
		self.buttonGuide = Button(self)
		self.buttonGuide["text"] = "Guide"
		self.buttonGuide["command"] = self.open_guide
		self.buttonGuide.grid(row=2, column=0, sticky=W)
		self.buttonStop = Button(self)
		self.buttonStop["text"] = "Stop Channel"
		self.buttonStop["command"] = self.stop_channel
		self.buttonStop.grid(row=3, column=0, sticky=W)
		
	def toggle_mode(self):
		global DEFAULT_MODE
		DEFAULT_MODE = not DEFAULT_MODE
		self.setToggleText()

	def toggle_skip(self):
		self.shouldSkip = not self.shouldSkip
		self.buttonSkip["text"] = "Skip episodes: "+str(self.shouldSkip)
			
	def quit_application(self):
		quitApplication()

class Episode(object):
	def __init__(self, path, timeslot):
		self.path = path
		self.series = getSeries(self.path)
		self.length = -1
		self.timeslot = timeslot
		self.numSlots = 1
		
	def getLength(self):
		if self.length == -1:
			self.length = getLength(self.path)
		return self.length

	def getNumSlots(self):
		return math.ceil(self.getLength() / HALF_HOUR)
		
def isVideo(name):
	return (name.lower().endswith(".avi")
	or name.lower().endswith(".mpg")
	or name.lower().endswith(".mpeg")
	or name.lower().endswith(".asf")
	or name.lower().endswith(".wmv")
	or name.lower().endswith(".wma")
	or name.lower().endswith(".mp4")
	or name.lower().endswith(".mov")
	or name.lower().endswith(".3gp")
	or name.lower().endswith(".ogg")
	or name.lower().endswith(".ogm")
	or name.lower().endswith(".mkv"))
	
def resetVariables():
	global videoPlayer
	global musicPlayer
	global vlc_instance
	global schedule
	global numSlots
	
	videoPlayer = 0
	musicPlayer = 0
	vlc_instance = 0
	schedule = []
	numSlots = -1

def quitApplication():
	root.destroy()
	CHANNEL_THREAD.set()
	sys.exit()

#gets the length of a media file (music or video)
def getLength(filename):
	result = subprocess.Popen(["ffprobe", filename],
	stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
	for line in result.stdout.readlines():
		line = line.decode("utf-8")
		if "Duration" in line:
			timestr = line[line.find(":")+2:line.find(",")]
			totalTime = int(timestr[timestr.find(".")+1:])
			h, m, s = timestr[:timestr.find(".")].split(':')
			totalTime =  int(h) * 3600000 + int(m) * 60000 + int(s)*1000 + totalTime
			return totalTime
			
	return HALF_HOUR - 1

#if we were away from the channel, we missed episodes airing. So, we skip them
def skipEpisodes(lastWatchedTime):
	currentTime = int(round(time.time() * 1000))
	while (currentTime - lastWatchedTime) > HALF_HOUR:
		lastSeenDate = datetime.datetime.fromtimestamp(lastWatchedTime/1000.0)
		timeslot = lastSeenDate.time().hour*2 +  math.floor(lastSeenDate.time().minute/30)
		loadEpisodeForTimeslot(timeslot, False)
		lastWatchedTime = lastWatchedTime + HALF_HOUR

#gets our current timeslot
def getTimeslot():
	if DEFAULT_MODE:
		timeslot = now().hour*2 +  math.floor(now().minute/30)
	else:
		timeslot = math.floor(now().second/10)
	
	return timeslot

# load the appropriate episode for the corresponding timeslot
# if we're in the middle of a movie, we do nothing
# timeslot: the next timeslot we're in
# shouldPlay: whether we actually want to play the episode in VLC, or just skip it
def loadEpisodeForTimeslot(timeslot, shouldPlay):
	global numSlots
	if (numSlots <= 0): # episode is over, load a new one
		numSlots = schedule[timeslot].numSlots - 1 #calculate how many slots the new show needs
		if shouldPlay:
			playEpisode(schedule[timeslot])
	else: #episode is still going, reduce the counter
		numSlots = numSlots - 1
		print('----just decreasing numSlots')
	return

def writeScheduleToDisk():
	f = open(CHANNEL_PATH+'channel.data', 'w')
	f.write(str(int(round(time.time() * 1000)))+'\n')
	for i in range(0, len(schedule)):
		f.write(schedule[i].path + '\n')
	f.close()

# Fetches the first episode at the top of the queue
# and pushies {series} to the back of the queue
def updateQueueAndGetNextEpisode(series):
	try:
		with open(CHANNEL_PATH+'queue.data', 'r') as file:
			queue = [line.rstrip() for line in file]
			file.close()
	except FileNotFoundError: # no queue file failure
		print("ERROR: Couldn't find queue file!")
		sys.exit()
	queue.append(series)
	nextEpisode = getFirstEpisode(queue[0])
	f = open(CHANNEL_PATH+'queue.data', 'w')
	f.write('\n'.join(queue[1:]))
	f.close()
	return nextEpisode

# Given an episode, updates the schedule with the next episode in the series
# If there are no more episodes, then load the next episode in the queue
def updateScheduleWithNextEpisode(episode):
	foundEpisode = False
	timeslot = episode.timeslot
	for dirpath, dirnames, files in os.walk(CHANNEL_PATH + episode.series):
		for name in files:
			episodePath = os.path.join(dirpath, name)
			if episodePath == episode.path:
				foundEpisode = True
			# Found the next episode in the series
			elif foundEpisode and getSeries(episodePath) == episode.series:
				schedule[timeslot] = Episode(episodePath, timeslot)
				writeScheduleToDisk()
				return
	newSeriesFirstEpisode = updateQueueAndGetNextEpisode(episode.series)
	schedule[timeslot] = Episode(newSeriesFirstEpisode, timeslot)
	writeScheduleToDisk()

# plays the video for the appropriate timeslot, and then sleeps for the remaining
# duration of the videoLength. Then plays the timer video after for the remaining duration
# of the timeslot.
def playEpisode(episode, skipTime = 0):
	updateScheduleWithNextEpisode(episode)
	media = vlc_instance.media_new(episode.path)
	videoPlayer.set_media(media)
	videoPlayer.play()
	if skipTime != 0:
		videoPlayer.set_time(skipTime)
	if DEFAULT_MODE:
		sleepLength = (episode.getLength() - skipTime) / 1000
		CHANNEL_THREAD.wait(sleepLength)
		if not checkChannelStopped():
			playTimer()

# Gets the remaining time in the timeslot, in ms
def getRemainingTime():
	return HALF_HOUR - timePassedInTimeslot()

# Plays a random song in the music directory, and returns its length, in ms
def pickSongAndPlay():
	global musicPlayer
	musicPlayer.audio_set_volume(BASE_VOLUME)
	musicPath = CHANNEL_PATH+"..IGNORE - MUSIC\\"
	song = musicPath+random.choice([x for x in os.listdir(musicPath) if os.path.isfile(os.path.join(musicPath, x))])
	songLength = getLength(song)
	musicPlayer.set_media(vlc_instance.media_new(song))
	musicPlayer.play()
	return songLength

def playMusic():
	global musicPlayer
	songLength = pickSongAndPlay()
	while songLength < getRemainingTime(): #repeatedly play random songs until time is up
		CHANNEL_THREAD.wait(songLength/1000)
		if checkChannelStopped():
			return
		pickSongAndPlay()
	# Play at full volume for 75% of the duration, then fade to 0
	fadeDelayRation = 3/4
	CHANNEL_THREAD.wait(getRemainingTime()*fadeDelayRation/1000)
	remainingTime = getRemainingTime()
	for x in range(0,BASE_VOLUME):
		musicPlayer.audio_set_volume(BASE_VOLUME - x)
		CHANNEL_THREAD.wait(remainingTime/BASE_VOLUME/1000)
		if checkChannelStopped():
			return
	musicPlayer.stop()

#plays a timer that counts down until the next episode slot
#also plays music while playing the timer			
def playTimer():
	media = vlc_instance.media_new(r"assets\30_min_timer.mp4")
	videoPlayer.set_media(media)
	videoPlayer.play()
	videoPlayer.set_time(timePassedInTimeslot())#play the timer
	playMusic()
	playEpisode(schedule[getTimeslot()])

def checkChannelStopped():
	if CHANNEL_THREAD.isSet():
		videoPlayer.stop()
		musicPlayer.stop()
		CHANNEL_THREAD.clear()
		return True
	return False

def getCurrentPlayingEpisode():
	timeslot = getTimeslot()
	i = 0
	nextIndex = 0
	while (nextIndex <= timeslot):
		i = nextIndex
		nextIndex = i + schedule[i].getNumSlots()
	return schedule[i]

# Gets the time thats passed in the timeslot, in ms
def timePassedInTimeslot():
	return (now().second + now().minute % 30 * 60) * 1000

def now():
	return datetime.datetime.now().time()

def startChannel():
	videoPlayer.audio_set_volume(BASE_VOLUME)
	
	if DEFAULT_MODE:
		episode = getCurrentPlayingEpisode()
		# Setup our video player.
		# If we start in the middle of a timeslot, we also want to skip
		# the video to its proper time.\
		# Total time skipped = 
		# (number of extra timeslots * HALF HOUR) +
		# (number of seconds + number of minutes past the nearest half hour, in seconds)
		skipTime = ((getTimeslot()-episode.timeslot) * HALF_HOUR +
		timePassedInTimeslot())
		if skipTime < episode.getLength(): #if the episode would still be playing
			playEpisode(episode, skipTime)
		else:
			playTimer()
	numSlots = -1
	while True:
		if checkChannelStopped():
			break
		time.sleep(1) #check every second if we should load a new episode
		if DEFAULT_MODE:
			#the first minute of the half hour is a new slot
			if now().second < 30 and now().minute%30 == 0: 
				loadEpisodeForTimeslot(getTimeslot(), True)
		# new slot of 10 seconds for testing mode
		elif datetime.datetime.now().time().second%10 < 5: 
			loadEpisodeForTimeslot(getTimeslot(), True)
			CHANNEL_THREAD.wait(7)
	return 0

def isValidDirectory(directory):
	return not '..IGNORE' in directory

# gets the series from the full path of the episode
# DO NOT CHANGE THIS CODE EVER
def getSeries(fullPath):
	# Get the first slash after the channel directory
	# Return the substring between the channel directory and this slash
	slashIndex = fullPath.find('\\', len(CHANNEL_PATH))
	return fullPath[len(CHANNEL_PATH) : slashIndex]

# gets the first episode in the series, returns its full path
# DO NOT CHANGE THIS CODE EVER
def getFirstEpisode(series):
	for dirpath, dirnames, files in os.walk(CHANNEL_PATH + series + '\\'):
		for name in files:
			if isVideo(name):
				return os.path.join(dirpath, name)
	sys.exit()

#creates a new TV schedule for our episode
def createChannelData():
	global NUMBER_SLOTS
	episodes = []
	currentTime = int(round(time.time() * 1000))
	seriesList = list(filter(isValidDirectory, os.listdir(CHANNEL_PATH)))
	if (len(seriesList) < NUMBER_SLOTS + 1):
		print("ERROR: not enough series to fill timeslots.")
		sys.exit()
	random.shuffle(seriesList)
	# Go through the series, find the very first video file for that series
	for series in seriesList[:NUMBER_SLOTS]:
		episodes.append(getFirstEpisode(series))

	f = open(CHANNEL_PATH+'channel.data', 'w')
	f.write(str(currentTime)+'\n')
	f.write('\n'.join(episodes))
	f.close()
	f = open(CHANNEL_PATH+'queue.data', 'w')
	f.write('\n'.join(seriesList[NUMBER_SLOTS:]))
	f.close()
	return currentTime, episodes

def loadChannelData():
	try:
		with open(CHANNEL_PATH+'channel.data', 'r') as file:
			channelData = [line.rstrip() for line in file]
			file.close()
			lastWatchedTime = int(channelData[0])
			channelData = channelData[1:]
			if len(channelData) < NUMBER_SLOTS:
				print("ERROR: not enough series to fill timeslots. Found: "+str(len(channelData))+" Expected: "+str(NUMBER_SLOTS)+"\n")
				sys.exit()
			return lastWatchedTime, channelData
	except FileNotFoundError: #first time booting the channel, make new schedule
		return createChannelData()
	
def setupChannel(shouldSkip):
	global NUMBER_SLOTS
	global vlc_instance
	global videoPlayer
	global musicPlayer

	#number of timeslots exist in a day. Normally, we have 24 hours, which is equal to 48 slots of 30min each
	if DEFAULT_MODE:
		NUMBER_SLOTS = 48
	else: #in testing, we make timeslots 10s long, and make a day 1 minute long, so total timeslots is 6
		NUMBER_SLOTS = 6

		resetVariables()
	#setup the video player
	vlc_instance = vlc.Instance("--quiet")
	videoPlayer = vlc_instance.media_player_new()
	videoPlayer.toggle_fullscreen()
	musicPlayer = vlc_instance.media_player_new()
	
	lastWatchedTime, episodes = loadChannelData()
	for row in episodes:
		schedule.append(Episode(row, len(schedule)))
	
	if DEFAULT_MODE and shouldSkip:
		skipEpisodes(lastWatchedTime)
	thread = Thread(target = startChannel, args = ())
	thread.start()
	
#MAIN
root = Tk()
root.title("Episode Controller")
root.geometry("800x400")
app = Application(root)
root.mainloop()

			
