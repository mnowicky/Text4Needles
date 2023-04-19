'''
Created on Dec 5, 2018

'''
import pyodbc
import traceback
import time
import requests
import json
from Logger import Logger
from test import phonenum

class Receiver(object):
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

    def __init__(self, idle, smsHost, smsUser, smsPassword, dbhost, dbport, dbuser, dbpassword, dbdatabase,errorStaff):
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
        print("receiver run")
        try:
            while(self.running):
                if(self.connectDB()):
                    messages=self.receiveMessages()
                    if(messages!=None):
                        self.processMessages(messages)
                time.sleep(self.idle)
        except:
            Logger.writeAndPrintLine("An unexpected error occurred in sender, halting: "+traceback.format_exc(),3)  
    
    def receiveMessages(self):
        allData='{"method":"sms.read_sms","params":{'
        allData+='"login":"'+self.smsUser+'",'
        allData+='"pass":"'+self.smsPassword+'",'
        allData+='"folder":"inbox","unread":"1"}}'
        
        try:
            response=requests.post(self.webAddr,data=allData)
        except:
            Logger.writeAndPrintLine('Error receiving messages, could not connect to SMEagle. '
            +traceback.format_exc(), 3)    
            
        parsedJson=json.loads(response.text)
        if(type(parsedJson['result'])==type('x')):
            #Logger.writeAndPrintLine('Could not receive messages: '+parsedJson['result'],2)
            return None
        else:
            return parsedJson['result']
    
    def processMessages(self, messages):
        #print("printing all messages")
        for message in messages:
            #print(str(message))
            #get party
            phonenum=str(message['SenderNumber'][-10:])#cut off the country code (1) if it exists
            Logger.writeAndPrintLine("Receiving message "+message["ID"]+" from "+phonenum+".",1)  
            try:
                party_id=self.getPartyForPhonenum(phonenum)
                case_id=None
                if(party_id!=None):
                    case_id=self.getCaseForParty(party_id)
                recipient=self.getRecipient(party_id, case_id)        
                #print("Phone: "+phonenum+" Recipient: "+str(recipient)+" Message: "+message['TextDecoded'])
                self.sendMessage(phonenum, party_id, case_id, recipient, message['TextDecoded'])
                if(case_id!=None):
                    self.noteCase(phonenum, party_id, case_id, recipient, message['TextDecoded'])
                self.sendAutoReplyIfNeeded(phonenum, party_id, case_id) 
                Logger.writeAndPrintLine("Received message "+message["ID"]+" from "+phonenum+".",1) 
            except:
                Logger.writeAndPrintLine("Error receiving message "+message["ID"]+" from "+phonenum+": "+traceback.format_exc(),1)  
            
        #print("Awaiting input")
        #input()
            
    def getRecipient(self, party_id, case_id):
        
        if(party_id==None):
            return "DEFAULT"
        
        #see if we have a recent conversation. 
        recipient=self.getLatestStaff(party_id)
        if(recipient!=None):
            return recipient
        
        if(case_id==None):#we have a party with no case or conversation
            return "DEFAULT"
        
        recipient=self.getStaffForCase(case_id)
        if(recipient!=None):
            return recipient
        return "DEFAULT"
    
    def getPartyForPhonenum(self, phonenum):
        print("phonenum: "+str(phonenum))
        sql="select top 1 id from WKM_party_phone_numbers where phonenum='"+phonenum+"'"
        cursor=self.dbConnection.cursor()
        cursor.execute(sql)
        #cursor.execute(sql,(phonenum))
        results=cursor.fetchall()
        cursor.close()
        if(len(results)==0):
            print("No party found")
            return None
        else:
            print("Matching party found: "+str(results[0][0]))
            return results[0][0]
    
    def getCaseForParty(self, party_id):
        #first, check recent conversations. 
        sql="select top 1 casenum from WKM_SMS_outbound where names_id='"+str(party_id)+"'"
        cursor=self.dbConnection.cursor()
        cursor.execute(sql)
        results=cursor.fetchall()
        cursor.close()
        if(len(results)!=0):
            print("Matching case found from outbound: "+str(results[0][0]))
            return results[0][0]
        
        #check cases next. 
        sql="select top 1 casenum from cases "
        sql+= "left join party on cases.casenum=party.case_id where party_id='"+str(party_id)+"'"
        sql+= "order by cases.open_status desc, (case when matcode='MVA' then 1 else 2 end), date_opened desc, close_date desc"
        cursor=self.dbConnection.cursor()
        cursor.execute(sql)
        results=cursor.fetchall()
        cursor.close()
        if(len(results)!=0):
            print("Matching case found from cases"+str(results[0][0]))
            return results[0][0]
        print("No casenum found")
        return None
        
    def getLatestStaff(self, party_id):
        sql="select top 1 staff_id from WKM_SMS_outbound where status='sent' and names_id='"+str(party_id)+"' and staff_id<>'ZTEXT'"
        sql+="and date_created>=today()-14 order by date_created desc"
        print("outbound partyid: "+str(party_id))
        cursor=self.dbConnection.cursor()
        cursor.execute(sql)
        results=cursor.fetchall()   
        cursor.close()
        if(len(results)==0):
            print("no staff found in outbound: "+results[0][0])
            return None
        else:
            print("Matched staff from outbound")
            return results[0][0]
            
    def getStaffForCase(self, case_id):
        sql="select top 1 staff_2 from cases inner join staff on cases.staff_2=staff.staff_code "
        sql+= "where staff.active='Y' and casenum='"+case_id+"'"
        cursor=self.dbConnection.cursor()
        cursor.execute(sql)
        results=cursor.fetchall()   
        cursor.close()
        if(len(results)==0):
            print("No staff found in cases")
            return None
        else:
            print("Matching staff found in cases: "+results[0][0])
            return results[0][0]
        
        
    def sanitize(self, text):
        return text.replace("'","''")
    
    def sendMessage(self, phonenum, party_id, case_id, recipient, message):
        message=message.replace('\n','\x0d\x0a')
        cursor=self.dbConnection.cursor()
        if(recipient=="DEFAULT"):
            sql="exec WKM_InsertMessageGroup ?,?,?,?,?,?,? commit"
            cursor.execute(sql, ("RECEPTION", message, case_id, party_id, phonenum, "ZTEXT", "N"))
        else:
            sql="exec WKM_InsertMessageFrom ?,?,?,?,?,?,? commit"
            cursor.execute(sql, (recipient, recipient, message, case_id, party_id, phonenum, "ZTEXT"))
        cursor.close()
        Logger.writeAndPrintLine("Needles message sent to "+recipient+" regarding text from "+phonenum,1)  
 
    def noteCase(self, phonenum, party_id, case_id, recipient, message):
        message=message.replace('\n','\x0d\x0a')
        body="To: "+recipient+'\x0d\x0a'
        body+="Taken By: ZTEXT"+'\x0d\x0a'
        body+="Date: "+str(time.strftime('%m/%d/%Y %H:%M:%S'))+'\x0d\x0a'
        body+="Phone: "+phonenum+'\x0d\x0a'+'\x0d\x0a'
        body+="Message: "+message
        sql="exec WKM_InsertCaseNote ?,?,?,? commit"
        cursor=self.dbConnection.cursor()
        cursor.execute(sql, ("Text Message",body,"ZTEXT",case_id))
        cursor.close()
        Logger.writeAndPrintLine("Needles note added to case "+str(case_id)+" regarding text from "+phonenum,1)  
        
    def sendAutoReplyIfNeeded(self, phonenum, party_id, case_id):
        print("checking after hours")
        sql="select ( case "
        sql+="when today() IN (select holiday_date from holiday) then 'HOLIDAY' "
        sql+="when datepart(dw,today())>=2 and datepart(dw,today())<=6 "
        sql+="and datepart(hh,now())>=8 and datepart(hh,now())<=16 then 'OFFICEHOURS' "
        sql+="else 'AFTERHOURS' end)"
        cursor=self.dbConnection.cursor()
        cursor.execute(sql)
        results=cursor.fetchall()   
        cursor.close()
        if(results[0][0]!="OFFICEHOURS"):
            print("Not in office hours")
            sql="select * from WKM_SMS_outbound where convert(date,date_created)=today() and staff_id='ZTEXT' and phonenum=?"
            cursor=self.dbConnection.cursor()
            cursor.execute(sql,[phonenum])
            results=cursor.fetchall() 
            if(len(results)==0):
                message="Hello! Our office is currently closed, but we've received your message and will get back to you during regular business hours."
                sql="insert into WKM_SMS_Outbound(body,phonenum,casenum,names_id,status,staff_id) VALUES(?,?,?,?,?,?) commit"
                cursor=self.dbConnection.cursor()
                cursor.execute(sql, [message, phonenum, case_id, party_id, 'out','ZTEXT'])
                cursor.close()
                Logger.writeAndPrintLine("After hours message sent to "+phonenum,1)  
            else:
                Logger.writeAndPrintLine("Already sent after hours message to "+phonenum+", skipping.",1)  
        #1. DO we need to autoreply       
        #2. Have we already autoreplied
        #3. autoreply
        
        
        
        
