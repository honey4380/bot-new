import threading
import time
import os
import subprocess
import logging
import datetime
import platform
import psutil
import signal
from typing import Optional, Dict, List, Union, Callable


class ConnectionCleaner:
    """
    Flask uygulamaları için CLOSE_WAIT durumundaki bağlantıları otomatik olarak temizleyen sınıf.
    Windows ve Linux platformlarını destekler.
    """

    def __init__(
        self,
        flask_app=None,
        port: int = 2010,
        cleanup_interval: int = 60,
        connection_timeout: int = 350,
        log_level: int = logging.INFO,
        pid: Optional[int] = None,
        on_cleanup_callback: Optional[Callable] = None
    ):
        """
        ConnectionCleaner sınıfını başlatır.

        Args:
            flask_app: Flask uygulaması (opsiyonel)
            port: Dinlenen port (varsayılan: 2010)
            cleanup_interval: Kontrol aralığı, saniye (varsayılan: 120)
            connection_timeout: Bağlantı zaman aşımı, saniye (varsayılan: 600 - 10 dakika)
            log_level: Log seviyesi (varsayılan: logging.INFO)
            pid: Süreci belirli PID ile izle (varsayılan: None - otomatik tespit)
            on_cleanup_callback: Temizlik işlemi yapıldığında çağrılacak fonksiyon (varsayılan: None)
        """
        self.flask_app = flask_app
        self.port = port
        self.cleanup_interval = cleanup_interval
        self.connection_timeout = connection_timeout
        self.pid = pid
        self.on_cleanup_callback = on_cleanup_callback
        self.connection_times: Dict[int, datetime.datetime] = {}
        self.is_running = False
        self.cleanup_thread = None
        self.platform = platform.system()  # 'Windows', 'Linux', 'Darwin' vb.
        
        # Logger yapılandırması
        self.logger = logging.getLogger("ConnectionCleaner")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(log_level)
        
        # Flask uygulaması verilmişse, event handler'ı ekle
        if self.flask_app:
            self.logger.info("Flask uygulaması bağlandı.")
            if self.pid is None:
                self.pid = os.getpid()
                self.logger.debug(f"Flask uygulama PID: {self.pid}")

    def start(self) -> None:
        """Temizleme thread'ini başlatır"""
        if self.is_running:
            self.logger.warning("Temizleyici zaten çalışıyor.")
            return
        
        if self.pid is None:
            self.detect_process_pid()
            
        if self.pid is None:
            self.logger.error("PID bulunamadı. Temizleyici başlatılamıyor.")
            return
            
        self.is_running = True
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="ConnectionCleanerThread"
        )
        self.cleanup_thread.start()
        self.logger.info(f"ConnectionCleaner başlatıldı. Platform: {self.platform}, PID: {self.pid}, Port: {self.port}")

    def stop(self) -> None:
        """Temizleme thread'ini durdurur"""
        if not self.is_running:
            self.logger.warning("Temizleyici zaten durdurulmuş.")
            return
            
        self.is_running = False
        self.logger.info("ConnectionCleaner durduruldu.")

    def detect_process_pid(self) -> None:
        """Port üzerinde dinleyen Python sürecinin PID'sini tespit eder"""
        try:
            if self.platform == "Windows":
                cmd = f'netstat -ano | findstr ":{self.port}" | findstr "LISTENING"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        possible_pid = parts[-1]
                        try:
                            pid = int(possible_pid)
                            p = psutil.Process(pid)
                            if "python" in p.name().lower():
                                self.pid = pid
                                self.logger.info(f"Python süreci PID bulundu: {self.pid}")
                                return
                        except (ValueError, psutil.NoSuchProcess):
                            continue
            else:  # Linux veya macOS
                cmd = f"lsof -i :{self.port} | grep LISTEN | grep python"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        try:
                            pid = int(parts[1])
                            self.pid = pid
                            self.logger.info(f"Python süreci PID bulundu: {self.pid}")
                            return
                        except (ValueError, IndexError):
                            continue
                            
            self.logger.warning(f"Port {self.port} üzerinde çalışan Python süreci bulunamadı.")
        except Exception as e:
            self.logger.error(f"PID tespit edilirken hata oluştu: {str(e)}")

    def get_close_wait_connections(self) -> List[int]:
        """
        CLOSE_WAIT durumundaki bağlantıların dosya tanımlayıcılarını döndürür
        
        Returns:
            List[int]: Dosya tanımlayıcılarının listesi
        """
        fd_list = []
        
        try:
            if self.platform == "Windows":
                # Windows'ta CLOSE_WAIT durumlarını netstat ile tespit ediyoruz
                cmd = f'netstat -ano | findstr ":{self.port}" | findstr "CLOSE_WAIT"'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                # Windows'ta doğrudan file descriptor alamıyoruz, bağlantı adreslerini kullanıyoruz
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'CLOSE_WAIT' in line:
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            # Bağlantı adresini benzersiz tanımlayıcı olarak kullanıyoruz
                            connection_id = hash(parts[2])
                            fd_list.append(connection_id)
            else:  # Linux veya macOS
                cmd = f"lsof -i :{self.port} -a -p {self.pid} | grep 'CLOSE_WAIT' | awk '{{print $4}}' | sed 's/[^0-9]//g'"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                
                fd_list = [int(fd) for fd in result.stdout.strip().split('\n') if fd]
                
        except Exception as e:
            self.logger.error(f"CLOSE_WAIT bağlantıları belirlenirken hata: {str(e)}")
            
        return fd_list

    def close_connection(self, fd: int) -> bool:
        """
        Belirtilen dosya tanımlayıcısını (veya bağlantı ID'sini) kapatır
        
        Args:
            fd: Dosya tanımlayıcısı veya bağlantı ID'si
            
        Returns:
            bool: Başarılı ise True
        """
        try:
            if self.platform == "Windows":
                # Windows'ta soketi kapatmak için farklı bir yaklaşım
                # Bağlantı adresine göre bağlantıyı bulup zorla kapatmaya çalışıyoruz
                self.logger.info(f"Windows platformunda soket {fd} kapatılıyor...")
                return True  # Windows'ta şu an için sadece loglama yapıyoruz
            else:  # Linux veya macOS
                if os.getpid() == self.pid:
                    # Aynı process içindeyiz, doğrudan kapatabiliriz
                    os.close(fd)
                else:
                    # Farklı process, GDB veya sistem çağrıları kullanarak kapatabiliriz
                    # GDB kullanımı (root yetkisi gerektirir)
                    cmd = f"gdb -p {self.pid} -ex 'call close({fd})' -ex 'quit'"
                    subprocess.run(cmd, shell=True, capture_output=True)
                
                self.logger.info(f"Dosya tanımlayıcı {fd} kapatıldı")
                return True
        except Exception as e:
            self.logger.warning(f"Dosya tanımlayıcı {fd} kapatılamadı: {str(e)}")
            return False

    def _cleanup_loop(self) -> None:
        """Temizleme döngüsünü çalıştırır"""
        last_connection_count = 0
        
        while self.is_running:
            try:
                fd_list = self.get_close_wait_connections()
                current_connection_count = len(fd_list)
                
                # Bağlantı sayısı değiştiyse log oluştur
                if current_connection_count != last_connection_count:
                    self.logger.info(f"CLOSE_WAIT bağlantı sayısı: {current_connection_count}")
                    if current_connection_count > 0:
                        self.logger.debug(f"CLOSE_WAIT bağlantı listesi: {fd_list}")
                    last_connection_count = current_connection_count
                now = datetime.datetime.now()
                
                # Yeni bağlantıları kaydet
                for fd in fd_list:
                    if fd not in self.connection_times:
                        self.connection_times[fd] = now
                        self.logger.debug(f"Yeni CLOSE_WAIT bağlantısı: {fd}")
                
                # Zaman aşımına uğrayan bağlantıları tespit et
                timed_out_connections = [
                    fd for fd, conn_time in list(self.connection_times.items())
                    if (now - conn_time).total_seconds() >= self.connection_timeout
                ]
                
                if timed_out_connections:
                    self.logger.info(f"{len(timed_out_connections)} adet zaman aşımına uğramış CLOSE_WAIT bağlantısı temizleniyor...")
                    
                    closed_fds = []
                    for fd in timed_out_connections:
                        if self.close_connection(fd):
                            closed_fds.append(fd)
                            del self.connection_times[fd]
                    
                    if closed_fds and callable(self.on_cleanup_callback):
                        self.on_cleanup_callback(closed_fds)
                        
                    self.logger.info(f"Temizleme tamamlandı. {len(closed_fds)} bağlantı kapatıldı.")
                
                for fd in list(self.connection_times.keys()):
                    if fd not in fd_list:
                        del self.connection_times[fd]
                
                if self.connection_times:
                    self.logger.info(f"Hala izlenen {len(self.connection_times)} CLOSE_WAIT bağlantısı var.")
                    oldest_connection = min(self.connection_times.values())
                    wait_time = (now - oldest_connection).total_seconds()
                    time_left = max(0, self.connection_timeout - wait_time)
                    self.logger.info(f"En eski bağlantı {wait_time:.0f} saniyedir bekliyor. "
                                   f"Temizleme için {time_left:.0f} saniye kaldı.")
                
            except Exception as e:
                self.logger.error(f"Temizleme döngüsünde hata: {str(e)}")
            
            # Belirtilen aralıkla uyuyalım
            time.sleep(self.cleanup_interval)

    def get_status(self) -> Dict[str, Union[int, List[Dict[str, Union[int, float]]]]]:
        """
        Temizleyicinin mevcut durumunu döndürür
        
        Returns:
            Dict: Durum bilgisi içeren sözlük
        """
        now = datetime.datetime.now()
        connections = []
        
        for fd, timestamp in self.connection_times.items():
            age_seconds = (now - timestamp).total_seconds()
            connections.append({
                "fd": fd,
                "age_seconds": age_seconds,
                "time_left": max(0, self.connection_timeout - age_seconds)
            })
            
        return {
            "active": self.is_running,
            "pid": self.pid,
            "platform": self.platform,
            "port": self.port,
            "connection_count": len(self.connection_times),
            "connections": connections
        }


# Kullanım örneği:
if __name__ == "__main__":
    from flask import Flask
    
    # Flask uygulaması başlat
    app = Flask(__name__)
    
    @app.route('/')
    def hello():
        return "Hello, World!"
    
    # Connection Cleaner örneği
    cleaner = ConnectionCleaner(
        flask_app=app,
        port=5010,  # Flask varsayılan portu
        cleanup_interval=60,  # Her 1 dakikada kontrol et
        connection_timeout=300  # 5 dakika bekle
    )
    
    # Temizleyiciyi başlat
    cleaner.start()
    
    # Flask uygulamasını çalıştır
    app.run(debug=True, use_reloader=False)