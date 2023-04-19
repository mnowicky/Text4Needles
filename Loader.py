'''
Created on Dec 5, 2018

'''
import configparser
import os
import sys
from threading import Thread
from Sender import Sender
from Receiver import Receiver
from Logger import Logger

class Loader(object):
    
    #config obj
    config = None
    configFileName="Text4Needles.config"
    
    #global
    runOnce=False
    idle=10
    errorStaff=''
    
    #SMS
    smsHost=""
    smsUser=""
    smsPassword=""
    
    #database params
    dbHost = None
    dbPort = 2638
    dbUser = 'dba'
    dbPassword = 'sql'
    dbDatabase = None
    
    #local vars
    sender=None
    receiver=None
    senderThread=None
    receiverThread=None

    def __init__(self):
        self.config = configparser.ConfigParser()
        
    def loadConfig(self):
        self.config.read(self.configFileName)
        
        #global configuration
        self.runOnce = self.config['DEFAULT']['runOnce']
        self.idle = int(self.config['DEFAULT']['idle'])
        self.errorStaff = self.config['DEFAULT']['errorStaff']
        
        #SMS configuration
        self.smsHost = self.config['SMS']['smsHost']
        self.smsUser = self.config['SMS']['smsUser']
        self.smsPassword = self.config['SMS']['smsPassword']
        
        #Database configuration
        self.dbHost = self.config['DATABASE']['host']
        self.dbPort = self.config['DATABASE']['port']
        self.dbUser = self.config['DATABASE']['user']
        self.dbPassword = self.config['DATABASE']['password']
        self.dbDatabase = self.config['DATABASE']['database']
        
    def printConfig(self):
        print("DEFAULT: ")
        print("runOnce: "+str(self.runOnce))
        print("idle: "+str(self.idle))
        print("errorStaff: "+str(self.errorStaff))
        print("")
        print("SMS: ")
        print("smsHost: "+self.smsHost)
        print("smsUser: "+self.smsUser)
        print("smsPassword: "+self.smsPassword)
        print("")
        print("DATABASE: ")
        print("dbHost: "+self.dbHost)
        print("dbPort: "+self.dbPort)
        print("dbUser: "+self.dbUser)
        print("dbPassword: "+self.dbPassword)
        print("dbDatabase: "+self.dbDatabase)
        
    def launch(self):
        Logger.writeAndPrintLine("Program started.", 0)
        self.loadConfig()
        print("Launching Text4Needles with the following parameters! :")
        self.printConfig()
        print("initializing classes")
        self.sender = Sender(self.idle, self.smsHost, self.smsUser, self.smsPassword, self.dbHost, self.dbPort, 
                             self.dbUser, self.dbPassword, self.dbDatabase, self.errorStaff)
        print("sender initialized")
        self.senderThread = Thread(target = self.sender.run)
        print("starting sender")
        self.senderThread.start()
        
        self.receiver = Receiver(self.idle, self.smsHost, self.smsUser, self.smsPassword, self.dbHost, self.dbPort, 
                             self.dbUser, self.dbPassword, self.dbDatabase, self.errorStaff)
        
        self.receiverThread = Thread(target = self.receiver.run)
        print("starting receiver")
        self.receiverThread.start()
        print("Finished launching.")
  
  
