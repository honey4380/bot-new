import json
import os
import time
import random
from datetime import datetime, timedelta
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from Helper.SeleniumSession import SeleniumSession
import pyotp
import subprocess



import logging
import logging.handlers


logPath = os.path.join(os.path.dirname(__file__), "logs")
if not os.path.exists(logPath):
    os.makedirs(logPath)
file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(logPath, 'SeleniumManager.log'),
    encoding='utf-8',
    maxBytes=1024*1024,
    backupCount=5
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        file_handler,
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("SessionManager")

class SeleniumSessionManager:
    def __init__(self, config_path=None,folder="data",health_check_interval=30):
        """
        SeleniumSessionManager sınıfı başlatıcısı
        
        Args:
            config_path (str, optional): Harici yapılandırma dosyası yolu
        """
        load_dotenv()
        self.config_path = config_path
        self.dataFolder = folder
        self.accounts = self._load_accounts(config_path)
        
        if not self.accounts:
            logger.error("Hiçbir hesap yapılandırması bulunamadı!")
            raise ValueError("Hesap yapılandırması bulunamadı")
        
        logger.info(f"Toplam {len(self.accounts)} hesap bulundu")
        
        self.account_statuses = {}
        
        self.active_accounts = []
        
        self.lock = Lock()
        
        self.accounts_map = {account["username"]: account for account in self.accounts}
        
        self._create_account_directories()
        
        self._initialize_accounts()
        
        self.help_check_interval = health_check_interval
        self.health_check_thread = Thread(target=self._token_health_check, daemon=False)
        self.health_check_thread.start()
        
        self.loginThreadPool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="LoginProcess")
        
        self.current_account_index = 0
        
        self.request_counters = {username: 0 for username in self.accounts_map.keys()}
        
        logger.info("SeleniumSessionManager başlatıldı")
    
    def _load_accounts(self, config_path=None):
        """
        Hesap bilgilerini yükle
        
        Args:
            config_path (str, optional): Harici yapılandırma dosyası yolu
            
        Returns:
            list: Hesap bilgilerini içeren liste
        """
        accounts = []
        
        # Harici yapılandırma dosyasından yükle
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as file:
                    accounts = json.load(file)
                logger.info(f"Hesaplar {config_path} dosyasından yüklendi")
                return accounts
            except Exception as e:
                logger.error(f"Yapılandırma dosyası yüklenirken hata: {str(e)}")
        
        # .env dosyasından yükle
        accounts_json = os.getenv("ACCOUNTS")
        if accounts_json:
            try:
                accounts = json.loads(accounts_json)
                logger.info("Hesaplar .env dosyasından yüklendi")
                return accounts
            except json.JSONDecodeError as e:
                logger.error(f"ACCOUNTS JSON ayrıştırma hatası: {str(e)}")
        
        # Tek hesap bilgilerini kontrol et
        username = os.getenv("USERNAME")
        password = os.getenv("PASSWORD")
        totp_secret = os.getenv("TOTP_SECRET")
        
        if username and password:
            account = {"username": username, "password": password}
            if totp_secret:
                account["totp"] = totp_secret
            
            accounts.append(account)
            logger.info("Tek hesap .env dosyasından yüklendi")
            return accounts
        
        return []
    
    def update_account(self, username, password, totp_secret=None):
        """
        Yeni bir hesap ekle
        
        Args:
            username (str): Kullanıcı adı
            password (str): Parola
            totp_secret (str, optional): TOTP gizli anahtarı
        """
        data = {
            "username": username,
            "totp": totp_secret,
            "isLoggedIn": False,
            "isAddedStorage": False,
            "isLoggedInTime": None,
            "message": None,
        }
        
        # Check if account already exists
        existing_account = self.accounts_map.get(username)
        login_success = False

        # Create SeleniumSession instance to test login
        selenium_session = SeleniumSession(data_dir=f"./data/{username}")

        try:
            # Try login with new credentials
            totp_code = None
            if totp_secret:
                totp = pyotp.TOTP(totp_secret)
                totp_code = totp.now()

            login_success = selenium_session.login_and_listen_requests(
                username=username,
                password=password,
                verification_code=totp_code
            )
            
            selenium_session.quit_driver()

            
            if login_success["status"] == False:
                logger.error(f"Login failed for {username}: {login_success['message']}")
                data["message"] = "Login failed with provided credentials"
                
                return data

            if login_success:
                # Update or add account
                new_account = {
                    "username": username,
                    "password": password,
                    "totp": totp_secret
                }

                if existing_account:
                    # Update existing account
                    existing_account.update(new_account)
                    logger.info(f"Account {username} updated successfully")
                else:
                    # Add new account
                    self.accounts.append(new_account)
                    self.accounts_map[username] = new_account
                    logger.info(f"Account {username} added successfully")

                # Save updated accounts to config file
                if self.config_path:
                    with open(self.config_path, 'w') as f:
                        json.dump(self.accounts, f, indent=2)

                data["isLoggedIn"] = True
                data["message"] = "Account updated/added successfully"
            else:
                data["message"] = "Login failed with provided credentials"

        except Exception as e:
            logger.error(f"Error updating account {username}: {str(e)}")
            data["message"] = f"Error: {str(e)}"

        return data
        
    def delete_account(self, username):
        """
        Hesabı sil
        
        Args:
            username (str): Kullanıcı adı
        """
        if username in self.accounts_map:
            del self.accounts_map[username]
            self.accounts = [account for account in self.accounts if account["username"] != username]
            
            # Hesap dizinini sil
            account_dir = f"./data/{username}"
            if os.path.exists(account_dir):
                os.rmdir(account_dir)
            
            # Yapılandırma dosyasını güncelle
            if self.config_path:
                with open(self.config_path, 'w') as f:
                    json.dump(self.accounts, f, indent=2)
            
            logger.info(f"{username} hesabı silindi")
        else:
            logger.warning(f"{username} hesabı bulunamadı")
        
    
    def _create_account_directories(self):
        """
        Her hesap için gereken dizinleri oluştur
        """
        for username in self.accounts_map.keys():
            account_dir = f"./data/{username}"
            
            # Dizin yoksa oluştur
            if not os.path.exists(account_dir):
                os.makedirs(account_dir, exist_ok=True)
                logger.info(f"{username} için dizin oluşturuldu: {account_dir}")
    
    def run_curl_command(self, curl_command):
            timeout = 5 * 60
            return subprocess.run(curl_command, shell=True, capture_output=True, text=True, timeout=timeout,encoding='utf-8')

    
    def refresh_token(self,loginRequestData, max_attempts=3):
        attempt = 0
        while attempt < max_attempts:
            try:
                curl_command = f'''curl "https://apisd.bopanel.com/token" \
                -H "accept: application/json, text/plain, */*" \
                -H "accept-language: en" \
                -H "content-type: application/x-www-form-urlencoded; charset=UTF-8" \
                -H "origin: https://sd.bopanel.com" \
                -H "priority: u=1, i" \
                -H "referer: https://sd.bopanel.com/" \
                -H "sec-ch-ua: \\"Microsoft Edge\\";v=\\"131\\", \\"Chromium\\";v=\\"131\\", \\"Not_A Brand\\";v=\\"24\\"" \
                -H "sec-ch-ua-mobile: ?0" \
                -H "sec-ch-ua-platform: \\"Windows\\"" \
                -H "sec-fetch-dest: empty" \
                -H "sec-fetch-mode: cors" \
                -H "sec-fetch-site: cross-site" \
                -H "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0" \
                --data-raw "client_id={loginRequestData['client_id']}&grant_type=refresh_token&refresh_token={loginRequestData['refresh_token']}"'''
                
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
                    time.sleep(2)
                else:
                    return None
                    
            except Exception as e:
                print(f"Hata oluştu: {str(e)} (Deneme {attempt + 1}/{max_attempts})")
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(2)

        return None
    
    
    
    def _initialize_accounts(self):
        """
        Tüm hesapları başlat ve durumlarını kontrol et
        """
        logger.info("Hesaplar başlatılıyor...")
        
        for username, account in self.accounts_map.items():
            # Hesap durumu oluştur
            self.account_statuses[username] = {
                "is_active": False,
                "last_login": None,
                "token_valid": False,
                "auth_token": None,
                "selenium_session": None,
                "token_check_time": None,
                "error_count": 0,
                "consecutive_errors": 0
            }
            
            
            if len(self.active_accounts) > 0:
                # İlk hesap dışında diğer hesaplar için ayrı thread başlat
                thread = Thread(target=self._login_account, args=(username,), daemon=False)
                thread.start()
            else:
                # İlk hesap için hemen giriş yap
                # Hesabı başlat
                res = self._login_account(username)
                
                if res:
                    logger.info(f"{username} hesabı başlatıldı")
                    self.account_statuses[username]["is_active"] = True
                    self.account_statuses[username]["last_login"] = datetime.now()
                else:
                    logger.error(f"{username} hesabı başlatılamadı")
                    self.account_statuses[username]["is_active"] = False
                    
        # hiç hesap aktif değilse, aktif hesap olana kadar hepsini tek tek dene
        if not self.active_accounts:
            logger.info("Hiçbir hesap aktif değil, aktif hesap bulunana kadar denenecek")
            while not self.active_accounts:
                for username in self.accounts_map.keys():
                    # Hesabı başlat
                    res = self._login_account(username)
                    
                    if res:
                        logger.info(f"{username} hesabı başlatıldı")
                        break
                    else:
                        logger.error(f"{username} hesabı başlatılamadı")
                        self.account_statuses[username]["is_active"] = False
                        self.account_statuses[username]["last_login"] = datetime.now()
                time.sleep(5)
    
    def _login_account(self, username):
        """
        Belirli bir hesapla giriş yap
        
        Args:
            username (str): Giriş yapılacak hesabın kullanıcı adı
            
        Returns:
            bool: Giriş başarılı ise True, değilse False
        """
        if username not in self.accounts_map:
            logger.error(f"Bilinmeyen hesap: {username}")
            return False
        
        account = self.accounts_map[username]
        password = account["password"]
        totp_secret = account.get("totp")
        
        logger.info(f"{username} hesabı için giriş yapılıyor...")
        
        try:
            # Hesap dizinini ayarla
            account_dir = f"{self.dataFolder}/{username}"
            
            # Check if we have valid session data first
            res = None
            try:
                if os.path.exists(f"{account_dir}/loginSuccessData.json"):
                    with open(f"{account_dir}/loginSuccessData.json", "r") as file:
                        login_request_data = json.load(file)
                    
                    # Try to refresh token first
                    res = self.refresh_token(login_request_data)
                    if res:
                        logger.info(f"{username} için mevcut oturum kullanılıyor")
                        
                        # Update account status
                        self.account_statuses[username] = {
                            "is_active": True,
                            "last_login": datetime.now(),
                            "token_valid": True,
                            "auth_token": res,
                            "selenium_session": None,
                            "token_check_time": datetime.now(),
                            "error_count": 0,
                            "consecutive_errors": 0
                        }
                        
                        # Add to active accounts
                        if username not in self.active_accounts:
                            self.active_accounts.append(username)
                        
                        return True
                    else:
                        logger.info(f"{username} için token yenilenemedi, yeni giriş yapılacak")
                        
            except Exception as e:
                logger.error(f"{username} için mevcut oturum kontrolü hatası: {str(e)}")
            
            # Only do new login if no valid session
            selenium_session = SeleniumSession(data_dir=account_dir)
            
            # TOTP kodu oluştur (eğer varsa)
            totp_code = None
            if totp_secret:
                totp = pyotp.TOTP(totp_secret)
                totp_code = totp.now()
                logger.debug(f"{username} için TOTP kodu oluşturuldu")
            
            # Giriş yap
            login_result = selenium_session.login_and_listen_requests(
                username=username,
                password=password,
                verification_code=totp_code
            )
            
            # Driver'ı kapat
            selenium_session.quit_driver()
            
            if login_result["status"] == False:
                logger.error(f"{username} için giriş başarısız: {login_result['message']}")
                return False
            
            # Read the saved login data
            try:
                with open(f"{account_dir}/loginSuccessData.json", "r") as file:
                    login_request_data = json.load(file)
            except Exception as e:
                logger.error(f"{username} için login verisi okunamadı: {str(e)}")
                return False
            
            auth_token = self.refresh_token(login_request_data)
            
            if not auth_token:
                logger.error(f"{username} için token alınamadı")
                
                with self.lock:
                    status = self.account_statuses[username]
                    status["is_active"] = False
                    status["token_valid"] = False
                    status["last_login"] = datetime.now()
                    status["error_count"] += 1
                    status["consecutive_errors"] += 1
                    
                    if username in self.active_accounts:
                        self.active_accounts.remove(username)
                
                return False
            
            # Hesap durumunu güncelle
            self.account_statuses[username] = {
                "is_active": True,
                "last_login": datetime.now(),
                "token_valid": True,
                "auth_token": auth_token,
                "selenium_session": selenium_session,
                "token_check_time": datetime.now(),
                "error_count": 0,
                "consecutive_errors": 0
            }
            
            # Aktif hesaplara ekle
            if username not in self.active_accounts:
                self.active_accounts.append(username)
            
            logger.info(f"{username} hesabı için giriş başarılı")
            return True
        
        except Exception as e:
            logger.error(f"{username} için giriş hatası: {str(e)}")
            
            # Hesap durumunu güncelle
            with self.lock:
                status = self.account_statuses[username]
                status["is_active"] = False
                status["token_valid"] = False
                status["last_login"] = datetime.now()
                status["error_count"] += 1
                status["consecutive_errors"] += 1
                
                if username in self.active_accounts:
                    self.active_accounts.remove(username)
            
            return False
        
    def ping_signalr(self,AuthToken=None):
        try:
            if AuthToken is None:
                print("AuthToken is None, cannot ping SignalR")
                return False
                
            access_token = AuthToken.replace(" ", "%20")
            timestamp = int(time.time() * 1000)
        
            # Tırnak işaretlerini düzelt ve escape karakterlerini düzenle
            curl_command = f"""curl -s "https://signalrserversd.apidigi.com/signalr/ping?access_token={access_token}&_={timestamp}" \\
            -H "accept: text/plain, */*; q=0.01" \\
            -H "accept-language: tr,en;q=0.9,en-GB;q=0.8,en-US;q=0.7" \\
            -H "content-type: application/x-www-form-urlencoded; charset=UTF-8" \\
            -H "origin: https://sd.bopanel.com" \\
            -H "priority: u=1, i" \\
            -H "referer: https://sd.bopanel.com/" \\
            -H "sec-ch-ua: Not A(Brand;v=8, Chromium;v=132, Microsoft Edge;v=132" \\
            -H "sec-ch-ua-mobile: ?0" \\
            -H "sec-ch-ua-platform: Windows" \\
            -H "sec-fetch-dest: empty" \\
            -H "sec-fetch-mode: cors" \\
            -H "sec-fetch-site: cross-site" \\
            -H "authorization: Bearer {AuthToken}" \\
            -H "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0\"""".strip()

            result = self.run_curl_command(curl_command)
        
            if result.stdout:
                try:
                    response = json.loads(result.stdout) if result.stdout else None
                    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - SignalR ping: {response}")
                    return response
                except json.JSONDecodeError:
                    print(f"Raw output: {result.stdout}")
                    if "true" in result.stdout.lower():
                        return True
                    return result.stdout
            else:
                if result.returncode != 0:
                    print(f"Curl error: {result.stderr}")
                    return False
                raise Exception(f"No output received. Return code: {result.returncode}, Error: {result.stderr}")

        except Exception as e:
            print(f"SignalR ping error: {str(e)}")
            return False

    
    
    def _token_health_check(self):
        """
        Tüm hesapların token sağlığını düzenli olarak kontrol et
        """
        logger.info("Token sağlık kontrolü başlatıldı")
        
        while True:
            active_count = 0
            inactive_count = 0
            
            for username, account in self.accounts_map.items():
                # Hesap durumunu kontrol et
                with self.lock:
                    status = self.account_statuses[username].copy()
                
                # Token geçerliliğini kontrol et
                if status["is_active"]:
                    try:
                        # En son kontrol zamanı
                        last_check = status["token_check_time"]
                        now = datetime.now()
                        
                        # Belirli bir süre geçtiyse kontrol et (5 dakika)
                        if not last_check or (now - last_check).total_seconds():
                            token_valid = True
                            
                            result = self.ping_signalr(status["auth_token"])
                            if isinstance(result, dict) and result.get("ResponseCode") == -1:
                                token_valid = False
                            try:
                                with open(f"{self.dataFolder}/{username}/loginSuccessData.json", "r") as file:
                                    login_request_data = json.load(file)
                                    
                                    result = self.refresh_token(login_request_data)
                                    if not result:
                                        token_valid = False
                            except Exception as e:
                                logger.error(f"{username} için loginSuccessData.json dosyası açılamadı: {str(e)}")
                                token_valid = False
                            
                            
                            
                            # Durumu güncelle
                            with self.lock:
                                self.account_statuses[username]["token_valid"] = token_valid
                                self.account_statuses[username]["token_check_time"] = now
                                
                                # Token geçersizse aktif hesaplardan çıkar ve yeniden login ol
                                if not token_valid:
                                    logger.warning(f"{username} için token geçersiz, yeniden giriş yapılıyor")
                                    
                                    if username in self.active_accounts:
                                        self.active_accounts.remove(username)
                                    
                                    self.loginThreadPool.submit(self._login_account, username)
                                else:
                                    active_count += 1
                                    logger.debug(f"{username} için token geçerli")
                    
                    except Exception as e:
                        logger.error(f"{username} için token kontrolü hatası: {str(e)}")
                        
                        # Durumu güncelle
                        with self.lock:
                            self.account_statuses[username]["token_valid"] = False
                            self.account_statuses[username]["error_count"] += 1
                            self.account_statuses[username]["consecutive_errors"] += 1
                            
                            # Aktif hesaplardan çıkar
                            if username in self.active_accounts:
                                self.active_accounts.remove(username)
                            
                            status["is_active"] = False
                            self.account_statuses[username]["is_active"] = False
                else:
                    inactive_count += 1
                
                # Aktif değilse, belirli aralıklarla yeniden login olmayı dene
                if not status["is_active"]:
                    last_login = status["last_login"]
                    now = datetime.now()
                    consecutive_errors = status["consecutive_errors"]
                    
                    # Hata sayısına göre bekleme süresi (exponential backoff)
                    wait_minutes = min(10, 2 * (2 ** consecutive_errors))
                    
                    # Son login'den beri belirlenen süre geçtiyse yeniden dene
                    if not last_login or (now - last_login).total_seconds() > (wait_minutes * 60):
                        logger.info(f"{username} için yeniden giriş deneniyor (son hatadan sonra {wait_minutes} dk geçti)")
                        self.loginThreadPool.submit(self._login_account, username)
            
            logger.info(f"Sağlık kontrolü: {active_count} aktif, {inactive_count} inaktif hesap")
            
            logger.debug(f"Bir sonraki kontrol için {self.help_check_interval} saniye bekleniyor")
            time.sleep(self.help_check_interval)
    
    def _select_best_account(self):
        """
        Select the most suitable account (load balancing)
        
        Returns:
            str: Selected account username
        """
            
        min_requests = float('inf')
        selected_username = None
        
        for username in self.active_accounts:
            requests = self.request_counters[username]
            if requests < min_requests:
                min_requests = requests
                selected_username = username
        
        if selected_username:      
            with open(self.dataFolder + f"/{selected_username}/loginSuccessData.json", "r") as file:
                login_request_data = json.load(file)
                tokenTest = self.refresh_token(login_request_data)
                if tokenTest:
                    logger.info(f"{selected_username} için token alındı")
                    self.request_counters[selected_username] += 1
                    return selected_username
                else:
                    logger.error(f"{selected_username} için token alınamadı")
                    return None
            
        
    def wait_for_active_accountSession(self):
        """
        Aktif bir hesabın hazır olmasını bekle
        
        Returns:
            str: Aktif hesap kullanıcı adı
        """
        while not self.active_accounts:
            time.sleep(5)
        
        return self._select_best_account()


    def get_next_auth_token(self):
        """
        Sıradaki aktif hesabın auth token'ını döndür (yük dengeleme)
        
        Returns:
            str: Auth token
        """
        username = self._select_best_account()
        
        if not username:
            logger.warning("Aktif hesap bulunamadı, token alınamıyor")
            return None
        
        with self.lock:
            auth_token = self.account_statuses[username]["auth_token"]
            return auth_token

    def get_next_session(self):
        """
        Sıradaki aktif hesabın SeleniumSession'ını döndür (yük dengeleme)
        
        Returns:
            SeleniumSession: SeleniumSession nesnesi
        """
        username = self._select_best_account()
        
        if not username:
            logger.warning("Aktif hesap bulunamadı, SeleniumSession alınamıyor, aktif hesap bekleniyor")
            return None
        
        with self.lock:
            selenium_session = self.account_statuses[username]["selenium_session"]
            # Eğer oturum nesnesi yoksa, sadece klasör yolu atayan hafif bir nesne oluştur
            if selenium_session is None:
                from Helper.SeleniumSession import SeleniumSession  # local import ile döngüden kaçın
                session_dir = f"{self.dataFolder}/{username}"
                selenium_session = SeleniumSession(data_dir=session_dir)
                # Driver başlatılmadı, güvenli.
                self.account_statuses[username]["selenium_session"] = selenium_session
            return selenium_session
    
    def get_active_accounts_count(self):
        """
        Aktif hesap sayısını döndür
        
        Returns:
            int: Aktif hesap sayısı
        """
        with self.lock:
            return len(self.active_accounts)
    
    def get_accounts_status(self):
        """
        Tüm hesapların durumunu döndür
        
        Returns:
            dict: Hesap durumları
        """
        result = {} 
        with self.lock:
            for username, status in self.account_statuses.items():
                result[username] = {
                    "is_active": status["is_active"],
                    "token_valid": status["token_valid"],
                    "last_login": status["last_login"].isoformat() if status["last_login"] else None,
                    "token_check_time": status["token_check_time"].isoformat() if status["token_check_time"] else None,
                    "error_count": status["error_count"],
                    "consecutive_errors": status["consecutive_errors"],
                    "request_count": self.request_counters.get(username, 0)
                }
        return result
    
    def refresh_sessions(self):
        """
        Tüm hesaplar için yeniden giriş yapılır
        
        Returns:
            dict: İşlem sonuçları
        """
        results = {}
        
        for username in self.accounts_map.keys():
            logger.info(f"{username} için yeniden giriş yapılıyor (manuel)")
            success = self.loginThreadPool.submit(self._login_account, username).result()
            results[username] = success
        
        return results
    
    def reset_request_counters(self):
        """
        İstek sayaçlarını sıfırla
        """
        with self.lock:
            for username in self.request_counters:
                self.request_counters[username] = 0
        
        logger.info("İstek sayaçları sıfırlandı")
        
    def close(self):
        """
        SeleniumSessionManager'ı kapat
        
        Returns:
            bool: Kapatma işlemi başarılı ise True, değilse False
        """
        logger.info("SeleniumSessionManager kapatılıyor...")
        
        # Thread havuzunu kapat
        self.loginThreadPool.shutdown(wait=True)
        
        # Tüm hesapların SeleniumSession'larını kapat
        for username, status in self.account_statuses.items():
            if status["selenium_session"]:
                try:
                    status["selenium_session"].quit_driver()
                    logger.info(f"{username} için SeleniumSession kapatıldı")
                except Exception as e:
                    pass
        logger.info("SeleniumSessionManager kapatıldı")
        return True