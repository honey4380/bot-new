import json
import subprocess
import urllib.parse

class CurlManager:
    
    def escapeString(self, string: str) -> str:
        # first escape backslashes, then escape double quotes
        return string.replace("\\", "\\\\").replace('"', '\\"')
    
    def generateCurlCommand(self, url: str, authToken: str,uid:str,secCHUA:str,userAgent:str,platform:str, raw_json_string: str=None) -> str:
        
        if raw_json_string is not None:
            if isinstance(raw_json_string, dict):
                raw_json_string = json.dumps(raw_json_string, ensure_ascii=False, indent=None)
            
            py_data = json.loads(raw_json_string)
            
            
            escaped_data = json.dumps(py_data, ensure_ascii=False, indent=None).replace('"', '\\"')
        else:
            escaped_data = ""

        
        
        
        curl_command = f'''curl "{url}" \
-H "accept: application/json, text/plain, */*" \
-H "accept-language: en" \
-H "authorization: Bearer {authToken}" \
-H "content-type: application/json" \
-H "origin: https://sd.bopanel.com" \
-H "priority: u=1, i" \
-H "referer: https://sd.bopanel.com/" \
-H "sec-ch-ua: {secCHUA}" \
-H "sec-ch-ua-mobile: ?0" \
-H "sec-ch-ua-platform: {platform}" \
-H "sec-fetch-dest: empty" \
-H "sec-fetch-mode: cors" \
-H "sec-fetch-site: cross-site" \
-H "timezone: 3" \
-H "uid: {uid}" \
-H "user-agent: {userAgent}" \
--data-raw "{escaped_data}"'''

        return curl_command
    
    def executeCurl(self, url: str, authToken: str,uid:str,secCHUA:str,userAgent:str,platform:str, raw_json_string: str=None) -> subprocess.CompletedProcess:
        timeout = 5 * 60
        curlCommand = self.generateCurlCommand(url, authToken,uid,secCHUA,userAgent,platform, raw_json_string)
        return subprocess.run(curlCommand, shell=True, capture_output=True, text=True, timeout=timeout,encoding='utf-8')

if __name__ == "__main__":
    cm = CurlManager()
    url = "https://apisd.bopanel.com/api/Report/GetClientTransactionHistoryReport"
    authToken = "ja9MiuAPxUAAGGrUoncbB65OikkutuM4Y2ZILVo5mRus35nkgjVdp3VLVR-XcnlvqjsKQpcguFgEj7v2uyaAhz9RhKgfFbY3c9JR2nEwM6u2I6z3ltR8QCPcjovcZWpe67r2Ao7jloM2YMWmjii8psHL9RW_8fxj9GLu-edB9dKsse8R-XOh1aulKZYW8GFmxkk1EzP7Meqj8yZjBWoaLKOWNg62jo773zHV6uiUvvmung19atdM7LZqRRnSeK0AizSrKV6McPGDEt8jjQ7UqfWTJCBzG6W72HeIrK69TDCTy0crrSXNXcngCq9NswkBJsG46kQh27EHJ0DKx38QAondPk5BkB_eCM4GtXTZiDolR_XvzKyDaJiS0ULRw6qK75s2q_3FVcnN6X35uzOHNPRJQJUpaU0nS5zCDwE2TZFwCbo01TQMiXjQFtQfsfAEVLO-HOH5sV71XIM4eTwi2AQFOMsYPZs0PfcXG64oNaCZoTDtfRDXKOGCYy4eNVDKNI0B-MgLjFwTymimYFrKBEz7SH1T55SqrR0d68zxKvcakdC_SNC1jSO2Z_xu7LF7-TDdKOLnbeYV65UhSaBGCqzUDvRcra4oI85oM_kKJzOj-9qzmqR4swUJH0mD2uml"
    raw_json = {
        "DateRange": "Last24Hours",
        "FromDate": "2025-01-14T10:41:32.000Z",
        "ToDate": "2025-01-15T10:41:32.000Z",
        "Page": 1,
        "Top": 100,
        "OperationTypeIds": [
            6,
            7,
            8,
            5,
            30,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            31,
            32,
            18,
            19,
            2,
            1,
            21,
            22,
            20,
            23,
            24,
            25,
            16,
            26,
            27,
            28,
            29,
            33,
            34,
            35,
            36,
            37,
            38,
            39,
            40,
            41,
            42,
            43,
            44,
            45,
            46,
            47,
            48,
            49,
            50,
            51,
            52,
            53,
            54,
            55,
            56,
            57,
            58,
            63,
            64,
            99,
            65,
            66,
            59,
            60,
            61,
            62,
            105,
            107,
            108,
            109,
            110,
            111,
            112,
            121,
            122,
            123,
            124,
            125,
            67,
            68,
            69,
            70,
            71,
            72,
            73,
            74,
            75,
            76,
            77,
            78,
            79,
            80,
            81,
            82,
            83,
            84,
            85,
            86,
            87,
            88,
            89,
            90,
            91,
            92,
            93,
            94,
            95,
            96,
            97,
            100,
            101,
            102,
            103,
            104,
            113,
            114,
            115,
            116,
            117,
            118,
            119,
            120,
            126,
            127,
            128,
            129,
            130,
            131,
            134,
            135,
            136,
            137,
            138,
            139
        ],
        "filterSearch": "",
        "ClientId": 11304253
}
    
    # Execute the curl command
    process = subprocess.run(
        cm.generateCurlCommand(url, authToken, raw_json),
        shell=True,
        capture_output=True,
        text=True,
        timeout=30 * 60,
        encoding='utf-8'
    )
    
    # Print the output
    print(process.stdout)
    
