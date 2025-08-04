import logging
import os
import datetime
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
class BonusResponse:
    def __init__(self,logging=False):
        self.realTime = None
        self.backendTime = None
        self.realTimeZone = None
        self.realTime_backendTimeDiff = None
        self.data = {
            "userId": None,
            "username": None,
            
            "isValid": False,
            "ValidMessage": None,
            "validCode": None,
            "validLogs": None,
            "validArgs": [],
            "logs": [],
            
            "SystemError": False,
            "SystemErrorMessage": None,
            
            "bonusLoad": False,
            "bonusLoaded": False,
            "bonuses": [],
        }
        self.logging = logging
        
    def setKey(self, key, value):
        self.data[key] = value
        return self.data
    
    def returnData(self):
        if self.logging:
            if self.data.get("SystemError"):
                logs_dir = os.path.join(os.getcwd(), "logs")
                os.makedirs(logs_dir, exist_ok=True)
                
                current_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                bonus_id = self.data.get("bonusId", "unknown")
                filename = f"{current_date}_bonus_{bonus_id}.txt"
                
                log_path = os.path.join(logs_dir, filename)
                with open(log_path, "w") as log_file:
                    log_file.write(f"Error Log for Bonus ID: {bonus_id}\n")
                    log_file.write(f"Time: {self.realTime}\n")
                    log_file.write(f"System Error: {self.data.get('SystemError')}\n")
                    log_file.write(f"Error Message: {self.data.get('SystemErrorMessage', 'N/A')}\n")
                    log_file.write(f"Valid: {self.data.get('isValid')}\n")
                    log_file.write(f"Valid Message: {self.data.get('ValidMessage', 'N/A')}\n\n")
                    log_file.write("--- Log Entries ---\n")
                    for log in self.data.get("logs", []):
                        log_file.write(f"{log}\n")
        self.data["finishTime"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
        
        return self.data
    
    def log(self, message):
        # Use current time if realTime is not set yet
        timeStr = self.realTime if self.realTime else datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        logMessage = f"{timeStr} - {message}"
        logging.info(logMessage)
        self.data["logs"].append(logMessage)
        return self.data
    
    def setValid(self, ValidMessage, isValid, validCode=None, errorIn=None,args:dict=None):
        self.data["ValidMessage"] = ValidMessage
        self.data["isValid"] = isValid
        self.data["validCode"] = validCode
        self.data["errorIn"] = errorIn
        if args:
            self.data["validArgs"] = [{"key": key, "value": value} for key, value in args.items()]
        return self.data
    
    def setSystemError(self, SystemErrorMessage:str, errorIn=None, validCode=10000):
        self.data["SystemErrorMessage"] = SystemErrorMessage
        self.data["SystemError"] = True
        self.data["validCode"] = validCode
        self.data["errorIn"] = errorIn
        return self.data
    
    def deleteKey(self, key):
        self.data.pop(key)
        return self.data
