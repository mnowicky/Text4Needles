import time

class Logger(object):
    """description of class"""
    logFile="logFile.txt"

    @staticmethod
    def writeAndPrintLine(text, errorLevel):
        message=Logger.getTimeStamp()+' '+Logger.getErrorString(errorLevel)+':\t'+text
        file=open(Logger.logFile, "a")
        file.write(message+'\n')
        file.close()
        print(message)

    @staticmethod
    def getErrorString(errLevel):
        return {0 : "[SYSTEM]",
                1 : "[INFO]",
                2 : "[WARNING]",
                3 : "[ERROR]",
                4 : "[FATAL]",
                5 : "[DEBUG]"
               }.get(errLevel, "[UNKNOWN]")

    @staticmethod
    def getTimeStamp():
        return str(time.strftime('%Y-%m-%d %H:%M:%S'))
                