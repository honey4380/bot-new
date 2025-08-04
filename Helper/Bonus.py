import json
from datetime import datetime, timedelta
from CampaignController import CampaignController
from Helper.BonusResponse import BonusResponse
import math

class BONUS:
    def __init__(self,userData:dict,controller:CampaignController,response:BonusResponse,bonus:dict):
        self.userData = userData
        self.bonusData = bonus
        self.controller = controller
        self.response = response
        
        self.name = bonus["data"]["InternalName"]
        self.id = bonus["data"]["Id"]
        self.productType = bonus["data"]["ProductType"]
        self.bonusType = bonus["data"]["BonusType"]
        self.endTime = bonus["data"]["EndTime"]
        self.startTime = bonus["data"]["StartTime"]
        self.noteJson = {
            "DepositDateRange": [],
            "DepositIds": [],
            "WithdrawIds": []
        }
        
        self.isFreeSpin = False
        if bonus["data"]["FreeSpinType"] == 1:
            self.isFreeSpin = True
        
        
        self.bonusDict = {
            "name": self.name,
            "id": self.id,
            "MaxBonusTaken": 0,
            "bonusTaken": 0,
            "currentBonusAmount": 0,
            "beforeBonusAmount": 0,
            "afterBonusAmount": 0,
            "isFreeSpin": self.isFreeSpin,
            "isLoaded": False,
            "bonusDepositIds": [],
            "bonusWithdrawIds": [],
        }
        

        
        
    def setBonusList(self):
        from_date, to_date = self.controller.dataRangeGenerator("day", 29,dateTimed=True)
        # ilk tarafı 2016 yılından başlatıyoruz çünkü tüm bonusları almak için
        from_date = datetime(2016, 1, 1)
        
        self.bonusList = self.controller.app.getPlayerBonuses(from_date, to_date, self.userData["userId"])
        print(f"Bonus List: {len(self.bonusList)}")
        self.bonusList = [x for x in self.bonusList if x["Status"] != 7]

        newBonusList = []
        for index, bonus in enumerate(self.bonusList):
            if bonus["Status"] == 4:
                if bonus["RemainBonusAmount"] != bonus["BonusAmount"]:
                    newBonusList.append(bonus)
            else:
                newBonusList.append(bonus)
                
        self.bonusList = newBonusList
        self.bonusList.sort(key=lambda x: x["CreationTime"], reverse=True)
        
        availableBonuses = self.bonusDict.get("availableBonuses", [])
        if availableBonuses is None:
            availableBonuses = []
            
        if availableBonuses == [] and self.id not in availableBonuses:
            availableBonuses.append(self.id)
            self.bonusDict["availableBonuses"] = availableBonuses
        
        self.currentBonusList = [x for x in self.bonusList if x["BonusCampaignId"] in availableBonuses]
        
        amountBonusses = self.bonusData.get("value", {}).get("amountBonusses", [])
        if not isinstance(amountBonusses, list):
            amountBonusses = []
        
        if self.id not in amountBonusses:
            amountBonusses.append(self.id)
        
        self.amountBonusList = [x for x in self.bonusList if x["BonusCampaignId"] in amountBonusses]
        
        
        self.currentBonusList = [x for x in self.bonusList if x["BonusCampaignId"] == self.id]
        self.currentBonusList.sort(key=lambda x: x["CreationTime"], reverse=True)
        self.userData["currentBonusList"] = self.currentBonusList
        self.userData["bonusList"] = self.bonusList
        
        return self.bonusList
    
    def setDict(self, key, value):
        self.bonusDict[key] = value
        return self.bonusDict
    
    def calculateBeforeAmount(self, resetDayCount:int=None,resetHour=0,startHour=0,endHour=24,activeDays:list=None,returnList=False):
        try:
            if resetDayCount:
                if type(resetDayCount) == int:
                    if resetDayCount < -1 or resetDayCount == 0:
                        return self.controller._returnError("RESET_COUNT_INVALID")
                    
                    today = datetime.fromisoformat(self.response.realTime).replace(hour=resetHour, minute=0, second=0, microsecond=0)
                    from_date = today
                    if resetDayCount > 1:
                        from_date = today - timedelta(days=resetDayCount)
                    
                    current_hour = datetime.fromisoformat(self.response.realTime).hour
                    if not (startHour <= current_hour < endHour):
                        return self.controller._returnMessage(False, "BONUS_HOUR_INVALID")
                    
                    if endHour == 24:
                        to_date = datetime.fromisoformat(self.response.realTime).replace(hour=23, minute=59, second=59, microsecond=0) - self.response.realTime_backendTimeDiff
                    else:
                        to_date = datetime.fromisoformat(self.response.realTime).replace(hour=endHour, minute=0, second=0, microsecond=0) - self.response.realTime_backendTimeDiff
                   
                    from_date = from_date - self.response.realTime_backendTimeDiff
                   
                    bonusList = [x for x in self.amountBonusList if 
                            self.controller.parse_datetime(x["CreationTime"]) >= from_date
                            and self.controller.parse_datetime(x["CreationTime"]) <= to_date]
                    
                if type(resetDayCount) == str and resetDayCount == "activeDays":
                    bonusList = []
                    if not activeDays or type(activeDays) != list or len(activeDays) != 7:
                        return self.controller._returnError("ACTIVE_DAYS_INVALID")

                    if resetHour == 24:
                        today = datetime.fromisoformat(self.response.realTime)
                        today = today.replace(hour=23, minute=59, second=59, microsecond=59)
                    else:
                        today = datetime.fromisoformat(self.response.realTime)
                        today = today.replace(hour=resetHour, minute=0, second=1, microsecond=0)
                    thisWeek = today.weekday()

                    # Check if current hour is between resetHour and endHour
                    current_hour = datetime.fromisoformat(self.response.realTime).hour
                    if not (startHour <= current_hour < endHour):
                        return self.controller._returnMessage(False, "BONUS_HOUR_INVALID")

                    #backend Today
                    today = datetime.fromisoformat(self.response.realTime)
                    for day_index, day in enumerate(activeDays):
                        if day == 1:
                            dayFromDate = today - timedelta(days=thisWeek - day_index)
                            
                            dayToDate = dayFromDate.replace(hour=23, minute=59, second=59, microsecond=0) - timedelta(hours=self.userData["realTimeZone"])
                            dayFromDate = dayFromDate.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=self.userData["realTimeZone"])
                            
                            filtered_bonuses = []
                            for x in self.amountBonusList:
                                bonus_time = self.controller.parse_datetime(x["CreationTime"])
                                if dayFromDate <= bonus_time <= dayToDate:
                                    filtered_bonuses.append(x)
                            
                            bonusList.extend(filtered_bonuses)
                            print(f"Day From: {dayFromDate} - Day To: {dayToDate} - Found bonuses: {len(filtered_bonuses)}")
                    print(f"Day From: {dayFromDate} - Day To: {dayToDate}")
            else:
                bonusList = self.amountBonusList
            
            if len(bonusList) == 0:
                self.setDict("beforeBonusAmount", 0)
                self.setDict("bonusTaken", 0)
                if returnList:
                    return []
                
                return 0
            
            
            if returnList:
                return bonusList
            ids = [x["BonusCampaignId"] for x in self.amountBonusList]
            totalAmount = sum([x["BonusAmount"] for x in bonusList if x["BonusCampaignId"] in ids])
            
            self.setDict("beforeBonusAmount", totalAmount)
            self.setDict("bonusTaken", len([x for x in bonusList if x["BonusCampaignId"] in ids]))
            
            return totalAmount
        except Exception as e:
            self.response.log(f"Error in calculateBeforeAmount: {str(e)}")
            return self.controller._returnError(str(e))
    
        
    def bonusAmountControl(self):
        try:
            amountData = self.bonusData["value"]
            calculationType = amountData.get("calculationType", None)
            amountRanges = amountData.get("amount", None)
            amountCalculation = amountData.get("amountCalculation", None)
            
            self.response.log(f"Bonus Amount Control - ID: {self.id}, Type: {calculationType}, Calculation: {amountCalculation}")
            
            if not isinstance(amountRanges, list):
                return self.controller._returnError("BONUS_AMOUNT_FORMAT_INVALID")
                
            beforeAmount = 0
            usageData = self.bonusData["usage"]
            maxAmount = amountData.get("max", None)
            
            # Handle weekly max amounts
            if maxAmount and isinstance(maxAmount, list) and len(maxAmount) == 7:
                day_index = datetime.fromisoformat(self.response.realTime).weekday()
                maxAmount = maxAmount[day_index]
            
            # Handle progressive max amounts based on usage count
            progressiveMax = amountData.get("progressiveMax", None)
            if progressiveMax and isinstance(progressiveMax, list):
                # Get current usage count for this bonus type
                currentUsageCount = len([x for x in self.currentBonusList if x["BonusCampaignId"] == self.id])
                
                # If it's the first usage, use index 0; second usage, use index 1, etc.
                progressiveIndex = min(currentUsageCount, len(progressiveMax) - 1)
                maxAmount = progressiveMax[progressiveIndex]
                
                self.response.log(f"Progressive max: Usage count {currentUsageCount}, using max amount {maxAmount}")

            # Calculate before amount based on usage settings
            if usageData.get("resetDayCount", None):
                resetDayCount = usageData["resetDayCount"]
                
                if type(resetDayCount) != int:
                    if resetDayCount != "activeDays":
                        return self.controller._returnError("RESET_COUNT_INVALID")
                    
                    activeDays = usageData.get("activeDays", None)
                    if not activeDays or type(activeDays) != list or len(activeDays) != 7:
                        return self.controller._returnError("ACTIVE_DAYS_INVALID")
                    
                    resetHour = usageData.get("resetHour", 0)
                    startHour = usageData.get("startHour", 0)
                    endHour = usageData.get("endHour", 24)
                    
                    beforeAmount = self.calculateBeforeAmount(resetDayCount, resetHour,startHour,endHour,activeDays) 
                    if type(beforeAmount) == dict:
                        return beforeAmount
                else:
                    
                    resetHour = usageData.get("resetHour", 0)
                    startHour = usageData.get("startHour", 0)
                    endHour = usageData.get("endHour", 24)
                    beforeAmount = self.calculateBeforeAmount(resetDayCount, resetHour,startHour,endHour)
                    if type(beforeAmount) == dict:
                        return beforeAmount
            else:
                beforeAmount = self.calculateBeforeAmount()
                
            if type(beforeAmount) == dict:
                return beforeAmount
                
            if maxAmount and beforeAmount >= maxAmount:
                return self.controller._returnMessage(False, "BONUS_MAX_AMOUNT_EXCEEDED")
        
            # Calculate bonus amount based on calculation type
            if calculationType == "fixed":
                
                amountCalculation = amountData.get("amountCalculation", None)
                
                # Fixed amounts can be either direct value or range-based
                if amountData.get("amountCalculation"):
                    # Range based fixed amounts (like freespin tiers based on deposit)
                    calculationDateTo = amountData.get("calculationDateTo", None)
                    calculationDateFrom = amountData.get("calculationDateFrom", None)
                    
                    calculationFirstDepositAfterHourCount = amountData.get("calculationFirstDepositAfterHour", 24)
                    calculationFirstDepositAfterHourRange = amountData.get("calculationFirstDepositAfterHourRange", [0, 24])
                    
                    if calculationDateTo is not None:
                        calculationDateTo = self.controller.parse_datetime(calculationDateTo) - self.response.realTime_backendTimeDiff
                        calculationDateTo = calculationDateTo.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    else:
                        calculationDateTo = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    if calculationDateFrom is not None:
                        calculationDateFrom = self.controller.parse_datetime(calculationDateFrom) - self.response.realTime_backendTimeDiff
                        calculationDateFrom = calculationDateFrom.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    else:
                        calculationDateFrom = datetime.now() - timedelta(days=1)
                        calculationDateFrom = calculationDateFrom.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    
                    
                    if not calculationFirstDepositAfterHourCount:
                        calculationFirstDepositAfterHourCount = 24
                        
                    if not calculationFirstDepositAfterHourRange:
                        calculationFirstDepositAfterHourRange = [0, 24]
                        
                    if not calculationFirstDepositAfterHourCount:
                        return self.controller._returnError("Bonus calculation hour invalid")
                    
                    
                    if not calculationFirstDepositAfterHourRange or type(calculationFirstDepositAfterHourRange) != list or len(calculationFirstDepositAfterHourRange) != 2:
                        return self.controller._returnError("Bonus calculation hour range invalid")
                    
                    
                
                    # calculationFirstDepositAfterHourRange real time ama bize gereken backend time bu yüzden calculationFirstDepositAfterHourRange'den realtime backendtime farkını çıkarıyoruz 
                    calcDiff = self.response.realTime_backendTimeDiff.total_seconds() / 3600
                    calculationFirstDepositAfterHourRange[0] -= calcDiff
                    calculationFirstDepositAfterHourRange[1] -= calcDiff
                    if calculationFirstDepositAfterHourRange[0] < 0:
                        calculationFirstDepositAfterHourRange[0] = calculationFirstDepositAfterHourRange[0] + 24
                    if calculationFirstDepositAfterHourRange[1] < 0:
                        calculationFirstDepositAfterHourRange[1] = calculationFirstDepositAfterHourRange[1] + 24
                    if calculationFirstDepositAfterHourRange[0] > 24:
                        calculationFirstDepositAfterHourRange[0] = calculationFirstDepositAfterHourRange[0] - 24
                    if calculationFirstDepositAfterHourRange[1] > 24:
                        calculationFirstDepositAfterHourRange[1] = calculationFirstDepositAfterHourRange[1] - 24
                        
                    
                    minDiff = amountData.get("minDiff", None)
                    maxDiff = amountData.get("maxDiff", None)
                    
                    if not calculationDateFrom or type(calculationDateFrom) != str:
                        return self.controller._returnError("BONUS_CALCULATION_DATES_INVALID")
                    
                    if not calculationDateTo  or type(calculationDateTo) != str :
                        return self.controller._returnError("BONUS_CALCULATION_DATES_INVALID")
                    
                    isProfit = False if amountData.get("amountCalculation") == "loss" else True
                    isDepositFilter = amountData.get("isDepositFilter", True)
                    FilterAllowedBonusses = amountData.get("FilterAllowedBonusses", None)
                    FilterReverse = amountData.get("FilterReverse", False)
                    isForceLastDeposit = amountData.get("isForceLastDeposit", False)
                    
                    baseAmount = 0
                    if amountData.get("amountCalculation") == "lastDeposit":
                        
                        lastDeposit = self.controller._CampaignController__returnLastDeposit(self.userData, 29)
                        if not lastDeposit:
                            return self.controller._returnMessage(False, "BONUS_AMOUNT_CALCULATION_ERROR")
                        
                        baseAmount = lastDeposit["FinalAmount"]
                        self.response.log(f"Using lastDeposit calculation: {baseAmount} TL")
                        self.noteJson["DepositIds"] = [lastDeposit["TransactionId"]]
                        self.setDict("bonusDepositIds", [lastDeposit["TransactionId"]])
                        
                        # Handle FilterAllowedBonusses for lastDeposit
                        if FilterAllowedBonusses and isinstance(FilterAllowedBonusses, list):
                            # Check if user has any of the allowed bonuses
                            userBonusList = self.setBonusList()
                            userBonusIds = [x["BonusCampaignId"] for x in userBonusList if x["Status"] in [1,2,6]]
                            
                            hasAllowedBonus = any(bonusId in FilterAllowedBonusses for bonusId in userBonusIds)
                            
                            if FilterReverse:
                                # If FilterReverse is true, user should NOT have allowed bonuses
                                if hasAllowedBonus:
                                    return self.controller._returnMessage(False, "BONUS_FILTER_RESTRICTED")
                            else:
                                # If FilterReverse is false, user should have allowed bonuses
                                if not hasAllowedBonus:
                                    return self.controller._returnMessage(False, "BONUS_FILTER_RESTRICTED")
                    
                    
                    elif amountCalculation == "lastDepositWithLoss":
                        self.response.log(f"Using lastDepositWithLoss calculation")
                        isProfit = False
                        profitDiff, profitDepositDict = self.controller._CampaignController__returnProfitCount(self.response, self.userData,calculationDateFrom,calculationDateTo,calculationFirstDepositAfterHourCount,calculationFirstDepositAfterHourRange,isDepositFilter,FilterAllowedBonusses,  minDiff, maxDiff, isProfit,FilterReverse)
                        if type(profitDiff) == dict:
                            return profitDiff
                        
                        
                        lastDeposit = self.controller._CampaignController__returnLastDeposit(self.userData, 29)
                        if not lastDeposit:
                            return self.controller._returnMessage(False, "BONUS_AMOUNT_CALCULATION_ERROR")
                        
                        controlledDepositIds = profitDepositDict["DepositIds"]
                        controlledDepositRange = profitDepositDict["DepositDateRange"]
                        self.response.log(f"Last Deposit: ID: {lastDeposit['TransactionId']} - Amount: {lastDeposit['FinalAmount']}")
                        if profitDiff > lastDeposit["FinalAmount"]:
                            
                            baseAmount = lastDeposit["FinalAmount"]
                        else:
                            baseAmount = profitDiff
                        controlledAllDepositIds = profitDepositDict["AllDepositIds"]
                        controlledAllDepositIds = list(set(controlledDepositIds + controlledAllDepositIds))
                        
                        controlledWithdrawIds = profitDepositDict["WithdrawIds"]
                        controlledWithdrawRange = profitDepositDict["WithdrawDateRange"]  
                        controlledAllWithdrawIds = profitDepositDict["AllWithdrawIds"]
                        
                        self.noteJson["DepositIds"] = controlledDepositIds
                        self.noteJson["DepositDateRange"] = controlledDepositRange
                        self.setDict("bonusDepositIds", controlledAllDepositIds)
                        
                        self.noteJson["WithdrawIds"] = controlledWithdrawIds
                        self.noteJson["WithdrawDateRange"] = controlledWithdrawRange
                        self.setDict("bonusWithdrawIds", controlledAllWithdrawIds)
                        
                        
                        if  baseAmount < 0:
                            return self.controller._returnMessage(False, "BONUS_USER_PROFIT")
                        
                    elif amountCalculation == "yesterdayTotalDeposit":
                        self.response.log(f"Using yesterdayTotalDeposit calculation")
                        # Get yesterday's total deposit amount
                        yesterday_control = self.controller._checkYesterdayTotalDeposit(self.userData, min=0)
                        if not yesterday_control["isValid"]:
                            return yesterday_control
                            
                        # Get yesterday's deposits for details
                        real_time_str = self.userData["realTime"]
                        real_today = self.controller.parse_datetime(real_time_str.replace('Z', ''))
                        real_yesterday_start = real_today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
                        real_yesterday_end = real_today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
                        
                        yesterday_start = real_yesterday_start - timedelta(hours=self.userData["realTimeZone"])
                        yesterday_end = real_yesterday_end - timedelta(hours=self.userData["realTimeZone"])
                        
                        yesterdayDeposits = self.controller.app.getUserDeposits(
                            self.userData["userId"], 
                            yesterday_start, 
                            yesterday_end
                        )["Deposits"]
                        
                        yesterdayDeposits = [d for d in yesterdayDeposits if d.get("Status") == 8]
                        
                        baseAmount = sum(d["FinalAmount"] for d in yesterdayDeposits)
                        
                        # Log deposit details for verification
                        self.response.log(f"Yesterday's Total Deposits: {baseAmount} TL from {len(yesterdayDeposits)} deposits")
                        for idx, deposit in enumerate(yesterdayDeposits, 1):
                            self.response.log(f"Deposit {idx}: {deposit['FinalAmount']} TL at {deposit['CreationTime']} (ID: {deposit['TransactionId']})")
                        
                        self.noteJson["DepositIds"] = [d["TransactionId"] for d in yesterdayDeposits]
                        self.setDict("bonusDepositIds", [d["TransactionId"] for d in yesterdayDeposits])
                        self.setDict("yesterdayTotalAmount", baseAmount)
                        self.setDict("yesterdayDepositCount", len(yesterdayDeposits))
                        
                        
                        
                    
                    elif amountData.get("amountCalculation") in ["profit", "loss"]:
                        
                        profitDiff,profitDepositDict = self.controller._CampaignController__returnProfitCount(self.response, self.userData,calculationDateFrom,calculationDateTo,calculationFirstDepositAfterHourCount,calculationFirstDepositAfterHourRange,isDepositFilter,FilterAllowedBonusses,  minDiff, maxDiff, isProfit,FilterReverse)
                        if type(profitDiff) == dict:
                            return profitDiff    
                        
                        controlledDepositIds = profitDepositDict["DepositIds"]
                        controlledDepositRange = profitDepositDict["DepositDateRange"]
                        controlledAllDepositIds = profitDepositDict["AllDepositIds"]
                        
                        controlledWithdrawIds = profitDepositDict["WithdrawIds"]
                        controlledWithdrawRange = profitDepositDict["WithdrawDateRange"]
                        controlledAllWithdrawIds = profitDepositDict["AllWithdrawIds"]
                        
                        
                        if type(profitDiff) == dict:
                            return profitDiff
                        
                        if amountCalculation == "profit":
                            if profitDiff <= 0:
                                return self.controller._returnMessage(False, "BONUS_USER_LOSS")
                            baseAmount = profitDiff
                            self.noteJson["DepositIds"] = controlledDepositIds
                            self.noteJson["DepositDateRange"] = controlledDepositRange
                            self.setDict("bonusDepositIds", controlledAllDepositIds)
                            
                            self.noteJson["WithdrawIds"] = controlledWithdrawIds
                            self.noteJson["WithdrawDateRange"] = controlledWithdrawRange
                            self.setDict("bonusWithdrawIds", controlledAllWithdrawIds)
                            
                        else:  # loss
                            if profitDiff <= 0:
                                return self.controller._returnMessage(False, "BONUS_USER_PROFIT")
                            baseAmount = profitDiff
                            self.noteJson["DepositIds"] = controlledDepositIds
                            self.noteJson["DepositDateRange"] = controlledDepositRange
                            self.setDict("bonusDepositIds", controlledAllDepositIds)
                            
                            self.noteJson["WithdrawIds"] = controlledWithdrawIds
                            self.noteJson["WithdrawDateRange"] = controlledWithdrawRange
                            self.setDict("bonusWithdrawIds", controlledAllWithdrawIds)
                            
                    # Find applicable range
                    applicable_range = None
                    for range_data in amountRanges:
                        min_amount = range_data.get("min", 0)
                        max_amount = range_data.get("max", float('inf'))
                        
                        if min_amount is None:
                            min_amount = 0
                        if max_amount is None:
                            max_amount = float('inf')
                        
                        # Check if baseAmount falls within this range
                        if baseAmount >= min_amount and baseAmount <= max_amount:
                            applicable_range = range_data
                            self.response.log(f"Found matching range: {min_amount}-{max_amount} for amount {baseAmount}")
                            break
                            
                    if not applicable_range:
                        self.response.log(f"No matching range found for amount {baseAmount}")
                        return self.controller._returnMessage(False, "BONUS_AMOUNT_RANGE_ERROR")
                        
                    self.bonusAmount = applicable_range["percentage"]
                else:
                    # Direct fixed amount (like welcome bonus with fixed value)
                    if len(amountRanges) != 1:
                        return self.controller._returnError("BONUS_AMOUNT_FORMAT_INVALID")
                    self.bonusAmount = amountRanges[0]["percentage"]
                    
                if maxAmount and beforeAmount + self.bonusAmount > maxAmount:
                    self.bonusAmount = maxAmount - beforeAmount
                    
                if self.bonusAmount <= 0:
                    return self.controller._returnMessage(False, "BONUS_MAX_AMOUNT_EXCEEDED")
                
                self.bonusAmount = math.ceil(self.bonusAmount)
                
                self.setDict("currentBonusAmount", self.bonusAmount)
                self.response.log(f"Bonus Amount: {self.bonusAmount}")
                return self.controller._returnMessage(True, "BONUS_AMOUNT_VALID", amount=self.bonusAmount)
            
            elif calculationType == "percentage":
                amountCalculation = amountData.get("amountCalculation", None)
                if not amountCalculation:
                    return self.controller._returnError("BONUS_CALCULATION_TYPE_INVALID")
                
                
                calculationDateTo = amountData.get("calculationDateTo", None)
                calculationDateFrom = amountData.get("calculationDateFrom", None)
                
                calculationFirstDepositAfterHourCount = amountData.get("calculationFirstDepositAfterHour", 24)
                calculationFirstDepositAfterHourRange = amountData.get("calculationFirstDepositAfterHourRange", [0, 24])
                
                if calculationDateTo is not None:
                    calculationDateTo = self.controller.parse_datetime(calculationDateTo) - self.response.realTime_backendTimeDiff
                    calculationDateTo = calculationDateTo.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                else:
                    calculationDateTo = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000Z")
                
                if calculationDateFrom is not None:
                    calculationDateFrom = self.controller.parse_datetime(calculationDateFrom) - self.response.realTime_backendTimeDiff
                    calculationDateFrom = calculationDateFrom.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                else:
                    calculationDateFrom = datetime.now() - timedelta(days=1)
                    calculationDateFrom = calculationDateFrom.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                
                if not calculationFirstDepositAfterHourCount:
                    calculationFirstDepositAfterHourCount = 24
                    
                if not calculationFirstDepositAfterHourRange:
                    calculationFirstDepositAfterHourRange = [0, 24]
                    
                if not calculationFirstDepositAfterHourCount:
                    return self.controller._returnError("Bonus calculation hour invalid")
                
                
                if not calculationFirstDepositAfterHourRange or type(calculationFirstDepositAfterHourRange) != list or len(calculationFirstDepositAfterHourRange) != 2:
                    return self.controller._returnError("Bonus calculation hour range invalid")
                
                calcDiff = self.response.realTime_backendTimeDiff.total_seconds() / 3600
                calculationFirstDepositAfterHourRange[0] -= calcDiff
                calculationFirstDepositAfterHourRange[1] -= calcDiff
                if calculationFirstDepositAfterHourRange[0] < 0:
                    calculationFirstDepositAfterHourRange[0] = calculationFirstDepositAfterHourRange[0] + 24
                if calculationFirstDepositAfterHourRange[1] < 0:
                    calculationFirstDepositAfterHourRange[1] = calculationFirstDepositAfterHourRange[1] + 24
                if calculationFirstDepositAfterHourRange[0] > 24:
                    calculationFirstDepositAfterHourRange[0] = calculationFirstDepositAfterHourRange[0] - 24
                if calculationFirstDepositAfterHourRange[1] > 24:
                    calculationFirstDepositAfterHourRange[1] = calculationFirstDepositAfterHourRange[1] - 24
            
                minDiff = amountData.get("minDiff", None)
                maxDiff = amountData.get("maxDiff", None)
                
                if not calculationDateFrom or type(calculationDateFrom) != str:
                    return self.controller._returnError("BONUS_CALCULATION_DATES_INVALID")
                
                if not calculationDateTo  or type(calculationDateTo) != str :
                    return self.controller._returnError("BONUS_CALCULATION_DATES_INVALID")
                
                isProfit = False if amountData.get("amountCalculation") == "loss" else True
                isDepositFilter = amountData.get("isDepositFilter", True)
                FilterAllowedBonusses = amountData.get("FilterAllowedBonusses", None)
                FilterReverse = amountData.get("FilterReverse", False)
                isForceLastDeposit = amountData.get("isForceLastDeposit", False)
                
                baseAmount = 0
                
                if amountCalculation == "lastDeposit":
                    self.response.log(f"Using lastDeposit calculation for percentage")
                    lastDeposit = self.controller._CampaignController__returnLastDeposit(self.userData, 29)
                    if not lastDeposit:
                        return self.controller._returnMessage(False, "BONUS_AMOUNT_CALCULATION_ERROR")
                    baseAmount = lastDeposit["FinalAmount"]
                    self.response.log(f"LastDeposit amount: {baseAmount} TL")
                    
                    self.noteJson["DepositIds"] = [lastDeposit["TransactionId"]]
                    self.setDict("bonusDepositIds", [lastDeposit["TransactionId"]])
                
                elif amountCalculation == "lastDepositWithLoss":
                    self.response.log(f"Using lastDepositWithLoss calculation for percentage")
                    isProfit = False
                    profitDiff, profitDepositDict = self.controller._CampaignController__returnProfitCount(self.response, self.userData,calculationDateFrom,calculationDateTo,calculationFirstDepositAfterHourCount,calculationFirstDepositAfterHourRange,isDepositFilter,FilterAllowedBonusses,  minDiff, maxDiff, isProfit,FilterReverse)
                    if type(profitDiff) == dict:
                        return profitDiff
                    
                    
                    lastDeposit = self.controller._CampaignController__returnLastDeposit(self.userData, 29)
                    if not lastDeposit:
                        return self.controller._returnMessage(False, "BONUS_AMOUNT_CALCULATION_ERROR")
                    
                    controlledDepositIds = profitDepositDict["DepositIds"]
                    controlledDepositRange = profitDepositDict["DepositDateRange"]
                    self.response.log(f"Last Deposit: ID: {lastDeposit['TransactionId']} - Amount: {lastDeposit['FinalAmount']}")
                    if profitDiff > lastDeposit["FinalAmount"]:
                        
                        baseAmount = lastDeposit["FinalAmount"]
                    else:
                        baseAmount = profitDiff
                    controlledAllDepositIds = profitDepositDict["AllDepositIds"]
                    controlledAllDepositIds = list(set(controlledDepositIds + controlledAllDepositIds))
                    
                    self.noteJson["DepositIds"] = controlledDepositIds
                    self.noteJson["DepositDateRange"] = controlledDepositRange
                    self.setDict("bonusDepositIds", controlledAllDepositIds)
                    
                    controlledWithdrawIds = profitDepositDict["WithdrawIds"]
                    controlledWithdrawRange = profitDepositDict["WithdrawDateRange"]
                    controlledAllWithdrawIds = profitDepositDict["AllWithdrawIds"]
                    self.noteJson["WithdrawIds"] = controlledWithdrawIds
                    self.noteJson["WithdrawDateRange"] = controlledWithdrawRange
                    self.setDict("bonusWithdrawIds", controlledAllWithdrawIds)
                        
                    
                
                elif amountCalculation in ["profit", "loss"]:
                    self.response.log(f"Using {amountCalculation} calculation for percentage")
                    profitDiff,profitDepositDict = self.controller._CampaignController__returnProfitCount(self.response, self.userData,calculationDateFrom,calculationDateTo,calculationFirstDepositAfterHourCount,calculationFirstDepositAfterHourRange,isDepositFilter,FilterAllowedBonusses,  minDiff, maxDiff, isProfit,FilterReverse)
                    if type(profitDiff) == dict:
                        return profitDiff
                    
                    controlledDepositIds = profitDepositDict["DepositIds"]
                    controlledDepositRange = profitDepositDict["DepositDateRange"]
                    controlledAllDepositIds = profitDepositDict["AllDepositIds"]
                    
                    controlledWithdrawIds = profitDepositDict["WithdrawIds"]
                    controlledWithdrawRange = profitDepositDict["WithdrawDateRange"]
                    controlledAllWithdrawIds = profitDepositDict["AllWithdrawIds"]
                    
                    
                    if amountCalculation == "profit":
                        if profitDiff <= 0:
                            return self.controller._returnMessage(False, "BONUS_USER_LOSS")
                        baseAmount = profitDiff
                        self.noteJson["DepositIds"] = controlledDepositIds
                        self.noteJson["DepositDateRange"] = controlledDepositRange
                        self.setDict("bonusDepositIds", controlledAllDepositIds)
                        
                        self.noteJson["WithdrawIds"] = controlledWithdrawIds
                        self.noteJson["WithdrawDateRange"] = controlledWithdrawRange
                        self.setDict("bonusWithdrawIds", controlledAllWithdrawIds)
                        
                    else:  # loss
                        if profitDiff <= 0:
                            return self.controller._returnMessage(False, "BONUS_USER_PROFIT")
                        baseAmount = profitDiff
                        self.noteJson["DepositIds"] = controlledDepositIds
                        self.noteJson["DepositDateRange"] = controlledDepositRange
                        self.setDict("bonusDepositIds", controlledAllDepositIds)
                        
                        self.noteJson["WithdrawIds"] = controlledWithdrawIds
                        self.noteJson["WithdrawDateRange"] = controlledWithdrawRange
                        self.setDict("bonusWithdrawIds", controlledAllWithdrawIds)
                        
                elif amountCalculation == "yesterdayTotalDeposit":
                    self.response.log(f"Using yesterdayTotalDeposit calculation for percentage")
                    # Get yesterday's total deposit amount  
                    yesterday_control = self.controller._checkYesterdayTotalDeposit(self.userData, min=0)
                    if not yesterday_control["isValid"]:
                        return yesterday_control
                        
                    # Get yesterday's deposits for details
                    real_time_str = self.userData["realTime"]
                    real_today = self.controller.parse_datetime(real_time_str.replace('Z', ''))
                    real_yesterday_start = real_today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
                    real_yesterday_end = real_today.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
                    
                    yesterday_start = real_yesterday_start - timedelta(hours=self.userData["realTimeZone"])
                    yesterday_end = real_yesterday_end - timedelta(hours=self.userData["realTimeZone"])
                    
                    yesterdayDeposits = self.controller.app.getUserDeposits(
                        self.userData["userId"], 
                        yesterday_start, 
                        yesterday_end
                    )["Deposits"]
                    
                    yesterdayDeposits = [d for d in yesterdayDeposits if d.get("Status") == 8]
                    
                    baseAmount = sum(d["FinalAmount"] for d in yesterdayDeposits)
                    
                    # Log deposit details for verification
                    self.response.log(f"Yesterday's Total Deposits: {baseAmount} TL from {len(yesterdayDeposits)} deposits")
                    for idx, deposit in enumerate(yesterdayDeposits, 1):
                        self.response.log(f"Deposit {idx}: {deposit['FinalAmount']} TL at {deposit['CreationTime']} (ID: {deposit['TransactionId']})")
                    
                    self.noteJson["DepositIds"] = [d["TransactionId"] for d in yesterdayDeposits]
                    self.setDict("bonusDepositIds", [d["TransactionId"] for d in yesterdayDeposits])
                    self.setDict("yesterdayTotalAmount", baseAmount)
                    self.setDict("yesterdayDepositCount", len(yesterdayDeposits))
                
                elif amountCalculation == "HaftalikReloaded":
                    self.response.log(f"Using HaftalikReloaded calculation for percentage")
                    # Weekly reload bonus - Previous week Monday 00:01 to Sunday 23:59
                    real_time_str = self.userData["realTime"]
                    real_now = self.controller.parse_datetime(real_time_str.replace('Z', ''))
                    
                    # Find previous week's Monday 00:01 to Sunday 23:59
                    current_weekday = real_now.weekday()  # 0=Monday, 6=Sunday
                    
                    # Calculate previous week's Monday
                    days_to_last_monday = current_weekday + 7  # Go back to previous Monday
                    prev_week_monday = real_now.replace(hour=0, minute=1, second=0, microsecond=0) - timedelta(days=days_to_last_monday)
                    
                    # Calculate previous week's Sunday
                    prev_week_sunday = prev_week_monday + timedelta(days=6)
                    prev_week_sunday = prev_week_sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
                    
                    # Convert to backend time
                    backend_week_start = prev_week_monday - timedelta(hours=self.userData["realTimeZone"])
                    backend_week_end = prev_week_sunday - timedelta(hours=self.userData["realTimeZone"])
                    
                    # Convert to string format for profit calculation
                    calculationDateFrom = backend_week_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    calculationDateTo = backend_week_end.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    
                    self.response.log(f"Previous weekly period: {prev_week_monday} to {prev_week_sunday} (user time)")
                    self.response.log(f"Backend period: {calculationDateFrom} to {calculationDateTo}")
                    
                    # Calculate previous week's loss (deposits - withdrawals)
                    isProfit = False  # We want loss calculation
                    profitDiff, profitDepositDict = self.controller._CampaignController__returnProfitCount(
                        self.response, 
                        self.userData,
                        calculationDateFrom,
                        calculationDateTo,
                        calculationFirstDepositAfterHourCount,
                        calculationFirstDepositAfterHourRange,
                        isDepositFilter,
                        FilterAllowedBonusses,  
                        minDiff, 
                        maxDiff, 
                        isProfit,
                        FilterReverse
                    )
                    
                    if type(profitDiff) == dict:
                        # Check if this is the generic "no deposit" error and make it more specific for weekly bonus
                        if profitDiff.get("code") == 6006:  # NO_DEPOSIT_IN_RANGE
                            week_start_str = prev_week_monday.strftime("%d.%m.%Y")
                            week_end_str = prev_week_sunday.strftime("%d.%m.%Y")
                            return self.controller._returnMessage(False, "WEEKLY_RELOAD_NO_DEPOSIT", 
                                                               weekStart=week_start_str, 
                                                               weekEnd=week_end_str)
                        return profitDiff
                    
                    if profitDiff <= 0:
                        return self.controller._returnMessage(False, "BONUS_USER_PROFIT")
                    
                    baseAmount = profitDiff
                    
                    controlledDepositIds = profitDepositDict["DepositIds"]
                    controlledDepositRange = profitDepositDict["DepositDateRange"]
                    controlledAllDepositIds = profitDepositDict["AllDepositIds"]
                    
                    controlledWithdrawIds = profitDepositDict["WithdrawIds"]
                    controlledWithdrawRange = profitDepositDict["WithdrawDateRange"]
                    controlledAllWithdrawIds = profitDepositDict["AllWithdrawIds"]
                    
                    self.noteJson["DepositIds"] = controlledDepositIds
                    self.noteJson["DepositDateRange"] = controlledDepositRange
                    self.setDict("bonusDepositIds", controlledAllDepositIds)
                    
                    self.noteJson["WithdrawIds"] = controlledWithdrawIds
                    self.noteJson["WithdrawDateRange"] = controlledWithdrawRange
                    self.setDict("bonusWithdrawIds", controlledAllWithdrawIds)
                    
                    self.response.log(f"Previous week's loss amount: {baseAmount} TL")
                
                # Find applicable percentage based on amount ranges
                applicable_range = None
                for range_data in amountRanges:
                    min_amount = range_data.get("min", 0)
                    max_amount = range_data.get("max", float('inf'))
                    
                    if min_amount is None:
                        min_amount = 0
                    if max_amount is None:
                        max_amount = float('inf')
                        
                    # Check if baseAmount falls within this range
                    if baseAmount >= min_amount and baseAmount <= max_amount:
                        applicable_range = range_data
                        self.response.log(f"Found matching range: {min_amount}-{max_amount} for amount {baseAmount}")
                        break
                
                    
                self.response.log(f"Applicable Range: {applicable_range}")
                if not applicable_range:
                    self.response.log(f"No matching range found for amount {baseAmount}")
                    return self.controller._returnMessage(False, "BONUS_AMOUNT_RANGE_ERROR")
                
                self.response.log(f"Min: {min_amount} - Max: {max_amount} - Percentage/FixedAmount: {applicable_range['percentage']}")
                self.response.log(f"Base Amount: {baseAmount}")
                        
                    
                self.bonusAmount = baseAmount * (applicable_range["percentage"] / 100)
                
                if maxAmount and self.bonusAmount > maxAmount:
                    self.bonusAmount = maxAmount
                    
                if maxAmount and beforeAmount + self.bonusAmount > maxAmount:
                    self.bonusAmount = maxAmount - beforeAmount
                    
                if self.bonusAmount <= 0:
                    return self.controller._returnMessage(False, "BONUS_MAX_AMOUNT_EXCEEDED")
                
                self.bonusAmount = math.ceil(self.bonusAmount)
                self.setDict("currentBonusAmount", self.bonusAmount)
                self.response.log(f"Total Final Bonus Amount: {self.bonusAmount}")
                return self.controller._returnMessage(True, "BONUS_AMOUNT_VALID")
                
            else:
                return self.controller._returnError("BONUS_CALCULATION_TYPE_INVALID")
        except Exception as e:
            self.response.log(f"Error in bonusAmountControl: {str(e)}")
            return self.controller._returnError(str(e))
        
        
    def bonusUsageControl(self):
        try:
            usageData = self.bonusData["usage"]
            
            # activeDays control
            if usageData.get("activeDays", None):
                activeDays = usageData["activeDays"]
                
                if not isinstance(activeDays, list):
                    return self.controller._returnError("ACTIVE_DAYS_FORMAT_INVALID")
                if len(activeDays) > 7 or len(activeDays) < 7:
                    return self.controller._returnError("ACTIVE_DAYS_LENGTH_INVALID") 
                if not all(isinstance(x, int) for x in activeDays):
                    return self.controller._returnError("ACTIVE_DAYS_TYPE_INVALID")
                
                realToday = datetime.fromisoformat(self.response.realTime)
                day_index = realToday.weekday()
                
                if activeDays[day_index] == 0:
                    return self.controller._returnMessage(False, "BONUS_INACTIVE")

            playerBonusList = self.setBonusList()
            if len(playerBonusList) == 0:
                return self.controller._returnMessage(True, "BONUS_NO_ACTIVE")
            
            playerBonusListActive = [x for x in playerBonusList if x["Status"] in [1,2,6]]
            if len(playerBonusListActive) > 0:
                return self.controller._returnMessage(False, "ACTIVE_BONUS_EXISTS")
            
            
            availableBonuses = usageData.get("availableBonuses", [])
            if availableBonuses is None:
                availableBonuses = []
            
            # eğer şuanki bonus bu listede yoksa ekle
            if self.id not in availableBonuses:
                availableBonuses.append(self.id)
            self.setDict("availableBonuses", availableBonuses)

            
            
            currentBonusList = [x for x in playerBonusList if x["BonusCampaignId"] in availableBonuses]
            currentBonusListActive = [x for x in playerBonusListActive if x["BonusCampaignId"] in availableBonuses]
            
            self.response.log(f"Player Bonus List: {len(playerBonusList)}")
            self.response.log(f"Player Bonus List Active: {len(playerBonusListActive)}")
            self.response.log(f"Current Bonus List: {len(currentBonusList)}")
            self.response.log(f"Current Bonus List Active: {len(currentBonusListActive)}")

            
            
            
            maxUsageCount = usageData.get("maxUses", None)
            self.setDict("MaxBonusTaken", maxUsageCount)
            
            # -1 ise sınırsız kullanım & büyük ise sınırsız kullanım
            if maxUsageCount > 0:
                # eğer reset time yoksa
                resetDayCount = usageData.get("resetDayCount", None)
                if not resetDayCount:
                    if len(currentBonusList) >= maxUsageCount:
                        return self.controller._returnMessage(False, "BONUS_MAX_USAGE")
                else:
                    resetDayCount = usageData["resetDayCount"]
                    resetHour = usageData.get("resetHour", 0)
                    startHour = usageData.get("startHour", 0)
                    endHour = usageData.get("endHour", 24)
                    activeDays = usageData.get("activeDays", None)
                    
                    resetList = self.calculateBeforeAmount(resetDayCount,resetHour,startHour,endHour,activeDays,returnList=True)
                    if type(resetList) == dict:
                        return resetList
                    
                    if len(resetList) >= maxUsageCount:
                        return self.controller._returnMessage(False, "BONUS_MAX_USAGE")
                    
                    else:
                        self.setDict("bonusTaken", len(resetList))
                        return self.controller._returnMessage(True, "BONUS_USAGE_VALID")

                return self.controller._returnMessage(True, "BONUS_USAGE_VALID")
            
            elif maxUsageCount == -1:
                self.response.log("Unlimited Usage")
                return self.controller._returnMessage(True, "BONUS_USAGE_VALID")

        except Exception as e:
            self.response.log(f"Error in bonusUsageControl: {str(e)}")
            return self.controller._returnError(str(e))
            
            
        
        
            
    
    def bonusConditionControl(self):
        conditions = self.bonusData["conditions"]
        
        if type(conditions) != dict:
            return self.controller._returnError("BONUS_CONDITIONS_INVALID")
        
        if conditions.get("activeBonusCheck", False):
            activeBonusList = [x for x in self.bonusList if x["Status"] in [1,2,6]]
            if len(activeBonusList) > 0:
                return self.controller._returnMessage(False, "ACTIVE_BONUS_EXISTS")
        
        if conditions.get("checkProfitDiff",None):
            # Talep saatinden önceki 24 saat içerisindeki bonus alınmayan yatırımlar hesaplanır

            # son 24 saatteki bonuslar:
            last24Hours = datetime.now() - timedelta(days=1)
            
        
        return self.controller._returnMessage(True, "BONUS_CONDITIONS_OK")
    
    
    def runCheckBonus(self):
        try:
            # bonus alımı kontrolü
            bonusControl = self.bonusUsageControl()
            self.response.log(f"Bonus Usage Control Result: {json.dumps(bonusControl)}")
            if not bonusControl["isValid"]:
                bonusControl["errorIn"] = "bonuses -> usage"
                return bonusControl
            
            # bonus şartlarının kontrolü
            bonusConditions = self.bonusConditionControl()
            if not bonusConditions["isValid"]:
                bonusConditions["errorIn"] = "bonuses -> conditions"
                return bonusConditions
            
            # Bonus alımı
            bonusAmount = self.bonusAmountControl()
            if not bonusAmount["isValid"]:
                bonusAmount["errorIn"] = "bonuses -> value"
                return bonusAmount
            
            if self.bonusDict["beforeBonusAmount"] == 0:
                self.setDict("beforeBonusAmount", None)
                self.setDict("afterBonusAmount", self.bonusAmount)
            else:
                self.setDict("afterBonusAmount", self.bonusDict["afterBonusAmount"] + self.bonusAmount)
            
            return self.controller._returnMessage(True, "BONUS_CHECK_OK")
        except Exception as e:
            self.response.log(f"Error in runCheckBonus: {str(e)}")
            return self.controller._returnError(str(e))

