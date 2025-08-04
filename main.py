import requests
import json
import subprocess
import shlex
from Helper.SeleniumSession import SeleniumSession
from datetime import datetime
from tqdm import tqdm
import time
from datetime import timedelta,timezone
from curlManager import CurlManager
import pyotp
from typing import Union
import inspect

from SeleniumManager import SeleniumSessionManager
import base64
import re

import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



class FenomenSession:
    def __init__(self,Manager:SeleniumSessionManager,RealTime:datetime=None,RealTimeZoneDiff:int=None):
        self.seleniumManager = Manager
        self.curlManager = CurlManager()
        self.RealTime = RealTime
        self.RealTimeZone = RealTimeZoneDiff
        self.seleniumSession = self.seleniumManager.get_next_session()
        if not self.seleniumSession:
            raise Exception("No available Selenium session")
        
        self.dataFolder = self.seleniumSession.folder
        print("FenomenSession initialized - SeleniumSessionId : ", self.seleniumSession.sessionId)
        
        res = self.refresh_loginData()
        try:
            self.AuthToken = self.refresh_token()
        except Exception as e:
            print(f"Error: {e}")
            self.AuthToken = None
        
        self.base_url = "https://sd.bopanel.com"
        self.playerList = []
        
    def refreshSessionData(self,seleniumSession:SeleniumSession):
        self.seleniumSession = seleniumSession
        self.dataFolder = seleniumSession.folder
        self.refresh_loginData()
        try:
            self.AuthToken = self.refresh_token()
        except Exception as e:
            print(f"Error: {e}")
            self.AuthToken = None
    
    
    def refresh_loginData(self):
        try:
            with open(f'{self.dataFolder}/loginSuccessData.json', 'r') as f:
                self.loginRequestData = json.load(f)
                self.uid = self.loginRequestData['uid']
                self.secCHUA = self.curlManager.escapeString(self.loginRequestData['secCHUA'])
                user_agent = self.curlManager.escapeString(self.loginRequestData['userAgent'])
                self.userAgent = user_agent.replace("HeadlessChrome","Chrome")
                
                self.platform = self.loginRequestData['platform']
                #self.platform = '\\"Linux\\"'
                
                
                #self.userAgent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
                #self.secCHUA = '\\"Google Chrome\\";v=\\"135\\", \\"Not-A.Brand\\";v=\\"8\\", \\"Chromium\\";v=\\"135\\"'
                
                
                print(f"UserAgent: {self.userAgent}")
                print(f"platform: {self.platform}")
                
            return True
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    def parse_datetime(self,date_str, toUtc3 = False):
        if "." in date_str:
            date_part, milli_part = date_str.split(".")
            milli_part = milli_part[:6].rstrip("Z")
            date_str = f"{date_part}.{milli_part}"

        try:
            if toUtc3:
                return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f") + timedelta(hours=3)
            
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            if toUtc3:
                return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S") + timedelta(hours=3)
            
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")  
    
    def refresh_token(self, max_attempts=3):
        attempt = 0
        while attempt < max_attempts:
            try:
                self.refresh_loginData()
                curl_command = f'''curl "https://apisd.bopanel.com/token" \
                -H "accept: application/json, text/plain, */*" \
                -H "accept-language: en-US,en;q=0.9" \
                -H "content-type: application/x-www-form-urlencoded" \
                -H "origin: https://sd.bopanel.com" \
                -H "priority: u=1, i" \
                -H "referer: https://sd.bopanel.com/" \
                -H "sec-ch-ua: {self.secCHUA}" \
                -H "sec-ch-ua-mobile: ?1" \
                -H "sec-ch-ua-platform: {self.platform}" \
                -H "sec-fetch-dest: empty" \
                -H "sec-fetch-mode: cors" \
                -H "sec-fetch-site: same-site" \
                -H "timezone: 3" \
                -H "uid: {self.generate_uid(self.uid)}" \
                -H "user-agent: {self.userAgent}" \
                --data-raw "client_id={self.loginRequestData['client_id']}&grant_type=refresh_token&refresh_token={self.loginRequestData['refresh_token']}"'''
                
                result = self.run_curl_command(curl_command)
                
                if result.returncode == 0:
                    try:
                        response_data = json.loads(result.stdout)
                        new_token = response_data.get("access_token")
                        
                        if (new_token):
                            return new_token
                            
                        print(f"Token boş döndü (Deneme {attempt + 1}/{max_attempts})")
                    except json.JSONDecodeError:
                        print(f"JSON parse hatası (Deneme {attempt + 1}/{max_attempts})")
                        
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(1)
                else:
                    next_session = self.seleniumManager.get_next_session()
                    if next_session:
                        self.refreshSessionData(next_session)
                    return None
                    
            except Exception as e:
                print(f"Hata oluştu: {str(e)} (Deneme {attempt + 1}/{max_attempts})")
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(2)

        return None
    
    def _b64_strip_prefix(self,value: str) -> str:
        """Base64‑kodlu metindeki 'Mj' (\x32\x4a) ön ekini ve '=' pad'lerini temizle."""
        return value.rstrip("=")[2:]


    def encode_timestamp(self,timestamp: Union[str, int], *, auto: bool = True) -> str | dict[str, str]:
        """Timestamp'i kodlar.

        auto=True  → Sadece uygun tek parçayı döndürür.
                     Eğer **suffix parçasının** ilk karakteri küçük harfse (a–z) onu seçer;
                     aksi halde **full parça** seçilir.

        auto=False → Her iki parçayı sözlük olarak döndürür {"suffix": .., "full": ..}.
        """
        ts_str = str(timestamp)

        part_suffix_raw = ts_str[-8:]
        b64_suffix = base64.b64encode(part_suffix_raw.encode()).decode()
        suffix_segment = self._b64_strip_prefix(b64_suffix)

        b64_full = base64.b64encode(ts_str.encode()).decode()
        full_segment = self._b64_strip_prefix(b64_full)

        if not auto:
            return {"suffix": suffix_segment, "full": full_segment}

        #segment = full_segment if suffix_segment[0].islower() else suffix_segment
        segment = suffix_segment if suffix_segment[0] == 'Y' else full_segment
        type = "full" if segment == full_segment else "suffix"
        logging.info(f" Selected mode: {type} = {timestamp} -> {segment}")
        return [segment, type]
    
    def findTimeStampType(self, base_uid: str) -> str:
        if "==" in base_uid:
            parts = base_uid.rsplit('==',1)
        elif "%3D%3D" in base_uid:
            parts = base_uid.rsplit('%3D%3D', 1)
        elif "%3D" in base_uid:
            parts = base_uid.rsplit('%3D', 1)
        elif "=" in base_uid:
            parts = base_uid.rsplit('=', 1)
        else:
            raise ValueError("Invalid UID format")
        encoded = self.encode_timestamp(parts[1],auto=False)
        
        if encoded["full"] in base_uid:
            return "full"
        elif encoded["suffix"] in base_uid:
            return "suffix"
        
    
    def generate_uid(self,base_uid: str) -> str:
        #return "NzcxMTExMjIxMDUxMDgxMDg5NzQ3NTM0NjQ4MzI0MDg3MTA1MTEwMTAwMTExMTE5MTE1MzI3ODg0MzI0OTQ4NDY0ODU5MzI4NzEwNTExMDU0NTI1OTMyMTIwNTQ1MjQxMzI2NTExMjExMjEwODEwMTg3MTAxOTg3NTEwNTExNjQ3NTM1MTU1NDY1MTU0MzI0MDc1NzI4NDc3NzY0NDMyMTA4MTA1MTA3MTAxMzI3MTEwMTk5MTA3MTExNDEzMjY3MTA0MTE0MTExMTA5MTAxNDc0OTUxNTM0NjQ4NDY0ODQ2NDgzMjgzOTcxMDI5NzExNDEwNTQ3NTM1MTU1NDY1MTU0MTc0NTQxNzQzMDcxMw==1745417430713"
        
        # fonksinun çağrıldığı fonksionun ismini print edelim
        caller = inspect.stack()[1]
        print(f"Called from function '{caller.function}' at line {caller.lineno} in {caller.filename}")
        
        try:
            # Ayrıştırma
            if "==" in base_uid:
                parts = base_uid.rsplit('==',1)
            elif "%3D%3D" in base_uid:
                parts = base_uid.rsplit('%3D%3D', 1)
            elif "%3D" in base_uid:
                parts = base_uid.rsplit('%3D', 1)
            elif "=" in base_uid:
                parts = base_uid.rsplit('=', 1)
            else:
                raise ValueError("Invalid UID format")
            base64_part = parts[0]
            timestamp_part = parts[1]
            
            timeStampType = self.findTimeStampType(base_uid)
            
            encoded_timestamp = self.encode_timestamp(timestamp_part, auto=False)[timeStampType]
            base64_part = base64_part[:-(len(encoded_timestamp) + 1)]
            base64_part += "T"
            
            nowTimestamp = int((datetime.now(timezone.utc)).timestamp() * 1000) - 1000 
            print(nowTimestamp)
            if self.RealTime:
                if self.RealTimeZone != None and self.RealTimeZone != 0:
                    nowTimestamp = int((self.RealTime + timedelta(hours=self.RealTimeZone)).timestamp() * 1000) - 1000
                    print(nowTimestamp)
                else:
                    nowTimestamp = int(self.RealTime.timestamp() * 1000) - 1000
                    print(self.RealTime.timestamp() * 1000)
            
            newEncoded_timestamp = self.encode_timestamp(str(nowTimestamp),auto=False)[timeStampType]
            #logging.info(f" Selected mode fixed: {timeStampType} = {nowTimestamp} -> {newEncoded_timestamp}")
            newUid = f"{base64_part}{newEncoded_timestamp}=={nowTimestamp}"
            return newUid
        except Exception as e:
            print(f"Error generating UID: {e}")
            return base_uid
        
        
        
    
    def run_curl_command(self, curl_command):
            timeout = 3 * 60
            return subprocess.run(curl_command, shell=True, capture_output=True, text=True, timeout=timeout,encoding='utf-8')

    ###USER INFO###
    ## PlayerInfo ##

    def getUserData(self, username,detailed=False):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return json.dumps({
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    })
                    
            curl_command = f'''curl "https://apisd.bopanel.com/api/Main/ApiRequest?TimeZone=3&LanguageId=en" \
            -H "accept: application/json, text/plain, */*" \
            -H "accept-language: en" \
            -H "authorization: Bearer {self.AuthToken}" \
            -H "content-type: application/x-www-form-urlencoded; charset=UTF-8" \
            -H "origin: https://sd.bopanel.com" \
            -H "priority: u=1, i" \
            -H "referer: https://sd.bopanel.com/" \
            -H "sec-ch-ua: {self.secCHUA}" \
            -H "sec-ch-ua-mobile: ?0" \
            -H "sec-ch-ua-platform: {self.platform}" \
            -H "sec-fetch-dest: empty" \
            -H "sec-fetch-mode: cors" \
            -H "sec-fetch-site: cross-site" \
            -H "timezone: 3" \
            -H "uid: {self.generate_uid(self.uid)}" \
            -H "user-agent: {self.userAgent}" \
            --data-raw "Method=GetClientsShort&Controller=Client&TimeZone=3&RequestObject=%7B%22SkipCount%22%3A0%2C%22TakeCount%22%3A100%2C%22OrderBy%22%3Anull%2C%22FieldNameToOrderBy%22%3A%22%22%2C%22PartnerIds%22%3A%5B%5D%2C%22RgsClientIds%22%3A%5B%5D%2C%22Ids%22%3A%5B%5D%2C%22Emails%22%3A%5B%5D%2C%22UserNames%22%3A%5B%7B%22OperationTypeId%22%3A1%2C%22StringValue%22%3A%22{username}%22%7D%5D%2C%22UniqueIds%22%3A%5B%5D%2C%22FirstNames%22%3A%5B%5D%2C%22LastNames%22%3A%5B%5D%2C%22MobileNumbers%22%3A%5B%5D%2C%22PhoneNumbers%22%3A%5B%5D%2C%22CurrencyIds%22%3A%5B%5D%2C%22DocumentNumbers%22%3A%5B%5D%2C%22RegistrationIps%22%3A%5B%5D%2C%22SportClinetIds%22%3A%5B%5D%2C%22ShebaNumbers%22%3A%5B%5D%2C%22SocialCardNumbers%22%3A%5B%5D%2C%22FromList%22%3Afalse%2C%22IsQuickSearch%22%3Atrue%7D"'''
    
            #result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
            result = self.run_curl_command(curl_command)
            json_result = json.loads(result.stdout)
            
            if json_result["ResponseCode"] == 29:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return json.dumps({
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    })
                return self.getUserData(username, detailed)
            
            if detailed:
                detailedData = self.getUserDataDetailed(username)
                json_result["detailedData"] = detailedData
            else:
                json_result["detailedData"] = None
            
            return json.dumps(json_result, indent=4)
            
        except Exception as e:
            return json.dumps({
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            })


    def getUserDataDetailed(self, username=None, userId=None):
        
        if not userId:
            userData = json.loads(self.getUserData(username))
            try:
                if not userData or not userData.get("ResponseObject", {}).get("Entities"):
                    return None
                userId = int(userData.get("ResponseObject", {}).get("Entities", [{}])[0].get("Id"))
            except:
                return None
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return json.dumps({
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    })
                    
            curl_command = f'''curl "https://apisd.bopanel.com/api/Main/ApiRequest?TimeZone=3&LanguageId=en" \
            -H "accept: application/json, text/plain, */*" \
            -H "accept-language: en" \
            -H "authorization: Bearer {self.AuthToken}" \
            -H "content-type: application/x-www-form-urlencoded; charset=UTF-8" \
            -H "origin: https://sd.bopanel.com" \
            -H "priority: u=1, i" \
            -H "referer: https://sd.bopanel.com/" \
            -H "sec-ch-ua: {self.secCHUA}" \
            -H "sec-ch-ua-mobile: ?0" \
            -H "sec-ch-ua-platform: {self.platform}" \
            -H "sec-fetch-dest: empty" \
            -H "sec-fetch-mode: cors" \
            -H "sec-fetch-site: cross-site" \
            -H "timezone: 3" \
            -H "uid: {self.generate_uid(self.uid)}" \
            -H "user-agent: {self.userAgent}" \
            --data-raw "Method=GetClientInfo&Controller=Client&TimeZone=3&RequestObject={userId}"'''


            #result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
            result = self.run_curl_command(curl_command)
            json_result = json.loads(result.stdout)
            
            if json_result["ResponseCode"] == 29:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return json.dumps({
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    })
                return self.getUserDataDetailed(username, userId)
                
            return json.dumps(json_result, indent=4)
            
        except Exception as e:
            return json.dumps({
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            })
        
    def getUserMainInfo(self, userid):
        try:
            if not userid:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "Userid is required",
                    "ResponseObject": None
                }
                
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            data = {
                "ClientId": int(userid)
            }

            response = self.curlManager.executeCurl(
                "https://apisd.bopanel.com/GetClientDetailsById",
                self.AuthToken,
                self.generate_uid(self.uid),
                self.secCHUA,
                self.userAgent,
                self.platform,
                data
            )

            if response.stdout:
                json_result = json.loads(response.stdout)
                
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getUserMainInfo(username)

                return json_result

            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }
        

    def getTotalPlayerCount(self, created_from, created_before):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
            
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            curlJson = {
            "SkipCount": 0,
            "TakeCount": 100,
            "OrderBy": None,
            "FieldNameToOrderBy": "",
            "PartnerId": None,
            "PartnerIds": [
                10285
            ],
            "CreatedFrom": created_from_str,
            "CreatedBefore": created_before_str,
            "Ids": [],
            "Emails": [],
            "UserNames": [],
            "Currencies": [],
            "LanguageIds": [],
            "Genders": [],
            "FirstNames": [],
            "LastNames": [],
            "DocumentNumbers": [],
            "DocumentIssuedBys": [],
            "MobileNumbers": [],
            "ZipCodes": [],
            "IsDocumentVerifieds": [],
            "PhoneNumbers": [],
            "RegionIds": [],
            "Categories": [],
            "BirthDates": [],
            "States": [],
            "CreationTimes": [],
            "Balances": [],
            "GGRs": [],
            "NETGamings": [],
            "IsEmailVerifieds": [],
            "ReferralIds": [],
            "LineIds": [],
            "RegistrationIps": [],
            "UniqueIds": [],
            "FromList": True,
            "HasDeposit": None,
            "Page": 1,
            "Top": 100,
            "filterSearch": "",
            "DateRange": "Today",
            "SocialCardNumber": None,
            "SportCategoryId": ""
        }
            
            try:
                result = self.curlManager.executeCurl(
                    "https://apisd.bopanel.com/api/Client/GetClientsTotalCount",
                    self.AuthToken,
                    self.generate_uid(self.uid),
                    self.secCHUA,
                    self.userAgent,
                    self.platform,
                    curlJson
                )
            except subprocess.TimeoutExpired:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "Digi Panel Not Responding",
                    "ResponseObject": None
                }

            if result.stdout:
                try:
                    json_result = json.loads(result.stdout)
                except:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": f"JSON parse hatası: {result.stdout}",
                        "ResponseObject": None
                    }
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                        
                        
                    return self.getTotalPlayerCount(created_from, created_before)
                if json_result.get("ResponseCode") != 0:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": json_result.get("ResponseMessage", "Total player count not getted"),
                        "ResponseObject": None
                    }
                
                total_count = json_result.get("ResponseObject", 0)
                if total_count == None:
                    raise Exception("No total count received")
                if total_count == 0:
                    raise Exception("No player found")
                return total_count
            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    
    def runCustomCurlCommand(self,url,dataType,data):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            if "apisd.bopanel.com" not in url or "https://apisd.bopanel.com" not in url:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "URL geçersiz",
                    "ResponseObject": None
                }
            
            if dataType == "form":
                curl_command = f'''curl "{url}" \
                    -H "accept: application/json, text/plain, */*" \
                    -H "accept-language: en" \
                    -H "authorization: Bearer {self.AuthToken}" \
                    -H "content-type: application/x-www-form-urlencoded; charset=UTF-8" \
                    -H "origin: https://sd.bopanel.com" \
                    -H "priority: u=1, i" \
                    -H "referer: https://sd.bopanel.com/" \
                    -H "sec-ch-ua: {self.secCHUA}" \
                    -H "sec-ch-ua-mobile: ?0" \
                    -H "sec-ch-ua-platform: {self.platform}" \
                    -H "sec-fetch-dest: empty" \
                    -H "sec-fetch-mode: cors" \
                    -H "sec-fetch-site: cross-site" \
                    -H "timezone: 3" \
                    -H "uid: {self.generate_uid(self.uid)}" \
                    -H "user-agent: {self.userAgent}" \
                    --data-raw "{data}"'''
                
                result = self.run_curl_command(curl_command)
                    
            elif dataType == "json":
                
                result = self.curlManager.executeCurl(
                    url,
                    self.AuthToken,
                    self.generate_uid(self.uid),
                    self.secCHUA,
                    self.userAgent,
                    self.platform,
                    data
                )
                
            if result.stdout:
                try:
                    json_result = json.loads(result.stdout)
                except:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "JSON parse hatası",
                        "ResponseObject": None
                    }
                
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Biraz sonra tekrar deneyin.",
                            "ResponseObject": None
                        }
                        
                        
                    return self.runCustomCurlCommand(url,dataType,data)

                if json_result.get("ResponseCode") != 0:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": json_result.get("ResponseMessage", "Custom curl command failed"),
                        "ResponseObject": None
                    }
                
                return json_result
                
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }
                
                
                
                
                
                
            
    def getUserList(self, created_from, created_before, updateSorting=False):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            sorting = not updateSorting
            
            totalPlayerCount = self.getTotalPlayerCount(created_from, created_before)
            if isinstance(totalPlayerCount, dict) and totalPlayerCount.get("ResponseCode") == -1:
                return totalPlayerCount
                
            playerList = []
            
            print(f"Total Player Count: {totalPlayerCount}")
            
            def getPlayerListForPage(skipCount, PerPage, attempt=0):
                print(f"Getting players for page {skipCount} gived {PerPage}")
                try:
                    
                    PageCount = skipCount + 1
                    
                    curl_command = f'''curl "https://apisd.bopanel.com/api/Main/ApiRequest?TimeZone=3&LanguageId=en" \
                    -H "accept: application/json, text/plain, */*" \
                    -H "accept-language: en" \
                    -H "authorization: Bearer {self.AuthToken}" \
                    -H "content-type: application/x-www-form-urlencoded; charset=UTF-8" \
                    -H "origin: https://sd.bopanel.com" \
                    -H "priority: u=1, i" \
                    -H "referer: https://sd.bopanel.com/" \
                    -H "sec-ch-ua: {self.secCHUA}" \
                    -H "sec-ch-ua-mobile: ?0" \
                    -H "sec-ch-ua-platform: {self.platform}" \
                    -H "sec-fetch-dest: empty" \
                    -H "sec-fetch-mode: cors" \
                    -H "sec-fetch-site: cross-site" \
                    -H "timezone: 3" \
                    -H "uid: {self.generate_uid(self.uid)}" \
                    -H "user-agent: {self.userAgent}" \
                    --data-raw "Method=GetClients&Controller=Client&TimeZone=3&RequestObject=%7B%22SkipCount%22%3A{skipCount}%2C%22TakeCount%22%3A{PerPage}%2C%22OrderBy%22%3Anull%2C%22FieldNameToOrderBy%22%3A%22%22%2C%22PartnerId%22%3Anull%2C%22PartnerIds%22%3A%5B10285%5D%2C%22CreatedFrom%22%3A%22{created_from_str}%22%2C%22CreatedBefore%22%3A%22{created_before_str}%22%2C%22Ids%22%3A%5B%5D%2C%22Emails%22%3A%5B%5D%2C%22UserNames%22%3A%5B%5D%2C%22Currencies%22%3A%5B%5D%2C%22LanguageIds%22%3A%5B%5D%2C%22Genders%22%3A%5B%5D%2C%22FirstNames%22%3A%5B%5D%2C%22LastNames%22%3A%5B%5D%2C%22DocumentNumbers%22%3A%5B%5D%2C%22DocumentIssuedBys%22%3A%5B%5D%2C%22MobileNumbers%22%3A%5B%5D%2C%22ZipCodes%22%3A%5B%5D%2C%22IsDocumentVerifieds%22%3A%5B%5D%2C%22PhoneNumbers%22%3A%5B%5D%2C%22RegionIds%22%3A%5B%5D%2C%22Categories%22%3A%5B%5D%2C%22BirthDates%22%3A%5B%5D%2C%22States%22%3A%5B%5D%2C%22CreationTimes%22%3A%5B%5D%2C%22Balances%22%3A%5B%5D%2C%22GGRs%22%3A%5B%5D%2C%22NETGamings%22%3A%5B%5D%2C%22IsEmailVerifieds%22%3A%5B%5D%2C%22ReferralIds%22%3A%5B%5D%2C%22LineIds%22%3A%5B%5D%2C%22RegistrationIps%22%3A%5B%5D%2C%22UniqueIds%22%3A%5B%5D%2C%22FromList%22%3Atrue%2C%22HasDeposit%22%3Anull%2C%22Page%22%3A{PageCount}%2C%22Top%22%3A{PerPage}%2C%22filterSearch%22%3A%22%22%2C%22DateRange%22%3A%22Today%22%2C%22SocialCardNumber%22%3Anull%2C%22SportCategoryId%22%3A%22%22%7D"'''


                    result = self.run_curl_command(curl_command)
                    
                    if result.stdout:
                        try:
                            json_result = json.loads(result.stdout)
                        except:
                            logging.info(f"JSON parse hatası: {result}")
                            return {
                                "ResponseCode": -1,
                                "ResponseMessage": "JSON parse hatası",
                                "ResponseObject": None
                            }
                        
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }
                            return getPlayerListForPage(skipCount, PerPage)
                        
                        # json_result > ResponseObject > Entities
                        with open('export/playerList.json', 'w') as f:
                            json.dump(json_result, f)
                        
                        currentList = json_result.get("ResponseObject", {}).get("Entities", [])
                        if len(currentList) == 0:
                            raise Exception("No players found")
                        
                        playerList.extend(currentList)
                    
                        return currentList
                    else:
                        raise Exception("No output received from subprocess")
                except Exception as e:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return getPlayerListForPage(skipCount, PerPage)

            
            
            if totalPlayerCount > 500:
                
                stepCount = 0
                for i in tqdm(range(0, totalPlayerCount, 500), desc="Getting Player List", unit="Players (500)"):
                    result = getPlayerListForPage(stepCount, 500)
                    # Eğer hata dönerse ana fonksiyondan çık
                    if isinstance(result, dict) and result.get("ResponseCode") == -1:
                        return result
                    stepCount += 1
            else:
                result = getPlayerListForPage(0, totalPlayerCount)
                if isinstance(result, dict) and result.get("ResponseCode") == -1:
                    return result
            
            
            with open('export/playerList.json', 'w') as f:
                json.dump(playerList, f)

            return playerList
            
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    ## DepositInfo ##
    def getPaymentSystemList(self):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            data = {
                "PaymentType": 1,
                "PartnerIds": [10285]
            }

            response = self.curlManager.executeCurl(
                "https://apisd.bopanel.com/api/PaymentSystem/GetPaymentSystemsForFilters",
                self.AuthToken,
                self.generate_uid(self.uid),
                self.secCHUA,
                self.userAgent,
                self.platform,
                data
            )

            if response.stdout:
                json_result = json.loads(response.stdout)
                
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getPaymentSystemList()

                return json_result.get("ResponseObject", [])

            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }
    
    def getDepositList(self,created_from,created_before, updateSorting=False):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            sorting = not updateSorting
            
            depositList = []
            
            global depositPage
            depositPage = 1
            depositTOP = 100
            
            
            def getDepositListForPage(skipCount, PerPage):
                print(f"Getting deposits for page {skipCount} gived {PerPage}...")
                try:
                    curl_command = f'''curl "https://apisd.bopanel.com/api/Report/GetPaymentRequestReport" \
                    -H "accept: application/json, text/plain, */*" \
                    -H "accept-language: en" \
                    -H "authorization: Bearer {self.AuthToken}" \
                    -H "content-type: application/json" \
                    -H "origin: https://sd.bopanel.com" \
                    -H "priority: u=1, i" \
                    -H "referer: https://sd.bopanel.com/" \
                    -H "sec-ch-ua: {self.secCHUA}" \
                    -H "sec-ch-ua-mobile: ?0" \
                    -H "sec-ch-ua-platform: {self.platform}" \
                    -H "sec-fetch-dest: empty" \
                    -H "sec-fetch-mode: cors" \
                    -H "sec-fetch-site: cross-site" \
                    -H "timezone: 3" \
                    -H "uid: {self.generate_uid(self.uid)}" \
                    -H "user-agent: {self.userAgent}" \
                    --data-raw "{{\\"PartnerIds\\":[10285],\\"DateRange\\":\\"Custom\\",\\"FromDate\\":\\"{created_from_str}\\",\\"ToDate\\":\\"{created_before_str}\\",\\"ClientId\\":null,\\"TransactionId\\":null,\\"ExternalId\\":null,\\"PaymentSystemIds\\":null,\\"InitialAmountCondition\\":null,\\"InitialAmount\\":null,\\"FinalAmountCondition\\":null,\\"FinalAmount\\":null,\\"OriginalCurrencies\\":null,\\"Statuses\\":null,\\"Sorting\\":{sorting},\\"Attention\\":null,\\"HasNote\\":null,\\"Page\\":{skipCount},\\"Top\\":{PerPage},\\"Type\\":2,\\"isCleanable\\":false,\\"filterSearch\\":\\"\\"}}"'''

                    dataRAW = '''
                    {
                    "PartnerIds": [10285],
                    "DateRange": "Custom",
                    "FromDate": "{created_from_str}",
                    "ToDate": "{created_before_str}",
                    "ClientId": null,
                    "TransactionId": null,
                    "ExternalId": null,
                    "PaymentSystemIds": null,
                    "InitialAmountCondition": null,
                    "InitialAmount": null,
                    "FinalAmountCondition": null,
                    "FinalAmount": null,
                    "OriginalCurrencies": null,
                    "Statuses": null,
                    "Sorting": true,
                    "Attention": null,
                    "HasNote": null,
                    "Page": {skipCount},
                    "Top": {PerPage},
                    "Type": 2,
                    "isCleanable": false,
                    "filterSearch": ""
                    }
                    '''.replace("{created_from_str}", created_from_str).replace("{created_before_str}", created_before_str).replace("{skipCount}", str(skipCount)).replace("{PerPage}", str(PerPage))
                    
                    result = self.curlManager.executeCurl("https://apisd.bopanel.com/api/Report/GetPaymentRequestReport",self.AuthToken,
                                                          self.generate_uid(self.uid),
                                                        self.secCHUA,
                                                        self.userAgent, self.platform,dataRAW)
                    


                    if result.stdout:
                        json_result = json.loads(result.stdout)
                        
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }, False
                            return getDepositListForPage(skipCount, PerPage)
                        
                        # json_result > ResponseObject > Entries
                        currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                        if len(currentList) == 0:
                            return [], False
                        
                        HasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                        
                        depositList.extend(currentList)
                        
                        return currentList, HasNext
                    else:
                        raise Exception("No output received from subprocess")
                        
                except Exception as e:
                    print(f"Error: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }, False
                    return getDepositListForPage(skipCount, PerPage)
            
            while True:
                result, HasNext = getDepositListForPage(depositPage, depositTOP)
                
                if HasNext:
                    depositPage += 1
                else:
                    break
            
            with open('export/depositList.json', 'w') as f:
                json.dump(depositList, f)
            
            return depositList
            
            
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    def getUserDeposits(self, userId, created_from=None, created_before=None,MaxDepositCount=None):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            # Tarih parametreleri yoksa son 30 günü al
            if not created_from or not created_before:
                created_from = (datetime.now() - timedelta(days=30)).replace(hour=0, minute=0, second=0)
                created_before = datetime.now()

            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"

            depositList = []
            global userDepositTotal
            userDepositTotal = 0
            
            depositPage = 1
            depositTOP = 100

            def getUserDepositsForPage(page, perPage):
                #print(f"Getting user deposits for page {page}, perPage: {perPage}")
                try:
                    # URL encoded data kullanarak deneyelim
                    curl_command = f'''curl "https://apisd.bopanel.com/api/Report/GetClientPaymentRequestReport" \
                    -H "accept: application/json, text/plain, */*" \
                    -H "accept-language: en" \
                    -H "authorization: Bearer {self.AuthToken}" \
                    -H "content-type: application/json" \
                    -H "origin: https://sd.bopanel.com" \
                    -H "priority: u=1, i" \
                    -H "referer: https://sd.bopanel.com/" \
                    -H "sec-ch-ua: {self.secCHUA}" \
                    -H "sec-ch-ua-mobile: ?0" \
                    -H "sec-ch-ua-platform: {self.platform}" \
                    -H "sec-fetch-dest: empty" \
                    -H "sec-fetch-mode: cors" \
                    -H "sec-fetch-site: cross-site" \
                    -H "timezone: 3" \
                    -H "uid: {self.generate_uid(self.uid)}" \
                    -H "user-agent: {self.userAgent}" \
                    --data-raw "{{\\"PartnerIds\\":[10285],\\"DateRange\\":\\"Custom\\",\\"FromDate\\":\\"{created_from_str}\\",\\"ToDate\\":\\"{created_before_str}\\",\\"ClientId\\":{userId},\\"TransactionId\\":null,\\"ExternalId\\":null,\\"PaymentSystemIds\\":null,\\"InitialAmountCondition\\":null,\\"InitialAmount\\":null,\\"FinalAmountCondition\\":null,\\"FinalAmount\\":null,\\"OriginalCurrencies\\":null,\\"Statuses\\":null,\\"Sorting\\":true,\\"Attention\\":null,\\"HasNote\\":null,\\"Page\\":{page},\\"Top\\":{perPage},\\"Type\\":2,\\"isCleanable\\":false}}"'''

                    result = self.run_curl_command(curl_command)
                    
                    if "You do not have permission" in result.stdout:
                        print("Permission error, trying to refresh token...")
                        self.AuthToken = self.refresh_token()
                        if not self.AuthToken:
                            return {
                                "ResponseCode": -1,
                                "ResponseMessage": "Token yenileme başarısız",
                                "ResponseObject": None
                            }, False
                        return getUserDepositsForPage(page, perPage)

                    if result.stdout:
                        try:
                            json_result = json.loads(result.stdout)
                            if json_result.get("ResponseCode") == 29:
                                self.AuthToken = self.refresh_token()
                                if not self.AuthToken:
                                    return {
                                        "ResponseCode": -1,
                                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                        "ResponseObject": None
                                    }, False
                                return getUserDepositsForPage(page, perPage)
                            
                            if json_result.get("ResponseCode") == 1020:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "No permission days to much: max 30 days",
                                    "ResponseObject": None
                                }
                            
                            if json_result.get("ResponseCode") == 6000:
                                time.sleep(0.2)
                            
                            
                            
                            try:
                                currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                                if len(currentList) == 0:
                                    return [], False
                                
                                HasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                                depositList.extend(currentList)
                                global userDepositTotal
                                userDepositTotal = json_result.get("ResponseObject", {}).get("TotalAmount", 0)
                                
                                return currentList, HasNext
                            except:
                                time.sleep(5)
                                return getUserDepositsForPage(page, perPage)
                        except json.JSONDecodeError as e:
                            print(f"JSON parse error: {e}")
                            return [], False
                    else:
                        raise Exception("No output received from subprocess")

                except Exception as e:
                    print(f"Error in getUserDepositsForPage: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }, False
                    return getUserDepositsForPage(page, perPage)

            while True:
                result, HasNext = getUserDepositsForPage(depositPage, depositTOP)
                if isinstance(result, dict) and result.get("ResponseCode") == -1:
                    return result
                
                if MaxDepositCount and len(depositList) >= MaxDepositCount:
                    for deposit in depositList:
                        if deposit.get("Status") == 8:
                            break
                        elif hasattr(deposit, "Status"):
                            if deposit.Status == 8:
                                break
                if HasNext:
                    depositPage += 1
                else:
                    break

            return {
                "TotalAmount": userDepositTotal,
                "Deposits": depositList
            }

        except Exception as e:
            print(f"Error in getUserDeposits: {e}")
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    ## WithdrawsInfo ##
    
    def getWithdrawList(self, created_from, created_before, userId=None, updateSorting=False):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            sorting = not updateSorting
            withdrawList = []
            withdrawPage = 1
            top = 100
            
            def getWithdrawListForPage(page, perPage):
                print(f"Getting withdraws for page {page}, top: {perPage}")
                try:
                    
                    clientId = userId if userId is not None else None
                    # Construct data raw similar to transactions but with Type=1
                    dataRAW = {
                        "PartnerIds": [10285],
                        "DateRange": "Today",
                        "FromDate": created_from_str,
                        "ToDate": created_before_str,
                        "ClientId": clientId,
                        "TransactionId": None,
                        "ExternalId": None,
                        "PaymentSystemIds": None,
                        "InitialAmountCondition": None,
                        "InitialAmount": None,
                        "FinalAmountCondition": None,
                        "FinalAmount": None,
                        "OriginalCurrencies": None,
                        "Statuses": None,
                        "Sorting": sorting,
                        "Attention": None,
                        "HasNote": None,
                        "Page": page,
                        "Top": perPage,
                        "Type": 1,
                        "isCleanable": False,
                        "filterSearch": ""
                    }
                    response = self.curlManager.executeCurl(
                        "https://apisd.bopanel.com/api/Report/GetPaymentRequestReport", 
                        self.AuthToken, 
                        self.generate_uid(self.uid),
                        self.secCHUA,
                        self.userAgent,
                        self.platform,
                        json.dumps(dataRAW)
                    )
                    
                    if response.stdout:
                        json_result = json.loads(response.stdout)
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }, False
                            return getWithdrawListForPage(page, perPage)
                        
                        currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                        if len(currentList) == 0:
                            return [], False
                        
                        hasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                        withdrawList.extend(currentList)
                        
                        return currentList, hasNext
                    else:
                        raise Exception("No output received from subprocess")
                except Exception as e:
                    print(f"Error: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }, False
                    return getWithdrawListForPage(page, perPage)
            
            while True:
                result, hasNext = getWithdrawListForPage(withdrawPage, top)
                if isinstance(result, dict) and result.get("ResponseCode") == -1:
                    return result
                if hasNext:
                    withdrawPage += 1
                else:
                    break
            
            with open('export/withdrawList.json', 'w') as f:
                json.dump(withdrawList, f)
            
            return withdrawList
        
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    ## Gaming History ##
    def getGamingHistory(self, created_from, created_before, userId):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            gamingHistoryList = []
            global gamingHistoryPage
            gamingHistoryPage = 1
            gamingHistoryTOP = 100
            
            def getGamingHistoryForPage(page, top):
                print(f"Getting gaming history for page {page}, top: {top}")
                try:
                    jsonRaw = '''
                    {
                        "PartnerId": 10285,
                        "ClientId": {username},
                        "BetAmount": null,
                        "WinAmount": null,
                        "GGR": null,
                        "GGRPercent": null,
                        "ProviderName": null,
                        "GameName": null,
                        "FromDate": "{DATE1}",
                        "ToDate": "{DATE2}",
                        "OrderBy": "",
                        "OrderDirection": null,
                        "Top": {TOP},
                        "Page": {PAGE},
                        "DateRange": "Custom"
                    }
                    '''
                    jsonRaw = jsonRaw.replace("{username}", str(userId)).replace("{DATE1}", created_from_str).replace("{DATE2}", created_before_str).replace("{TOP}", str(top)).replace("{PAGE}", str(page))
                    response = self.curlManager.executeCurl("https://apisd.bopanel.com/api/Client/GetClientsGamingHistory", self.AuthToken, 
                                                            self.generate_uid(self.uid),
                                                            self.secCHUA,
                                                            self.userAgent,
                                                            self.platform,
                                                            jsonRaw)
                    
                    if response.stdout:
                        json_result = json.loads(response.stdout)
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }, False
                            return getGamingHistoryForPage(page, top)
                        
                        currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                        if len(currentList) == 0:
                            return [], False
                        
                        HasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                        
                        gamingHistoryList.extend(currentList)
                        
                        return currentList, HasNext
                    
                    else:
                        raise Exception("No output received from subprocess")
                except Exception as e:
                    print(f"Error in getGamingHistoryForPage: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }, False
                    return getGamingHistoryForPage(page, top)
                
            while True:
                result, HasNext = getGamingHistoryForPage(gamingHistoryPage, gamingHistoryTOP)
                if isinstance(result, dict) and result.get("ResponseCode") == -1:
                    return result
                
                if HasNext:
                    gamingHistoryPage += 1
                else:
                    break
                
            return gamingHistoryList
        
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }  

    ## TransactionsInfo ##
    def getOperationTypes(self):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            curl_command = f"""curl "https://apisd.bopanel.com/api/PartnerSettings/GetPartnerOperationTypes?PartnerId=10285" \
            -H "accept: application/json, text/plain, */*" \
            -H "accept-language: en" \
            -H "authorization: Bearer {self.AuthToken}" \
            -H "content-type: application/json" \
            -H "origin: https://sd.bopanel.com" \
            -H "priority: u=1, i" \
            -H "referer: https://sd.bopanel.com/" \
            -H "sec-ch-ua: {self.secCHUA}" \
            -H "sec-ch-ua-mobile: ?0" \
            -H "sec-ch-ua-platform: {self.platform}" \
            -H "sec-fetch-dest: empty" \
            -H "sec-fetch-mode: cors" \
            -H "sec-fetch-site: cross-site" \
            -H "timezone: 3" \
            -H "uid: {self.generate_uid(self.uid)}" \
            -H "user-agent: {self.userAgent}"
            """

            response = self.run_curl_command(curl_command)
            
            if response.stdout:
                json_result = json.loads(response.stdout)
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getOperationTypes()
                
                return json_result.get("ResponseObject", [])
            
            else:
                raise Exception("No output received from subprocess")
            
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }
            
            
    def getTransactions(self, created_from, created_before, userId=None, operationTypeIds=None):
        
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            userId = "null" if userId is None else userId
            if operationTypeIds is None:
                operationTypeIds = [x.get("Id") for x in self.getOperationTypes()]
        
            transactionList = []
            page = 1
            top = 100

            def getTransactionsForPage(page, top):
                print(f"Getting transactions for page {page}, top: {top}")
                try:
                    jsonRaw = {
                        "DateRange": "Custom",
                        "FromDate": str(created_from_str),
                        "ToDate": str(created_before_str),
                        "Page": page,
                        "Top": top,
                        "OperationTypeIds": operationTypeIds,
                        "filterSearch": "",
                        "ClientId": userId
                    }
                    
                    response = self.curlManager.executeCurl(
                        "https://apisd.bopanel.com/api/Report/GetClientTransactionHistoryReport", 
                        self.AuthToken, 
                        self.generate_uid(self.uid),
                        self.secCHUA,
                        self.userAgent,
                        self.platform,
                        jsonRaw
                    )
                    
                    if response.stdout:
                        json_result = json.loads(response.stdout)
                        print(json_result)
                        
                        # InvalidInputParameters hatası kontrolü
                        if json_result.get("ResponseCode") == 1013:
                            print(f"Invalid parameters error: {json_result}")
                            return {
                                "ResponseCode": 1013,
                                "ResponseMessage": "Geçersiz parameterler. Lütfen tarih aralığını kontrol edin.",
                                "ResponseObject": None
                            }, False
                            
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }, False
                            return getTransactionsForPage(page, top)
                    
                        currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                        if len(currentList) == 0:
                            return [], False
                        
                    
                    
                        HasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                    
                        transactionList.extend(currentList)
                    
                        return currentList, HasNext
                
                    else:
                        raise Exception("No output received from subprocess")
                    
                except Exception as e:
                    print(f"Error in getTransactionsForPage: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }, False
                    return getTransactionsForPage(page, top)
            
            while True:
                result, HasNext = getTransactionsForPage(page, top)
                
                
                # Hata durumunu kontrol et
                if isinstance(result, dict) and result.get("ResponseCode"):
                    return result
            
                if HasNext:
                    page += 1
                else:
                    break
            return transactionList
    
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    ## Player Bonuses ##
    def getEnumList(self):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                
            curl_command = f"""curl "https://apisd.bopanel.com/api/Enumeration/GetEnumList" \
            -H "accept: application/json, text/plain, */*" \
            -H "accept-language: en" \
            -H "authorization: Bearer {self.AuthToken}" \
            -H "content-type: application/x-www-form-urlencoded; charset=UTF-8" \
            -H "origin: https://sd.bopanel.com" \
            -H "priority: u=1, i" \
            -H "referer: https://sd.bopanel.com/" \
            -H "sec-ch-ua: {self.secCHUA}" \
            -H "sec-ch-ua-mobile: ?0" \
            -H "sec-ch-ua-platform: {self.platform}" \
            -H "sec-fetch-dest: empty" \
            -H "sec-fetch-mode: cors" \
            -H "sec-fetch-site: cross-site" \
            -H "timezone: 3" \
            -H "uid: {self.generate_uid(self.uid)}" \
            -H "user-agent: {self.userAgent}" \
            --data-raw "Method=GetEnumList&Controller=EnumerationModel&TimeZone=3&RequestObject=%5B%22ClientBonusCampaignStatus%22%2C%22BonusCampaignTriggerType%22%2C%22CategoryTypes%22%2C%22BonusType%22%2C%22PresentationBonusType%22%2C%22ExpressOddType%22%2C%22SportEventState%22%2C%22BonusCampaignWalletType%22%2C%22ProviderBonusType%22%2C%22FreeBetWinType%22%2C%22FreeSpinType%22%2C%22ProductType%22%5D"
            """
            
            response = self.run_curl_command(curl_command)
            
            
            if response.stdout:
                json_result = json.loads(response.stdout)
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getEnumList()
                
                with open(self.dataFolder + "/enumList.json", "w") as f:
                    json.dump(json_result.get("ResponseObject", {}), f)
                
                return json_result.get("ResponseObject" , {})
                
            else:
                raise Exception("No output received from subprocess")
            
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }
        
    
    def getPlayerBonuses(self, created_from, created_before, userId,IsActiveBonuses=False, productType=None,BonusType=None):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            bonusesList = []
            page = 1
            top = 100
            
            def getPlayerBonusesForPage(page, top):
                try:
                    jsonRaw = {
                        "ClientId": userId,
                        "BonusType": BonusType,
                        "ProductType": productType,
                        "TriggerType": None,
                        "BonusCampaignId": None,
                        "Status": None,
                        "FromDate": created_from_str,
                        "ToDate": created_before_str,
                        "Page": page,
                        "Top": top,
                        "DateRange": "Custom"
                    }
                    
                    response = self.curlManager.executeCurl(
                        "https://apisd.bopanel.com/api/BonusCampaign/GetClientBonusCampaigns", 
                        self.AuthToken, 
                        self.generate_uid(self.uid),
                        self.secCHUA,
                        self.userAgent,
                        self.platform,
                        jsonRaw
                    )
                    
                    if response.stdout:
                        json_result = json.loads(response.stdout)
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }, False
                            return getPlayerBonusesForPage(page, top)
                        
                        if json_result.get("ResponseCode") == 0:
                    
                            currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                            if len(currentList) == 0:
                                return [], False
                        
                            HasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                        
                            bonusesList.extend(currentList)
                        
                            return currentList, HasNext
                        else:
                            json_result["ResponseCode"] = -1
                            return json_result, False
                
                    else:
                        raise Exception("No output received from subprocess")
                    
                except Exception as e:
                    print(f"Error in getPlayerBonusesForPage: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }, False
                    return getPlayerBonusesForPage(page, top)
                
            while True:
                result, HasNext = getPlayerBonusesForPage(page, top)
                if isinstance(result, dict) and result.get("ResponseCode") == -1:
                    return result
                
                if HasNext:
                    page += 1
                else:
                    break
            
            print(f"Bonuses: {len(bonusesList)}")
            activeBonusStatusList = [1,2,6]
            if IsActiveBonuses:
                bonusesList = [x for x in bonusesList if x["Status"] in activeBonusStatusList]
            print(f"Filtered Bonuses: {len(bonusesList)}")
            return bonusesList
        
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    ## CasinoBetsInfo ##

    def getCasinoBets(self, created_from, created_before,userId=None,stateIds: list = None,maxBetCount=None):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            print((created_before - created_from).days)
            if (created_before - created_from).days > 31:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "Tarih aralığı maksimum 30 gün olabilir.",
                    "ResponseObject": None
                }
            
            casinoBetsList = []
            page = 1
            top = 100
            
            if userId is None:
                userId = "null"
            else:
                userId = str(userId)
            
            def getCasinoBetsForPage(page, top):
                print(f"Getting casino bets for page {page}, top: {top}")
                try:
                    
                    data = {
                    "DateRange": "Custom",
                    "FromDate": created_from_str,
                    "ToDate": created_before_str,
                    "ByBet": True,
                    "ClientId": userId,
                    "ShowOriginalCurrency": False,
                    "States": stateIds,
                    "ProviderIds": [],
                    "Ids": None,
                    "BetAmounts": None,
                    "WinAmounts": None,
                    "DeviceTypes": [],
                    "ProductNames": None,
                    "RoundIds": None,
                    "BonusIds": None,
                    "OrderBy": None,
                    "OrderDirection": None,
                    "Page": page,
                    "Top": top,
                    "filterSearch": ""
                }
                
                    result = self.curlManager.executeCurl(
                        "https://apisd.bopanel.com/api/Report/GetPlayerCasinoBetsReport", 
                        self.AuthToken, 
                        self.generate_uid(self.uid),
                        self.secCHUA,
                        self.userAgent,
                        self.platform,
                        json.dumps(data)
                    )
                    if result.stdout:
                        json_result = json.loads(result.stdout)
                        
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }
                            return getCasinoBetsForPage(page, top)
                        
                        
                        
                        currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                        if len(currentList) == 0:
                            return [], False
                        
                        HasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                        
                        casinoBetsList.extend(currentList)
                        
                        return currentList, HasNext
                    else:
                        raise Exception("No output received from subprocess")
                        
                except Exception as e:
                    print(f"Error: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }, False
                    return getCasinoBetsForPage(page, top)
            
            while True:
                result, HasNext = getCasinoBetsForPage(page, top)
                
                if maxBetCount and len(casinoBetsList) >= maxBetCount:
                    break
                
                if HasNext:
                    page += 1
                else:
                    break
            
            with open('export/casinoBetsList.json', 'w') as f:
                json.dump(casinoBetsList, f)
            
            return casinoBetsList
            
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    ## Sport Bets ##
    def getSportBets(self, created_from, created_before, userId=None, stateIds: list = None,maxBetCount=None):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            if (created_before - created_from).days > 31:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "Tarih aralığı maksimum 30 gün olabilir.",
                    "ResponseObject": None
                }
            
            sportBetsList = []
            page = 1
            top = 100
            
            userId = "null" if userId is None else str(userId)
            
            def getSportBetsForPage(page, top):
                print(f"Getting sport bets for page {page}, top: {top}")
                try:
                    data = {
                        "DateRange": "Custom", 
                        "FromDate": created_from_str,
                        "ToDate": created_before_str,
                        "ByBet": True,
                        "ClientId": userId,
                        "ShowOriginalCurrency": False,
                        "States": stateIds,
                        "ProviderIds": [],
                        "Ids": None,
                        "BetAmounts": None,
                        "WinAmounts": None,
                        "DeviceTypes": [],
                        "ProductNames": None,
                        "RoundIds": None,
                        "BonusIds": None,
                        "LeagueName": "",
                        "EventName": "",
                        "SportName": "",
                        "OrderBy": None,
                        "OrderDirection": None,
                        "Page": page,
                        "Top": top,
                        "filterSearch": ""
                    }
                    
                    result = self.curlManager.executeCurl(
                        "https://apisd.bopanel.com/api/Report/GetPlayerSportBetsReport",
                        self.AuthToken,
                        self.generate_uid(self.uid),
                        self.secCHUA,
                        self.userAgent,
                        self.platform,
                        json.dumps(data)
                    )
                    
                    if result.stdout:
                        json_result = json.loads(result.stdout)
                        
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }, False
                            return getSportBetsForPage(page, top)
                        
                        currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                        if len(currentList) == 0:
                            return [], False
                        
                        HasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                        sportBetsList.extend(currentList)
                        
                        return currentList, HasNext
                    else:
                        raise Exception("No output received from subprocess")
                        
                except Exception as e:
                    print(f"Error: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.", 
                            "ResponseObject": None
                        }, False
                    return getSportBetsForPage(page, top)
            
            while True:
                result, HasNext = getSportBetsForPage(page, top)
                if isinstance(result, dict) and result.get("ResponseCode") == -1:
                    return result
                
                if maxBetCount and len(sportBetsList) >= maxBetCount:
                    break
                
                if HasNext:
                    page += 1
                else:
                    break
            
            with open('export/sportBetsList.json', 'w') as f:
                json.dump(sportBetsList, f)
            
            return sportBetsList
            
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }
    
    def getSportBetDetails(self, betId):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            # Get sport bet details by ID using GET request
            curl_command = f'''curl "https://apisd.bopanel.com/api/Report/GetDigitainSportBetDetailsReport?Id={betId}" \
            -H "accept: application/json, text/plain, */*" \
            -H "accept-language: en" \
            -H "authorization: Bearer {self.AuthToken}" \
            -H "content-type: application/json" \
            -H "origin: https://apisd.bopanel.com" \
            -H "referer: https://apisd.bopanel.com/" \
            -H "sec-ch-ua: {self.secCHUA}" \
            -H "sec-ch-ua-mobile: ?0" \
            -H "sec-ch-ua-platform: {self.platform}" \
            -H "sec-fetch-dest: empty" \
            -H "sec-fetch-mode: cors" \
            -H "sec-fetch-site: same-origin" \
            -H "timezone: 3" \
            -H "uid: {self.generate_uid(self.uid)}" \
            -H "user-agent: {self.userAgent}"'''

            result = self.run_curl_command(curl_command)
            
            if result.stdout:
                json_result = json.loads(result.stdout)
                
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getSportBetDetails(betId)
                
                return json_result
            else:
                raise Exception("No output received from subprocess")
                
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    def getSportBetsGeneralReport(self, created_from, created_before, stateIds: list = None, maxBetCount=None):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            
            if (created_before - created_from).days > 31:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "Tarih aralığı maksimum 30 gün olabilir.",
                    "ResponseObject": None
                }
            
            sportBetsList = []
            page = 1
            top = 100
            
            def getSportBetsForPage(page, top):
                print(f"Getting sport bets for page {page}, top: {top}")
                try:
                    data = {
                        "PartnerIds": [10285],
                        "DateRange": "Custom", 
                        "FromDate": created_from_str,
                        "ToDate": created_before_str,
                        "ByBet": True,
                        "ClientId": None,
                        "ShowOriginalCurrency": False,
                        "ShowOpenBetsOnly": False,
                        "States": stateIds,
                        "ProviderIds": [],
                        "Ids": None,
                        "BetAmounts": None,
                        "WinAmounts": None,
                        "DeviceTypes": [],
                        "ProductNames": None,
                        "RoundIds": None,
                        "BonusIds": None,
                        "LeagueName": "",
                        "EventName": "",
                        "SportName": "",
                        "OrderBy": None,
                        "OrderDirection": None,
                        "Page": page,
                        "Top": top,
                        "filterSearch": ""
                    }
                    
                    result = self.curlManager.executeCurl(
                        "https://apisd.bopanel.com/api/Report/GetSportBetsReport",
                        self.AuthToken,
                        self.generate_uid(self.uid),
                        self.secCHUA,
                        self.userAgent,
                        self.platform,
                        json.dumps(data)
                    )
                    
                    if result.stdout:
                        json_result = json.loads(result.stdout)
                        
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }, False
                            return getSportBetsForPage(page, top)
                        
                        currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                        if len(currentList) == 0:
                            return [], False
                        
                        HasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                        sportBetsList.extend(currentList)
                        
                        return currentList, HasNext
                    else:
                        raise Exception("No output received from subprocess")
                        
                except Exception as e:
                    print(f"Error: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.", 
                            "ResponseObject": None
                        }, False
                    return getSportBetsForPage(page, top)
            
            while True:
                result, HasNext = getSportBetsForPage(page, top)
                if isinstance(result, dict) and result.get("ResponseCode") == -1:
                    return result
                
                if maxBetCount and len(sportBetsList) >= maxBetCount:
                    break
                
                if HasNext:
                    page += 1
                else:
                    break
            
            with open('export/sportBetsList.json', 'w') as f:
                json.dump(sportBetsList, f)
            
            return sportBetsList
            
        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }
                        
    ## Multi Account count ##
    def getMultiAccountCount(self, userId=None):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            if userId is None:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "User ID is required",
                    "ResponseObject": None
                }
                
            response = self.runCustomCurlCommand(
                f"https://apisd.bopanel.com/api/ReportRiskyActions/GetPlayerMultiAccounts?clientId={userId}",
                "form",
                ""
            )

            #response = self.curlManager.executeCurl(
            #    f"https://apisd.bopanel.com/api/ReportRiskyActions/GetPlayerMultiAccounts?clientId={userId}",
            #    self.generate_uid(self.uid),
            #    self.secCHUA,
            #    self.userAgent,
            #    self.platform,
            #    self.AuthToken
            #)

            if response:
                if type(response) != dict:
                    json_result = json.loads(response)
                else:
                    json_result = response
                
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getMultiAccountCount(userId)

                return json_result.get("ResponseObject", [])

            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    #Active Domain Info
    def getActiveDomain(self, partnerId=10285):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            data = {
                "DomainName": None,
                "PartnerId": partnerId,
                "FromDate": "2015-12-31T22:00:00.000Z", 
                "ToDate": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "Status": None,
                "DateRange": "AllTimes"
            }

            response = self.curlManager.executeCurl(
                "https://apisd.bopanel.com/api/DomainConfiguration/GetDomains",
                self.AuthToken,
                self.generate_uid(self.uid),
                self.secCHUA,
                self.userAgent,
                self.platform,
                data
            )

            if response.stdout:
                json_result = json.loads(response.stdout)
                
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return None
                    return self.getActiveDomain(partnerId)

                domains = json_result.get("ResponseObject", [])
                print( [x.get("Name") for x in domains])
                non_reserve_domains = [d for d in domains if not d.get("IsReserve")]
                
                if non_reserve_domains:
                    return max(non_reserve_domains, key=lambda x: int(re.search(r'bahisfanatik(\d+)\.com', x.get("Name", "")).group(1)) if re.search(r'bahisfanatik(\d+)\.com', x.get("Name", "")) else 0)
                return None
            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            print(f"Error in getActiveDomain: {e}")
            return None

    # Get Bonus Campaigns
    def getBonusCampaigns(self, bonusCampaignId=None,IsActiveBonuses=False,dateTimeTo=None):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.", 
                        "ResponseObject": None
                    }
            
            # Get current date in ISO format
            current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
            if dateTimeTo:
                current_time = dateTimeTo
            
            bonusCampaignsList = []
            page = 1
            top = 100
            
            if IsActiveBonuses:
                IsActiveBonuses = 1
            else:
                IsActiveBonuses = None
            
            def getBonusCampaignsForPage(page):
                try:
                    data = {
                        "PartnerIds": [10285],
                        "DateRange": "AllTimes", 
                        "InternalName": None,
                        "Id": None,
                        "ProductType": None,
                        "TriggerType": None, 
                        "BonusType": None,
                        "Status": IsActiveBonuses,
                        "ShowBonusesCreatedBySport": False,
                        "DateFiltrationType": 2,
                        "Top": top,
                        "Page": page,
                        "filterSearch": "",
                        "FromDate": "2015-12-31T22:00:00.000Z",
                        "ToDate": current_time,
                        "BonusCampaignId": bonusCampaignId if bonusCampaignId else ""
                    }

                    response = self.curlManager.executeCurl(
                        "https://apisd.bopanel.com/api/BonusCampaign/GetBonusCampaigns",
                        self.AuthToken,
                        self.generate_uid(self.uid),
                        self.secCHUA,
                        self.userAgent,
                        self.platform,
                        data
                    )

                    if response.stdout:
                        json_result = json.loads(response.stdout)
                        
                        if json_result.get("ResponseCode") == 29:
                            self.AuthToken = self.refresh_token()
                            if not self.AuthToken:
                                return {
                                    "ResponseCode": -1,
                                    "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                                    "ResponseObject": None
                                }, False
                            return getBonusCampaignsForPage(page)

                        currentList = json_result.get("ResponseObject", {}).get("Entries", [])
                        if len(currentList) == 0:
                            return [], False
                            
                        HasNext = json_result.get("ResponseObject", {}).get("HasNext", False)
                        bonusCampaignsList.extend(currentList)
                        
                        return currentList, HasNext

                    else:
                        raise Exception("No output received from subprocess")

                except Exception as e:
                    print(f"Error in getBonusCampaignsForPage: {e}")
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None 
                        }, False
                    return getBonusCampaignsForPage(page)

            while True:
                result, HasNext = getBonusCampaignsForPage(page)
                if isinstance(result, dict) and result.get("ResponseCode") == -1:
                    return result
                    
                if HasNext:
                    
                    page += 1
                else:
                    break
                    
            return bonusCampaignsList

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    # Add Bonus 
    def addBonus(self, bonusCampaignId, clientId, productType, bonusAmount=0, freeSpinCount=None, note=""):
        
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }
                    
            if bonusAmount is not None and bonusAmount > 0 and freeSpinCount is not None and freeSpinCount > 0:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "bonusAmount ve freeSpinCount aynı anda kullanılamaz", 
                    "ResponseObject": None
                }
                
            if bonusAmount is None and freeSpinCount is None:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "bonusAmount veya freeSpinCount gerekli",
                    "ResponseObject": None
                }

            data = {
                "bonusCampaignId": bonusCampaignId,
                "clientId": clientId,
                "partnerId": 10285,
                "productType": productType,
                "hasLinkIteration": False,
                "iterationKey": None,
                "bonusAmount": bonusAmount,
                "freeSpinCount": freeSpinCount,
                "note": note
            }

            response = self.curlManager.executeCurl(
                "https://apisd.bopanel.com/api/BonusCampaign/AddManualBonusCampaignToClient",
                self.AuthToken,
                self.generate_uid(self.uid),
                self.secCHUA,
                self.userAgent,
                self.platform,
                data
            )

            if response.stdout:
                json_result = json.loads(response.stdout)
                print(json_result)
                
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.addBonus(bonusCampaignId, clientId, productType, bonusAmount, freeSpinCount, note)

                return json_result

            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }
    
    
    def addBonusDirectly(self,clientId,bonusCampaignId,value,note=""):
        try:
            bonus = self.getBonusCampaigns(bonusCampaignId,IsActiveBonuses=True)
            
            if not bonus:
                return {
                    "ResponseCode": -1,
                    "ResponseMessage": "Bonus bulunamadı",
                    "ResponseObject": None
                }
                
            bonus = bonus[0]
            
            name = bonus["InternalName"]
            id = bonus["Id"]
            productType = bonus["ProductType"]
            bonusType = bonus["BonusType"]
            endTime = bonus["EndTime"]
            startTime = bonus["StartTime"]
            
            isFreeSpin = False
            if bonus["FreeSpinType"] == 1:
                isFreeSpin = True
                
                
            if isFreeSpin:
                response = self.addBonus(
                    bonusCampaignId,
                    clientId,
                    productType,
                    bonusAmount=0,
                    freeSpinCount=value,
                    note=note
                )
            else:
                response = self.addBonus(
                    bonusCampaignId,
                    clientId, 
                    productType,
                    bonusAmount=value,
                    freeSpinCount=None,
                    note=note
                )
                
            if response.get("ResponseCode") == 0:
                return {
                    "ResponseCode": 0,
                    "ResponseMessage": "Bonus başarıyla eklendi",
                    "ResponseObject": response
                }
            return response
        except:
            return {
                "ResponseCode": -1,
                "ResponseMessage": "Bir hata oluştu",
                "ResponseObject": None
            }


    # GET MAIN INFO PANEL
    def getMainInfoDeposits(self, created_from, created_before):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            data = {
                "FromDate": created_from_str,
                "ToDate": created_before_str,
                "PartnerIds": [10285]
            }

            response = self.curlManager.executeCurl(
                "https://apisd.bopanel.com/GetDeposits",
                self.AuthToken,
                self.generate_uid(self.uid),
                self.secCHUA,
                self.userAgent,
                self.platform,
                data
            )

            if response.stdout:
                json_result = json.loads(response.stdout)
                print(json_result)
                
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getMainInfoDeposits(created_from, created_before)

                return json_result.get("ResponseObject", [])

            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }
    
    def getMainInfoWithdrawals(self, created_from, created_before):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            data = {
                "FromDate": created_from_str,
                "ToDate": created_before_str,
                "IsCreatedOrUpdate": False,
                "PartnerIds": [10285],
                "ByBet": 1,
                "filterSearch": "",
                "DateRange": "Custom"
            }

            response = self.curlManager.executeCurl(
                "https://apisd.bopanel.com/GetWithdrawals",
                self.AuthToken,
                self.generate_uid(self.uid),
                self.secCHUA,
                self.userAgent,
                self.platform,
                data
            )

            if response.stdout:
                json_result = json.loads(response.stdout)
                print(json_result)
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getMainInfoWithdrawals(created_from, created_before)

                return json_result.get("ResponseObject", [])

            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    def getMainInfoProviderBets(self, created_from, created_before):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z") 
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            data = {
                "FromDate": created_from_str,
                "ToDate": created_before_str,
                "IsCreatedOrUpdate": False,
                "PartnerIds": [10285],
                "ByBet": 1,
                "filterSearch": "",
                "DateRange": "Custom"
            }

            response = self.curlManager.executeCurl(
                "https://apisd.bopanel.com/GetProviderBets",
                self.AuthToken,
                self.generate_uid(self.uid),
                self.secCHUA,
                self.userAgent,
                self.platform,
                data
            )

            if response.stdout:
                json_result = json.loads(response.stdout)
                print(json_result)
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getMainInfoProviderBets(created_from, created_before)

                return json_result.get("ResponseObject", {})

            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    def getMainInfoPlayersInfo(self, created_from, created_before):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                        "ResponseObject": None
                    }

            created_from_str = created_from.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            created_before_str = created_before.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            data = {
                "FromDate": created_from_str,
                "ToDate": created_before_str,
                "IsCreatedOrUpdate": False,
                "PartnerIds": [10285],
                "ByBet": 1,
                "filterSearch": "",
                "DateRange": "Custom"
            }
            response = self.curlManager.executeCurl(
                "https://apisd.bopanel.com/GetPlayersInfo",
                self.AuthToken,
                self.generate_uid(self.uid),
                self.secCHUA,
                self.userAgent,
                self.platform,
                data
            )

            if response.stdout:
                json_result = json.loads(response.stdout)
                print(json_result)
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş. Lütfen yeniden giriş yapın.",
                            "ResponseObject": None
                        }
                    return self.getMainInfoPlayersInfo(created_from, created_before)

                return json_result.get("ResponseObject", {})

            else:
                raise Exception("No output received from subprocess")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    def updateUser(self, userId, userData):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Oturum süresi dolmuş",
                        "ResponseObject": None
                    }

            response = self.curlManager.executeCurl(
                "https://apisd.bopanel.com/ChangeClientDetails",
                self.AuthToken,
                self.generate_uid(self.uid),
                self.secCHUA,
                self.userAgent,
                self.platform,
                userData
            )

            if response.stdout:
                json_result = json.loads(response.stdout)
                
                if json_result.get("ResponseCode") == 29:
                    self.AuthToken = self.refresh_token()
                    if not self.AuthToken:
                        return {
                            "ResponseCode": -1,
                            "ResponseMessage": "Oturum süresi dolmuş",
                            "ResponseObject": None
                        }
                    return self.updateUser(userId, userData)

                return json_result
            else:
                raise Exception("No response received")

        except Exception as e:
            return {
                "ResponseCode": -1,
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    def ping_signalr(self):
        try:
            if not self.AuthToken:
                self.AuthToken = self.refresh_token()
                if not self.AuthToken:
                    return {
                        "ResponseCode": -1,
                        "ResponseMessage": "Token could not be refreshed",
                        "ResponseObject": None
                    }
                
            access_token = self.AuthToken.replace(" ", "%20")
            timestamp = int(time.time() * 1000)
        
            # Tırnak işaretlerini düzelt ve escape karakterlerini düzenle
            curl_command = f"""curl -s "https://signalrserversd.apidigi.com/signalr/ping?access_token={access_token}&_={timestamp}" \\
            -H "accept: text/plain, */*; q=0.01" \\
            -H "accept-language: tr,en;q=0.9,en-GB;q=0.8,en-US;q=0.7" \\
            -H "content-type: application/x-www-form-urlencoded; charset=UTF-8" \\
            -H "origin: https://sd.bopanel.com" \\
            -H "priority: u=1, i" \\
            -H "referer: https://sd.bopanel.com/" \\
            -H "sec-ch-ua: {self.secCHUA}" \\
            -H "sec-ch-ua-mobile: ?0" \\
            -H "sec-ch-ua-platform: {self.platform}" \\
            -H "sec-fetch-dest: empty" \\
            -H "sec-fetch-mode: cors" \\
            -H "sec-fetch-site: cross-site" \\
            -H "authorization: Bearer {self.AuthToken}" \\
            -H "user-agent: {self.userAgent}"
            """

            result = self.run_curl_command(curl_command)
        
            if result.stdout:
                try:
                    response = json.loads(result.stdout) if result.stdout else None
                    return response
                except json.JSONDecodeError:
                    print(f"Raw output: {result.stdout}")
                    if "true" in result.stdout.lower():
                        return True
                    return result.stdout
            else:
                if result.returncode != 0:
                    print(f"Curl error: {result.stderr}")
                raise Exception(f"No output received. Return code: {result.returncode}, Error: {result.stderr}")

        except Exception as e:
            print(f"SignalR ping error: {str(e)}")
            return {
                "ResponseCode": -1, 
                "ResponseMessage": str(e),
                "ResponseObject": None
            }

    


if __name__ == "__main__":
    manager = SeleniumSessionManager("/data/ACCOUNTS.json")
    api = FenomenSession(manager)
    
    print(api.ping_signalr())
    #print(api.getMultiAccountCount("11419608"))
    
    username = "16524581"
    
    datenow = datetime.now()
    date1dayago = datenow - timedelta(days=1)
    
    playerCount = api.getTotalPlayerCount(date1dayago, datenow)
    print(playerCount)