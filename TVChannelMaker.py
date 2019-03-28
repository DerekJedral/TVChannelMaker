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

videoPlayer = 0
vlc_instance = 0
musicPlayer = 0

CHANNEL_PATH = 0
channelData = 0
schedule = []
lastWatchedTime = 0

slotCounter = 0 # sometimes shows will go for more than half an hour, in which case we override other shows
previousSlot = -1 #the previous video we played
totalNumSlots = -1 #number of slots this episode is going to take

root = 0

stopChannel = False
shouldSkip = False
PLAY_MODE = "Default"

NUMBER_SLOTS = 48
HALF_HOUR = 1800000
BASE_VOLUME = 70
exit = threading.Event()

class Application(Frame):
	def __init__(self, master):
		Frame.__init__(self,master)
		self.grid()
		self.inNormalMode = True
		self.create_widgets()
	
	def create_widgets(self):
		global shouldSkip
		self.addInitialButtons()
		self.text = Text(self, width = 60, height = 20, wrap= WORD)
		self.text.grid(row=1, column =1,rowspan=3, sticky = E)
		
		self.buttonSkip = Button(self)
		self.buttonSkip["text"] = "Skip episodes: "+str(shouldSkip)
		self.buttonSkip["command"] = self.toggle_skip
		self.buttonSkip.grid(row=3, column=2, sticky=W)
		
	def open_guide(self):
		self.text.delete(0.0, END)
		counter = 0
		scheduleString = ""
		totalSlots = 0
		currentEpisodeTitle = ""
		for episode in schedule:
			if self.inNormalMode:
				temp = time.strftime('%H:%M', time.gmtime(counter*1800))
				scheduleString = scheduleString+temp+":"	
			else:
				scheduleString = scheduleString+ str(counter)+":"
			if totalSlots == 0:
				totalSlots =  math.floor(episode.length/1000/60/30)
				currentEpisodeTitle = episode.title
				scheduleString=scheduleString+episode.title+"\n"
			else:
				totalSlots=totalSlots-1
				scheduleString=scheduleString+currentEpisodeTitle+"\n"
			counter=counter+1
		
		self.text.insert(0.0, scheduleString)
	def stop_channel(self):
		global stopChannel
		exit.set()
		
		self.text.delete(0.0, END)
		self.text.insert(0.0, "Stopping Channel")
		
		self.buttonGuide.grid_forget()
		self.buttonStop.grid_forget()
		self.addInitialButtons()
		self.addStoppedButtons()
		
	def pick_channel(self):
		global CHANNEL_PATH
		root = tk.Tk()
		root.withdraw()
		CHANNEL_PATH = tk.filedialog.askdirectory()
		if not CHANNEL_PATH.endswith("/") and not CHANNEL_PATH.endswith("\\"):
			CHANNEL_PATH = CHANNEL_PATH+"/"
		self.text.delete(0.0, END)
		self.text.insert(0.0, "Channel: "+CHANNEL_PATH)
		self.addStoppedButtons()
	
	def startChannel(self):
		global stopChannel
		self.buttonStart.grid_forget()
		self.buttonToggle.grid_forget()
		self.buttonQuit.grid_forget()
		self.buttonPick.grid_forget()
		self.addPlayingButtons()
		resetVariables()
		setupChannel()

	def addInitialButtons(self):
		self.buttonQuit = Button(self)
		self.buttonQuit["text"] = "Quit"
		self.buttonQuit["command"] = self.quit_application
		self.buttonQuit.grid(row=0, column=2, sticky=W)
	
		self.buttonPick = Button(self)
		self.buttonPick["text"] = "Pick Channel"
		self.buttonPick["command"] = self.pick_channel
		self.buttonPick.grid(row=1, column=0, sticky=W)
	
	def addStoppedButtons(self):
		self.buttonStart = Button(self)
		self.buttonStart["text"] = "Start Channel"
		self.buttonStart["command"] = self.startChannel
		self.buttonStart.grid(row=2, column=0, sticky=W)
		
		self.buttonToggle = Button(self)
		if self.inNormalMode:
			self.buttonToggle["text"] = "Switch to test mode"
		else:
			self.buttonToggle["text"] = "Switch to default mode"
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
		global NUMBER_SLOTS
		global PLAY_MODE
		global schedule
		schedule = []
		if self.inNormalMode:
			self.buttonToggle["text"] = "Switch to default mode"
			self.inNormalMode = False
			resetVariables()
			PLAY_MODE = "Test"
		else:
			self.buttonToggle["text"] = "Switch to test mode"
			self.inNormalMode = True
			resetVariables()
			PLAY_MODE = "Default"
	
	def toggle_skip(self):
		global shouldSkip
		shouldSkip = not shouldSkip
		self.buttonSkip["text"] = "Skip episodes: "+str(shouldSkip)
			
		
	def quit_application(self):
		quitApplication()

class Episode(object):
	def __init__(self, path):
		self.path = path.replace("\\", "/").rstrip()
		self.folder = getPath(self.path)
		self.length = getLength(self.path)
		try:
			with open(self.path[:self.path.rfind("/")+1]+'series.data','r') as file:
				seriesData = file.readlines()
			
			self.title = seriesData[0].rstrip()
			file.close()
		
		except FileNotFoundError:
			if self.length > 1000 * 60 * 60: #we define movies to be over an hour
				self.title = self.path[self.path.rfind("/")+1:self.path.rfind(".")]
			else:
				try:
					with open(self.folder+'series.data', 'r') as file:
						seriesData = file.readlines()
					
					self.title = seriesData[0].rstrip()
					file.close()
				
				except FileNotFoundError: #data file for series does not exist, so we'll create a new one
					index = self.folder.rfind("/",0,len(self.folder)-1)
					self.title = self.folder[index+1:len(self.folder)-1]

def isVideo(name):
	return name.lower().endswith(".avi") or name.lower().endswith(".mpg") or name.lower().endswith(".mpeg") or name.lower().endswith(".asf") or name.lower().endswith(".wmv") or name.lower().endswith(".wma") or name.lower().endswith(".mp4") or name.lower().endswith(".mov") or name.lower().endswith(".3gp") or name.lower().endswith(".ogg") or name.lower().endswith(".ogm") or name.lower().endswith(".mkv")
	
def resetVariables():
	global videoPlayer
	global musicPlayer
	global vlc_instance
	global channelData
	global schedule
	global slotCounter
	global previousSlot
	global stopChannel
	
	videoPlayer = 0
	musicPlayer = 0
	vlc_instance = 0
	channelData = 0
	schedule = []
	slotCounter = 0 # sometimes shows will go for more than half an hour, in which case we override other shows
	previousSlot = -1 #the previous video we played
	stopChannel = False
	root = 0

def quitApplication():
	root.destroy()
	exit.set()
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
			
	return 1799999
	
def getPath(fullPath):
	global CHANNEL_PATH
	choppedPath = fullPath[len(CHANNEL_PATH):]
	if choppedPath.find("/") != -1:
		choppedPath = choppedPath[:choppedPath.find("/")] #get path to show folder
	nextpath = CHANNEL_PATH + choppedPath
	nextpath = nextpath.replace("\\", "/")
	nextpath = nextpath+'/'
	return nextpath

#re-writes and reads our channel data file, so we have an updated one for future use and the schedule		
def reloadData():
	global channelData
	global schedule
	with open(CHANNEL_PATH+'channel.data', 'w') as file:
		file.write(str(int(round(time.time() * 1000)))+"\n")
		file.writelines(channelData)
	
	with open(CHANNEL_PATH+'channel.data', 'r') as file:
		channelData = file.readlines()
	channelData = channelData[1:]
	file.close()
	schedule = []
	loadSchedule()
	
#update our channel.data file with our current episode progress
def updateData(timeslot, path):
	channelData[timeslot] = path
	reloadData();

#if we were away from the channel, we missed episodes airing. So, we skip them
def skipEpisodes():
	global lastWatchedTime

	currentTime = int(round(time.time() * 1000))
	while (currentTime - lastWatchedTime) > HALF_HOUR:
		lastSeenDate = datetime.datetime.fromtimestamp(lastWatchedTime/1000.0)
		timeslot = lastSeenDate.time().hour*2 +  math.floor(lastSeenDate.time().minute/30)
		loadNextEpisode(timeslot, False)
		lastWatchedTime = lastWatchedTime + HALF_HOUR
	
	return None

#creates a new TV schedule for our episode
def createNewSchedule():
	global channelData
	global NUMBER_SLOTS
	channelData = []
	counter = 0
	for dirpath, dirnames, files in os.walk(CHANNEL_PATH):
		for name in files:
			if isVideo(name):
				isAdded = False
				for row in channelData: #iterate through all episodes we've added to see if we've added this show yet
					index = os.path.join(dirpath, name).find("\\",len(CHANNEL_PATH))
					if row.find(os.path.join(dirpath, name)[:index]) != -1:
						isAdded = True
						break
				
				if isAdded is False: #add our episode to the schedule
					channelData.append(os.path.join(dirpath, name)+"\n")
					counter = counter+1
			if counter == NUMBER_SLOTS:
				break
		if counter == NUMBER_SLOTS:
			break
	
	if counter < NUMBER_SLOTS:
		print("ERROR: not enough series to fill timeslots. Found: "+str(counter)+" Expected: "+str(NUMBER_SLOTS)+"\n")
		exit()
	else:
		f = open(CHANNEL_PATH+'channel.data', 'w')
		f.write(str(int(round(time.time() * 1000)))+"\n")
		f.writelines(channelData)
		f.close()
		
#load video schedule
def loadSchedule():
	for row in channelData:
		episode = Episode(row)
		schedule.append(episode)

# writes to a series flag file
def updateFlagFile(path, isEligible, seriesTitle):
	eligibility = isEligible + "\n"
	try: # we update both the flag of the show we will air next, and the show that comes after
		with open(path+'series.data', 'r') as file:
			seriesData = file.readlines()
		seriesData[1] = eligibility
		
		with open(path+'series.data', 'w') as file:
			file.writelines(seriesData)
		
		file.close()
	except FileNotFoundError: #data file for series does not exist, so we'll create a new one
		index = path.rfind("/", 0, len(path)-1)
		if seriesTitle is None:
			seriesTitle =  path[index+1:len(path)-1]
	
		f = open(path+'series.data', 'w')
		f.write(seriesTitle+"\n")
		f.write(eligibility)
		f.close()

#update the flag our next series, and the series after that
def updateFlags(path):
	foundCurrentDirectory = False
	foundUpdateDirectory = False
	
	updateFlagFile(path, "false", None)
	
	for dirpath, dirname,files in os.walk(CHANNEL_PATH):
		if foundCurrentDirectory and (dirpath.replace("\\", "/")+'/' != path): #we found the next series. let's update the flag
			updateFlagFile(getPath(dirpath), "true", None)
			return None
		elif (dirpath.replace("\\", "/")+'/' == path):
			foundCurrentDirectory = True
		
	#there is no next series, so we start from the first one again
	for dirpath, dirname,files in os.walk(CHANNEL_PATH):
		for name in files:
			if isVideo(name):
				dirpath = dirpath.replace("\\", "/")
				updateFlagFile(dirpath, "true", None)
				return None
		
#Look at the metadata file for the series, and determine if it's eligable to air
def isEligibleVideo(path):
	try:
		with open(path+'series.data', 'r') as file:
			flags = file.readlines()
	except FileNotFoundError:
		return True
	
	file.close()
	return flags[1].find("false") == -1

# we have to either find the next episode in the series to air, or a brand new series
def updateSeries(timeslot):
	if timeslot == -1: #we have not set to update
		return None
	
	foundCurrentVideo = False
	nextEpisode = None
	firstEpisode = None
	firstPath = ''
	
	for dirpath, dirnames, files in os.walk(CHANNEL_PATH):
		for name in files:
			if isVideo(name):
				video = os.path.join(dirpath, name).replace("\\", "/")
				path = getPath(video)
				if firstEpisode is None: #also save the very first show that's not airing in our channel
					isAiring = False
					for episode in schedule:
						if episode.folder == path:
							isAiring = True
							break
					if isAiring is False: #
						firstEpisode = video
				if not foundCurrentVideo: #loop until we find the episode we just watched, and then every episode after is a candidate
					if video == schedule[timeslot].path:
						foundCurrentVideo = True
					continue
				if foundCurrentVideo or nextEpisode is None: # we found either the next episode, or a new series
					for episode in schedule:
						if episode.folder == path:
							break # the series is currently airing, so we break out of the current loop, but keep searching
					if isEligibleVideo(path): #show is not airing and is eligable, so let's update our channel schedule
						if nextEpisode is None:
							nextEpisode = video
						elif nextEpisode is not None and foundCurrentVideo: # we found an eligible series after our current one, so that takes priority
							updateData(timeslot, video+"\n")
							updateFlags(path) # update metadata of video to show that its now airing
							return None
					if foundCurrentVideo and schedule[timeslot].path.find(path) != -1: # we found the next episode in the series
						updateData(timeslot, video+"\n")
						return None
						
	if nextEpisode is None: # we couldn't find an eligible series at all. Should never happen in theory
		nextEpisode = firstEpisode #since there's no eligible series, we have to start from the beginning
	print("next episode: "+nextEpisode)
	updateData(timeslot, nextEpisode+"\n")
	updateFlags(getPath(nextEpisode)) # update metadata of video to show that its now airing

#gets our current timeslot
def getTimeslot():
	if PLAY_MODE == "Default":
		timeslot = datetime.datetime.now().time().hour*2 +  math.floor(datetime.datetime.now().time().minute/30)
	else:
		timeslot = math.floor(datetime.datetime.now().time().second/10)
	
	return timeslot
	
# load the appropriate episode for the corresponding timeslot
# if we're in the middle of a movie, we do nothing
# timeslot: the next timeslot we're in
# shouldPlay: whether we actually want to play the episode in VLC, or just skip it
def loadNextEpisode(timeslot, shouldPlay):
	global slotCounter
	global previousSlot
	global totalNumSlots
	if slotCounter ==  totalNumSlots: # this case occurs if we have just started a new episode.
		updateSeries(previousSlot)  # if we started a new episode, we have to update the previous series we were watching to it's next episode tomorrow.
	if (slotCounter <= 0): # episode is over, load a new one
		slotCounter = math.floor(getLength(schedule[timeslot].path)/HALF_HOUR) #calculate how many slots the new show needs
		totalNumSlots = slotCounter
		previousSlot = timeslot
		if shouldPlay:
			playAndSleep(timeslot)
	else: #episode is still going, reduce the counter
		slotCounter = slotCounter - 1
	
	return 0
	
#plays the video for the appropriate timeslot, and then sleeps for the remaining duration of the videoLength
#then plays the timer video after
def playAndSleep(timeslot, skipTime = 0):
	media = vlc_instance.media_new(schedule[timeslot].path)
	videoPlayer.set_media(media)
	videoPlayer.play()
	if skipTime != 0:
		videoPlayer.set_time(skipTime)
	if PLAY_MODE == "Default":
		sleepLength = (getLength(schedule[timeslot].path) - skipTime)/1000
		exit.wait(sleepLength)
		if not checkChannelStopped():
			playTimer()

#plays a timer that counts down until the next episode slot
#also plays music while playing the timer			
def playTimer():
	global musicPlayer
	media = vlc_instance.media_new(r"assets\30_min_timer.mp4")
	videoPlayer.set_media(media)
	videoPlayer.play()
	timePassed = datetime.datetime.now().time().second*1000+(datetime.datetime.now().time().minute%30)*1000*60
	timeRemaining = 1000*60*30 - timePassed
	counter = timeRemaining
	videoPlayer.set_time(timePassed)#play the timer
	musicPlayer.audio_set_volume(BASE_VOLUME)
	musicPath = CHANNEL_PATH+"_music\\"
	while True: #repeatedly play random songs until time is up
		song = musicPath+random.choice([x for x in os.listdir(musicPath) if os.path.isfile(os.path.join(musicPath, x))])
		songLength = getLength(song)
		sleepTime = songLength
		musicPlayer.set_media(vlc_instance.media_new(song))
		musicPlayer.play()
		if songLength < timeRemaining: #if we can play the whole song, let's do it
			exit.wait(songLength/1000)
			if checkChannelStopped():
				return
			timeRemaining = timeRemaining - songLength - 1
		else: #we can't play the whole song, so we fade to 0 volume over time
			fadeDelayRation = 3/4
			exit.wait(timeRemaining*fadeDelayRation/1000)
			volume = BASE_VOLUME
			for x in range(0,BASE_VOLUME):
				volume = volume - 1
				musicPlayer.audio_set_volume(volume)
				exit.wait(timeRemaining*(1-fadeDelayRation)/BASE_VOLUME/1000)
				if checkChannelStopped():
					return
			break

	musicPlayer.audio_set_volume(BASE_VOLUME)
	musicPlayer.stop()

def checkChannelStopped():
	if exit.isSet():
		videoPlayer.stop()
		musicPlayer.stop()
		exit.clear()
		return True
	return False
	
def startChannel():
	videoPlayer.audio_set_volume(BASE_VOLUME)
	if PLAY_MODE == "Default":
		timeslot = datetime.datetime.now().time().hour*2 +  math.floor(datetime.datetime.now().time().minute/30) #calculate current timeslot
		counter = 0
		playingIndex = 0
		numSlots = 0
		while (counter <= timeslot): # we go through our schedule, and figure out when things are playing. Movies take longer, and so take more slots, calculated to the nearest half hour rounded up
			if (numSlots <= 0):
				numSlots = math.floor(schedule[counter].length/HALF_HOUR)
				playingIndex = counter
			else:
				numSlots = numSlots - 1
			
			counter = counter + 1
		
		#setup our video player. If we start in the middle of a timeslot, we also want to skip the video to its proper time
		skipTime = datetime.datetime.now().time().second*1000+(datetime.datetime.now().time().minute%30)*1000*60+HALF_HOUR*(math.floor(schedule[playingIndex].length/HALF_HOUR)-numSlots)
		videoLength = getLength(schedule[getTimeslot()].path)
		if skipTime < videoLength: #if the episode would still be playing
			playAndSleep(playingIndex, skipTime)
		else:
			print("skipping, skipTime "+str(skipTime)+" vidLength "+str(getLength(schedule[getTimeslot()].path)) + " asd")
			playTimer()
	while True:
		if checkChannelStopped():
			break
		time.sleep(1) #check every second if we should load a new episode
		if PLAY_MODE == "Default":
			if datetime.datetime.now().time().second < 30 and datetime.datetime.now().time().minute%30 == 0: #the first minute of the half hour is a new slot
				loadNextEpisode(getTimeslot(), True)
		
		elif datetime.datetime.now().time().second%10 < 5: # new slot of 10 seconds for testing mode
			loadNextEpisode(getTimeslot(), True)
			exit.wait(7)
		
	return 0

def setupChannel():
	global CHANNEL_PATH
	global PLAY_MODE
	global shouldSkip
	global channelData
	global videoPlayer
	global vlc_instance
	global musicPlayer
	global NUMBER_SLOTS
	global lastWatchedTime

	#number of timeslots exist in a day. Normally, we have 24 hours, which is equal to 48 slots of 30min each
	if PLAY_MODE == "Default":
		NUMBER_SLOTS = 48
	else: #in testing, we make timeslots 10s long, and make a day 1 minute long, so total timeslots is 6
		NUMBER_SLOTS = 6

	#setup the videoe player
	vlc_instance = vlc.Instance("--quiet")
	videoPlayer = vlc_instance.media_player_new()
	videoPlayer.toggle_fullscreen()
	musicPlayer = vlc_instance.media_player_new()
	
	#load up the channel where we left off from
	try:
		with open(CHANNEL_PATH+'channel.data', 'r') as file:
			channelData = file.readlines()
			file.close()
			lastWatchedTime = int(channelData[0].rstrip())
			channelData = channelData[1:]
			if len(channelData) < NUMBER_SLOTS:
				print("ERROR: not enough series to fill timeslots. Found: "+str(len(channelData))+" Expected: "+str(NUMBER_SLOTS)+"\n")
				exit()
	except FileNotFoundError: #first time booting the channel, make new schedule
		createNewSchedule()
		lastWatchedTime = int(round(time.time() * 1000))
	
	loadSchedule()
	for series in schedule: #these should in theory be set, but won't be for the very first time.
		updateFlagFile(series.folder, "false", series.title)
		
	if PLAY_MODE == "Default" and shouldSkip:
		skipEpisodes()
	thread = Thread(target = startChannel, args = ())
	thread.start()
	
#MAIN
root = Tk()
root.title("Episode Controller")
root.geometry("600x400")
app = Application(root)
root.mainloop()

			
