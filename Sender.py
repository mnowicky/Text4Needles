'''
Created on Dec 5, 2018

@author: treusch
'''
import pyodbc
import traceback
import time
import requests
import json
import re
from Logger import Logger

class Sender(object):
    '''
    classdocs
    '''
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
    
    #operational vars
    idle=10
    dbConnection = None
    running = True
    webAddr=''
    errorStaff=''

    def __init__(self, idle, smsHost, smsUser, smsPassword, dbhost, dbport, dbuser, dbpassword, dbdatabase, errorStaff):
        self.idle=idle
        self.smsHost=smsHost
        self.smsUser=smsUser
        self.smsPassword=smsPassword
        self.dbHost=dbhost
        self.dbPort=dbport
        self.dbUser=dbuser
        self.dbPassword=dbpassword
        self.dbDatabase=dbdatabase
        self.webAddr='http://'+self.smsHost+'/index.php/jsonrpc/sms'
        self.errorStaff=errorStaff
        
    def connectDB(self):
        try:
            self.dbConnection = pyodbc.connect('UID='+self.dbUser+';PWD='+self.dbPassword+';DSN='+self.dbHost)
        except: 
            Logger.writeAndPrintLine("Could not connect specified database.", 3)    
            return False
        return True

    def disconnectDB(self):
        self.dbConnection.close()
        
    def run(self):
        print("sender run")
        try:
            while(self.running):
                if(self.connectDB()):
                    messages=self.getNeedMessages()
                    if(len(messages)==0):
                        continue
                    self.sendMessages(messages)
                time.sleep(self.idle)
        except:
            print("An unexpected error occurred in Sender, halting: "+traceback.format_exc())
            Logger.writeAndPrintLine("An unexpected error occurred in sender, halting: "+traceback.format_exc(),3)    
        
    def getNeedMessages(self):
        sql="select id, phonenum, body, staff_id, casenum, sp_name(names_id,1) as name, names_id"
        sql+=" from WKM_SMS_outbound where status='out'"
        cursor=self.dbConnection.cursor()
        cursor.execute(sql)
        messages=cursor.fetchall()
        return messages
        #messages function as a 2D array. len(messages)==0 when results are empty. 
        
    def sendMessages(self, messages):
        for message in messages:
            self.sendMessage(message)

    
          
    def sendMessage(self, message):
        '''
            in: {id, phonenum, message, staff}
        '''
        #We're going to use the "JSONRPC method". POST seems like a more intelligent way to pass large messages then GET.
        if(message[1]==None or message[1]==''):
            Logger.writeAndPrintLine("Can't send message "+str(message[0])+", must have a phone number.", 3)
            self.sendErrorMessage(message,"Can't send your message, could not locate a valid phone number for specified contact.", message[3])
            return None
        if(message[2]==None or message[2]==''):
            Logger.writeAndPrintLine("Can't send message "+str(message[0])+", must have a body.", 3)
            self.sendErrorMessage(message,"Can't send your message, you didn't type anything into the message body!", message[3])
            return None
        allData={}
        allData['method']="sms.send_sms"
        params={}
        params["login"]=self.smsUser
        params["pass"]=self.smsPassword
        params["to"]=message[1]
        params["message"]=self.cleanMessageHistory(message[2])
        allData["params"]=params
        allData=json.dumps(allData)
        #allData='{"method":"sms.send_sms","params":{'
        #allData+='"login":"'+self.smsUser+'",'
        #allData+='"pass":"'+self.smsPassword+'",'
        #allData+='"to":"'+message[1]+'",'
        #allData+='"message":"'+self.sanitizeMessage(message[2])+'"}}'
        print(allData)
        Logger.writeAndPrintLine('Sending message '+str(message[0])+' to '+str(message[1]), 1)
        try:
            response=requests.post(self.webAddr,data=allData)
        except:
            Logger.writeAndPrintLine('Error sending message '+str(message[0])+' Could not connect to SMEagle. '
                                     +traceback.format_exc(), 3)
            return
        parsedJson=json.loads(response.text)
        if('OK' in parsedJson['result']):
            smsID=re.search('ID=(\d*)\s', parsedJson['result']).group(1)
            Logger.writeAndPrintLine('Message sent. out:'+str(message[0])+', sms:'+str(smsID), 1)
            self.markMessageSent(message, smsID)
        else:
            errMessage='Error sending message '+str(message[0])+': '+parsedJson['result']+'. '+traceback.format_exc()
            Logger.writeAndPrintLine(errMessage, 3)
            self.sendErrorMessage(message, errMessage, self.errorStaff)

    
    def markMessageSent(self, message, smsID):
        sql="update WKM_SMS_outbound SET status='sent', date_sent=now(), sms_id='"
        sql+=str(smsID)+"' WHERE id='"+str(message[0])+"' commit"
        cursor=self.dbConnection.cursor()
        cursor.execute(sql)
    
    def markMessageError(self, message):
        sql="update WKM_SMS_outbound SET status='error' WHERE id='"+str(message[0])+"' commit"
        cursor=self.dbConnection.cursor()
        cursor.execute(sql)
        
    def sendErrorMessage(self, message, error, staff):
        body='Message unsent due to the following error: '+error+' \x0d\x0a'
        body+='To: '+str(message[5])+'\x0d\x0a'
        body+='Number: '+str(message[1])+'\x0d\x0a'
        body+='Casenum: '+str(message[4])+'\x0d\x0a'
        body+='Message: '+str(message[2])+'\x0d\x0a'
        body+='message_id: '+str(message[0])
        sql="exec WKM_InsertMessage ?,?,?,?,?,? commit"
        cursor=self.dbConnection.cursor()
        if(message[6]=="" or message[6]==0):
            nameID=None
        else:
            nameID=message[6]
        cursor.execute(sql,(staff,staff,body,message[4],nameID,message[1]))
        
        self.markMessageError(message)
        
    def cleanMessageHistory(self, message):
        histIndex=message.find("=============")
        if(histIndex>=0):
            return message[0:histIndex-1]
        else:
            return message
        
        