from flask import Flask, jsonify, request, redirect, render_template
from flasgger import Swagger
from datetime import datetime, timedelta
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt
from main import FenomenSession
from SeleniumManager import SeleniumSessionManager
import json
import threading
import time
from random import randint
from bonusController import CampaignController, IBonusControlRequest
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
import os

import logging



import time_machine


logger = logging.getLogger(__name__)

import faulthandler
faulthandler.enable()

from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp


seleniumManager = SeleniumSessionManager("data/ACCOUNTS.json")


app = Flask(__name__)
swagger = Swagger(app)

app.config['JWT_SECRET_KEY'] = 'fenomen_7x4K9#mP2$vL5@nW8*qR3'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=365)
jwt = JWTManager(app)
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=365)

# API servis durumu için global değişken
api_service_active = True

# API durumunu izleyen değişkenler
api_status = {
    "is_active": True,
    "stopped_at": None,
    "resumed_at": datetime.now(),
    "stopped_by": None,
    "resumed_by": None
}

# API servis durumunu kontrol eden decorator
def check_api_status(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not api_status["is_active"]:
            inactive_time = None
            if api_status["stopped_at"]:
                inactive_time = datetime.now() - api_status["stopped_at"]
                inactive_seconds = inactive_time.total_seconds()
                hours, remainder = divmod(inactive_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                inactive_time_str = f"{int(hours)}s {int(minutes)}d {int(seconds)}s"
            else:
                inactive_time_str = "bilinmiyor"
                
            stopped_by = api_status["stopped_by"] or "bilinmeyen kullanıcı"
            
            return jsonify({
                "success": False,
                "error": "API servisi şu anda devre dışı",
                "inactive_since": api_status["stopped_at"].isoformat() if api_status["stopped_at"] else None,
                "inactive_duration": inactive_time_str,
                "stopped_by": stopped_by
            }), 503
        return f(*args, **kwargs)
    return decorated_function

token_stats = {
    "last_check_time": datetime.now(),
    "token_alive_since": datetime.now(),
    "previous_token_lifetime": None,
    "is_token_alive": True,
    "token_death_time": None 
}

fenomen_session = FenomenSession(seleniumManager)
bonus_controller = CampaignController(seleniumManager)

executor = ThreadPoolExecutor(max_workers=3)
workerCount = 10
bonus_executor = ThreadPoolExecutor(max_workers=workerCount, thread_name_prefix="bonus")
for i in range(workerCount):
    bonus_executor.submit(lambda: None)
    
def shutdown_executors():
    logger.info("Uygulama kapatılıyor, thread havuzları düzgünce kapatılıyor...")
    executor.shutdown(wait=True)
    bonus_executor.shutdown(wait=True)
    logger.info("Thread havuzları başarıyla kapatıldı.")


import atexit
atexit.register(shutdown_executors)

def async_route(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        def run_in_executor():
            with app.app_context():
                return f(*args, **kwargs)
        return executor.submit(run_in_executor).result()
    return wrapped

# API yönetim endpointleri
@app.route('/api/stop', methods=['POST'])
@jwt_required()
def stop_api():
    """
    API servisini durdur
    ---
    tags:
      - API Management
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            reason:
              type: string
              example: "Bakım çalışması"
              description: "Durdurma sebebi (opsiyonel)"
    responses:
      200:
        description: API servisi başarıyla durduruldu
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            stopped_at:
              type: string
              format: date-time
            stopped_by:
              type: string
      401:
        description: Yetkisiz erişim
    """
    global api_status
    
    current_user = get_jwt_identity()
    data = request.get_json() or {}
    reason = data.get('reason', 'Belirtilmemiş')
    
    api_status["is_active"] = False
    api_status["stopped_at"] = datetime.now()
    api_status["stopped_by"] = f"{current_user} ({reason})"
    
    return jsonify({
        "success": True,
        "message": "API servisi durduruldu",
        "stopped_at": api_status["stopped_at"].isoformat(),
        "stopped_by": api_status["stopped_by"]
    })

@app.route('/api/resume', methods=['POST'])
@jwt_required()
def resume_api():
    """
    API servisini devam ettir
    ---
    tags:
      - API Management
    security:
      - Bearer: []
    responses:
      200:
        description: API servisi başarıyla yeniden başlatıldı
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
            resumed_at:
              type: string
              format: date-time
            resumed_by:
              type: string
            stopped_duration:
              type: string
              description: API'nin durdurulmuş olduğu süre
      401:
        description: Yetkisiz erişim
    """
    global api_status
    
    current_user = get_jwt_identity()
    
    stopped_duration = None
    if api_status["stopped_at"]:
        duration = datetime.now() - api_status["stopped_at"]
        total_seconds = duration.total_seconds()
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        stopped_duration = f"{int(hours)}s {int(minutes)}d {int(seconds)}s"
    
    api_status["is_active"] = True
    api_status["resumed_at"] = datetime.now()
    api_status["resumed_by"] = current_user
    
    return jsonify({
        "success": True,
        "message": "API servisi yeniden başlatıldı",
        "resumed_at": api_status["resumed_at"].isoformat(),
        "resumed_by": api_status["resumed_by"],
        "stopped_duration": stopped_duration
    })

@app.route('/api/status', methods=['GET'])
def api_status_check():
    """
    API servisinin durumunu kontrol et
    ---
    tags:
      - API Management
    responses:
      200:
        description: API servis durumu
        schema:
          type: object
          properties:
            is_active:
              type: boolean
            stopped_at:
              type: string
              format: date-time
            resumed_at:
              type: string
              format: date-time
            stopped_by:
              type: string
            resumed_by:
              type: string
            uptime:
              type: string
              description: API'nin çalışma süresi (aktifse)
            downtime:
              type: string
              description: API'nin durdurulma süresi (pasifse)
    """
    current_time = datetime.now()
    
    response = {
        "is_active": api_status["is_active"],
        "stopped_at": api_status["stopped_at"].isoformat() if api_status["stopped_at"] else None,
        "resumed_at": api_status["resumed_at"].isoformat() if api_status["resumed_at"] else None,
        "stopped_by": api_status["stopped_by"],
        "resumed_by": api_status["resumed_by"]
    }
    
    # Uptime veya downtime hesapla
    if api_status["is_active"]:
        if api_status["resumed_at"]:
            uptime = current_time - api_status["resumed_at"]
            total_seconds = uptime.total_seconds()
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            response["uptime"] = f"{int(hours)}s {int(minutes)}d {int(seconds)}s"
    else:
        if api_status["stopped_at"]:
            downtime = current_time - api_status["stopped_at"]
            total_seconds = downtime.total_seconds()
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            response["downtime"] = f"{int(hours)}s {int(minutes)}d {int(seconds)}s"
    
    return jsonify(response)

@app.route('/api/datetime', methods=['GET'])
def get_current_datetime():
    """
    Get current datetime
    ---
    tags:
      - Debugging
    responses:
      200:
        description: Current datetime
    """
    return jsonify({"datetime": datetime.now()})

# 1. Home endpoint
@app.route("/", methods=['GET'])
def home():
    return redirect("/apidocs")

ADMIN_CREDENTIALS = {
    "username": "admin",
    "password": "fenomen2025!"
}

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """
    Admin kullanıcısı için Token oluştur
    ---
    tags:
      - Authentication
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
              example: "admin"
            password:
              type: string
              example: "adminpassword"
    responses:
      200:
        description: Başarılı giriş
      401:
        description: Geçersiz kimlik bilgileri
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if username == ADMIN_CREDENTIALS['username'] and password == ADMIN_CREDENTIALS['password']:
        access_token = create_access_token(identity=username)
        return jsonify({'access_token': access_token}), 200
    
    return jsonify({'error': 'Geçersiz kimlik bilgileri'}), 401

@app.route('/api/protected', methods=['GET'])
@jwt_required()
@check_api_status
def protected():
    """
    Token kontrol
    ---
    tags:
      - Authentication
    security:
      - Bearer: []
    responses:
      200:
        description: Başarılı erişim
      401:
        description: Geçersiz veya eksik token
    """
    current_user = get_jwt_identity()
    return jsonify({'logged_in_as': current_user}), 200

# 2. getUserList endpoint
@app.route('/api/getUserList', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_list():
    """
    Belirli bir tarih aralığındaki kullanıcı listesini getir
    ---
    tags:
      - User Operations
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-26T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2024-12-27T00:00:00"
              description: "Bitiş tarihi"
    responses:
      200:
        description: Kullanıcı listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    
    try:
        try:
          data = request.get_json()
          created_from = datetime.fromisoformat(data['created_from'])
          created_before = datetime.fromisoformat(data['created_before'])
        except:
          return jsonify({"success": False, "error": "Geçersiz istek parametreleri"}), 400
        
        result = fenomen_session.getUserList(created_from, created_before)
        
        
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": "Belirtilen tarih aralığında kullanıcı bulunamadı"}), 204
          
        try:
          if result.get("ResponseCode") == -1:
            if "No player found" in result.get("ResponseMessage", ""):
              return {"data": result, "success": False}, 204
          
            return {"data": result, "success": False}, 404
        except:
          pass
            
        return jsonify({"success": True, "data": result}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 3. getUserData endpoint
@app.route('/api/getUserData/<username>', methods=['GET'])
@jwt_required()
@check_api_status
def get_user_data(username):
    """
    Kullanıcı adına göre kullanıcı bilgilerini getir
    ---
    tags:
      - User Operations
    parameters:
      - name: username
        in: path
        type: string
        required: true
        description: Aranacak kullanıcı adı
    responses:
      200:
        description: Kullanıcı bilgileri başarıyla getirildi
      404:
        description: Kullanıcı bulunamadı
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        result = fenomen_session.getUserData(username)
        user_data = json.loads(result)
        
        if user_data.get("ResponseCode") == -1:
          if "Oturum süresi dolmuş" in user_data.get("ResponseMessage", ""):
            return {"success": False, "error": "Oturum süresi dolmuş"}, 401
          return {"data": user_data, "success": False}, 404
        
        try:
          if not user_data or not user_data.get('ResponseObject', {}).get('Entities'):
              return jsonify({"success": True, "message": f"'{username}' kullanıcı adına sahip kullanıcı bulunamadı"}), 204
        except:
          return jsonify({"success": False, "error": "Kullanıcı bilgileri alınamadı"}), 204
        return jsonify({"success": True, "data": user_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/updateUser/<userId>', methods=['POST'])
@jwt_required()
@check_api_status
def update_user(userId):
    """
    Kullanıcı bilgilerini güncelle
    ---
    tags:
      - User Operations
    parameters:
      - name: userId
        in: path
        type: integer
        required: true
        description: Kullanıcı ID'si
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            Btag:
              type: string
              example: "12122121"
              description: "Btag değeri"
    responses:
      200:
        description: Kullanıcı başarıyla güncellendi
      400:
        description: Geçersiz istek
      500:
        description: Sunucu hatası
    """
    try:
        data = request.get_json()
        
        # Get current user data first
        current_data = fenomen_session.getUserMainInfo(userId)
        if current_data.get("ResponseCode") != 0:
            return jsonify({
                "success": False,
                "error": "Kullanıcı bulunamadı"
            }), 404

        # Update only Btag field
        user_data = current_data["ResponseObject"]
        user_data["Btag"] = data.get("Btag")
        
        result = fenomen_session.updateUser(userId, user_data)
        
        if result.get("ResponseCode") == 0:
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get("ResponseMessage", "Güncelleme başarısız")
            }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/getUserData/<username>/detailed', methods=['GET'])
@jwt_required()
@check_api_status
def get_user_data_detailed(username):
    """
    Kullanıcı adına göre detaylı kullanıcı bilgilerini getir
    ---
    tags:
      - User Operations
    parameters:
      - name: username
        in: path
        type: string
        required: true
        description: Aranacak kullanıcı adı
    responses:
      200:
        description: Kullanıcı bilgileri başarıyla getirildi
      404:
        description: Kullanıcı bulunamadı
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
      result = fenomen_session.getUserDataDetailed(username)
      if result is None:
        return jsonify({"success": True, "message": f"'{username}' kullanıcı adına sahip kullanıcı bulunamadı"}), 404
      
      user_data = json.loads(result)
      
      
      if user_data.get("ResponseCode") == -1:
        if "Oturum süresi dolmuş" in user_data.get("ResponseMessage", ""):
          return {"success": False, "error": "Oturum süresi dolmuş"}, 401
        return {"data": user_data, "success": False}, 404
      
      try:
        if not user_data or not user_data.get('ResponseObject', {}):
          return jsonify({"success": True, "message": f"'{username}' kullanıcı adına sahip kullanıcı bulunamadı"}), 204
      except:
        return jsonify({"success": False, "error": "Kullanıcı bilgileri alınamadı"}), 204
      return jsonify({"success": True, "data": user_data.get('ResponseObject', {})})
    except Exception as e:
      return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getUserMainInfo/<userId>', methods=['GET'])
@jwt_required()
@check_api_status
def get_user_main_info(userId):
  """
  Kullanıcı ID'sine göre detaylı kullanıcı bilgilerini getir
  ---
  tags:
    - User Operations
  parameters:
    - name: userId
      in: path
      type: string
      required: true
      description: Kullanıcı ID'si
  responses:
    200:
      description: Kullanıcı bilgileri başarıyla getirildi
    404:
      description: Kullanıcı bulunamadı
    401:
      description: Oturum süresi dolmuş
    500:
      description: Sunucu hatası
  """
  try:
    result = fenomen_session.getUserMainInfo(userId)
    
    if result.get("ResponseCode") == -1:
      if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
        return {"success": False, "error": "Oturum süresi dolmuş"}, 401
      return {"success": False, "error": result.get("ResponseMessage", "Kullanıcı bilgileri alınamadı")}, 404
    
    if not result or not result.get('ResponseObject'):
      return jsonify({"success": True, "message": f"'{userId}' ID'sine sahip kullanıcı bulunamadı"}), 204
    
    return jsonify({"success": True, "data": result})
  except Exception as e:
    return jsonify({"success": False, "error": str(e)}), 500



@app.route("/api/signalr-ping", methods=['GET'])
@jwt_required()
@check_api_status
def signalr_ping():
    """
    SignalR bağlantısını kontrol et
    ---
    tags:
      - Account Management
    responses:
      200:
        description: SignalR ping başarılı
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: object
              description: SignalR ping yanıtı
            timestamp:
              type: string
              format: date-time 
      401:
        description: Geçersiz token
      500:
        description: Sunucu hatası
    """
    try:
        result = fenomen_session.ping_signalr()
        
        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            return jsonify({
                "success": False,
                "error": result.get("ResponseMessage", "SignalR ping başarısız"),
                "timestamp": datetime.now().isoformat()
            }), 500
            
        return jsonify({
            "success": True,
            "data": result,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "success": False, 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/accounts/status', methods=['GET'])
@jwt_required()
@check_api_status
def accounts_status():
    """
    Tüm hesapların durumunu getir
    ---
    tags:
      - Account Management
    security:
      - Bearer: []
    responses:
      200:
        description: Hesap durumları başarıyla getirildi
      401:
        description: Yetkisiz erişim
    """
    accounts = seleniumManager.get_accounts_status()
    active_count = seleniumManager.get_active_accounts_count()
    
    return jsonify({
        "success": True,
        "accounts": accounts,
        "active_count": active_count,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/accounts/refresh', methods=['POST'])
@jwt_required()
@check_api_status
def refresh_accounts():
    """
    Tüm hesaplar için yeniden giriş yap
    ---
    tags:
      - Account Management
    security:
      - Bearer: []
    responses:
      200:
        description: Hesaplar başarıyla yenilendi
      401:
        description: Yetkisiz erişim
    """
    current_user = get_jwt_identity()
    logger.info(f"Tüm hesaplar için yeniden giriş yapılıyor. İsteyen kullanıcı: {current_user}")
    
    results = seleniumManager.refresh_sessions()
    
    return jsonify({
        "success": True,
        "results": results,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/accounts/counters/reset', methods=['POST'])
@jwt_required()
@check_api_status
def reset_counters():
    """
    İstek sayaçlarını sıfırla
    ---
    tags:
      - Account Management
    security:
      - Bearer: []
    responses:
      200:
        description: Sayaçlar başarıyla sıfırlandı
      401:
        description: Yetkisiz erişim
    """
    current_user = get_jwt_identity()
    logger.info(f"İstek sayaçları sıfırlanıyor. İsteyen kullanıcı: {current_user}")
    
    seleniumManager.reset_request_counters()
    
    return jsonify({
        "success": True,
        "message": "İstek sayaçları sıfırlandı",
        "timestamp": datetime.now().isoformat()
    })
    
@app.route('/api/accounts/update', methods=['POST'])
@jwt_required()
@check_api_status
def update_account():
    """
    Yeni hesap ekle veya var olan hesabı güncelle
    ---
    tags:
      - Account Management
    security:
      - Bearer: []
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
              example: "usertest"
              description: "Hesap kullanıcı adı"
            password:
              type: string
              example: "password123"
              description: "Hesap parolası"
            totp_secret:
              type: string
              example: "JBSWY3DPEHPK3PXP"
              description: "TOTP gizli anahtarı (opsiyonel)"
              required: false
    responses:
      200:
        description: Hesap başarıyla eklendi/güncellendi
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            data:
              type: object
              properties:
                username:
                  type: string
                isLoggedIn:
                  type: boolean
                message:
                  type: string
      400:
        description: Geçersiz istek parametreleri
      401:
        description: Yetkisiz erişim
      500:
        description: Sunucu hatası
    """
    try:
        data = request.get_json()
        
        if not all(key in data for key in ['username', 'password']):
            return jsonify({
                "success": False,
                "error": "username ve password zorunlu alanlardır"
            }), 400
        
        username = data['username']
        password = data['password']
        totp_secret = data.get('totp_secret')
        
        current_user = get_jwt_identity()
        logger.info(f"Hesap güncelleme/ekleme isteği: {username} (İsteyen: {current_user})")
        
        result = seleniumManager.update_account(username, password, totp_secret)
        
        if result.get("isLoggedIn", False):
            logger.info(f"Hesap başarıyla güncellendi/eklendi: {username}")
            return jsonify({
                "success": True,
                "data": result
            })
        else:
            logger.warning(f"Hesap güncellenemedi/eklenemedi: {username}, Mesaj: {result.get('message')}")
            return jsonify({
                "success": False,
                "error": result.get("message", "Hesap güncellenemedi/eklenemedi"),
                "data": result
            }), 400
        
    except Exception as e:
        logger.error(f"Hesap güncelleme/ekleme hatası: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/accounts/delete/<username>', methods=['DELETE'])
@jwt_required()
@check_api_status
def delete_account(username):
    """
    Hesabı sil
    ---
    tags:
      - Account Management
    security:
      - Bearer: []
    parameters:
      - name: username
        in: path
        required: true
        type: string
        description: "Silinecek hesabın kullanıcı adı"
    responses:
      200:
        description: Hesap başarıyla silindi
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            message:
              type: string
              example: "Hesap başarıyla silindi"
      401:
        description: Yetkisiz erişim
      404:
        description: Hesap bulunamadı
      500:
        description: Sunucu hatası
    """
    try:
        current_user = get_jwt_identity()
        logger.info(f"Hesap silme isteği: {username} (İsteyen: {current_user})")
        
        if username not in seleniumManager.accounts_map:
            logger.warning(f"Silinmeye çalışılan hesap bulunamadı: {username}")
            return jsonify({
                "success": False,
                "error": f"{username} hesabı bulunamadı"
            }), 404
        
        # Aktif session sayısını kontrol et
        active_count = seleniumManager.get_active_accounts_count()
        if active_count <= 1 and username in seleniumManager.active_accounts:
            logger.error(f"Son aktif hesap silinemez: {username}")
            return jsonify({
                "success": False,
                "error": "Son aktif hesap silinemez. En az bir aktif hesap olmalıdır."
            }), 400
        
        seleniumManager.delete_account(username)
        
        logger.info(f"Hesap başarıyla silindi: {username}")
        return jsonify({
            "success": True,
            "message": f"{username} hesabı başarıyla silindi"
        })
        
    except Exception as e:
        logger.error(f"Hesap silme hatası ({username}): {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# Get payment System list on Deposit Operations
@app.route('/api/getPaymentSystemList', methods=['POST'])
@jwt_required()
@check_api_status
def get_payment_system_list():
  """
  Ödeme sistemi listesini getir
  ---
  tags:
    - Deposit Operations
  responses:
    200:
      description: Ödeme sistemi listesi başarıyla getirildi
    401:
      description: Oturum süresi dolmuş
    500:
      description: Sunucu hatası
  """
  try:
    result = fenomen_session.getPaymentSystemList()
    
    try:
      if isinstance(result, dict) and result.get("ResponseCode") == -1:
        if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
          return {"success": False, "error": "Oturum süresi dolmuş"}, 401
        return {"data": result, "success": False}, 500
    except:
      pass
      
    if not result or (isinstance(result, list) and len(result) == 0):
      return jsonify({"success": True, "message": "Ödeme sistemi listesi boş"}), 204
        
    return jsonify({"success": True, "data": result})
  except Exception as e:
    return jsonify({"success": False, "error": str(e)}), 500

# 6. getDepositList endpoint
@app.route('/api/getDepositList', methods=['POST'])
@jwt_required()
@check_api_status
def get_deposit_list():
    """
    Belirli bir tarih aralığındaki deposit listesini getir
    ---
    tags:
      - Deposit Operations
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-27T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2024-12-27T12:00:00"
              description: "Bitiş tarihi"
            update_sorting:
              type: boolean
              format: boolean
              example: false
              description: "UpdateDate güncellemeleri (Default CreatedDate)"
    responses:
      200:
        description: Deposit listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        try:
          data = request.get_json()
          try:
            created_from = datetime.fromisoformat(data['created_from'])
            created_before = datetime.fromisoformat(data['created_before'])
            sorting = data.get('update_sorting', False)
          except:
              created_from = datetime.fromisoformat(data['created_from'].replace(" ", "T"))
              created_before = datetime.fromisoformat(data['created_before'].replace(" ", "T"))
              sorting = data.get('update_sorting', False)
        except:
          return jsonify({"success": False, "error": "Geçersiz istek parametreleri"}), 400
        
        result = fenomen_session.getDepositList(created_from, created_before, sorting)
        
        try:
          if result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404
        except:
          pass
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": "Belirtilen tarih aralığında yatırım işlemi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getUserDepositsForId/<userId>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_depositsWithId(userId):
    """
    Belirli bir kullanıcının deposit geçmişini getir
    ---
    tags:
      - Deposit Operations
    parameters:
      - name: userId
        in: path
        type: integer
        required: true
        description: Kullanıcı ID'si
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-08T00:00:00"
              description: "Başlangıç tarihi (Opsiyonel, varsayılan son 30 gün)"
            created_before:
              type: string
              format: date-time
              example: "2025-01-07T00:00:00"  
              description: "Bitiş tarihi (Opsiyonel, varsayılan şu an)"
    responses:
      200:
        description: Kullanıcı deposit listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json() or {}
        created_from = None
        created_before = None
        
        if 'created_from' in data:
            created_from = datetime.fromisoformat(data['created_from'])
        if 'created_before' in data:
            created_before = datetime.fromisoformat(data['created_before'])
            
        result = fenomen_session.getUserDeposits(userId, created_from, created_before)
        
        try:
          if result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404
        except:
          pass
        
        if not result or not result.get('Deposits') or len(result['Deposits']) == 0:
            return jsonify({"success": True, "message": f"{userId} ID'li kullanıcının belirtilen tarih aralığında yatırım işlemi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getUserDepositsForUsername/<username>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_depositsWithUsername(username):
    """
    Belirli bir kullanıcının deposit geçmişini getir
    ---
    tags:
      - Deposit Operations
    parameters:
      - name: username
        in: path
        type: string
        required: true
        description: Kullanıcı adı
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-08T00:00:00"
              description: "Başlangıç tarihi (Opsiyonel, varsayılan son 30 gün)"
            created_before:
              type: string
              format: date-time
              example: "2025-01-07T00:00:00"  
              description: "Bitiş tarihi (Opsiyonel, varsayılan şu an)"
    responses:
      200:
        description: Kullanıcı deposit listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json() or {}
        created_from = None
        created_before = None
        
        if 'created_from' in data:
            created_from = datetime.fromisoformat(data['created_from'])
        if 'created_before' in data:
            created_before = datetime.fromisoformat(data['created_before'])
        
        userData = json.loads(fenomen_session.getUserData(username))
        
        try:
          if userData.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in userData.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": userData, "success": False}, 404
        except:
          pass
        
        if not userData or not userData.get("ResponseObject", {}).get("Entities"):
            return jsonify({"success": True, "message": f"'{username}' kullanıcı adına sahip kullanıcı bulunamadı"}), 204
            
        userId = int(userData.get("ResponseObject", {}).get("Entities", [{}])[0].get("Id"))
        result = fenomen_session.getUserDeposits(userId, created_from, created_before)
        
        try:
          if result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404
        except:
          pass
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"'{username}' kullanıcısının belirtilen tarih aralığında yatırım işlemi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Bets Operations

@app.route('/api/getUserGamingHistoryForID/<userId>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_gamingHistoryWithId(userId):
    """
    Belirli bir kullanıcının oyun geçmişini getir
    ---
    tags:
      - Gaming Operations
    parameters:
      - name: userId
        in: path
        type: integer
        required: true
        description: Kullanıcı ID'si
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-08T00:00:00"
              description: "Başlangıç tarihi (Opsiyonel, varsayılan son 30 gün)"
            created_before:
              type: string
              format: date-time
              example: "2025-01-07T00:00:00"  
              description: "Bitiş tarihi (Opsiyonel, varsayılan şu an)"
    responses:
      200:
        description: Kullanıcı oyun geçmişi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json() or {}
        created_from = None
        created_before = None
        
        if 'created_from' in data:
            created_from = datetime.fromisoformat(data['created_from'])
        if 'created_before' in data:
            created_before = datetime.fromisoformat(data['created_before'])
            
        if not created_from:
            created_from = datetime.now() - timedelta(days=30)
        if not created_before:
            created_before = datetime.now()
        print(userId)
        result = fenomen_session.getGamingHistory(created_from, created_before, userId=userId)
        
        try:
          if result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404
        except:
          pass
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"'{userId}' id'li kullanıcının belirtilen tarih aralığında oyun geçmişi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getUserGamingHistoryForUsername/<username>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_gamingHistoryWithUsername(username):
    """
    Belirli bir kullanıcının oyun geçmişini getir
    ---
    tags:
      - Gaming Operations
    parameters:
      - name: username
        in: path
        type: string
        required: true
        description: Kullanıcı adı
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-08T00:00:00"
              description: "Başlangıç tarihi (Opsiyonel, varsayılan son 30 gün)"
            created_before:
              type: string
              format: date-time
              example: "2025-01-07T00:00:00"  
              description: "Bitiş tarihi (Opsiyonel, varsayılan şu an)"
    responses:
      200:
        description: Kullanıcı oyun geçmişi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json() or {}
        created_from = None
        created_before = None
        
        if 'created_from' in data:
            created_from = datetime.fromisoformat(data['created_from'])
        if 'created_before' in data:
            created_before = datetime.fromisoformat(data['created_before'])
            
        if not created_from:
            created_from = datetime.now() - timedelta(days=30)
        if not created_before:
            created_before = datetime.now()
            
        userData = json.loads(fenomen_session.getUserData(username))
        try:
          if not userData or not userData.get("ResponseObject", {}).get("Entities"):
              return jsonify({"success": True, "message": f"'{username}' kullanıcı adına sahip kullanıcı bulunamadı"}), 204
              
          userId = int(userData.get("ResponseObject", {}).get("Entities", [{}])[0].get("Id"))
        except:
          return jsonify({"success": False, "error": "Kullanıcı bilgileri bulunamadı"}), 400
        result = fenomen_session.getGamingHistory(created_from, created_before, userId)
        
        try:
          if result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404
        except:
          pass
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"'{username}' kullanıcısının belirtilen tarih aralığında oyun geçmişi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getTransactionsForId/<userId>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_transactionsWithId(userId):
    """
    Belirli bir kullanıcının işlem geçmişini getir
    ---
    tags:
      - Transaction Operations
    parameters:
      - name: userId
        in: path
        type: integer
        required: true
        description: Kullanıcı ID'si
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2025-01-15T00:00:00"
              description: "Başlangıç tarihi (Format: YYYY-MM-DDTHH:mm:ss)"
            created_before:
              type: string
              format: date-time
              example: "2025-01-15T02:00:00"
              description: "Bitiş tarihi (Format: YYYY-MM-DDTHH:mm:ss)"
            operationTypeIds:
              type: array
              items:
                type: integer
              example: [1, 2, 3]
              description: "İşlem tipi ID'leri (Opsiyonel, varsayılan tüm işlemler)"
              required: false
    responses:
      200:
        description: Kullanıcı işlem geçmişi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        try:
            data = request.get_json()
            # Tarihleri parçalara ayırıp datetime oluştur
            from_parts = data['created_from'].split('T')
            to_parts = data['created_before'].split('T')
            operationTypeIds = data.get('operationTypeIds', None)
            
            from_date = from_parts[0].split('-')
            from_time = from_parts[1].split(':')
            
            to_date = to_parts[0].split('-')
            to_time = to_parts[1].split(':')
            
            created_from = datetime(
                int(from_date[0]),  # year
                int(from_date[1]),  # month
                int(from_date[2]),  # day
                int(from_time[0]),  # hour
                int(from_time[1]),  # minute
                int(from_time[2])   # second
            )
            
            created_before = datetime(
                int(to_date[0]),    # year
                int(to_date[1]),    # month
                int(to_date[2]),    # day
                int(to_time[0]),    # hour
                int(to_time[1]),    # minute
                int(to_time[2])     # second
            )
            
        except Exception as e:
            return jsonify({
                "success": False, 
                "error": "Geçersiz tarih formatı. Örnek format: YYYY-MM-DDTHH:mm:ss (2025-01-15T00:00:00)"
            }), 400
            
        result = fenomen_session.getTransactions(created_from, created_before, userId, operationTypeIds)
        
        try:
            if result.get("ResponseCode") == -1:
                if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                    return {"success": False, "error": "Oturum süresi dolmuş"}, 401
                return {"data": result, "success": False}, 404
        except:
            pass
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"{userId} ID'li kullanıcının belirtilen tarih aralığında işlem geçmişi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getTransactionsForUsername/<username>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_transactionsWithUsername(username):
    """
    Belirli bir kullanıcının işlem geçmişini getir
    ---
    tags:
      - Transaction Operations
    parameters:
      - name: username
        in: path
        type: string
        required: true
        description: Kullanıcı adı
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2025-01-15T00:00:00"
              description: "Başlangıç tarihi (Format: YYYY-MM-DDTHH:mm:ss)"
            created_before:
              type: string
              format: date-time
              example: "2025-01-15T02:00:00"
              description: "Bitiş tarihi (Format: YYYY-MM-DDTHH:mm:ss)"
            operationTypeIds:
              type: array
              items:
                type: integer
              example: [1, 2, 3]
              description: "İşlem tipi ID'leri (Opsiyonel, varsayılan tüm işlemler)"
              required: false
    responses:
      200:
        description: Kullanıcı işlem geçmişi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        try:
            data = request.get_json()
            # Tarihleri parçalara ayırıp datetime oluştur
            from_parts = data['created_from'].split('T')
            to_parts = data['created_before'].split('T')
            operationTypeIds = data.get('operationTypeIds', None)
            
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
            
        except Exception as e:
            return jsonify({
                "success": False, 
                "error": "Geçersiz tarih formatı. Örnek format: YYYY-MM-DDTHH:mm:ss (2025-01-15T00:00:00)"
            }), 400
            
        userData = json.loads(fenomen_session.getUserData(username))
        if not userData or not userData.get("ResponseObject", {}).get("Entities"):
            return jsonify({"success": True, "message": f"'{username}' kullanıcı adına sahip kullanıcı bulunamadı"}), 204
            
        userId = int(userData.get("ResponseObject", {}).get("Entities", [{}])[0].get("Id"))
        result = fenomen_session.getTransactions(created_from, created_before, userId, operationTypeIds)
        
        try:
            if result.get("ResponseCode") == -1:
                if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                    return {"success": False, "error": "Oturum süresi dolmuş"}, 401
                return {"data": result, "success": False}, 404
        except:
            pass
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"'{username}' kullanıcısının belirtilen tarih aralığında işlem geçmişi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getEnumList', methods=['GET'])
@jwt_required()
@check_api_status
def get_enum_list():
    """
    Kullanılabilicek tüm varyasyonları getirirlistesini getir
    ---
    tags:
      - Bonus Operations
    responses:
      200:
        description: Kullanılabilicek tüm varyasyonların listesi başarıyla getirildi
      401:
        description: Oturum süresi dolmuş
      500:
        description: Sunucu hatası
    """
    try:
        result = fenomen_session.getEnumList()
        
        try:
            if result.get("ResponseCode") == -1:
                if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                    return {"success": False, "error": "Oturum süresi dolmuş"}, 401
                return {"data": result, "success": False}, 404
        except:
            pass
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getPlayerBonuses/<userId>', methods=['POST'])
@jwt_required()
@check_api_status
def get_player_bonuses(userId):
    """
    Kullanıcının bonus geçmişini getir
    ---
    tags:
      - Bonus Operations
    parameters:
      - name: userId
        in: path
        type: integer
        required: true
        description: Kullanıcı ID'si
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2025-01-14T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2025-01-15T02:00:00"
              description: "Bitiş tarihi"
            IsActiveBonuses:
              type: boolean
              example: false
              description: "Aktif bonuslar mı? (true/false)"
            productType:
              type: integer
              example: null
              description: |
                Ürün tipi ID'si (Opsiyonel)
            bonusType:
              type: integer
              example: null  
              description: |
                Bonus tipi ID'si (Opsiyonel)
    responses:  
      200:
        description: Bonus listesi başarıyla getirildi
        schema:
          type: object
          properties:
            success:
              type: boolean
              example: true
            data:
              type: array
              items:
                type: object
                properties:
                  Id:
                    type: integer
                  BonusType:
                    type: integer
                  ProductType:
                    type: integer
                  Amount:
                    type: number
                  Status:
                    type: integer
                  CreatedAt:
                    type: string
                    format: date-time
      400:
        description: Geçersiz istek parametreleri
      401:
        description: Oturum süresi dolmuş
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json()
        
        try:
            from_parts = data['created_from'].split('T')
            to_parts = data['created_before'].split('T')
            
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
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Geçersiz tarih formatı. Örnek format: YYYY-MM-DDTHH:mm:ss (2025-01-15T00:00:00)"
            }), 400
            
        IsActiveBonuses = data.get('IsActiveBonuses')
        productType = data.get('productType')
        bonusType = data.get('bonusType')
        
        result = fenomen_session.getPlayerBonuses(created_from, created_before, userId,IsActiveBonuses, productType, bonusType)
        
        try:
            if result.get("ResponseCode") == -1:
                if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                    return {"success": False, "error": "Oturum süresi dolmuş"}, 401
                return {"data": result, "success": False}, 404
        except:
            pass
            
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"{userId} ID'li kullanıcının belirtilen tarih aralığında bonus işlemi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/getOperationTypes', methods=['GET'])
@jwt_required()
@check_api_status
def get_operation_types():
    """
    İşlem tiplerini listele
    ---
    tags:
      - Transaction Operations
    responses:
      200:
        description: İşlem tipleri başarıyla getirildi
      401:
        description: Oturum süresi dolmuş
      500:
        description: Sunucu hatası
    """
    try:
        result = fenomen_session.getOperationTypes()
        
        try:
            if isinstance(result, dict) and result.get("ResponseCode") == -1:
                if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                    return {"success": False, "error": "Oturum süresi dolmuş"}, 401
                return {"data": result, "success": False}, 404
        except:
            pass
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getWithdrawList', methods=['POST'])
@jwt_required()
@check_api_status
def get_withdraw_list():
    """
    Belirli bir tarih aralığındaki çekim listesini getir
    ---
    tags:
      - Withdraw Operations  
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-27T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2024-12-27T12:00:00"
              description: "Bitiş tarihi"
            update_sorting:
              type: boolean
              format: boolean
              example: false
              description: "UpdateDate sıralaması (Default false: CreatedDate sıralaması)"
    responses:
      200:
        description: Çekim listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        try:
          data = request.get_json()
          created_from = datetime.fromisoformat(data['created_from'])
          created_before = datetime.fromisoformat(data['created_before'])
          update_sorting = data.get('update_sorting', False)
        except:
          return jsonify({"success": False, "error": "Geçersiz istek parametreleri"}), 400
        
        result = fenomen_session.getWithdrawList(created_from, created_before,updateSorting=update_sorting)
        
        try:
          if result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404
        except:
          pass
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": "Belirtilen tarih aralığında çekim işlemi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getUserWithdrawsForId/<userId>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_withdrawsWithId(userId):
    """
    Belirli bir kullanıcının çekim geçmişini getir
    ---
    tags:
      - Withdraw Operations
    parameters:
      - name: userId
        in: path
        type: integer
        required: true
        description: Kullanıcı ID'si
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-08T00:00:00"
              description: "Başlangıç tarihi (Opsiyonel, varsayılan son 30 gün)"
            created_before:
              type: string
              format: date-time
              example: "2025-01-07T00:00:00"  
              description: "Bitiş tarihi (Opsiyonel, varsayılan şu an)"
    responses:
      200:
        description: Kullanıcı çekim listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri  
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json() or {}
        created_from = None
        created_before = None
        
        if 'created_from' in data:
            created_from = datetime.fromisoformat(data['created_from'])
        if 'created_before' in data:
            created_before = datetime.fromisoformat(data['created_before'])
            
        result = fenomen_session.getWithdrawList(created_from, created_before, userId)
        
        try:
          if result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404
        except:
          pass
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"{userId} ID'li kullanıcının belirtilen tarih aralığında çekim işlemi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getUserWithdrawsForUsername/<username>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_withdrawsWithUsername(username):
    """
    Belirli bir kullanıcının çekim geçmişini getir
    ---
    tags:
      - Withdraw Operations
    parameters:
      - name: username
        in: path
        type: string
        required: true
        description: Kullanıcı adı
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-08T00:00:00"
              description: "Başlangıç tarihi (Opsiyonel, varsayılan son 30 gün)"
            created_before:
              type: string
              format: date-time
              example: "2025-01-07T00:00:00"  
              description: "Bitiş tarihi (Opsiyonel, varsayılan şu an)"
    responses:
      200:
        description: Kullanıcı çekim listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası 
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json() or {}
        created_from = None
        created_before = None
        
        if 'created_from' in data:
            created_from = datetime.fromisoformat(data['created_from'])
        if 'created_before' in data:
            created_before = datetime.fromisoformat(data['created_before'])
        
        userData = json.loads(fenomen_session.getUserData(username))
        
        try:
          if userData.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in userData.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": userData, "success": False}, 404
        except:
          pass
        
        if not userData or not userData.get("ResponseObject", {}).get("Entities"):
            return jsonify({"success": True, "message": f"'{username}' kullanıcı adına sahip kullanıcı bulunamadı"}), 204
            
        userId = int(userData.get("ResponseObject", {}).get("Entities", [{}])[0].get("Id"))
        result = fenomen_session.getWithdrawList(created_from, created_before, userId)
        
        try:
          if result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
              return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404
        except:
          pass
        
        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"'{username}' kullanıcısının belirtilen tarih aralığında çekim işlemi bulunamadı"}), 204
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/getActiveDomain', methods=['GET'])
@jwt_required()
@check_api_status
def get_active_domain():
    """
    
    Aktif alan adını getir
    ---
    tags:
      - Authentication
    responses:
      200:
        description: Aktif alan adı başarıyla getirildi
        schema:
          type: object
          properties:
            success:
              type: boolean
              description: İşlem başarılı mı
            activeDomain:
              type: string
              description: Aktif alan adı
      500:
        description: Sunucu hatası
    """
    try:
        active_domain = fenomen_session.getActiveDomain()
        return jsonify({"success": True, "activeDomain": active_domain})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/check-token', methods=['GET'])
@jwt_required()
@check_api_status
def check_token():
    """
    JWT token süresini kontrol et
    ---
    tags:
      - Authentication
    responses:
      200:
        description: Token durumu
        schema:
          type: object
          properties:
            valid:
              type: boolean
              description: Token'ın geçerli olup olmadığı
            expires_in:
              type: integer
              description: Kalan süre (saniye)
            expires_at:
              type: string
              description: Bitiş zamanı (ISO format)
            formatted_time_left:
              type: string
              description: Kalan süre (formatlanmış)
      401:
        description: Geçersiz veya süresi dolmuş token
    """
    try:
        jwt_data = get_jwt()
        exp_timestamp = jwt_data.get("exp")
        current_timestamp = datetime.now().timestamp()
        
        expires_in = int(exp_timestamp - current_timestamp)
        expires_at = datetime.fromtimestamp(exp_timestamp)
        
        years = expires_in // (365*24*3600)
        remaining = expires_in % (365*24*3600)
        days = remaining // (24*3600)
        remaining = remaining % (24*3600)
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        
        formatted_time = f"{years} year, {days} day, {hours} hour, {minutes} min"
        
        return jsonify({
            "valid": expires_in > 0,
            "expires_in": expires_in if expires_in > 0 else 0,
            "expires_at": expires_at.isoformat(),
            "formatted_time_left": formatted_time if expires_in > 0 else "Token süresi dolmuş"
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "valid": False,
            "message": "Token geçersiz veya süresi dolmuş"
        }), 401

@app.route('/api/getUserCasinoBetsForUsername/<username>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_casino_bets_username(username):
    """
    Belirli bir kullanıcının casino bet geçmişini getir
    ---
    tags:
      - Bets Operations
    parameters:
      - name: username
        in: path
        type: string
        required: true
        description: Kullanıcı adı
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-27T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2024-12-27T12:00:00"
              description: "Bitiş tarihi"
            stateIds:
              type: array
              items:
                type: integer
              example: []
              description: "Durum ID'leri (Opsiyonel)"
    responses:
      200:
        description: Kullanıcının casino bet listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json()
        created_from = datetime.fromisoformat(data['created_from'])
        created_before = datetime.fromisoformat(data['created_before'])
        stateIds = data.get('stateIds')

        # Önce kullanıcı ID'sini al
        userData = json.loads(fenomen_session.getUserData(username))
        if not userData or not userData.get("ResponseObject", {}).get("Entities"):
            return jsonify({"success": True, "message": f"'{username}' kullanıcı adına sahip kullanıcı bulunamadı"}), 204

        userId = int(userData.get("ResponseObject", {}).get("Entities", [{}])[0].get("Id"))
        result = fenomen_session.getCasinoBets(created_from, created_before, userId,stateIds)

        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404

        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"'{username}' kullanıcısının belirtilen tarih aralığında casino bet işlemi bulunamadı"}), 204

        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/GetCasinoBetsReport', methods=['POST'])
@jwt_required()
@check_api_status
def get_casino_bets_report():
    """
    Casino betlerinin raporunu getir
    ---
    tags:
      - Bets Operations
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-27T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2024-12-27T12:00:00"
              description: "Bitiş tarihi"
            stateIds:
              type: array
              items:
                type: integer
              example: []
              description: "Durum ID'leri (Opsiyonel)"
    responses:
      200:
        description: Casino bet raporu başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json()
        created_from = datetime.fromisoformat(data['created_from'])
        created_before = datetime.fromisoformat(data['created_before'])
        stateIds = data.get('stateIds')

        result = fenomen_session.getCasinoBetsGeneralReport(created_from, created_before, stateIds)

        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404

        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"Belirtilen tarih aralığında casino bet işlemi bulunamadı"}), 204

        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
        

@app.route('/api/GetSportBetsReport', methods=['POST'])
@jwt_required()
@check_api_status
def get_sport_bets_report():
    """
    Spor betlerinin raporunu getir
    ---
    tags:
      - Bets Operations
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-27T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2024-12-27T12:00:00"
              description: "Bitiş tarihi"
            stateIds:
              type: array
              items:
                type: integer
              example: []
              description: "Durum ID'leri (Opsiyonel)"
    responses:
      200:
        description: Kullanıcının casino bet listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json()
        created_from = datetime.fromisoformat(data['created_from'])
        created_before = datetime.fromisoformat(data['created_before'])
        stateIds = data.get('stateIds')


        result = fenomen_session.getSportBetsGeneralReport(created_from, created_before, stateIds)

        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404

        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"Belirtilen tarih aralığında spor bet işlemi bulunamadı"}), 204

        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/GetSportBetsReport/<betId>', methods=['GET'])
@jwt_required()
@check_api_status
def get_sport_bets_report_id(betId):
    """
    Belirli bir spor betinin raporunu getir
    ---
    tags:
      - Bets Operations
    parameters:
      - name: betId
        in: path
        type: string
        required: true
        description: Bet ID
    responses:
      200:
        description: Spor bet detayı başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        result = fenomen_session.getSportBetDetails(betId)

        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404

        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"'{betId}' bet ID'sine sahip bet bulunamadı"}), 204

        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/getUserSportBetsForUsername/<username>', methods=['POST'])
@jwt_required()
@check_api_status
def get_user_sport_bets_username(username):
    """
    Belirli bir kullanıcının spor bet geçmişini getir
    ---
    tags:
      - Bets Operations
    parameters:
      - name: username
        in: path
        type: string
        required: true
        description: Kullanıcı adı
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2024-12-27T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2024-12-27T12:00:00"
              description: "Bitiş tarihi"
            stateIds:
              type: array
              items:
                type: integer
              example: []
              description: "Durum ID'leri (Opsiyonel)"
              required: false
    responses:
      200:
        description: Kullanıcının spor bet listesi başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
      204:
        description: İçerik bulunamadı
    """
    try:
        data = request.get_json()
        created_from = datetime.fromisoformat(data['created_from'])
        created_before = datetime.fromisoformat(data['created_before'])
        stateIds = data.get('stateIds')

        # Önce kullanıcı ID'sini al
        userData = json.loads(fenomen_session.getUserData(username))
        if not userData or not userData.get("ResponseObject", {}).get("Entities"):
            return jsonify({"success": True, "message": f"'{username}' kullanıcı adına sahip kullanıcı bulunamadı"}), 204

        userId = int(userData.get("ResponseObject", {}).get("Entities", [{}])[0].get("Id"))
        result = fenomen_session.getSportBets(created_from, created_before, userId=userId, stateIds=stateIds)

        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                return {"success": False, "error": "Oturum süresi dolmuş"}, 401
            return {"data": result, "success": False}, 404

        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({"success": True, "message": f"'{username}' kullanıcısının belirtilen tarih aralığında spor bet işlemi bulunamadı"}), 204

        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getBonusControls', methods=['GET'])
@jwt_required()
@check_api_status
def get_bonus_controls():
    """
    Bonus kontrollerinin listesini getir
    ---
    tags:
      - Bonus Controls
    responses:
      200:
        description: Bonus kontrol listesi başarıyla getirildi
      401:
        description: Yetkisiz erişim
      500:
        description: Sunucu hatası
    """
    try:
        controls = bonus_controller.getControlList()
        return jsonify({"success": True, "data": json.loads(controls)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
      
      


def run_in_isolated_thread(func, *args, **kwargs):
    """
    Fonksiyonu izole bir thread'de çalıştırır.
    Bu sayede freeze_time kullanımı diğer thread'leri etkilemez.
    """
    future = bonus_executor.submit(func, *args, **kwargs)
    
    result, status_code = future.result()
    
    return result, status_code


def process_bonus_control_request(data):
    """
    Bonus kontrol isteğini işleyen fonksiyon
    """
    
    baseErrorJson = {
              "SystemError": True,
              "SystemErrorMessage": "Hata: Kullanıcı bulunamadı",
              "ValidMessage": None,
              "bonusLoad": False,
              "bonuses": [],
              "isValid": False,
              "userId": None,
              "username": None,
              "validCode": 1999
            }
    try:
        with app.app_context():
          if not data:
              baseErrorJson["SystemErrorMessage"] = "İstek boş"
              baseErrorJson["validCode"] = 10000
              baseErrorJson["SystemError"] = True
              baseErrorJson["bonuses"] = []
              return jsonify(baseErrorJson), 200

          required_fields = ["bonuses", "loadBonus", "controlParams", "realTime", "realTimeZone"]
          for field in required_fields:
              if field not in data:
                  baseErrorJson["SystemErrorMessage"] = f"'{field}' alanı gerekli"
                  baseErrorJson["validCode"] = 10000
                  baseErrorJson["SystemError"] = True
                  baseErrorJson["bonuses"] = []
                  return jsonify(baseErrorJson), 200
                  
          
                  
          # username veya userid olmalı
          if "username" not in data and "userid" not in data:
            baseErrorJson["SystemErrorMessage"] = "'username' veya 'userid' alanlarından biri gerekli"
            return jsonify(baseErrorJson), 200
            
          if "userid" in data and data["userid"] is not None:
              userid = data["userid"]
          elif "username" in data and data["username"] is not None:
              userData = json.loads(fenomen_session.getUserData(data["username"]))
                
              # eğer response kod 22 ise kullanıcı bulunamadı demektir
              if not userData or userData.get("ResponseCode") == 22:
                baseErrorJson["SystemErrorMessage"] = "Hata: Kullanıcı bilgileri alınamadı"
                return jsonify(baseErrorJson), 200
              
              if userData.get("ResponseCode") == -1:
                baseErrorJson["SystemErrorMessage"] = "Hata: Kullanıcı bilgileri alınamadı"
                return jsonify(baseErrorJson), 200
              
              userid = int(userData.get("ResponseObject", {}).get("Entities", [{}])[0].get("Id"))
              data["userid"] = userid
        backendTime = datetime.fromisoformat(data["realTime"]) - timedelta(hours=data["realTimeZone"])
        backendTime = backendTime.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with time_machine.travel(backendTime,tick=True):
            timeTest = datetime.now()
            controller = IBonusControlRequest(data,seleniumManager)
            result = controller.run()
          
            if result.get("SystemError"):
                return result, 200
            return result, 200

    except Exception as e:
        baseErrorJson["SystemErrorMessage"] = str(e)
        baseErrorJson["SystemError"] = True
        return baseErrorJson, 200
    
@app.route('/api/checkBonusEligibility', methods=['POST'])
@jwt_required()
@check_api_status
def check_bonus_eligibility():
    """
    Bonus hak kontrolü yap
    ---
    tags:
      - Bonus Controls
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            bonuses:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: integer
                    example: 4483
                  value:
                    type: object
                    properties:
                      calculationType:
                        type: string
                      amount:
                        type: number
                  usage:
                    type: object
                    properties:
                      maxUses:
                        type: integer
                  conditions:
                    type: object
            username:
              type: string
              example: "username girilse oncelikli o yüzden null kullanın id kullanıcaksanız"
            userid:
              type: integer
              example: 123456
            loadBonus:
              type: boolean
              example: false
            controlParams:
              type: array
              items:
                type: object
                properties:
                  controlName:
                    type: string
                  params:
                    type: object
    responses:
      200:
        description: Bonus kontrolü başarıyla yapıldı
      400:
        description: Geçersiz istek
      401:
        description: Yetkisiz erişim
      500:
        description: Sunucu hatası
    """
    baseErrorJson = {
              "SystemError": True,
              "SystemErrorMessage": "Hata: Kullanıcı bulunamadı",
              "ValidMessage": None,
              "bonusLoad": False,
              "bonuses": [],
              "isValid": False,
              "userId": None,
              "username": None,
              "validCode": 1999
            }
    try:
      data = request.get_json()
      return run_in_isolated_thread(process_bonus_control_request, data)
    except Exception as e:
      baseErrorJson["SystemErrorMessage"] = str(e)
      baseErrorJson["SystemError"] = True
      return jsonify(baseErrorJson), 200
      
      
    
        
        
@app.route('/api/addBonusDirectly', methods=['POST'])
@jwt_required()
@check_api_status
def add_bonus_directly():
  """
  Kullanıcıya doğrudan bonus ekle
  ---
  tags:
    - Bonus Operations
  parameters:
    - name: body
      in: body
      required: true
      schema:
        type: object
        properties:
          clientId:
            type: integer
            example: 123456
            description: Kullanıcı ID'si
          bonusCampaignId:
            type: integer
            example: 789
            description: Bonus kampanya ID'si
          value:
            type: number
            example: 100
            description: Bonus tutarı
          note:
            type: string
            example: "Bu bonus fenomenbot tarafından eklendi!"
            description: Bonus notu (opsiyonel)
  responses:
    200:
      description: Bonus başarıyla eklendi
      schema:
        type: object
        properties:
          success:
            type: boolean
          data:
            type: object
    400:
      description: Geçersiz istek parametreleri
    401:
      description: Yetkisiz erişim
    500:
      description: Sunucu hatası
  """
  try:
    data = request.get_json()
    
    if not all(key in data for key in ['clientId', 'bonusCampaignId', 'value']):
      return jsonify({
        "success": False,
        "error": "clientId, bonusCampaignId ve value zorunlu alanlardır"
      }), 400

    result = fenomen_session.addBonusDirectly(
      data['clientId'],
      data['bonusCampaignId'],
      data['value'],
      data.get('note', '')
    )

    if result.get("ResponseCode") == -1:
      return jsonify({
        "success": False,
        "error": result.get("ResponseMessage", "Bonus eklenirken bir hata oluştu")
      }), 400

    return jsonify({
      "success": True,
      "data": result
    })

  except Exception as e:
    return jsonify({
      "success": False,
      "error": str(e)
    }), 500

@app.route('/api/getBonusCampaigns', methods=['GET'])
@jwt_required()
@check_api_status
def get_bonus_campaigns():
    """
    Mevcut bonus kampanyalarını getir 
    ---
    tags:
      - Bonus Operations
    parameters:
      - name: bonusCampaignId
        in: query
        type: integer
        required: false
        description: Belirli bir bonus kampanyasının ID'si (opsiyonel)
      - name: IsActiveBonuses
        in: query
        type: boolean
        required: false
        default: false
        description: Sadece aktif bonusları getir
    responses:
      200:
        description: Bonus kampanyaları başarıyla getirildi
        schema:
          type: object
          properties:
            success:
              type: boolean
            data:
              type: array
              items:
                type: object
                properties:
                  Id:
                    type: integer
                  InternalName:
                    type: string
                  BonusType:
                    type: integer
                  ProductType:
                    type: integer
                  StartTime:
                    type: string
                    format: date-time
                  EndTime:
                    type: string
                    format: date-time
                  Status:
                    type: integer
      401:
        description: Oturum süresi dolmuş
      500:
        description: Sunucu hatası
    """
    try:
        bonus_campaign_id = request.args.get('bonusCampaignId', type=int, default=None)
        is_active_bonuses = request.args.get('IsActiveBonuses', type=bool, default=False)

        result = fenomen_session.getBonusCampaigns(
            bonusCampaignId=bonus_campaign_id, 
            IsActiveBonuses=is_active_bonuses
        )

        try:
            if isinstance(result, dict) and result.get("ResponseCode") == -1:
                if "Oturum süresi dolmuş" in result.get("ResponseMessage", ""):
                    return {"success": False, "error": "Oturum süresi dolmuş"}, 401
                return {"success": False, "data": result}, 404
        except:
            pass

        if not result or (isinstance(result, list) and len(result) == 0):
            return jsonify({
                "success": True, 
                "message": "Herhangi bir bonus kampanyası bulunamadı"
            }), 204

        return jsonify({
            "success": True,
            "data": result
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/bonusDocs', methods=['GET'])
@app.route('/bonusdocs/', methods=['GET'])
def bonus_docs():
    """
    Bonus API Dokümantasyonu
    """
    try:
        controls = json.loads(bonus_controller.getControlList())
        
        
        bonus_info_path = os.path.join(os.path.dirname(__file__), 'bonusinfo')

        with open(os.path.join(bonus_info_path, 'bonus_variations.json'), 'r', encoding='utf-8') as f:
            bonus_variations = json.load(f)
            
        with open(os.path.join(bonus_info_path, 'usage_examples.json'), 'r', encoding='utf-8') as f:
            usage_examples = json.load(f)
        
        # Her kontrole örnek ekleyelim
        for name, control in controls.items():
            if name == "checkLastDeposit":
                control["examples"] = [
                    {
                        "title": "Basit Yatırım Kontrolü",
                        "code": {
                            "days": 1,
                            "min": 100,
                            "checkIsUsed": True
                        },
                        "description": "Son yatırım tutarı minimum 100 TL olucak ve kullanmamış olucak ve son 1 gün içerisinde olucak"
                    },
                    {
                        "title": "Detaylı Yatırım Kontrolü",
                        "code": {
                            "days": 1,
                            "min": 100,
                            "max": 1000,
                            "checkIsUsed": True,
                            "beforeBalanceMin": 3,
                            "checkFirstDeposit": True
                        },
                        "description": "Son yatırım tutarı 100-1000 TL arasında olucak ve kullanmamış olucak ve son 1 gün içerisinde olucak ve bakiyesi en az 3 tl olucak"
                    }
                ]
        
        return render_template(
            'bonus_docs.html',
            controls=controls,
            bonus_variations=bonus_variations,
            usage_examples=usage_examples
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/runSingleControl', methods=['POST'])
@jwt_required()
@check_api_status
def run_single_control():
    """
    Tek bir bonus kontrolü yap
    ---
    tags:
      - Bonus Controls
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
              example: "testuser"
              description: "Kullanıcı adı"
            controlName: 
              type: string
              example: "checkCurrentBalance"
              description: "Çalıştırılacak kontrol metodu"
            params:
              type: object
              example: {"max": 1000, "min": 100}
              description: "Kontrol için gerekli parametreler"
    responses:
      200:
        description: Kontrol başarıyla yapıldı
        schema:
          type: object
          properties:
            success:
              type: boolean
            isValid:
              type: boolean 
            message:
              type: string
            code:
              type: integer
      400:
        description: Geçersiz istek parametreleri
      401:
        description: Yetkisiz erişim
      404:
        description: Kontrol bulunamadı
      500:
        description: Sunucu hatası
    """
    try:
        data = request.get_json()
        
        if not all(key in data for key in ['username', 'controlName', 'params']):
            return jsonify({
                "success": False,
                "error": "username, controlName ve params zorunlu alanlardır"
            }), 400

        try:
          controller = CampaignController(seleniumManager)
        except:
          return jsonify({
              "success": False,
              "error": "Kampanya kontrolü başlatılamadı"
          }), 500
        
        # Kontrol listesini al
        controls = json.loads(controller.getControlList())
        
        # Kontrol var mı kontrol et
        if data['controlName'] not in controls:
            return jsonify({
                "success": False,
                "error": f"{data['controlName']} isimli kontrol bulunamadı"
            }), 404

        # Kullanıcı bilgilerini al  
        
        user = json.loads(fenomen_session.getUserData(data['username']))
        if not user or user.get("ResponseCode") == 22:
            return jsonify({
                "success": False,
                "error": f"{data['username']} isimli kullanıcı bulunamadı"
            }), 404
        print(user)
        userData = controller.checkUser(user["ResponseObject"]["Entities"][0]["Id"])
        if not userData:
            return jsonify({
                "success": False,
                "error": f"{data['username']} isimli kullanıcı bulunamadı"
            }), 404

        # Kontrolü çalıştır
        result = controller.runControl(data['controlName'], userData, data['params'])

        return jsonify({
            "success": True,
            "isValid": result["isValid"],
            "message": result["message"],
            "code": result["code"]
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/getDashboardDeposits', methods=['POST'])
@jwt_required()
@check_api_status
def get_dashboard_deposits():
    """
    Dashboard için deposit istatistiklerini getir
    ---
    tags:
      - Main Dashboard
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2025-02-10T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2025-02-22T00:00:00"
              description: "Bitiş tarihi"
    responses:
      200:
        description: Dashboard deposit istatistikleri başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
    """
    try:
        data = request.get_json()
        created_from = datetime.fromisoformat(data['created_from'])
        created_before = datetime.fromisoformat(data['created_before'])
        
        result = fenomen_session.getMainInfoDeposits(created_from, created_before)
        
        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            return jsonify({"success": False, "error": result["ResponseMessage"]}), 500
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getDashboardWithdrawals', methods=['POST']) 
@jwt_required()
@check_api_status
def get_dashboard_withdrawals():
    """
    Dashboard için çekim istatistiklerini getir
    ---
    tags:
      - Main Dashboard
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2025-02-01T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2025-02-15T00:00:00"
              description: "Bitiş tarihi"
    responses:
      200:
        description: Dashboard çekim istatistikleri başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
    """
    try:
        data = request.get_json()
        created_from = datetime.fromisoformat(data['created_from'])
        created_before = datetime.fromisoformat(data['created_before'])
        
        result = fenomen_session.getMainInfoWithdrawals(created_from, created_before)
        
        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            return jsonify({"success": False, "error": result["ResponseMessage"]}), 500
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getDashboardBets', methods=['POST'])
@jwt_required()
@check_api_status 
def get_dashboard_bets():
    """
    Dashboard için bahis istatistiklerini getir
    ---
    tags:
      - Main Dashboard
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2025-02-01T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2025-02-15T00:00:00"
              description: "Bitiş tarihi"
    responses:
      200:
        description: Dashboard bahis istatistikleri başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
    """
    try:
        data = request.get_json()
        created_from = datetime.fromisoformat(data['created_from'])
        created_before = datetime.fromisoformat(data['created_before'])
        
        result = fenomen_session.getMainInfoProviderBets(created_from, created_before)
        
        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            return jsonify({"success": False, "error": result["ResponseMessage"]}), 500
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/getDashboardPlayers', methods=['POST'])
@jwt_required()
@check_api_status
def get_dashboard_players():
    """
    Dashboard için oyuncu istatistiklerini getir
    ---
    tags:
      - Main Dashboard
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            created_from:
              type: string
              format: date-time
              example: "2025-02-01T00:00:00"
              description: "Başlangıç tarihi"
            created_before:
              type: string
              format: date-time
              example: "2025-02-15T00:00:00"
              description: "Bitiş tarihi"
    responses:
      200:
        description: Dashboard oyuncu istatistikleri başarıyla getirildi
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
    """
    try:
        data = request.get_json()
        created_from = datetime.fromisoformat(data['created_from']) 
        created_before = datetime.fromisoformat(data['created_before'])
        result = fenomen_session.getMainInfoPlayersInfo(created_from, created_before)
        
        if isinstance(result, dict) and result.get("ResponseCode") == -1:
            return jsonify({"success": False, "error": result["ResponseMessage"]}), 500
            
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
      
@app.route('/api/curl', methods=['POST'])
@jwt_required()
@check_api_status
def custom_curl_request():
    """
    Belirtilen URL'ye özel bir curl isteği gönder
    ---
    tags:
      - Debugging
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            url:
              type: string
              example: "https://example.com/api"
              description: "Curl isteği gönderilecek URL"
            dataType:
              type: string
              enum: ["form", "json"]
              example: "json"
              description: "Veri tipi ('form' veya 'json')"
            data:
              type: object
              example: {"key": "value"}
              description: "Gönderilecek veri içeriği"
    responses:
      200:
        description: Curl isteği başarıyla tamamlandı
      400:
        description: Geçersiz istek parametreleri
      500:
        description: Sunucu hatası
    """

    try:
      data = request.get_json()
      
      if not all(key in data for key in ['url', 'dataType', 'data']):
        return jsonify({
          "success": False,
          "error": "url, dataType ve data zorunlu alanlardır"
        }), 400
      
      if data['dataType'] not in ['form', 'json']:
        return jsonify({
          "success": False,
          "error": "dataType 'form' veya 'json' olmalıdır"
        }), 400
      
      result = fenomen_session.runCustomCurlCommand(
        data['url'],
        data['dataType'],
        data['data']
      )
      
      if isinstance(result, dict) and result.get("ResponseCode") == -1:
        return jsonify({
          "success": False,
          "error": result.get("ResponseMessage", "Curl isteği başarısız oldu"),
          "message": result.get("ResponseObject", "Curl isteği başarısız oldu")
        }), 500
      
      return jsonify({
        "success": True,
        "data": result
      })
      
    except Exception as e:
      return jsonify({
        "success": False,
        "error": str(e)
      }), 500


swagger.template = {
    "swagger": "2.0",
    "info": {
        "title": "Fenomen API",
        "description": """
Fenomenbet API with Authentication
""",
        "version": "1.7.8"
    },
    "basePath": "/",
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "securityDefinitions": {
        "Bearer": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Authorization header using the Bearer scheme. Example: \"Authorization: Bearer {token}\""
        }
    },
    "security": [
        {
            "Bearer": []
        }
    ],
    "tags": [
        {
            "name": "Bonus Controls",
            "description": "Bonus uygunluk kontrolleri"
        },
        {
            "name": "Authentication",
            "description": "authentication operations"
        },
        {
            "name": "Account Management",
            "description": "Account management operations" 
        },
        {
            "name": "User Operations",
            "description": "User information retrieval operations"
        },
        {
            "name": "Deposit Operations",
            "description": "Deposit information retrieval operations"
        },
        {
            "name": "Transaction Operations",
            "description": "Transaction history operations"
        },
        {
            "name": "Bonus Operations",
            "description": "Bonus işlemleri"
        },
        {
            "name": "Bets Operations",
            "description": "Sport ve Casino bet information retrieval operations"
        },
        {
            "name": "Gaming Operations",
            "description": "Gaming information retrieval operations"
        },
        {
            "name": "Withdraw Operations",
            "description": "Withdraw information retrieval operations"
        },
        {
            "name": "Main Dashboard",
            "description": "Ana dashboard istatistikleri işlemleri"
        },
        {
            "name": "Debugging",
            "description": "Debugging operations"
        }
    ]
}

from ConnectionCleaner import ConnectionCleaner
cleaner = ConnectionCleaner(
  app,
)

cleaner.start()

if __name__ == '__main__':
    app.run(debug=True, port=5010)
