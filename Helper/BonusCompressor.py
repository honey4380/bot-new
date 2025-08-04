import json
import re
from datetime import datetime

class BonusCompressor:
    @staticmethod
    def compress(data):
        default_date = '2025-03-25 18:17:06'
        default_date_iso = '2025-03-25T18:17:06.6666667'
        
        deposit_range = data.get('DepositDateRange')
        deposit_ids = data.get('DepositIds', [])
        withdraw_ids = data.get('WithdrawIds', [])
        withdraw_range = data.get('WithdrawDateRange')
        
        deposit_ids_str = "null" if not deposit_ids else ",".join(str(id) for id in deposit_ids)
        
        withdraw_ids_str = "null" if not withdraw_ids else ",".join(str(id) for id in withdraw_ids)
        
        deposit_range_str = "null"
        if deposit_range is not None and isinstance(deposit_range, list) and len(deposit_range) == 2:
            if (deposit_range[0] != default_date and deposit_range[0] != default_date_iso) or \
               (deposit_range[1] != default_date and deposit_range[1] != default_date_iso):
                deposit_range_str = f"{deposit_range[0]},{deposit_range[1]}"
        
        withdraw_range_str = "null"
        if withdraw_range is not None and isinstance(withdraw_range, list) and len(withdraw_range) == 2:
            if (withdraw_range[0] != default_date and withdraw_range[0] != default_date_iso) or \
               (withdraw_range[1] != default_date and withdraw_range[1] != default_date_iso):
                withdraw_range_str = f"{withdraw_range[0]},{withdraw_range[1]}"
        
        compressed = f"DP[({deposit_ids_str}),({deposit_range_str})]*DW[({withdraw_ids_str}),({withdraw_range_str})]"
        
        return compressed
    
    @staticmethod
    def decompress(compressed_str):
        default_date = '2025-03-25 18:17:06'
        
        try:
            parts = compressed_str.split('*')
            if len(parts) != 2:
                raise ValueError("Geçersiz sıkıştırılmış format")
                
            deposit_part = parts[0]
            withdraw_part = parts[1]
            
            deposit_match = re.match(r'DP\[\(([^)]*)\),\(([^)]*)\)\]', deposit_part)
            if not deposit_match:
                raise ValueError("Geçersiz deposit formatı")
                
            deposit_ids_str = deposit_match.group(1)
            deposit_range_str = deposit_match.group(2)
            
            withdraw_match = re.match(r'DW\[\(([^)]*)\),\(([^)]*)\)\]', withdraw_part)
            if not withdraw_match:
                raise ValueError("Geçersiz withdraw formatı")
                
            withdraw_ids_str = withdraw_match.group(1)
            withdraw_range_str = withdraw_match.group(2)
            
            deposit_ids = []
            if deposit_ids_str.lower() != "null" and deposit_ids_str:
                deposit_ids = [int(id_str) for id_str in deposit_ids_str.split(',')]
            
            withdraw_ids = []
            if withdraw_ids_str.lower() != "null" and withdraw_ids_str:
                withdraw_ids = [int(id_str) for id_str in withdraw_ids_str.split(',')]
            
            deposit_range = None
            if deposit_range_str.lower() != "null" and deposit_range_str:
                dates = deposit_range_str.split(',')
                if len(dates) == 2:
                    deposit_range = dates
            
            withdraw_range = None
            if withdraw_range_str.lower() != "null" and withdraw_range_str:
                dates = withdraw_range_str.split(',')
                if len(dates) == 2:
                    withdraw_range = dates
            
            result = {
                'DepositDateRange': deposit_range,
                'DepositIds': deposit_ids,
                'WithdrawIds': withdraw_ids,
                'WithdrawDateRange': withdraw_range
            }
            
            return result
            
        except Exception as e:
            raise ValueError(f"String açılırken hata oluştu: {str(e)}")
        
    @staticmethod
    def is_compressed(input_str):
        if not isinstance(input_str, str):
            return False
        
        pattern = r'^DP\[\(([^)]*)\),\(([^)]*)\)\]\*DW\[\(([^)]*)\),\(([^)]*)\)\]$'
        
        match = re.match(pattern, input_str)
        return match is not None
        
if __name__ == "__main__":
    data1 = {
        "DepositDateRange": ["2025-03-25T18:17:06.6666667", "2025-03-25T18:17:06.6666667"],
        "DepositIds": [123156456],
        "WithdrawIds": [123156456, 146531561],
        "WithdrawDateRange": None
    }
    
    compreessed_str1 = BonusCompressor.compress(data1)
    notCompressed = "DP[(4362351950,9730217387,195216656),(null)]*DW[(195044382),(null)]"
    
    print(BonusCompressor.is_compressed(compreessed_str1))  # True
    print(BonusCompressor.is_compressed(notCompressed))  # False
    print(BonusCompressor.decompress(notCompressed))  # Decompressed data
    