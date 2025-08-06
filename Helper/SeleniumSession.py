from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
import time
import random
import json
import datetime
import os
from seleniumwire import webdriver
import selenium_stealth
from io import BytesIO
import gzip
import requests

import subprocess
import platform
import shlex
import pyotp

import dotenv   
dotenv.load_dotenv()

# Get configuration from environment
DIGIURL = os.getenv('DIGIURL', 'https://sd.bopanel.com')

import logging
from selenium.webdriver.remote.remote_connection import LOGGER
LOGGER.setLevel(logging.WARNING)

class SeleniumSession:
    def __init__(self,data_dir=None):
        self.folder = data_dir
        os.makedirs(self.folder, exist_ok=True)
        self.driver = None
        self.uid = None
        self.auth = None
        self.isDriverActive = False
        self.sessionId = random.randint(100000,999999)
        
    def get_chrome_version(self):
        os_name = platform.system()
        if os_name == "Windows":
            output = subprocess.check_output(
                ["reg", "query", r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon", "/v", "version"],
                stderr=subprocess.DEVNULL, text=True
            )
            return output.strip().split()[-1]
        for cmd in (["google-chrome", "--version"], ["chromium-browser", "--version"]):
            try:
                ver = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
                return ver.strip().split()[-1]
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        return ""
    
    def setup_driver(self):
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument('--start-maximized')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--incognito')
        
        
        # Headless mod için ek ayarlar
        options.add_argument('--headless')
        
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--enable-javascript')
        options.add_argument('--disable-notifications')
        options.add_argument('--allow-popups')
        options.add_argument('--allow-popups-to-escape-sandbox')
        
        version = self.get_chrome_version().split(".")[0]
        ua = f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version}.0.0.0 Safari/537.36"
        options.add_argument(f'user-agent={ua}')
        
        # ChromeDriver'ı kurulum ve başlatma
        driverPath = ChromeDriverManager().install()
        print(f"ChromeDriver path: {driverPath}")
        service = Service(driverPath)
        
        try:
            self.driver = webdriver.Chrome(options=options, service=service)
        except Exception as e:
            print(f"Chrome başlatma hatası: {e}")
            raise e

        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
              get: () => undefined
            })
            """
        })
        
        self.driver.set_window_size(1920, 1080)
        self.driver.implicitly_wait(40)
        self.actions = ActionChains(self.driver)


    def login_and_listen_requests(self, username=None, password=None,verification_code=None):
        result = {
            "status": False,
            "message": ""
        }
        
        
        if self.isDriverActive:
            while self.isDriverActive:
                time.sleep(1)
            return result
            
        self.isDriverActive = True
        if self.driver is None or not self.driver.service.is_connectable():
            self.setup_driver()
        
        
        if not username:
            username = os.getenv("FUSERNAME")
        if not password:
            password = os.getenv("FPASSWORD")
        
        
        if not username or not password:
            result["message"] = "Username or password not found"
            self.isDriverActive = False
            return result

        try:
            
            
            self.driver.get(f'{DIGIURL}/')
            
            self.push_key(Keys.F12)
            
            WebDriverWait(self.driver, 40).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            username_input = WebDriverWait(self.driver, 40).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='username']"))
            )
            username_input.clear()
            username_input.send_keys(username)

            password_input = WebDriverWait(self.driver, 40).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']"))
            )
            password_input.clear()
            password_input.send_keys(password)

            login_button = WebDriverWait(self.driver, 40).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            self.driver.execute_script("arguments[0].click();", login_button)

            try:
                code_input = WebDriverWait(self.driver, 3).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, "input.centrivo-otp-input"))
                )
            except Exception as e:
                result["status"] = False 
                result["message"] = "Code input field not found within 3 seconds"
                self.isDriverActive = False
                return result
            
            
            code_input.clear()
            code_input.send_keys(str(verification_code))

            verify_button = WebDriverWait(self.driver, 40).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            self.driver.execute_script("arguments[0].click();", verify_button)

            WebDriverWait(self.driver, 60).until(
                EC.url_contains("welcome")
            )

            time_limit = 10
            start_time = time.time()

            data_to_save = {
                "Login": None,
                "LoginAfter": None,
                "refresh_token": None,
                "client_id": None,
                "uid": None
            }

            while time.time() - start_time < time_limit:
                for request in self.driver.requests:
                    if "token" in request.url and request.method == "POST":
                        login_data = {
                            "Request URL": request.url,
                            "Request Headers": dict(request.headers),
                            "Request Body": request.body.decode('utf-8') if request.body else None,
                            "Response": {
                                "Status Code": None,
                                "Headers": None,
                                "Body": None
                            },
                            "Additional Data": {
                                "uid": None,
                                "refresh_token": None
                            }
                            
                        }

                        # Request Body'den u_id ve client_id değerini al
                        if login_data["Request Body"]:
                            try:
                                request_body_params = dict(item.split('=') for item in login_data["Request Body"].split('&'))
                                login_data["Additional Data"]["uid"] = request_body_params.get("u_id", None)
                                login_data["Additional Data"]["client_id"] = request_body_params.get("client_id", None)
                            except Exception as e:
                                result["message"] = f"Request Body'den u_id alınırken hata oluştu: {e}"

                        if request.response:
                            login_data["Response"]["Status Code"] = request.response.status_code
                            login_data["Response"]["Headers"] = dict(request.response.headers)

                            if 'gzip' in request.response.headers.get('content-encoding', ''):
                                try:
                                    compressed_data = BytesIO(request.response.body)
                                    decompressed_data = gzip.GzipFile(fileobj=compressed_data).read()
                                    response_body = decompressed_data.decode('utf-8')
                                except Exception as e:
                                    result["message"] = f"Yanıt açılırken hata oluştu: {e}"
                                    response_body = None
                            else:
                                response_body = request.response.body.decode('utf-8')

                            if response_body:
                                try:
                                    response_json = json.loads(response_body)
                                    login_data["Additional Data"]["refresh_token"] = response_json.get("refresh_token", None)
                                    data_to_save["Login"] = login_data

                                    # İkinci isteği bul ve işle
                                    second_request_start_time = time.time()
                                    while time.time() - second_request_start_time < time_limit:
                                        for post_request in self.driver.requests:
                                            if "token" in post_request.url and post_request.method == "POST" and "grant_type=refresh_token" in (post_request.body.decode('utf-8') if post_request.body else ""):

                                                post_request_data = {
                                                    "Request URL": post_request.url,
                                                    "Request Headers": dict(post_request.headers),
                                                    "Request Body": post_request.body.decode('utf-8') if post_request.body else None,
                                                    "Response": {
                                                        "Status Code": None,
                                                        "Headers": None,
                                                        "Body": None
                                                    }
                                                }

                                                if post_request.response:
                                                    post_request_data["Response"]["Status Code"] = post_request.response.status_code
                                                    post_request_data["Response"]["Headers"] = dict(post_request.response.headers)

                                                    if 'gzip' in post_request.response.headers.get('content-encoding', ''):
                                                        try:
                                                            compressed_data = BytesIO(post_request.response.body)
                                                            decompressed_data = gzip.GzipFile(fileobj=compressed_data).read()
                                                            post_response_body = decompressed_data.decode('utf-8')
                                                        except Exception as e:
                                                            result["message"] = f"Yanıt açılırken hata oluştu: {e}"
                                                            post_response_body = None
                                                    else:
                                                        post_response_body = post_request.response.body.decode('utf-8')

                                                    if post_response_body:
                                                        try:
                                                            post_request_data["Response"]["Body"] = json.loads(post_response_body)
                                                        except json.JSONDecodeError as e:
                                                            result["message"] = f"JSON formatına dönüştürme hatası: {e}"
                                                            
                                                data_to_save["LoginAfter"] = post_request_data
                                                data_to_save["refresh_token"] = post_request_data["Response"]["Body"].get("refresh_token", None)
                                                data_to_save["client_id"] = data_to_save["Login"]["Additional Data"]["client_id"]
                                                data_to_save["uid"] = data_to_save["Login"]["Additional Data"]["uid"]
                                                data_to_save["secCHUA"] = data_to_save["Login"]["Request Headers"]["sec-ch-ua"]
                                                data_to_save["userAgent"] = data_to_save["Login"]["Request Headers"]["user-agent"]
                                                data_to_save["platform"] = data_to_save["Login"]["Request Headers"]["sec-ch-ua-platform"]
                                                break
                                        else:
                                            time.sleep(1)
                                            continue
                                        break

                                except json.JSONDecodeError as e:
                                    result["message"] = f"JSON formatına dönüştürme hatası: {e}"

                        with open(f"{self.folder}/loginSuccessData.json", "w", encoding="utf-8") as f:
                            json.dump(data_to_save, f, indent=4)
                        
                        self.extractAllData()
                            

                        result["status"] = True
                        result["message"] = "Login and subsequent request successful"
                        
                        
                        if not data_to_save["Login"]:
                            result["status"] = False
                            result["message"] = "Login request not found"
                        if not data_to_save["LoginAfter"]:
                            result["status"] = False
                            result["message"] = "Login after request not found"
                            
                        if not data_to_save["refresh_token"]:
                            result["status"] = False
                            result["message"] = "Refresh token not found"
                            
                        if not data_to_save["client_id"]:
                            result["status"] = False
                            result["message"] = "Client ID not found"
                        if not data_to_save["uid"]:
                            result["status"] = False
                            result["message"] = "UID not found"
                        self.isDriverActive = False
                        return result

                time.sleep(1)

        except Exception as e:
            result["message"] = f"Login error: {str(e)}"
            print(f"Exception details: {str(e)}")
            # Hata durumunda ekran görüntüsü al
            if hasattr(self.driver, 'save_screenshot'):
                self.driver.save_screenshot(f"{self.folder}/error_screenshot.png")
            result["status"] = False

        print(f"Login result: {result}")
        self.isDriverActive = False
        return result
        
    def inject_session_data(self):
        self.driver.get(f"{DIGIURL}")
        self.random_wait(2, 4)

        try:
            with open('data/local_storage.json', 'r') as f:
                local_storage = json.load(f)
                
                for key, value in local_storage.items():
                    if key == 'authData':
                        auth_data = local_storage['authData']
                        parsed_auth = json.loads(auth_data)
                        safe_auth = json.dumps(parsed_auth).replace('\\', '\\\\').replace('"', '\\"')
                        script = f'''
                            try {{
                                window.localStorage.setItem("{key}", "{safe_auth}");
                            }} catch(e) {{
                                console.error("Error setting {key}:", e);
                            }}
                        '''
                        self.driver.execute_script(script)
                    elif isinstance(value, (str, int, float, bool)):
                        if isinstance(value, str):
                            safe_value = value.replace('\\', '\\\\').replace('"', '\\"')
                        else:
                            safe_value = str(value)
                        script = f'''
                            try {{
                                window.localStorage.setItem("{key}", "{safe_value}");
                            }} catch(e) {{
                                console.error("Error setting {key}:", e);
                            }}
                        '''
                        self.driver.execute_script(script)

            stored_auth = self.driver.execute_script('return window.localStorage.getItem("authData");')
            if not stored_auth:
                print("Warning: authData could not be verified in localStorage")

        except Exception as e:
            print(f"Error injecting localStorage data: {e}")
        try:
            with open('data/cookies.json', 'r') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    try:
                        if 'expiry' in cookie:
                            del cookie['expiry']
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        print(f"Cookie error for {cookie.get('name','unknown')}: {e}")
        except Exception as e:
            print(f"Error loading cookies: {e}")
                    
        self.driver.refresh()

    def load_dashboard(self):
        self.driver.get(f"{DIGIURL}/#/platform/welcome") 
        self.random_wait(2, 4)
        
    def quit_driver(self):
        self.driver.quit()
        
    def find_element(self,by=By.ID,value=None):
        return WebDriverWait(self.driver,40).until(EC.presence_of_element_located((by,value)))
    
    def find_elements(self,by=By.ID,value=None):
        return WebDriverWait(self.driver,40).until(EC.presence_of_all_elements_located((by,value)))
    
    def click_element(self,by=By.ID,value=None,wait_time=40):
        WebDriverWait(self.driver,wait_time).until(EC.element_to_be_clickable((by,value))).click()

    def humman_type(self,element,text):
        for char in text:
            element.send_keys(char)
            time.sleep(random.randint(1,5)/30)
            
    def random_wait(self, min_seconds=1, max_seconds=3):
        time.sleep(random.uniform(min_seconds, max_seconds))

    def send_keys(self,by=By.ID,value=None,text=None):
        WebDriverWait(self.driver,40).until(EC.element_to_be_clickable((by,value))).send_keys(text)

    def push_key(self,key,count=1):
        for _ in range(count):
            self.send_keys(By.TAG_NAME,"html",key)
            time.sleep(random.randint(1,5)/30)
    
    
    def click_element_at_active_element(self):
        active_element = self.driver.switch_to.active_element
        active_element.click()
        
    def extractAllData(self):
        
            
        with open(f"{self.folder}/header.json","w",encoding="utf-8") as file:
            json.dump(self.driver.execute_script("return Object.fromEntries(new Headers())"),file,indent=4)
        
        with open(f"{self.folder}/cookies.json","w",encoding="utf-8") as file:
            json.dump(self.driver.get_cookies(),file,indent=4)
            
        with open(f"{self.folder}/local_storage.json","w",encoding="utf-8") as file:
            json.dump(self.driver.execute_script("return window.localStorage"),file,indent=4)
            
        with open(f"{self.folder}/session_storage.json","w",encoding="utf-8") as file:
            json.dump(self.driver.execute_script("return window.sessionStorage"),file,indent=4)

    def run_curl_command(self, curl_command):
        try:
            result = subprocess.run(shlex.split(curl_command), capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            return str(e)
        
    
    

if __name__ == "__main__":
    session = SeleniumSession()
    session.login_and_listen_requests()

