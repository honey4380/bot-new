from main import FenomenSession
from datetime import datetime, timedelta
import json
import traceback
import inspect
from Helper.BonusResponse import BonusResponse
import os

from SeleniumManager import SeleniumSessionManager
from Helper.BonusCompressor import BonusCompressor
import random

class CampaignController:
    def __init__(self,seleniumManager:SeleniumSessionManager):
        try:
            self.app = FenomenSession(seleniumManager,RealTime=datetime.now(),RealTimeZoneDiff=3)
        except:
            raise Exception("FenomenSession oluşturulamadı")
        
        self.enum_list = self.get_enum_list()
        self.bonus_types = {}
        self.product_types = {}
        self.bonus_status = {}
        self.bonusCompressor = BonusCompressor()
        
        if self.enum_list and isinstance(self.enum_list, dict):
            self.bonus_types = self.enum_list.get('BonusType', [])
            
            self.product_types = self.enum_list.get('ProductType', [])
            
            self.bonus_status = self.enum_list.get('ClientBonusCampaignStatus', [])

            
        self.cache_folder = "./cache/"
        self.controls = {}
        self.getControlList()
        self.validMessages = self._loadValidMessages()
        
    def get_enum_list(self):
        """Enum listesini al veya cache'den oku"""
        try:
            enum_list = self.app.getEnumList()
            
            if isinstance(enum_list, dict) and not enum_list.get("ResponseCode") == -1:
                return enum_list
                
            try:
                with open(self.app.dataFolder + '/enumList.json', 'r') as f:
                    return json.load(f)
            except:
                print("Cache'den enum listesi okunamadı")
                return None
                
        except Exception as e:
            print(f"Enum listesi alınamadı: {str(e)}")
            return None

    ### KONTROLLER ###
    
    # Genel Kontrol Fonksionu #
    
    def ErrorFunc(self, e, frame_info=None):
        if frame_info is None:
            frame_info = traceback.extract_stack()[-2]
        print(f"Error in function {frame_info.name} at line {frame_info.lineno}: {str(e)}")
        return self._returnError(f"Error in function {frame_info.name} at line {frame_info.lineno}: {str(e)}")
        
    def dataRangeGenerator(self, rangeType: str, attr, dateTimed=False):
        now = datetime.now()
        
        if rangeType == "week":
            start_date = now - timedelta(weeks=attr)
        elif rangeType == "day":
            start_date = now - timedelta(days=attr)
        elif rangeType == "hour":
            start_date = now - timedelta(hours=attr)
        elif rangeType == "minute":
            start_date = now - timedelta(minutes=attr)
        else:
            return None
        
        from_parts = start_date.strftime("%Y-%m-%dT%H:%M:%S").split('T')
        to_parts = now.strftime("%Y-%m-%dT%H:%M:%S").split('T')
        
        if dateTimed:
            from_date = from_parts[0].split('-')
            from_time = from_parts[1].split(':')
            
            to_date = to_parts[0].split('-')
            to_time = to_parts[1].split(':')
            
            created_from = datetime(
                int(from_date[0]),
                int(from_date[1]),
                int(from_date[2]),
                int(from_time[0]),
                int(from_time[1]),
                int(from_time[2]) 
            )
            
            created_before = datetime(
                int(to_date[0]),
                int(to_date[1]),
                int(to_date[2]),
                int(to_time[0]),
                int(to_time[1]),
                int(to_time[2]) 
            )
            
            return created_from, created_before
        else:
            return start_date.strftime("%Y-%m-%dT%H:%M:%S"), now.strftime("%Y-%m-%dT%H:%M:%S")  
    
    def checkUser(self, userid):
        """Kullanıcı kontrolü"""
        try:
            
            userData = json.loads(self.app.getUserDataDetailed(userId=userid))
            if userData is None or not isinstance(userData, dict):
                return False
            
            data = {
                'userId': userid,
                'username': userData["ResponseObject"]["UserName"],
                'userInfo': userData["ResponseObject"]
            }
            return data
        except Exception as e:
            self.ErrorFunc(e)
            return False        
    
    
    # Data return functions
    def __returnDeposits(self, data: dict, days=1,rangeType="day"):
        """Yatırım listesi"""
        try:
            from_date, to_date = self.dataRangeGenerator(rangeType, days,dateTimed=True)
            deposits = self.app.getUserDeposits(data["userId"], from_date, to_date)["Deposits"]
            
            depositList = []
            for deposit in deposits:
                if isinstance(deposit, dict):
                    if deposit.get("Status") == 8:
                        depositList.append(deposit)
                elif hasattr(deposit, "Status"):
                    if deposit.Status == 8:
                        depositList.append(deposit)
            depositList.sort(key=lambda x: x.CreationTime if hasattr(x, "CreationTime") else x["CreationTime"], reverse=True)
            print(f"Lenght of deposit list: {len(depositList)}")
            return depositList
        except Exception as e:
            self.ErrorFunc(e)
            return False
        
    def __returnLastDeposit(self, data: dict, days=1,maxDepositCount=1):
        """Son yatırım işlemini döndürür"""
        try:
            from_date, to_date = self.dataRangeGenerator("day", days,dateTimed=True)
            DepositList = self.app.getUserDeposits(data["userId"], from_date, to_date,MaxDepositCount=maxDepositCount)["Deposits"]
            DepositList = [deposit for deposit in DepositList if deposit["Status"] == 8]
            DepositList.sort(key=lambda x: x["CreationTime"], reverse=True)
            if len(DepositList) == 0:
                return None
            return DepositList[0]
        except Exception as e:
            self.ErrorFunc(e)
            return False
    
    def __returnBonuses(self, data: dict, days=-1):
        """Bonus listesi"""
        try:
            from_date, to_date = self.dataRangeGenerator("day", days,dateTimed=True)
            
            # Eğer tüm bonuslar alınacaksa
            if days == -1:
                from_date = datetime(2016, 1, 1)
            
            result = self.app.getPlayerBonuses(from_date, to_date, data["userId"],True)
            
            # Hata kontrolü
            if isinstance(result, dict):
                if result.get("ResponseCode") == -1:
                    return False
                if not result.get("ResponseObject"):
                    return []
                    
            bonusList = result if isinstance(result, list) else []
            bonusList.sort(key=lambda x: x["CreationTime"], reverse=True)
            return bonusList
            
        except Exception as e:
            self.ErrorFunc(e)
            return False
    
            
            return withdrawList
        except Exception as e:
            self.ErrorFunc(e)
            return False
    
    def __returnCurrentBalance(self, data: dict):
        """Mevcut bakiyeyi al"""
        try:
            return data["userInfo"]["Balance"]
        except Exception as e:
            self.ErrorFunc(e)
            return False
    
    def __returnCasinoBets(self, data: dict, days=1):
        """Casino bet listesi"""
        try:
            from_date, to_date = self.dataRangeGenerator("day", days,dateTimed=True)
            casinoBets = self.app.getCasinoBets(from_date, to_date, data["userId"])
            return casinoBets
        except Exception as e:
            self.ErrorFunc(e)
            return False
    
    def __returnSportBets(self, data: dict, days=1):
        """Spor bet listesi"""
        try:
            from_date, to_date = self.dataRangeGenerator("day", days,dateTimed=True)
            sportBets = self.app.getSportBets(from_date, to_date, data["userId"])
            return sportBets
        except Exception as e:
            self.ErrorFunc(e)
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
   
    def filter_by_hour_range(self, items_list, hour_range, date_field="CreationTime"):
        """
        Filter a list of items by an hour range.
        
        Parameters:
        -----------
        items_list : list
            List of dictionaries containing datetime fields to filter
        hour_range : list
            A list with two elements representing [start_hour, end_hour]
        date_field : str, default="CreationTime"
            Name of the field containing the datetime string to check
            
        Returns:
        --------
        list
            Filtered list of items that fall within the specified hour range
        """
        # If no filtering needed
        if hour_range == [21,21]:
            return items_list
        
        filtered_items = []
        
        # Check if the range spans across midnight
        if hour_range[0] > hour_range[1]:
            # This is a range like 21-3 (overnight)
            # Get items from the first part of the range (e.g., 21-24)
            night_items = [x for x in items_list if 
                            self.parse_datetime(x[date_field]).hour >= hour_range[0]]
            filtered_items.extend(night_items)
            
            # Get items from the second part of the range (e.g., 0-3)
            morning_items = [x for x in items_list if 
                            self.parse_datetime(x[date_field]).hour < hour_range[1] or 
                            (hour_range[1] == 0 and 
                            self.parse_datetime(x[date_field]).hour == 0 and 
                            self.parse_datetime(x[date_field]).minute == 0 and 
                            self.parse_datetime(x[date_field]).second == 0)]
            filtered_items.extend(morning_items)
        else:
            # Normal time range within the same day
            filtered_items = [x for x in items_list if 
                                self.parse_datetime(x[date_field]).hour >= hour_range[0]]
            
            if hour_range[1] == 24:
                filtered_items = [x for x in filtered_items if 
                                    self.parse_datetime(x[date_field]).hour <= 23 and 
                                    self.parse_datetime(x[date_field]).minute <= 59 and 
                                    self.parse_datetime(x[date_field]).second <= 59]
            else:
                filtered_items = [x for x in filtered_items if 
                                    self.parse_datetime(x[date_field]).hour < hour_range[1] or
                                    (self.parse_datetime(x[date_field]).hour == hour_range[1] and
                                    self.parse_datetime(x[date_field]).minute == 0 and
                                    self.parse_datetime(x[date_field]).second == 0)]
        
        return filtered_items
    
    def __returnProfitCount(self,responseObject:BonusResponse, data: dict, fromdate:str,todate:str,calculationFirstDepositAfterHourCount,calculationFirstDepositAfterHourRange=[0,24],isDepositFilter:bool=True,FilterAllowedBonusses:list=None,minDiff:float=None,maxDiff:float=None,isProfit=None,FilterReverse=False):
        """İki tarih arasındaki yatırım ve çekim farkını döndürür"""
        try:
            if not fromdate or not todate:
                return self._returnError("Date required"),False
            
            # Remove trailing 'Z' if present and parse the datetime
            
            toDate = self.parse_datetime(todate) + timedelta(seconds=1)
            
            fromDate = self.parse_datetime(fromdate)
            
            
            
            depositCount = self.__returnDepositCount(data)
            if type(depositCount) != int or depositCount < 1:
                return self._returnMessage(False, "NO_DEPOSIT_IN_RANGE"),False

                
            if not calculationFirstDepositAfterHourCount:
                calculationFirstDepositAfterHourCount = 24
            
            bonusDepositIds = []
            bonusWithdrawIds = []
            
            if isDepositFilter:
                bonuses = data["bonusList"]
                bonuses = [x for x in bonuses if self.parse_datetime(x["CreationTime"]) <= toDate]
                if FilterAllowedBonusses:
                    # eğer FilterReverse True ise sadece Allowed bonuslar filtre edilecek
                    if FilterReverse:
                        bonuses = [x for x in bonuses if x["BonusCampaignId"] in FilterAllowedBonusses]
                    else:
                        bonuses = [x for x in bonuses if x["BonusCampaignId"] not in FilterAllowedBonusses]
                
                controlledDateRanges = []
                for bonus in bonuses:
                    try:
                        if self.bonusCompressor.is_compressed(bonus["Note"]):
                            bonusNote = self.bonusCompressor.decompress(bonus["Note"])
                            
                            if bonusNote.get("DepositIds") and len(bonusNote["DepositIds"]) > 0:
                                bonusDepositIds.extend(bonusNote["DepositIds"])
                            if bonusNote.get("DepositDateRange") and len(bonusNote["DepositDateRange"]) == 2:
                                if bonusNote["DepositDateRange"] in controlledDateRanges:
                                    continue
                                controlledDateRanges.append(bonusNote["DepositDateRange"])
                                depositSearchFrom, depositSearchTo = bonusNote["DepositDateRange"]
                                depositSearchFrom = self.parse_datetime(depositSearchFrom)
                                depositSearchTo = self.parse_datetime(depositSearchTo)
                                bonusDeposits = self.app.getUserDeposits(data["userId"], depositSearchFrom - timedelta(milliseconds=1), depositSearchTo + timedelta(milliseconds=1))["Deposits"]
                                bonusDepositIds.extend([x["TransactionId"] for x in bonusDeposits])
                            
                            if bonusNote.get("WithdrawIds") and len(bonusNote["WithdrawIds"]) > 0:
                                bonusWithdrawIds.extend(bonusNote["WithdrawIds"])
                            if bonusNote.get("WithdrawDateRange") and len(bonusNote["WithdrawDateRange"]) == 2:
                                if bonusNote["WithdrawDateRange"] in controlledDateRanges:
                                    continue
                                withdrawSearchFrom, withdrawSearchTo = bonusNote["WithdrawDateRange"]
                                withdrawSearchFrom = self.parse_datetime(withdrawSearchFrom)
                                withdrawSearchTo = self.parse_datetime(withdrawSearchTo)
                                bonusWithdraws = self.app.getWithdrawList(data["userId"], withdrawSearchFrom - timedelta(milliseconds=1), withdrawSearchTo + timedelta(milliseconds=1))["Withdraws"]
                                bonusWithdrawIds.extend([x["TransactionId"] for x in bonusWithdraws])
                            
                        else:
                            try:
                                
                                bonusNote = json.loads(bonus["Note"].replace('\\','"'))
                                
                                if bonusNote.get("DepositIds") and len(bonusNote["DepositIds"]) > 0:
                                    bonusDepositIds.extend(bonusNote["DepositIds"])
                                elif bonusNote.get("DepositDateRange") and len(bonusNote["DepositDateRange"]) == 2:
                                    depositSearchFrom, depositSearchTo = bonusNote["DepositDateRange"]
                                    depositSearchFrom = self.parse_datetime(depositSearchFrom)
                                    depositSearchTo = self.parse_datetime(depositSearchTo)
                                    bonusDeposits = self.app.getUserDeposits(data["userId"], depositSearchFrom + timedelta(seconds=1), depositSearchTo - timedelta(seconds=1))["Deposits"]
                                    bonusDepositIds.extend([x["TransactionId"] for x in bonusDeposits])
                                    
                            except Exception as e:
                                print(f"Bonus Note JSON Error: {str(e)}")
                                # eğer bonus note bu şekildeyse
                                try:
                                    if bonusNote.startswith("//"):
                                        # 1. tarih
                                        depositSearchFrom = bonusNote.split("//")[1].split(" ")[0]
                                        depositSearchFrom = self.parse_datetime(depositSearchFrom)
                                        depositSearchFrom = depositSearchFrom.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=data["realTimeZone"])
                                        # 2. tarih
                                        depositSearchTo = bonusNote.split("//")[1].split(" ")[1]
                                        depositSearchTo = self.parse_datetime(depositSearchTo)
                                        depositSearchTo = depositSearchTo.replace(hour=23, minute=59, second=59, microsecond=999999) - timedelta(hours=data["realTimeZone"])
                                        
                                        # 1. tarih ve 2. tarih arasındaki yatırımları al
                                        bonusDeposits = self.app.getUserDeposits(data["userId"], depositSearchFrom + timedelta(seconds=1), depositSearchTo - timedelta(seconds=1))["Deposits"]
                                        # bonusDepositIds'e ekle
                                        bonusDepositIds.extend([x["TransactionId"] for x in bonusDeposits])
                                    else:
                                        bonusNote = json.loads("[" + bonus["Note"] + "]")
                                        bonusDepositIds.extend(bonusNote)
                                except:
                                    pass
                            
                    except:
                        pass
                
                bonusDepositIds = list(set(bonusDepositIds))
                        
            # 24 saatteki Onaylanmış yatırımları al
            deposits = [x for x in self.app.getUserDeposits(data["userId"], fromDate, toDate)["Deposits"] if x["Status"] == 8]
            
            
            filteredDeposits = [x for x in deposits if x["TransactionId"] not in bonusDepositIds]
            filteredDeposits.sort(key=lambda x: self.parse_datetime(x["CreationTime"]), reverse=False)
            
            
            if len(deposits) > 0 and len(filteredDeposits) == 0:
                return self._returnMessage(False, "NO_FILTRED_DEPOSIT_IN_RANGE"),False
            
            
            
            # Handle time ranges that span across days
            # Check if the range spans across midnight
            
     
            filteredDeposits = self.filter_by_hour_range(filteredDeposits, calculationFirstDepositAfterHourRange)
     
            if len(deposits) == 0 and len(filteredDeposits) == 0:
                return self._returnMessage(False, "NO_DEPOSIT_IN_RANGE"),False
            
            if len(filteredDeposits) == 0:
                return self._returnMessage(False, "NO_DEPOSIT_IN_HOUR_RANGE"),False
            
            withrawsCount = self.__returnWithdrawCount(data)
            if type(withrawsCount) != int:
                return self._returnError("Withdraw count is not valid"),False
            
            responseObject.log(f"{len(filteredDeposits)} deposits found in the specified range")
            
            totalControlDiff = 0
            # bonus alabildiği yatırımların idleri
            controlledBonusDepositIds = []
            controlledBonusWithdrawIds = []
            
            # çekimlerin içerisinde teker teker gez
            controlledWithdraws = []
            
            controlledDeposits = []
            controlledBonusDepositDict = {}
            
            if calculationFirstDepositAfterHourCount == "calculationDate":
                totalDepositAmount = sum(x["FinalAmount"] for x in filteredDeposits)
                
                withdraws = [x for x in self.app.getWithdrawList(fromDate, toDate, data["userId"]) if x["Status"] == 8]

                if type(withdraws) != list:
                    return self._returnError("Withdraws are not valid"),False
                
                totalWithdrawAmount = sum(x["FinalAmount"] for x in withdraws)
                
                if isProfit:
                    diff = totalWithdrawAmount - totalDepositAmount
                else:
                    diff = totalDepositAmount - totalWithdrawAmount
                    
                totalControlDiff += diff
                
            else:
                totalWithdrawAmount = 0
                filteredDeposits.sort(key=lambda x: self.parse_datetime(x["CreationTime"]), reverse=False)
                    
                for deposit in filteredDeposits:
                    if deposit in controlledDeposits:
                        continue
                    
                    depositAmount = deposit["FinalAmount"]
                    deposit_id = deposit.get('TransactionId', 'N/A')
                    
                    responseObject.log(f" Processing deposit: ID={deposit_id}, Amount={depositAmount}")
                    
                    # Yatırım yapıldığı tarihten önceki 24 saat içerisindeki çekimleri al  (24 saat öncesinden talep tarihine kadar)
                    controlToDate = toDate
                    controlFromDate = self.parse_datetime(deposit["CreationTime"]) - (timedelta(hours=calculationFirstDepositAfterHourCount))
                    
                    
                    responseObject.log(f"Looking for withdrawals between {controlFromDate} and {controlToDate}")
                    
                    if withrawsCount != 0:
                        withdraws = [x for x in self.app.getWithdrawList(controlFromDate, controlToDate, data["userId"]) if x["Status"] == 8]
                        withdraws = [x for x in withdraws if x["TransactionId"] not in bonusWithdrawIds]
                        
                        for cw in controlledWithdraws:
                            if cw in withdraws and cw[1] == 0:
                                withdraws.remove(cw)
                            
                        if type(withdraws) != list:
                            responseObject.log(f" ERROR: Withdrawals data is not valid")
                            return self._returnError("Withdraws are not valid"),False
                        
                        initial_withdraw_count = len(withdraws)
                        responseObject.log(f" Found {initial_withdraw_count} initial withdrawals")
                        
                        #withdraws = self.filter_by_hour_range(withdraws, calculationFirstDepositAfterHourRange)
                        
                        withdraws.sort(key=lambda x: x["CreationTime"], reverse=False)
                    else:
                        withdraws = []
                        responseObject.log(f" No withdrawals to check (withrawsCount=0)")
                        
                    if len(withdraws) == 0:
                        controlledDeposits.append(deposit)
                        totalControlDiff += depositAmount
                        responseObject.log(f" No matching withdrawals found. Adding deposit amount {depositAmount} to totalControlDiff: {totalControlDiff}")
                        controlledBonusDepositIds.append(deposit["TransactionId"])
                        continue
                    withdraws.sort(key=lambda x: x["CreationTime"], reverse=False)
                    # Log individual withdrawals
                    responseObject.log(f" Found {len(withdraws)} withdrawals for deposit {deposit_id}:")
                    for idx, withdraw in enumerate(withdraws):
                        for cw in controlledWithdraws:
                            if cw[0] == withdraw and cw[1] == 0:
                                withdraws.remove(withdraw)
                    
                    
                    
                    for idx, withdraw in enumerate(withdraws):
                        w_id = withdraw.get('TransactionId', 'N/A')
                        w_amount = withdraw.get('FinalAmount', 0)
                        w_time = withdraw.get('CreationTime', 'Unknown')
                        
                        ifcontrolledInside = [x for x in controlledWithdraws if x[0] == withdraw]
                        if len(ifcontrolledInside) > 0:
                            ifcontrolledInside = ifcontrolledInside[0][1]
                        else:
                            ifcontrolledInside = w_amount
                            
                        responseObject.log(f" - Withdrawal #{idx+1}: ID={w_id}, Amount={w_amount}, NowAmount={ifcontrolledInside}, Time={w_time}")
                        if totalWithdrawAmount > 0:
                            depositAmount = depositAmount - totalWithdrawAmount
                            totalWithdrawAmount = 0
                        
                        withdrawAmount = withdraw["FinalAmount"]
                        if withdraw in [x[0] for x in controlledWithdraws]:
                            controlledWithdraw = [x for x in controlledWithdraws if x[0] == withdraw][0]
                            withdrawAmount = controlledWithdraw[1]
                        
                        if totalControlDiff > 0:
                            withdrawAmount = withdrawAmount - totalControlDiff
                            totalControlDiff = 0
                            
                        if not isProfit:
                            if withdrawAmount >= depositAmount:
                                newWithdrawAmount = withdrawAmount - (depositAmount)
                                controlledWithdraws = [x for x in controlledWithdraws if x[0] != withdraw]
                                controlledWithdraws.append([withdraw, newWithdrawAmount])
                                controlledDeposits.append(deposit)
                                controlledBonusDepositIds.append(deposit["TransactionId"])
                                responseObject.log(f" Deposit {deposit_id} added to controlled deposits")
                                break
                            
                            else:
                                if depositAmount > withdrawAmount + totalWithdrawAmount:
                                    totalWithdrawAmount += withdrawAmount
                                    controlledWithdraws = [x for x in controlledWithdraws if x[0] != withdraw]
                                    controlledWithdraws.append([withdraw, 0])
                                else:
                                    newWithdrawAmount = withdrawAmount - (depositAmount - totalWithdrawAmount)
                                    controlledWithdraws = [x for x in controlledWithdraws if x[0] != withdraw]
                                    controlledWithdraws.append([withdraw, newWithdrawAmount])
                        
                        else:
                            if depositAmount >= withdrawAmount:
                                newDepositAmount = depositAmount - withdrawAmount
                                controlledWithdraws = [x for x in controlledWithdraws if x[0] != withdraw]
                                controlledWithdraws.append([withdraw, newDepositAmount])
                                controlledDeposits.append(deposit)
                                controlledBonusDepositIds.append(deposit["TransactionId"])
                                responseObject.log(f" Deposit {deposit_id} added to controlled deposits")
                                break
                            else:
                                if withdrawAmount > depositAmount + totalWithdrawAmount:
                                    totalWithdrawAmount += depositAmount
                                    controlledWithdraws = [x for x in controlledWithdraws if x[0] != withdraw]
                                    controlledWithdraws.append([withdraw, 0])
                                else:
                                    newDepositAmount = depositAmount - (withdrawAmount - totalWithdrawAmount)
                                    controlledWithdraws = [x for x in controlledWithdraws if x[0] != withdraw]
                                    controlledWithdraws.append([withdraw, newDepositAmount]) 

                    if deposit in controlledDeposits:
                        continue
                    
                    if isProfit:
                        diff = totalWithdrawAmount - depositAmount
                        responseObject.log(f" PROFIT calculation: {totalWithdrawAmount} - {depositAmount} = {diff}")
                    else:
                        diff = depositAmount - totalWithdrawAmount
                        responseObject.log(f" LOSS calculation: {depositAmount} - {totalWithdrawAmount} = {diff}")
                        
                    prev_total_diff = totalControlDiff
                    totalControlDiff += diff
                    totalWithdrawAmount = 0
                    responseObject.log(f" Updated totalControlDiff: {prev_total_diff} + {diff} = {totalControlDiff}")
                    # eğer total dif mindifften büyükse
                    if minDiff and minDiff < totalControlDiff:
                        controlledDeposits.append(deposit)
                        controlledBonusDepositIds.append(deposit["TransactionId"])
                        responseObject.log(f" minDiff ({minDiff}) is less than totalControlDiff ({totalControlDiff}). Adding deposit {deposit_id} to controlled list.")
                    else:
                        responseObject.log(f" Deposit {deposit_id} not added to controlled list (minDiff: {minDiff}, totalControlDiff: {totalControlDiff})")
            
            for cw in controlledWithdraws:
                controlledBonusWithdrawIds.append(cw[0]["TransactionId"])
            controlledBonusWithdrawIds = list(set(controlledBonusWithdrawIds))
            
            controlledBonusDepositDict["AllWithdrawIds"] = controlledBonusWithdrawIds
            if len(controlledBonusWithdrawIds) > 3:
                withdrawDates = [x[0]["CreationTime"] for x in controlledWithdraws]
                withdrawDates.sort()
                fDate = self.parse_datetime(withdrawDates[0]).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                tDate = self.parse_datetime(withdrawDates[-1]).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                withdrawDateRange = [fDate, tDate]
                controlledBonusWithdrawIds = []
            else:
                withdrawDateRange = None
            
            controlledBonusDepositDict["AllDepositIds"] = controlledBonusDepositIds
            if len(controlledBonusDepositIds) > 3:
                
                bonusDepositDates = [x["CreationTime"] for x in controlledDeposits]
                bonusDepositDates.sort()
                fDate = self.parse_datetime(bonusDepositDates[0]).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                tDate = self.parse_datetime(bonusDepositDates[-1]).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
                bonusDepositDateRange = [fDate, tDate]
                controlledBonusDepositIds = []
            else:
                bonusDepositDateRange = None
            
            controlledBonusDepositDict["DepositIds"] = controlledBonusDepositIds
            controlledBonusDepositDict["DepositDateRange"] = bonusDepositDateRange
            
            controlledBonusDepositDict["WithdrawIds"] = controlledBonusWithdrawIds
            controlledBonusDepositDict["WithdrawDateRange"] = withdrawDateRange
            responseObject.log(f" Final totalControlDiff computed: {totalControlDiff}")
            
            absControlDiff = abs(totalControlDiff)
            if isProfit:
                
                if minDiff and totalControlDiff < minDiff:
                    return self._returnMessage(False, "PROFIT_UNDER_MIN", minDiff=minDiff, totalControlDiff=absControlDiff),False
                
                if maxDiff and totalControlDiff > maxDiff:
                    return self._returnMessage(False, "PROFIT_OVER_MAX", maxDiff=maxDiff, totalControlDiff=absControlDiff),False
            else:
                if minDiff and totalControlDiff < minDiff:
                    return self._returnMessage(False, "LOSS_UNDER_MIN", minDiff=minDiff, totalControlDiff=absControlDiff),False
                
                if maxDiff and totalControlDiff > maxDiff:
                    return self._returnMessage(False, "LOSS_OVER_MAX", maxDiff=maxDiff, totalControlDiff=absControlDiff),False
            
            return totalControlDiff, controlledBonusDepositDict

        except Exception as e:
            return self._returnError(f"Error in profit count calculation: {str(e)}"),False
    
    
    
    
    
    def __returnDepositCount(self, data: dict):
        """Yatırım sayısını döndürür"""
        try:
            data = data["userInfo"]["TotalDepositsCount"]
            return int(data)
        except Exception as e:
            self.ErrorFunc(e)
            return False
        
    def __returnWithdrawCount(self, data: dict):
        """Çekim sayısını döndürür"""
        try:
            data = data["userInfo"]["TotalWithdrawalsCount"]
            return int(data)
        except Exception as e:
            self.ErrorFunc(e)
            return False
        
    
    
    # control return data
    def _returnMessage(self, isValid , messageKey, **kwargs):
        if not self.validMessages:
            return {"isValid": isValid, "message": messageKey, "code": 1999}
            
            
        print(f"Message key: {messageKey}")
        messageData = self.validMessages.get(messageKey, self.validMessages["GENERAL_ERROR"])
        message = messageData["message"]
        
        # Replace placeholders in message
        if kwargs:
            message = message.format(**kwargs)
            
        messageData = {
            "isValid": isValid, 
            "message": message,
            "code": messageData["code"],
            "args": kwargs
        }
        
        if messageKey == "GENERAL_ERROR":
            messageData["error"] = kwargs.get("errorMessage", "General error")
            
        return messageData
    
        
        
    def _returnError(self, error_message):
        print(f"Error: {error_message}")
        return self._returnMessage(False, "GENERAL_ERROR", errorMessage=error_message)
    
    def _loadValidMessages(self):
        try:
            path =  os.path.join(os.path.dirname(__file__), 'validMessages.json')
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading valid messages: {str(e)}")
            return None
    
    ### Kontroller ###
    
    # Şuanki bakiyesi kontrolü (max ve min değerlerine göre kontrol yapar)
    def _checkCurrentBalance(self, userData: dict, max: float = None, min: float = None):
        """
        Mevcut bakiyenin belirtilen sınırlar içinde olup olmadığını kontrol eder.
        Bu metod, kullanıcının şuanki bakiyesinin opsiyonel minimum ve maksimum eşikler arasında olup olmadığını doğrular.
        
        Parametreler:
            max (float, opsiyonel): İzin verilen maksimum bakiye. Varsayılan: None
            min (float, opsiyonel): Gerekli minimum bakiye. Varsayılan: None
        """
        try:
            currentBalance = self.__returnCurrentBalance(userData)
            if max and currentBalance > max:
                return self._returnMessage(False, "BALANCE_OVER", currentBalance=currentBalance, max=max)
            
            if min and currentBalance < min:
                return self._returnMessage(False, "BALANCE_UNDER", currentBalance=currentBalance, min=min)
            
            return self._returnMessage(True, "CURRENT_BALANCE_OK", currentBalance=currentBalance)
        except Exception as e:
            return self.ErrorFunc(e)
    
    # Kullanıcının Bakiyesinin artıdamı eksidemi olduğunu kontrol eder (isProfit True ise: artıda ise True döner, False ise: ekside ise True döner)
    def _checkBalanceProfit(self, userData: dict, isProfit:bool=True, maxDiff:float=None, minDiff:float=None):
        """
        Kullanıcının para yatırma ve çekme işlemlerine göre kar/zarar durumunu kontrol eder ve bonus almaya uygun olup olmadığını belirler.
        Parameters
        ----------
        isProfit : bool, optional
            Kar durumu kontrolü için True, zarar durumu kontrolü için False (varsayılan True yani kullanıcı kar durumunda bonus alabilir)
        maxDiff : float, optional
            Maksimum kar/zarar limiti (varsayılan None)
        minDiff : float, optional
            Minimum kar/zarar limiti (varsayılan None)
            
        Notes
        -----
        - Kar durumu kontrolünde (isProfit=True):
            * Çekilen miktar > Yatırılan miktar ise ve limitler dahilindeyse bonus alınabilir
            * Aksi durumda bonus alınamaz
        - Zarar durumu kontrolünde (isProfit=False):
            * Çekilen miktar < Yatırılan miktar ise ve limitler dahilindeyse bonus alınabilir
            * Aksi durumda bonus alınamaz
        """
        
        try:
            totalDepositAmount = userData["userInfo"]["TotalDepositsAmount"]
            totalWithdrawAmount = userData["userInfo"]["TotalWithdrawalsAmount"]
            
            diff = totalDepositAmount - totalWithdrawAmount
            print(f"Total deposit amount: {totalDepositAmount}, Total withdraw amount: {totalWithdrawAmount}, Diff: {diff}")
            # Positive diff (totalDepositAmount > totalWithdrawAmount) means user is at a LOSS
            # Negative diff (totalDepositAmount < totalWithdrawAmount) means user is PROFITABLE
            
            # Calculate absolute difference for cleaner code
            abs_diff = abs(diff)
            
            if isProfit:
                # We're checking profit limits (whether user is profitable or not)
                if diff < 0:  # User is profitable (withdrew more than deposited)
                    if maxDiff and abs_diff > maxDiff:
                        return self._returnMessage(False, "PROFIT_OVER", diff=abs_diff, maxDiff=maxDiff)
                    return self._returnMessage(True, "PROFIT_OK", diff=abs_diff)
                else:  # User is at loss or break-even (deposited >= withdrew)
                    return self._returnMessage(True, "USER_NOT_PROFITABLE", diff=diff)
            else:
                # We're checking loss limits (whether user is at a loss or not)
                if diff > 0:  # User is at a loss (deposited more than withdrew)
                    if maxDiff and diff > maxDiff:
                        return self._returnMessage(False, "LOSS_OVER", diff=diff, maxDiff=maxDiff)
                    if minDiff and diff < minDiff:
                        return self._returnMessage(False, "LOSS_UNDER", diff=diff, minDiff=minDiff)
                    return self._returnMessage(True, "LOSS_OK", diff=diff)
                else:  # User is profitable or break-even (withdrew >= deposited)
                    return self._returnMessage(True, "USER_NOT_AT_LOSS", diff=abs_diff)
        
        except Exception as e:
            return self.ErrorFunc(e)
            

    # Beklemede Bet varmı kontrolü (HasBet True ise: bet varsa True döner, False ise: bet yoksa True döner)
    def _checkPendingBet(self, userData: dict, days:dict=1,hasBet:bool=True):
        """
        Belirlenen tarih aralığında kullanıcının bekleyen bahislerini kontrol eder.
        Bu fonksiyon, verilen kullanıcı için spor ve casino bahislerini sorgular ve 
        belirtilen tarih aralığında bekleyen bahis olup olmadığını kontrol eder.
        Parametreler:
            days (dict, varsayılan=1): Sorgulanacak gün sayısı
                - Geçmiş tarihe doğru kaç gün kontrol edileceğini belirler
            hasBet (bool, varsayılan=True): Bahis kontrolü için beklenen durum
                - True: Bahis olması bekleniyor
                - False: Bahis olmaması bekleniyor
        Dönüş Değeri:
            dict: İşlem sonucunu içeren mesaj ve durum bilgisi
        Notlar:
            - Fonksiyon hem spor hem de casino bahislerini kontrol eder
            - Tarih aralığı dataRangeGenerator fonksiyonu ile oluşturulur
            - Sadece durum kodu 0 olan (bekleyen) bahisler kontrol edilir
            - Hata durumunda ErrorFunc ile hata mesajı döndürülür
        """
        
        try:
            from_date, to_date = self.dataRangeGenerator("day", days,dateTimed=True)
            
            casinoBets = self.app.getCasinoBets(from_date, to_date, userData["userId"],[1,0])
            sportBets = self.app.getSportBets(from_date, to_date, userData["userId"],[1,0])
            
            if len(casinoBets) == 0 and len(sportBets) == 0:
                return self._returnMessage(not hasBet, "NO_PENDING_BET")
            return self._returnMessage(hasBet, "PENDING_BET")
            
        except Exception as e:
            return self.ErrorFunc(e)
    
    # Kullanıcı kaydı belirlenen gün sayısı içinde mi kontrolü
    def _checkUserRegister(self,userData, days:int=1):
        """
        Kullanıcının kayıt tarihinin belirtilen gün aralığında olup olmadığını kontrol eder.
        Verilen kullanıcı verisindeki kayıt tarihinin, günümüzden geriye doğru belirlenen gün sayısı
        içerisinde olup olmadığını kontrol eder. Örneğin days=1 için son 24 saat içinde kayıt olup
        olmadığını kontrol eder.
        Parameters
        ----------
        days : int, optional
            Kontrol edilecek gün sayısı (varsayılan değer 1)
            Pozitif tam sayı olmalıdır.
        Returns
        -------
        dict
            success : bool
                İşlemin başarılı olup olmadığını belirten değer
            message : str
                İşlem sonucunu açıklayan mesaj
        Notes
        -----
        - Tarih formatı "YYYY-MM-DDTHH:MM:SS" şeklinde olmalıdır
        - Hata durumunda ErrorFunc metodu çağrılır
        - dataRangeGenerator metodu kullanılarak tarih aralığı oluşturulur
        """
        
        try:
            from_date, to_date = self.dataRangeGenerator("day", days,dateTimed=True)
            reg_date_str = userData["userInfo"]["RegistrationDate"].split('.')[0]
            registerDate = datetime.strptime(reg_date_str, "%Y-%m-%dT%H:%M:%S")
            if registerDate >= from_date and registerDate <= to_date:
                return self._returnMessage(True, "USER_REGISTERED_IN_RANGE")
            return self._returnMessage(False, "USER_NOT_REGISTERED_IN_RANGE", registerDate=registerDate)
        except Exception as e:
            return self.ErrorFunc(e)
        
    # Yatırım kontrolü(HasDeposit True ise: yatırım varsa True döner, False ise: yatırım yoksa True döner)
    def _checkDepositExist(self, userData, hasDeposit:bool=True, days:int=None):
        """
        Belirtilen gün aralığında kullanıcının yatırım işlemi yapıp yapmadığını kontrol eder.
        Parametreler:
            days (int): Geriye dönük kaç günlük yatırımların kontrol edileceği (Eğer verilmez ise toplam yatırım sayısından baz alınır direkt olarak kontrol yapılır)
            hasDeposit (bool): HasDeposit True ise: yatırım varsa True döner, False ise: yatırım yoksa True döner
        """
        try:
            if days is not None:
                depositList = self.__returnDeposits(userData, days)
                if type(depositList) == dict:
                    return depositList
                
                if len(depositList) == 0:
                    return self._returnMessage(not hasDeposit, "NO_DEPOSIT_IN_RANGE")
                
            else:
                depositCount = self.__returnDepositCount(userData)
                if depositCount == -1:
                    return self._returnMessage(False, "DEPOSIT_COUNT_ERROR")
                
                if depositCount == 0:
                    return self._returnMessage(not hasDeposit, "NO_DEPOSIT_IN_RANGE")
            return self._returnMessage(hasDeposit, "DEPOSIT_IN_RANGE")
        except Exception as e:
            return self.ErrorFunc(e)
        
    def _checkDepositCount(self, userData, max:int=None, min:int=None):
        """
        Yatırım sayısını kontrol eder.
        Parametreler:
            max (int, optional): İzin verilen maksimum yatırım sayısı
            min (int, optional): İzin verilen minimum yatırım sayısı
        """
        try:
            depositCount = self.__returnDepositCount(userData)
            if depositCount == -1:
                return self._returnMessage(False, "DEPOSIT_COUNT_ERROR")
            
            # ikisi aynı verildiyse
            if max and min and max == min:
                if depositCount == max:
                    return self._returnMessage(True, "DEPOSIT_COUNT_EQUAL", depositCount=depositCount, max=max)
                return self._returnMessage(False, "DEPOSIT_COUNT_NOT_EQUAL", depositCount=depositCount, max=max)
            
            if max and depositCount > max:
                return self._returnMessage(False, "DEPOSIT_COUNT_OVER", depositCount=depositCount, max=max)
            
            if min and depositCount < min:
                return self._returnMessage(False, "DEPOSIT_COUNT_UNDER", depositCount=depositCount, min=min)
            
            return self._returnMessage(True, "DEPOSIT_COUNT_OK", depositCount=depositCount)
        except Exception as e:
            return self.ErrorFunc(e)
        
    # Çekim kontrolü(HasWithdraw True ise: çekim varsa True döner, False ise: çekim yoksa True döner)
    def _checkWithdrawCount(self, userData, max:int=None, min:int=None):
        """
        Belirtilen gün aralığında kullanıcının çekim sayısını kontrol eder.
        Parametreler:
            days (int): Geriye dönük kaç günlük çekimlerin kontrol edileceği
            maxWithdrawCount (int, optional): İzin verilen maksimum çekim sayısı
            minWithdrawCount (int, optional): İzin verilen minimum çekim sayısı
        """
        try:
            withdrawCount = self.__returnWithdrawCount(userData)
            if withdrawCount == -1:
                return self._returnMessage(False, "WITHDRAW_COUNT_ERROR")
            
            # ikisi aynı verildiyse
            if max and min and max == min:
                if withdrawCount == max:
                    return self._returnMessage(True, "WITHDRAW_COUNT_EQUAL", withdrawCount=withdrawCount, max=max)
                return self._returnMessage(False, "WITHDRAW_COUNT_NOT_EQUAL", withdrawCount=withdrawCount, max=max)
            
            if max and withdrawCount > max:
                return self._returnMessage(False, "WITHDRAW_COUNT_OVER", withdrawCount=withdrawCount, max=max)
            
            if min and withdrawCount < min:
                return self._returnMessage(False, "WITHDRAW_COUNT_UNDER", withdrawCount=withdrawCount, min=min)
            
            return self._returnMessage(True, "WITHDRAW_COUNT_OK", withdrawCount=withdrawCount)
        except Exception as e:
            return self.ErrorFunc(e)
        
        

    
    # Yatırım miktarı kontrolü (Son yatırım miktarın üstündemi veya altındamı & yatırım öncesi bakiyesi kaç & bakiyeyi yatırımdan sonra kullanmışmı kontrolü)
    def _checkLastDeposit(self, userData,days:int=1, max:float = None, min:float = None,checkIsUsed:bool = False,checkFirstDeposit:bool=False, checkSecondDeposit:bool=False, beforeBalanceMin:float = None, beforeBalanceMax:float = None):
        """
        Son yatırımın belirli kriterlere uygunluğunu kontrol eden fonksiyon.
        Bu fonksiyon, kullanıcının son yatırımını çeşitli kriterlere göre kontrol eder ve uygunluğunu değerlendirir.
        Yatırımın miktarı, zamanı, kullanım durumu ve önceki bakiye gibi parametrelere göre kontrol yapılır.
        Parameters:
            userData (dict): Kullanıcı bilgilerini içeren sözlük.
                            Mutlaka "userId" anahtarı içermelidir.
            days (int, optional): Son kaç günlük yatırımların kontrol edileceği. 
                                 Varsayılan değer 1'dir.
            max (float, optional): İzin verilen maksimum yatırım miktarı.
                                  None ise üst limit kontrolü yapılmaz.
                                  Yatırım bu değerden büyükse False döner.
            min (float, optional): İzin verilen minimum yatırım miktarı.
                                  None ise alt limit kontrolü yapılmaz.
                                  Yatırım bu değerden küçükse False döner.
            checkIsUsed (bool, optional): Yatırım sonrası bet kontrolü yapılıp yapılmayacağı.
                                         True ise, yatırım sonrası yapılan casino ve spor betleri kontrol edilir.
                                         Bet yapılmışsa False döner.
                                         Varsayılan değer False'dur.
            checkFirstDeposit (bool, optional): İlk yatırım kontrolü yapılıp yapılmayacağı.
                                              True ise, kullanıcının birden fazla yatırımı varsa False döner.
                                              Varsayılan değer False'dur.
            checkSecondDeposit (bool, optional): İkinci yatırım kontrolü yapılıp yapılmayacağı.
                                               True ise, gün içerisindeki ikinci yatırım kontrolü yapılır.
                                               Varsayılan değer False'dur.
            beforeBalanceMin (float, optional): Yatırım öncesi minimum bakiye limiti.
                                              None ise kontrol yapılmaz.
                                              Yatırım öncesi bakiye bu değerden küçükse False döner.
            beforeBalanceMax (float, optional): Yatırım öncesi maksimum bakiye limiti.
                                                None ise kontrol yapılmaz.
                                                Yatırım öncesi bakiye bu değerden büyükse False döner.
        Notes:
            - Fonksiyon herhangi bir hata durumunda ErrorFunc ile hata mesajı döner
            - Yatırım listesi boş ise False döner
            - checkIsUsed=True iken bet kontrollerinde hata olursa ErrorFunc ile hata mesajı döner
            - Tüm para birimi değerleri aynı birimde olmalıdır
            - datetime karşılaştırmaları UTC'ye göre yapılır
            - checkFirstDeposit ve checkSecondDeposit aynı anda True olamaz
        """
        
        try:
            # First and second deposit checks cannot be both True
            if checkFirstDeposit and checkSecondDeposit:
                return self._returnError("checkFirstDeposit ve checkSecondDeposit aynı anda True olamaz")
            
            depositList = self.__returnDeposits(userData, days)
            if len(depositList) == 0:
                return self._returnMessage(False, "NO_DEPOSIT_IN_RANGE")
            
            # First deposit check - only one deposit ever
            if checkFirstDeposit:
                totalDepositcount = self.__returnDepositCount(userData)
                if totalDepositcount > 1:
                    return self._returnMessage(False, "MULTIPLE_DEPOSITS")
            
            # Second deposit check - exactly two deposits today, and current is the second one
            if checkSecondDeposit:
                # Get today's deposits only (not last N days, but today specifically)
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                tomorrow = today + timedelta(days=1)
                
                todayDeposits = [x for x in self.app.getUserDeposits(userData["userId"], today, tomorrow)["Deposits"] if x["Status"] == 8]
                todayDeposits.sort(key=lambda x: x["CreationTime"], reverse=False)  # Oldest first
                
                # Must have exactly 2 deposits today
                if len(todayDeposits) < 2:
                    return self._returnMessage(False, "NOT_SECOND_DEPOSIT_OF_DAY", 
                                             depositCount=len(todayDeposits))
                elif len(todayDeposits) > 2:
                    return self._returnMessage(False, "MORE_THAN_TWO_DEPOSITS_TODAY", 
                                             depositCount=len(todayDeposits))
                
                # Current deposit must be the second one (most recent)
                currentDepositId = depositList[0]["TransactionId"]
                secondDepositId = todayDeposits[1]["TransactionId"] if len(todayDeposits) >= 2 else None
                
                if currentDepositId != secondDepositId:
                    return self._returnMessage(False, "NOT_CURRENT_SECOND_DEPOSIT")
            
            lastDepositAmount = float(depositList[0]["FinalAmount"])
            if max and lastDepositAmount > max:
                return self._returnMessage(False, "DEPOSIT_OVER", lastDepositAmount=int(lastDepositAmount), max=max)
            
            if min and lastDepositAmount < min:
                return self._returnMessage(False, "DEPOSIT_UNDER", lastDepositAmount=int(lastDepositAmount), min=min)
            
            if checkIsUsed:
                lastDepositCreateDate = datetime.strptime(depositList[0]["CreationTime"].split('.')[0], "%Y-%m-%dT%H:%M:%S")
                nowDate = datetime.now()
                # bu tarihten sonra casino veya spor bet yapmışmı kontrolü
                casinoBets = self.app.getCasinoBets(lastDepositCreateDate, nowDate, userData["userId"],maxBetCount=1)
                sportBets = self.app.getSportBets(lastDepositCreateDate, nowDate, userData["userId"],maxBetCount=1)
                
                print(f"Lenght of casino bets: {len(casinoBets)}")
                print(f"Lenght of sport bets: {len(sportBets)}")
                
                if  type(casinoBets) != list or type(sportBets) != list:
                    return self._returnError("Bet kontrolü yapılırken hata oluştu")

                if len(casinoBets) > 0 :
                    return self._returnMessage(False, "CASINO_BET_AFTER_DEPOSIT")
                if len(sportBets) > 0 :
                    return self._returnMessage(False, "SPORT_BET_AFTER_DEPOSIT")
                
                
            
            reqBeforeBalance = float(depositList[0]["BalanceBefore"])
            # Yatırım öncesi bakiye balanceMin'den küçükse False döner
            if beforeBalanceMin and reqBeforeBalance < beforeBalanceMin:
                return self._returnMessage(False, "BEFORE_BALANCE_UNDER", reqBeforeBalance=reqBeforeBalance, beforeBalanceMin=beforeBalanceMin)
            
            # Yatırım öncesi bakiye balanceMax'ten büyükse False döner
            if beforeBalanceMax and reqBeforeBalance > beforeBalanceMax:
                return self._returnMessage(False, "BEFORE_BALANCE_OVER", reqBeforeBalance=reqBeforeBalance, beforeBalanceMax=beforeBalanceMax)
            
            # Success message varies based on deposit type check
            if checkFirstDeposit:
                return self._returnMessage(True, "FIRST_DEPOSIT_OK", lastDepositAmount=lastDepositAmount)
            elif checkSecondDeposit:
                return self._returnMessage(True, "SECOND_DEPOSIT_OK", lastDepositAmount=lastDepositAmount)
            else:
                return self._returnMessage(True, "DEPOSIT_AMOUNT_OK", lastDepositAmount=lastDepositAmount)
                
        except Exception as e:
            return self.ErrorFunc(e)
    
    # Son yatırımın yatırım yöntemi kontrolü (hasMethod True ise: Son yatırım belirtilen yöntemlerden biriyse True döner, False ise: Son yatırım belirtilen yöntemde değilse True döner)
    def _checkLastDepositMethod(self, userData, depositMethod:list=[], hasMethod:bool=True):
        """
        Son yatırımın belirtilen yöntemde olup olmadığını kontrol eder.
        
        Parametreler:
            depositMethod (list): Kontrol edilecek yatırım yöntemleri
            hasMethod (bool): True ise: Son yatırım belirtilen yöntemlerden biriyse True döner, False ise: Son yatırım belirtilen yöntemde değilse True döner
        """
        try:
            deposit = self.__returnLastDeposit(userData, 29)
            
            if not deposit:
                return self._returnMessage(False, "NO_DEPOSIT_FOUND")
            depositPaymentSystemName = deposit["PaymentSystemName"]
            
            if not depositPaymentSystemName:
                return self._returnError("DEPOSIT_METHOD_UNKNOWN")
            
            if depositPaymentSystemName not in depositMethod:
                return self._returnMessage(not hasMethod, "DEPOSIT_METHOD_ALLOWED", depositPaymentSystemName=depositPaymentSystemName)
            return self._returnMessage(hasMethod, "DEPOSIT_METHOD_NOT_ALLOWED", depositPaymentSystemName=depositPaymentSystemName)
        except Exception as e:
            return self.ErrorFunc(e)
    
    # Aktif bonusu varmı kontrolü (HasActiveBonus True ise: aktif bonus varsa True döner, False ise: aktif bonus yoksa True döner)
    def _checkActiveBonusExist(self, userData, hasActiveBonus:bool=True):
        """
        Kullanıcının aktif bonusunun olup olmadığını kontrol eder.
        Parameters
        ----------
        hasActiveBonus : bool, default=True
            Kontrol edilmek istenen durum. True ise aktif bonus varlığı,
            False ise aktif bonus yokluğu kontrol edilir.
        Returns
        -------
        dict
            İşlem sonucunu içeren sözlük yapısı.
            Başarılı durumda:
                - success: bool
                - message: str (Durum mesajı)
            Hata durumunda:
                - error: bool
                - message: str (Hata mesajı)
        Notes
        -----
        - Eğer aktif bonus varsa ve hasActiveBonus=True ise success=True döner
        - Eğer aktif bonus yoksa ve hasActiveBonus=False ise success=True döner
        - Bu iki durum dışında success=False döner
        - Herhangi bir hata durumunda ErrorFunc ile hata yönetimi yapılır
        """
        
        try:
            activeBonuses = self.__returnBonuses(userData)
            if activeBonuses is False:
                return self._returnMessage(False, "GENERAL_ERROR", errorMessage="Bonus listesi alınamadı")
                
            if isinstance(activeBonuses, list):
                # Sadece aktif (Status=2) olan bonusları filtrele
                
                if len(activeBonuses) == 0:
                    return self._returnMessage(not hasActiveBonus, "NO_ACTIVE_BONUS")
                return self._returnMessage(hasActiveBonus, "ACTIVE_BONUS")
                
            return self._returnMessage(False, "GENERAL_ERROR", errorMessage="Bonus listesi geçersiz formatta")
            
        except Exception as e:
            return self.ErrorFunc(e)
    
    # IP çakışması kontrolü (Çakışma varsa False döner, yoksa True döner)
    def _checkIpConflict(self, userData):
        """
        IP ve cihaz çakışmasını kontrol eden fonksiyon. Aynı IP'den veya cihazdan yapılan hesap kullanımlarını tespit eder.
        Notlar:
            - Herhangi bir çakışma bulunduğunda False döner
        """
        
        try:
            result = self.app.getMultiAccountCount(userData["userId"])
            if int(result["m_Item1"]) > 0:
                return self._returnMessage(False, "IP_CONFLICT")
            if int(result["m_Item2"]) > 0:
                return self._returnMessage(False, "DEVICE_CONFLICT")
            return self._returnMessage(True, "NO_CONFLICT")
        except Exception as e:
            return self.ErrorFunc(e)
    
    # Çekim işlemi kontrolü (HasWithdraw True ise: çekim işlemi varsa True döner, False ise: çekim işlemi yoksa True döner)
    def _checkWithdrawExist(self, userData,days:int=1,controlAfterDeposit:bool=False, hasWithdraw:bool=False,  controlMinDepositDiff:float=None, controlHourCount:int=24):
        """
        Kullanıcının çekim işlemlerini kontrol eden ve çeşitli koşullara göre değerlendiren fonksiyon.
        Bu fonksiyon, belirtilen gün aralığında kullanıcının çekim işlemlerini kontrol eder. İsteğe bağlı olarak
        son yatırımdan sonraki çekimleri veya yatırım-çekim farkını kontrol edebilir.

        Parameters
        ----------
        days : int, default=1
            Kontrol edilecek gün sayısı. Örneğin 7 girilirse son 7 gündeki işlemler kontrol edilir.
            Minimum değer 1'dir.

        controlAfterDeposit : bool, default=False  
            Son yatırım sonrası çekim kontrolü yapar.
            - True: Sadece son yatırımdan sonraki çekimleri kontrol eder
            - False: Tüm çekimleri kontrol eder
            
        hasWithdraw : bool, default=False
            Çekim varlığı kontrolü yapar.
            - True: Çekim yapılmış olması beklenir, yapılmamışsa hata döner
            - False: Çekim yapılmamış olması beklenir, yapılmışsa hata döner
            
        controlMinDepositDiff : float, optional
            Yatırım ve çekim arasındaki minimum fark kontrolü. 
            Örneğin 100 girilirse, son yatırım miktarı ile çekim miktarı arasında
            en az 100 birimlik fark olması beklenir.
            None ise bu kontrol yapılmaz.
            
        controlHourCount : int, optional
            controlMinDepositDiff ile birlikte kullanılır.
            Kontrol edilecek saat aralığını belirler.
            Örneğin 24 girilirse son 24 saatteki işlemler kontrol edilir.
            Minimum değer 1'dir.
            
        Notes
        -----
        - hasWithdraw ve controlMinDepositDiff parametrelerinden sadece biri kullanılmalıdır
        - controlMinDepositDiff kullanılıyorsa controlHourCount mutlaka belirtilmelidir 
        - controlHourCount 1'den küçük olamaz
        - Çekim kontrollerinde sadece Status=8 olan çekimler dikkate alınır
        """
        print(f"Today: {datetime.now()}")
        
        
        try:
            if hasWithdraw is None and controlMinDepositDiff is None:
                return self._returnError("Bir kontrol parametresi belirtilmelidir: hasWithdraw veya minDepositDiff için sağlanmalı kontrol")
            
            if hasWithdraw is not None and controlMinDepositDiff is not None:
                return self._returnError("Tek bir kontrol parametresi belirtilmelidir: hasWithdraw veya minDepositDiff için sağlanmalı kontrol")
            
            if controlAfterDeposit or controlMinDepositDiff:

                depositList = self.__returnDeposits(userData, days)
                if len(depositList) == 0:
                    return self._returnMessage(False, "NO_DEPOSIT_IN_RANGE")
                
                from_date, to_date = self.dataRangeGenerator("day", days,dateTimed=True)
                
                
                lastDepositCreateDate = self.parse_datetime(depositList[0]["CreationTime"])
                
                if controlHourCount < 1:
                    return self._returnError("checkWithdrawExist'de Saat sayısı 1'den küçük olamaz")
                to_date = lastDepositCreateDate
                from_date = lastDepositCreateDate - timedelta(hours=controlHourCount)
                print(f"lastDepositCreateDate: {lastDepositCreateDate}")
                print(f"Control time ranges: {from_date} - {to_date}")
                
                withdrawList = [x for x in self.app.getWithdrawList(from_date, to_date, userData["userId"]) if x["Status"] == 8]
            else:
                from_date, to_date = self.dataRangeGenerator("day", days,dateTimed=True)
                
                from_date = datetime.now() - timedelta(hours=controlHourCount)
                withdrawList = [x for x in self.app.getWithdrawList(from_date, to_date, userData["userId"]) if x["Status"] == 8]
            
            if controlMinDepositDiff:
                if len(withdrawList) == 0:
                    withdrawAmount = 0.0
                else:
                    withdrawAmount = sum([x["FinalAmount"] for x in withdrawList])
                
                Diff = depositList[0]["FinalAmount"] - withdrawAmount
                
                if Diff < controlMinDepositDiff:
                    return self._returnMessage(False, "DEPOSIT_WITHDRAW_DIFF_UNDER",HourCount=controlHourCount, Diff=Diff, controlMinDepositDiff=controlMinDepositDiff)
                    
                    
            
            if len(withdrawList) == 0:
                return self._returnMessage(not hasWithdraw, "NO_WITHDRAW_IN_RANGE")
            return self._returnMessage(hasWithdraw, "WITHDRAW_IN_RANGE")
        except Exception as e:
            return self.ErrorFunc(e)

    
    
    def _checkTimeRange(self,userData,startHour=0, endHour=24):
        """
        Belirtilen saat aralığında olunup olunmadığını kontrol eder.
        Parameters
        ----------
        startHour : int, optional
            Başlangıç saati (varsayılan 0)
        endHour : int, optional
            Bitiş saati (varsayılan 24)
        """
        try:
            realTime = userData["realTime"]
            
            now = datetime.fromisoformat(realTime)
            start = now.replace(hour=startHour, minute=0, second=0, microsecond=0)
            end = now.replace(hour=endHour, minute=0, second=0, microsecond=0)
            
            if now >= start and now <= end:
                return self._returnMessage(True, "TIME_RANGE_OK")
            return self._returnMessage(False, "TIME_RANGE_DEF", startHour=startHour, endHour=endHour)
        except Exception as e:
            return self.ErrorFunc(e)
        
    
    def _checkProfitControlDetailed(self, userData, days:int=1, controlLastDepositBefore:bool=False,
                           calculationFirstDepositAfterHourCount=24,
                           calculationFirstDepositAfterHourRange=[0,24], 
                           isDepositFilter:bool=True, 
                           minDiff:float=None, 
                           maxDiff:float=None, 
                           isProfit:bool=None):
        """
        Belirli bir tarih aralığında kullanıcının kar/zarar durumunu kontrol eder.
        
        Parameters
        ----------
        userData : dict
            Kullanıcı verilerini içeren sözlük
        days : int, default=1
            Kontrol edilecek gün sayısı
        controlLastDepositBefore : bool, default=False
            Son yatırımdan önceki çekimleri kontrol et
        calculationFirstDepositAfterHourCount : int, default=24
            Hesaplanacak saat sayısı veya "calculationDate" değeri
        calculationFirstDepositAfterHourRange : list, default=[0,24]
            Hesaplanacak saat aralığı [başlangıç, bitiş]
        isDepositFilter : bool, default=True
            Bonus depozitlerini filtrele
        minDiff : float, optional
            Minimum kar/zarar farkı
        maxDiff : float, optional
            Maksimum kar/zarar farkı
        isProfit : bool, optional
            True: Kâr durumu kontrolü (çekim > yatırım)
            False: Zarar durumu kontrolü (yatırım > çekim)
            None: Her iki durum da kabul edilir
        
        Returns
        -------
        dict
            İşlem sonucunu içeren sözlük
        """
        try:
            # Tarih değerleri belirtilmemişse, son 24 saati kullanın
            
            fromdate, todate = self.dataRangeGenerator("day", days,dateTimed=True)
            
            if controlLastDepositBefore:
                # Son yatırımdan önceki çekimleri kontrol et
                lastDeposit = self.__returnLastDeposit(userData, 29)
                if not lastDeposit:
                    return self._returnMessage(False, "NO_DEPOSIT_FOUND")
                
                lastDepositDate = self.parse_datetime(lastDeposit["CreationTime"])
                todate = lastDepositDate
                fromdate = lastDepositDate - timedelta(days=days)
            
            
            # Kar/zarar hesapla
            profit_result, deposit_details = self.__returnProfitCount(
                userData, 
                fromdate, 
                todate,
                calculationFirstDepositAfterHourCount,
                calculationFirstDepositAfterHourRange,
                isDepositFilter,
                minDiff,
                maxDiff,
                isProfit
            )
            
            # Hata durumunu kontrol et
            if isinstance(profit_result, dict) and not profit_result.get("isValid", True):
                return profit_result
            
            # Sonuçları döndür
            return self._returnMessage(True, "PROFIT_CONTROL_OK", profitResult=profit_result)
            
        except Exception as e:
            return self.ErrorFunc(e)
            
    def _checkYesterdayTotalDeposit(self, userData, min:float=None, max:float=None):
        """
        Dünkü toplam yatırım miktarını kontrol eder.
        
        Parameters
        ----------
        userData : dict
            Kullanıcı verilerini içeren sözlük
        min : float, optional
            Minimum toplam yatırım miktarı
        max : float, optional  
            Maksimum toplam yatırım miktarı
            
        Returns
        -------
        dict
            İşlem sonucunu içeren sözlük
        """
        try:
            # Use user's real time, not server time
            real_time_str = userData["realTime"]
            real_today = datetime.fromisoformat(real_time_str.replace('Z', ''))
            
            # Yesterday's date range in user's real time
            real_yesterday_start = real_today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
            real_yesterday_end = real_today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
            
            # Convert to backend time (subtract timezone difference)
            yesterday_start = real_yesterday_start - timedelta(hours=userData["realTimeZone"])
            yesterday_end = real_yesterday_end - timedelta(hours=userData["realTimeZone"])
            
            # Get yesterday's deposits
            deposits = self.app.getUserDeposits(
                userData["userId"], 
                yesterday_start, 
                yesterday_end
            )["Deposits"]
            
            # Filter only approved deposits (Status = 8)
            yesterdayDeposits = [d for d in deposits if d.get("Status") == 8]
            
            if not yesterdayDeposits:
                return self._returnMessage(False, "NO_DEPOSIT_YESTERDAY")
            
            # Calculate total deposit amount for yesterday
            totalAmount = sum(d["FinalAmount"] for d in yesterdayDeposits)
            
            # Check minimum requirement
            if min and totalAmount < min:
                return self._returnMessage(False, "YESTERDAY_DEPOSIT_UNDER", 
                                         totalAmount=totalAmount, min=min)
            
            # Check maximum limit                             
            if max and totalAmount > max:
                return self._returnMessage(False, "YESTERDAY_DEPOSIT_OVER", 
                                         totalAmount=totalAmount, max=max)
                                         
            return self._returnMessage(True, "YESTERDAY_DEPOSIT_OK", 
                                     totalAmount=totalAmount, depositCount=len(yesterdayDeposits))
                                     
        except Exception as e:
            return self.ErrorFunc(e)

    def getControlList(self):
        """Kontrol fonksiyonlarının listesini ve parametrelerini döndürür"""
        
        controls = {}
        
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith('_check') and name != '_checkUser' and not name.startswith('__'):
                sig = inspect.signature(method)
                doc = inspect.getdoc(method)
                
                params = []
                for param_name, param in sig.parameters.items():
                    if param_name != 'self' and param_name != 'userData':
                        param_info = {
                            'name': param_name,
                            'type': str(param.annotation.__name__) if param.annotation != inspect._empty else 'any',
                            'default': param.default if param.default != inspect._empty else None,
                            'required': param.default == inspect._empty
                        }
                        params.append(param_info)
                
                controlName = name[1:]
                
                controls[controlName] = {
                    'description': doc if doc else '',
                    'parameters': params
                }
        self.controls = controls
        return json.dumps(controls, indent=4)
    
    def runControl(self, controlName, userData, params):
        """Kontrol fonksiyonunu çalıştırır"""
        try:
            controlFunc = getattr(self, f'_{controlName}', None)
            if not controlFunc:
                return self._returnError(f"{controlName} kontrolü bulunamadı veya bir hata oluştu")
            
            return controlFunc(userData, **params)
        except Exception as e:
            return self.ErrorFunc(e)

    def _checkKombineKuponSigorta(self, userData, days:int=7, minMatches:int=4, maxMatches:int=8, minOdds:float=1.50, minBetAmount:float=100, maxBonusAmount:float=5000, requestTimeLimitHours:int=48):
        """
        Kombine kupon sigortası için uygunluk kontrolü
        - 4-8 maç arası kombine kupon
        - Tüm maçlar min 1.50 oran
        - Min 100 TL kupon bedeli
        - Tek maç kaybı
        - Max 5000 TL bonus
        - Günde 1 kez
        - Belirtilen saat sınırı içinde talep edilmeli
        """
        try:
            from_date, to_date = self.dataRangeGenerator("day", days, dateTimed=True)
            
            # Spor bahislerini çek
            sportBets = self.app.getSportBets(from_date, to_date, userData["userId"], [2, 3])  # Kaybeden ve kazanan bahisler
            
            if not sportBets:
                return self._returnMessage(False, "NO_SPORT_BETS_FOUND")
            
            eligible_bets = []
            time_expired_bets = 0
            
            for bet in sportBets:
                try:
                    # Bet detaylarını al
                    betDetails = self.app.getSportBetDetails(bet["BetId"])
                    if not betDetails:
                        continue
                    
                    # Kombine bet kontrolü
                    if betDetails.get("BetType") != "Combination":
                        continue
                    
                    selections = betDetails.get("Selections", [])
                    match_count = len(selections)
                    
                    # Maç sayısı kontrolü
                    if match_count < minMatches or match_count > maxMatches:
                        continue
                    
                    # Kupon bedeli kontrolü
                    bet_amount = float(bet.get("BetAmount", 0))
                    if bet_amount < minBetAmount:
                        continue
                    
                    # Oran kontrolü
                    all_odds_valid = True
                    for selection in selections:
                        odds = float(selection.get("Odds", 0))
                        if odds < minOdds:
                            all_odds_valid = False
                            break
                    
                    if not all_odds_valid:
                        continue
                    
                    # Tek maç kaybı kontrolü
                    lost_count = 0
                    won_count = 0
                    
                    for selection in selections:
                        result = selection.get("Result")
                        if result == "Lost":
                            lost_count += 1
                        elif result == "Won":
                            won_count += 1
                    
                    # Sadece 1 maç kaybetmiş olmalı
                    if lost_count != 1:
                        continue
                    
                    # En az 3 maç kazanmış olmalı
                    if won_count < 3:
                        continue
                    
                    # Sistem kuponu kontrolü
                    if bet.get("IsSystem", False):
                        continue
                    
                    # İade edilebilir bahis kontrolü
                    if bet.get("IsRefundable", False):
                        continue
                    
                    # 48 saat limit kontrolü
                    bet_settle_time = self.parse_datetime(bet["SettlementTime"] if bet.get("SettlementTime") else bet["CreationTime"])
                    current_time = datetime.now()
                    hours_since_settlement = (current_time - bet_settle_time).total_seconds() / 3600
                    
                    if hours_since_settlement > requestTimeLimitHours:
                        time_expired_bets += 1
                        continue  # Skip bets older than 48 hours
                    
                    # Bonus yüzdesini hesapla
                    if match_count >= 8:
                        bonus_percentage = 100
                    elif match_count == 7:
                        bonus_percentage = 50
                    elif match_count == 6:
                        bonus_percentage = 40
                    elif match_count == 5:
                        bonus_percentage = 30
                    else:  # 4 maç
                        bonus_percentage = 20
                    
                    bonus_amount = (bet_amount * bonus_percentage) / 100
                    
                    # Max bonus kontrolü
                    if bonus_amount > maxBonusAmount:
                        bonus_amount = maxBonusAmount
                    
                    eligible_bets.append({
                        "betId": bet["BetId"],
                        "betAmount": bet_amount,
                        "matchCount": match_count,
                        "bonusPercentage": bonus_percentage,
                        "bonusAmount": bonus_amount,
                        "betDate": bet["CreationTime"]
                    })
                    
                except Exception as e:
                    continue
            
            if not eligible_bets:
                if time_expired_bets > 0:
                    return self._returnMessage(False, "KOMBINE_KUPON_TIME_LIMIT_EXCEEDED")
                return self._returnMessage(False, "NO_ELIGIBLE_KOMBINE_BETS")
            
            # En yüksek kupon bedelini al (çoklu uygun bahis durumunda)
            best_bet = max(eligible_bets, key=lambda x: x["bonusAmount"])
            
            # Günlük limit kontrolü
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
            
            today_bonuses = self.app.getPlayerBonuses(today_start, today_end, userData["userId"])
            kombine_bonus_today = 0
            
            for bonus in today_bonuses:
                if "kombine" in bonus.get("Note", "").lower():
                    kombine_bonus_today += 1
            
            if kombine_bonus_today >= 1:
                return self._returnMessage(False, "DAILY_KOMBINE_BONUS_LIMIT_EXCEEDED")
            
            return self._returnMessage(True, "KOMBINE_KUPON_SIGORTA_ELIGIBLE", 
                                     betData=best_bet, 
                                     bonusAmount=best_bet["bonusAmount"])
            
        except Exception as e:
            return self.ErrorFunc(e)

    def _checkSuperFanatikBonus(self, userData, minDailyDeposit:float=1000, maxBonusAmount:float=10000, requiredDays:int=7, bonusIds:list=None):
        """
        Super Fanatik Casino Bonusu kontrolü
        - Hafta boyunca her gün min 1000 TL yatırım
        - Haftalık ortalama hesaplama
        - Max 10.000 TL bonus
        - Pazartesi 00:01 - Pazar 22:00 arası
        - Salı 23:59'a kadar talep edilmeli
        """
        try:
            from datetime import datetime, timedelta
            
            # Haftalık tarih aralığını hesapla (Pazartesi-Pazar)
            now = datetime.now()
            
            # Bu haftanın pazartesini bul
            days_since_monday = now.weekday()  # 0=Monday, 6=Sunday
            monday_start = now - timedelta(days=days_since_monday)
            monday_start = monday_start.replace(hour=0, minute=1, second=0, microsecond=0)
            
            # Pazar 22:00'ı bul
            sunday_end = monday_start + timedelta(days=6)
            sunday_end = sunday_end.replace(hour=22, minute=0, second=0, microsecond=0)
            
            # Şu an Pazar 22:00'dan sonra mı kontrol et
            if now < sunday_end:
                return self._returnMessage(False, "SUPER_FANATIK_TIME_NOT_REACHED")
            
            # Salı 23:59'dan önce mi kontrol et
            tuesday_deadline = monday_start + timedelta(days=1)  # Salı
            tuesday_deadline = tuesday_deadline.replace(hour=23, minute=59, second=59)
            
            if now > tuesday_deadline:
                return self._returnMessage(False, "SUPER_FANATIK_TIME_EXPIRED")
            
            # Haftalık yatırımları çek
            deposits = self.app.getDeposits(monday_start, sunday_end, userData["userId"], [8])  # Onaylanmış yatırımlar
            
            if not deposits:
                return self._returnMessage(False, "NO_DEPOSITS_IN_WEEK")
            
            # Günlük yatırımları grupla
            daily_deposits = {}
            total_weekly_amount = 0
            
            for deposit in deposits:
                deposit_date = self.controller.parse_datetime(deposit["CreationTime"])
                day_key = deposit_date.strftime("%Y-%m-%d")
                
                if day_key not in daily_deposits:
                    daily_deposits[day_key] = []
                
                daily_deposits[day_key].append(deposit)
                total_weekly_amount += float(deposit["Amount"])
            
            # Her gün kontrol et
            missing_days = []
            for i in range(7):  # 7 gün
                check_date = monday_start + timedelta(days=i)
                day_key = check_date.strftime("%Y-%m-%d")
                
                if day_key not in daily_deposits:
                    missing_days.append(check_date.strftime("%A"))
                    continue
                
                # O gün minimum yatırım kontrolü
                daily_total = sum(float(dep["Amount"]) for dep in daily_deposits[day_key])
                if daily_total < minDailyDeposit:
                    return self._returnMessage(False, "DAILY_DEPOSIT_INSUFFICIENT", 
                                             missingDay=check_date.strftime("%A"),
                                             dailyAmount=daily_total,
                                             requiredAmount=minDailyDeposit)
            
            if missing_days:
                return self._returnMessage(False, "MISSING_DAILY_DEPOSITS", missingDays=missing_days)
            
            # Ortalama hesapla
            weekly_average = total_weekly_amount / 7
            bonus_amount = min(weekly_average, maxBonusAmount)
            
            # Günlük Super Fanatik bonus limiti kontrol et (sadece bonusIds verilmişse)
            if bonusIds:
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                fanatik_bonus_today = self.controller._CampaignController__returnBonusCount(
                    userData, today_start, today_end, bonusIds
                )
                
                if fanatik_bonus_today >= 1:
                    return self._returnMessage(False, "WEEKLY_SUPER_FANATIK_LIMIT_EXCEEDED")
            
            return self._returnMessage(True, "SUPER_FANATIK_BONUS_ELIGIBLE", 
                                     weeklyTotal=total_weekly_amount,
                                     weeklyAverage=weekly_average,
                                     bonusAmount=bonus_amount,
                                     depositDays=len(daily_deposits))
            
        except Exception as e:
            return self._returnMessage(False, "GENERAL_ERROR", errorMessage=str(e))

    def _checkWelcomeBonus(self, userData, minDeposit:float=100, sportBonusIds:list=None, casinoBonusIds:list=None):
        """
        Hoşgeldin bonusu kontrolü - Spor ve Casino ayrı bonuslar
        - Toplam 3 kez başvuru (spor+casino toplamı)
        - İlk başvuru: Sadece yatırım yeterli, %100 2000 TL'ye kadar
        - İkinci başvuru: Yatırımda çekim yapmamış olmalı, %100 2500 TL'ye kadar  
        - Üçüncü başvuru: Yatırımda çekim yapmamış olmalı, %100 3000 TL'ye kadar
        - Minimum 100 TL yatırım
        - Her üyenin toplam 3 hakkı var (7500 TL'ye kadar)
        """
        try:
            # Minimum yatırım kontrolü
            lastDeposit = self.__returnLastDeposit(userData, 30)
            if not lastDeposit:
                return self._returnMessage(False, "NO_DEPOSIT_FOUND")
            
            if lastDeposit["FinalAmount"] < minDeposit:
                return self._returnMessage(False, "DEPOSIT_UNDER", lastDepositAmount=lastDeposit["FinalAmount"], min=minDeposit)
            
            # Toplam hoşgeldin bonus kullanım sayısını hesapla
            total_welcome_bonuses = 0
            all_bonus_ids = []
            
            if sportBonusIds:
                all_bonus_ids.extend(sportBonusIds)
            if casinoBonusIds:
                all_bonus_ids.extend(casinoBonusIds)
            
            if all_bonus_ids:
                from_date = datetime(2016, 1, 1)
                to_date = datetime.now()
                
                bonuses = self.app.getPlayerBonuses(from_date, to_date, userData["userId"])
                welcome_bonuses = [b for b in bonuses if b["BonusCampaignId"] in all_bonus_ids and b["Status"] != 7]
                total_welcome_bonuses = len(welcome_bonuses)
            
            # Maksimum 3 kullanım kontrolü
            if total_welcome_bonuses >= 3:
                return self._returnMessage(False, "WELCOME_BONUS_COMPLETED", totalUses=total_welcome_bonuses)
            
            current_stage = total_welcome_bonuses + 1
            
            # Aşama limitleri
            stage_limits = {1: 2000, 2: 2500, 3: 3000}
            max_bonus = stage_limits[current_stage]
            
            # İkinci ve üçüncü başvuru için çekim kontrolü
            if current_stage > 1:
                # Son yatırımdan sonra çekim yapılmış mı kontrol et
                lastDepositDate = self.parse_datetime(lastDeposit["CreationTime"])
                current_time = datetime.now()
                
                # Son yatırımdan şimdiye kadar çekim var mı
                withdraws = self.app.getWithdrawList(lastDepositDate, current_time, userData["userId"])
                approved_withdraws = [w for w in withdraws if w.get("Status") == 8]
                
                if approved_withdraws:
                    return self._returnMessage(False, "WITHDRAW_AFTER_DEPOSIT_FOUND", 
                                             stage=current_stage,
                                             withdrawCount=len(approved_withdraws))
            
            # Aktif bonus kontrolü
            activeBonuses = self.__returnBonuses(userData, days=1)
            if activeBonuses and isinstance(activeBonuses, list) and len(activeBonuses) > 0:
                active_bonus_exists = any(b.get("Status") == 2 for b in activeBonuses)
                if active_bonus_exists:
                    return self._returnMessage(False, "ACTIVE_BONUS_EXISTS")
            
            # Beklemede bet kontrolü
            pendingBetCheck = self._checkPendingBet(userData, days=1, hasBet=False)
            if not pendingBetCheck.get("isValid"):
                return self._returnMessage(False, "PENDING_BET_EXISTS")
            
            # Son 24 saat çekim kontrolü
            withdrawCheck = self._checkWithdrawExist(userData, days=1, hasWithdraw=False, controlHourCount=24)
            if not withdrawCheck.get("isValid"):
                return self._returnMessage(False, "RECENT_WITHDRAW_EXISTS")
            
            # Bonus miktarını hesapla (%100)
            bonus_amount = min(lastDeposit["FinalAmount"], max_bonus)
            
            return self._returnMessage(True, "WELCOME_BONUS_ELIGIBLE", 
                                     stage=current_stage,
                                     depositAmount=lastDeposit["FinalAmount"],
                                     bonusAmount=bonus_amount,
                                     maxBonus=max_bonus,
                                     totalUses=total_welcome_bonuses,
                                     remainingUses=3-total_welcome_bonuses)
            
        except Exception as e:
            return self.ErrorFunc(e)

