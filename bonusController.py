from main import FenomenSession
from datetime import timedelta
import datetime
import json
import traceback
import inspect

from Helper.BonusResponse import BonusResponse
from CampaignController import CampaignController
import builtins

from Helper.Bonus import BONUS
from SeleniumManager import SeleniumSessionManager
from Helper.BonusCompressor import BonusCompressor

class IBonusControlRequest:
    def __init__(self,controlData: dict,seleniumManager: SeleniumSessionManager):
        self.response = BonusResponse()
        self.seleniumManager = seleniumManager
        
        self.controlData = controlData
        self.bonusCompressor = BonusCompressor()
    
    def run(self):
        try:
            self.controller = CampaignController(self.seleniumManager)
        except Exception as e:
            if "FenomenSession oluşturulamadı" in str(e):
                self.response.setValid("Aktif hesap bulunamadı, aktif hesap bekleniyor", False, 10001)
                return self.response.returnData()
            self.response.setSystemError("FenomenSession oluşturulamadı "+str(e),"bonusController")
            return self.response.returnData()
        
        
        self.bonusDataList = []
        
        if (type(self.controlData) != dict):
            return self.response.setSystemError("Konrol verisi dict olmalı","bonuses")
        
        try:
            self.Bonuses = self.controlData["bonuses"]
            self.userid = self.controlData["userid"]
            self.loadBonus = self.controlData["loadBonus"]
            
            self.realTimeZone = self.controlData["realTimeZone"]
            self.realTime = self.controlData["realTime"]
            self.activeWithdrawControl = self.controlData["activeWithdrawControl"] if "activeWithdrawControl" in self.controlData else True
            
            self.response.realTime = self.realTime
            self.response.realTimeZone = self.realTimeZone
            
            # backend always utc0
            self.backendTime = self.controller.parse_datetime(self.realTime) - timedelta(hours=self.realTimeZone)
            
            self.response.setKey("bonusLoad", self.loadBonus)
            self.response.setKey("backendTime", self.backendTime)
            self.response.setKey("realTime", self.realTime)
            
            self.response.realTime_backendTimeDiff = self.controller.parse_datetime(self.realTime) - self.backendTime
            
            bannedControlDict = {
                3: "BlockedForGeneralBonusCampaign",
                1: "BlockedForCasinoBonusCampaign",
                2: "BlockedForSportBonusCampaign",
            }
            
            try:
                self.userMainInfo = self.controller.app.getUserMainInfo(self.userid)
                
                if not self.userMainInfo or self.userMainInfo["ResponseCode"] != 0:
                    return self.response.setSystemError("Kullanıcı bulunamadı","bonuses")
                
                self.userMainInfo = self.userMainInfo["ResponseObject"]
                
                self.BonusIds = [x["id"] for x in self.Bonuses]
                for bonusId in self.BonusIds:
                    bonus = self.controller.app.getBonusCampaigns(bonusId, IsActiveBonuses=True)
                    
                    productType = bonus[0]["ProductType"]
                    if productType in bannedControlDict.keys():
                        if self.userMainInfo[bannedControlDict[productType]]:
                            self.response.setValid(self.controller._returnMessage(False, "BONUS_BANNED")["message"], False, self.controller.validMessages["BONUS_BANNED"]["code"])
                            return self.response.returnData()
                        
            except Exception as e:
                self.response.log(f"Error checking bonus ban status: {str(e)}")
                pass
            
            if type(self.loadBonus) != bool:
                try:
                    if self.loadBonus != "true" and self.loadBonus != "false":
                        if self.loadBonus.lower() == "true":
                            self.loadBonus = True
                        if self.loadBonus.lower() == "false":
                            self.loadBonus = False
                        if int(self.loadBonus) == 1:
                            self.loadBonus = True
                        if int(self.loadBonus) == 0:
                            self.loadBonus = False
                except:
                    return self.response.setSystemError("loadBonus bool veya '1' veya '0' olmalı","bonuses")
                finally:
                    if type(self.loadBonus) != bool:
                        return self.response.setSystemError("loadBonus bool veya '1' veya '0' olmalı","bonuses")
                    
            self.controlParams = self.controlData["controlParams"]
        except KeyError as e:
            return self.response.setSystemError(f"Paremetre eksik: {str(e)}","bonuses")
        
        
                
                
        
        
        testDatetimenow = datetime.datetime.now()
        realTime = datetime.datetime.fromisoformat(self.realTime)
        
        self.userData = self.controller.checkUser(self.userid)
        self.userData["realTime"] = self.realTime
        self.userData["realTimeZone"] = self.realTimeZone
        if not self.userData:
            return self.response.setSystemError("Kullanıcı bulunamadı","bonuses")
        
        try:
            if self.activeWithdrawControl:
                if self.userData["userInfo"]["BookedBalance"] > 0:
                    self.response.setValid(self.controller._returnMessage(False, "ACTIVE_WITHDRAW")["message"], False, self.controller.validMessages["ACTIVE_WITHDRAW"]["code"])
                    return self.response.returnData()
        except Exception as e:
            self.response.log(f"Error checking active withdraw: {str(e)}")
            pass
        
        self.response.setKey("userId", self.userid)
        self.response.setKey("username", self.userData["username"])
        
        # paramsları kontrol edicez teker teker herhangi birisi false dönerse işlemi durdurucaz kullanıcının neden bonus alamadığını belirtecez
        self.response.log(f"Starting controlParams check. Total controls: {len(self.controlParams)}")
        for control in self.controlParams:
            controlName = control["controlName"]
            params = control["params"]
            
            self.response.log(f"Running control: {controlName} with params: {params}")
            
            if not self.controller.controls.get(controlName):
                return self.response.setSystemError(f"{controlName} kontrolü bulunamadı","controlParams")
                
            controlResult = self.controller.runControl(controlName, self.userData, params)
            self.response.log(f"Control {controlName} result: {controlResult}")
            
            if not controlResult["isValid"]:
                if controlResult.get("error"):
                    self.response.setSystemError(controlResult["error"],"controlParams -> "+controlName)
                    return self.response.returnData()
                self.response.setValid(controlResult["message"], False, controlResult["code"],"controlParams -> "+controlName,controlResult["args"])
                return self.response.returnData()
            
        # Process all bonuses and collect results
        validBonuses = []
        invalidBonuses = []
        
        # Enhanced multi-bonus processing
        bonusPriorities = {}
        bonusGroups = {}
        
        for bonus in self.Bonuses:
            if not bonus["id"]:
                invalidBonuses.append({
                    "id": bonus.get("id", "unknown"),
                    "error": "Bonus id belirtilmeli",
                    "isValid": False
                })
                continue
                
            # Extract multi-bonus parameters
            priority = bonus.get("priority", 0)  # Higher = more important
            mutuallyExclusive = bonus.get("mutuallyExclusive", [])  # Can't be combined with these IDs
            requiredBonuses = bonus.get("requiredBonuses", [])  # Needs these bonuses first
            bonusGroup = bonus.get("bonusGroup", None)  # Only one per group
            maxCombined = bonus.get("maxCombined", None)  # Max total if combined
            
            bonusPriorities[bonus["id"]] = priority
            if bonusGroup:
                if bonusGroup not in bonusGroups:
                    bonusGroups[bonusGroup] = []
                bonusGroups[bonusGroup].append(bonus)

            try:
                bonusData = self.controller.app.getBonusCampaigns(bonus["id"], IsActiveBonuses=True,dateTimeTo=self.realTime)
                if not bonusData or len(bonusData) == 0:
                    invalidBonuses.append({
                        "id": bonus["id"],
                        "error": f"{bonus['id']} id'li bonus bulunamadı veya aktif değil",
                        "isValid": False
                    })
                    continue
                bonusData = bonusData[0]

                bonus["data"] = bonusData
                
                bonusProcessor = BONUS(self.userData,self.controller,self.response,bonus)
                
                result = bonusProcessor.runCheckBonus()
                
                if not result["isValid"]:
                    invalidBonuses.append({
                        "id": bonus["id"],
                        "name": bonusProcessor.name,
                        "error": result.get("error", result.get("message", "Unknown error")),
                        "isValid": False,
                        "bonusDict": bonusProcessor.bonusDict,
                        "priority": priority
                    })
                else:
                    # Add multi-bonus metadata
                    bonusProcessor.mutuallyExclusive = mutuallyExclusive
                    bonusProcessor.requiredBonuses = requiredBonuses  
                    bonusProcessor.priority = priority
                    bonusProcessor.maxCombined = maxCombined
                    bonusProcessor.bonusGroup = bonusGroup
                    
                    validBonuses.append(bonusProcessor)
                    
            except Exception as e:
                self.response.log(f"Error processing bonus {bonus.get('id', 'unknown')}: {str(e)}")
                invalidBonuses.append({
                    "id": bonus.get("id", "unknown"),
                    "error": f"Processing error: {str(e)}",
                    "isValid": False,
                    "priority": priority
                })
        
        # Enhanced multi-bonus conflict resolution
        finalValidBonuses = self._resolveMultiBonusConflicts(validBonuses, bonusGroups)
        
        # Update response with final bonuses
        for bonus in finalValidBonuses:
            self.response.data["bonuses"].append(bonus.bonusDict)
            self.bonusDataList.append(bonus)
        
        # Set overall validation status
        if len(finalValidBonuses) > 0:
            message = f"{len(finalValidBonuses)} bonus" + ("" if len(finalValidBonuses) == 1 else "es") + " onaylandı"
            self.response.setValid(message, True, self.controller.validMessages["BONUS_APPROVED"]["code"])
        else:
            # Priority-based error reporting
            if invalidBonuses:
                # Sort by priority and return highest priority error
                invalidBonuses.sort(key=lambda x: x.get("priority", 0), reverse=True)
                firstInvalid = invalidBonuses[0]
                self.response.setSystemError(firstInvalid["error"], "bonuses")
                return self.response.returnData()
            else:
                self.response.setSystemError("No bonuses to process", "bonuses")
                return self.response.returnData()
        
        # Add detailed multi-bonus info to response
        if invalidBonuses:
            self.response.setKey("invalidBonuses", invalidBonuses)
        
        self.response.setKey("multiBonusInfo", {
            "totalProcessed": len(self.Bonuses),
            "validCount": len(finalValidBonuses), 
            "invalidCount": len(invalidBonuses),
            "conflictsResolved": len(validBonuses) - len(finalValidBonuses),
            "bonusGroups": list(bonusGroups.keys())
        })
        
        for bonus in self.bonusDataList:
            escapedJsonNote = self.bonusCompressor.compress(bonus.noteJson)
            self.response.log(f"Compressed Json Note: {escapedJsonNote}")
        
        if self.loadBonus:
            for bonus in self.bonusDataList:
                try:
                    self.response.log(f"Processing bonus: {bonus.name} - Amount: {bonus.bonusAmount}")
                    
                    #escapedJsonNote = json.dumps(bonus.noteJson,ensure_ascii=True)
                    #escapedJsonNote = escapedJsonNote.replace('"', '\\"')
                    #escapedJsonNote = escapedJsonNote.replace("'", "\\'")
                    
                    if bonus.isFreeSpin:
                        loadResponse = self.controller.app.addBonus(
                            bonus.id,
                            self.userData["userId"],
                            bonus.productType,
                            bonusAmount=0,
                            freeSpinCount=bonus.bonusAmount,
                            note=escapedJsonNote
                        )
                        
                    else:
                        loadResponse = self.controller.app.addBonus(
                            bonus.id, 
                            self.userData["userId"],
                            bonus.productType,
                            bonusAmount=bonus.bonusAmount,
                            freeSpinCount=None,
                            note=escapedJsonNote
                        )
                    
                    if loadResponse.get("ResponseCode") == 0:
                        bonus.bonusDict["isLoaded"] = True
                        self.response.log(f"Bonus {bonus.name} loaded successfully")
                    else:
                        self.response.log(f"Failed to load bonus {bonus.name}: {loadResponse}")
                        bonus.bonusDict["isLoaded"] = False
                        
                except Exception as e:
                    self.response.log(f"Error loading bonus {bonus.name}: {str(e)}")
                    bonus.bonusDict["isLoaded"] = False
            
            # Set global bonusLoaded flag based on individual bonus loading results
            loadedBonuses = [bonus for bonus in self.bonusDataList if bonus.bonusDict.get("isLoaded", False)]
            if loadedBonuses:
                self.response.setKey("bonusLoaded", True)
                self.response.log(f"{len(loadedBonuses)} bonus başarıyla yüklendi")
            else:
                self.response.setKey("bonusLoaded", False)
                self.response.log("Hiçbir bonus yüklenemedi")
        
        return self.response.returnData()
                
    def _resolveMultiBonusConflicts(self, validBonuses, bonusGroups):
        """
        Advanced multi-bonus conflict resolution
        Handles priority, mutual exclusion, groups, dependencies, and combined limits
        """
        if not validBonuses:
            return []
        
        # Sort by priority (highest first)
        validBonuses.sort(key=lambda x: getattr(x, 'priority', 0), reverse=True)
        
        finalBonuses = []
        usedBonusIds = set()
        usedGroups = set()
        totalCombinedAmount = 0
        
        for bonus in validBonuses:
            bonusId = bonus.id
            priority = getattr(bonus, 'priority', 0)
            mutuallyExclusive = getattr(bonus, 'mutuallyExclusive', [])
            requiredBonuses = getattr(bonus, 'requiredBonuses', [])
            bonusGroup = getattr(bonus, 'bonusGroup', None)
            maxCombined = getattr(bonus, 'maxCombined', None)
            
            # Check if already processed
            if bonusId in usedBonusIds:
                continue
            
            # Check bonus group exclusion (only one per group)
            if bonusGroup and bonusGroup in usedGroups:
                self.response.log(f"Bonus {bonusId} skipped - group {bonusGroup} already used")
                continue
            
            # Check mutual exclusion
            hasConflict = any(excludeId in usedBonusIds for excludeId in mutuallyExclusive)
            if hasConflict:
                conflictIds = [excludeId for excludeId in mutuallyExclusive if excludeId in usedBonusIds]
                self.response.log(f"Bonus {bonusId} skipped - conflicts with {conflictIds}")
                continue
            
            # Check required bonuses (dependencies)
            if requiredBonuses:
                missingRequired = [reqId for reqId in requiredBonuses if reqId not in usedBonusIds]
                if missingRequired:
                    self.response.log(f"Bonus {bonusId} skipped - missing required bonuses {missingRequired}")
                    continue
            
            # Check combined amount limit
            if maxCombined:
                if totalCombinedAmount + bonus.bonusAmount > maxCombined:
                    adjustedAmount = maxCombined - totalCombinedAmount
                    if adjustedAmount > 0:
                        self.response.log(f"Bonus {bonusId} amount adjusted from {bonus.bonusAmount} to {adjustedAmount}")
                        bonus.bonusAmount = adjustedAmount
                        bonus.setDict("currentBonusAmount", adjustedAmount)
                    else:
                        self.response.log(f"Bonus {bonusId} skipped - would exceed combined limit")
                        continue
            
            # Add to final list
            finalBonuses.append(bonus)
            usedBonusIds.add(bonusId)
            if bonusGroup:
                usedGroups.add(bonusGroup)
            totalCombinedAmount += bonus.bonusAmount
            
            self.response.log(f"Bonus {bonusId} ({bonus.name}) included - Priority: {priority}, Amount: {bonus.bonusAmount}")
        
        return finalBonuses

if __name__ == "__main__":
    with open("./bonusJsons/30anlıkKayip.json", "r",encoding="utf-8") as f:
        testJson = json.loads(f.read())
    
    bonusControl = IBonusControlRequest(testJson).run()
    print(json.dumps(bonusControl, indent=2, ensure_ascii=False))
