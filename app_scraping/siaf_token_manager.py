import time
import logging
import base64
import json
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
from rest_framework import status
import requests
from playwright.sync_api import sync_playwright

# Configurar logging
logger = logging.getLogger(__name__)

# Constantes para el manejo de tokens SIAF
SIAF_CACHE_KEY = "siaf_tokens"
SIAF_LOGIN_LOCK_KEY = "siaf_login_lock"
SIAF_ACCESS_TOKEN_EXPIRY = 60 * 60  # 60 minutos en segundos
SIAF_REFRESH_TOKEN_EXPIRY = 30 * 60  # 30 minutos en segundos
TOKEN_REFRESH_THRESHOLD = 5 * 60  # 5 minutos antes de expirar
URL_LOGIN = "https://apps.mef.gob.pe/weblanding/#/landing"

def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica un token JWT sin verificar la firma
    """
    try:
        # Dividir el token en partes
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        # Decodificar el payload (segunda parte)
        payload = parts[1]
        # Agregar padding si es necesario
        payload += '=' * (4 - len(payload) % 4)
        
        # Decodificar de base64
        decoded_bytes = base64.urlsafe_b64decode(payload)
        decoded_str = decoded_bytes.decode('utf-8')
        
        # Parsear JSON
        return json.loads(decoded_str)
    except Exception as e:
        logger.error(f"Error al decodificar token JWT: {e}")
        return None

def get_token_expiration_time(token: str) -> Optional[int]:
    """
    Obtiene el tiempo de expiración de un token JWT
    """
    try:
        decoded = decode_jwt_token(token)
        if decoded and 'exp' in decoded:
            return decoded['exp']
        return None
    except Exception as e:
        logger.error(f"Error al obtener expiración del token: {e}")
        return None

def calculate_token_duration(token: str) -> Optional[int]:
    """
    Calcula la duración en segundos de un token JWT
    """
    try:
        decoded = decode_jwt_token(token)
        if decoded and 'exp' in decoded and 'iat' in decoded:
            return decoded['exp'] - decoded['iat']
        return None
    except Exception as e:
        logger.error(f"Error al calcular duración del token: {e}")
        return None

class SIAFTokenManager:
    """
    Clase para gestionar los tokens de autenticación de SIAF    
    """
    
    def __init__(self):
        self.cache_key = SIAF_CACHE_KEY
        self.login_lock_key = SIAF_LOGIN_LOCK_KEY
    
    def get_tokens(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene los tokens almacenados en caché
        """
        try:
            tokens = cache.get(self.cache_key)
            if tokens and self._is_token_valid(tokens):
                return tokens
            


            
        except Exception as e:
            logger.error(f"Error al obtener tokens: {e}")
            return None
    
    def _is_token_valid(self, tokens: Dict[str, Any]) -> bool:
        """
        Verifica si el token de acceso es válido y no está próximo a expirar
        """
        try:
            if not tokens or 'access_token' not in tokens:
                return False
            
            current_time = time.time()
            
            # Usar el tiempo de expiración real del token JWT si está disponible
            if 'access_token_expires_at' in tokens:
                expiration_time = tokens['access_token_expires_at']
            else:
                # Fallback: calcular desde el token JWT
                access_exp = get_token_expiration_time(tokens['access_token'])
                if access_exp:
                    expiration_time = access_exp
                else:
                    return False
            
            # Verifica si el token expira en los próximos 5 minutos
            return current_time < (expiration_time - TOKEN_REFRESH_THRESHOLD)
        except Exception as e:
            logger.error(f"Error al validar token: {e}")
            return False
    
    def _is_refresh_token_valid(self, tokens: Dict[str, Any]) -> bool:
        """
        Verifica si el refresh token es válido
        """
        try:
            if not tokens or 'refresh_token' not in tokens:
                return False
            
            current_time = time.time()
            
            # Usar el tiempo de expiración real del token JWT si está disponible
            if 'refresh_token_expires_at' in tokens:
                refresh_expiration_time = tokens['refresh_token_expires_at']
            else:
                # Fallback: calcular desde el token JWT
                refresh_exp = get_token_expiration_time(tokens['refresh_token'])
                if refresh_exp:
                    refresh_expiration_time = refresh_exp
                else:
                    return False
            
            return current_time < refresh_expiration_time
        except Exception as e:
            logger.error(f"Error al validar refresh token: {e}")
            return False
    
    def store_tokens(self, tokens: Dict[str, Any]) -> bool:
        """
        Almacena los tokens en caché con el timeout apropiado
        """
        try:
            # Calcula el timeout basado en la expiración del refresh token
            timeout = tokens.get('refresh_token_expires_at', 0) - time.time()
            if timeout <= 0:
                timeout = SIAF_REFRESH_TOKEN_EXPIRY
            
            cache.set(self.cache_key, tokens, timeout=int(timeout))
            logger.info("Tokens almacenados exitosamente en caché")
            return True
        except Exception as e:
            logger.error(f"Error al almacenar tokens: {e}")
            return False
    
    def clear_tokens(self) -> bool:
        """
        Elimina los tokens del caché
        """
        try:
            cache.delete(self.cache_key)
            logger.info("Tokens eliminados del caché")
            return True
        except Exception as e:
            logger.error(f"Error al eliminar tokens: {e}")
            return False
    
    def acquire_login_lock(self) -> bool:
        """
        Adquiere un lock para evitar múltiples logins simultáneos
        """
        try:
            return cache.add(self.login_lock_key, True, timeout=60)  # 60 segundos de lock
        except Exception as e:
            logger.error(f"Error al adquirir login lock: {e}")
            return False
    
    def release_login_lock(self) -> bool:
        """
        Libera el lock de login
        """
        try:
            cache.delete(self.login_lock_key)
            return True
        except Exception as e:
            logger.error(f"Error al liberar login lock: {e}")
            return False
    
    def get_token_info(self, tokens: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtiene información detallada de los tokens
        """
        try:
            if not tokens:
                return {"error": "No hay tokens disponibles"}
            
            current_time = time.time()
            
            # Información del access token
            access_token_info = {}
            if 'access_token' in tokens:
                decoded_access = decode_jwt_token(tokens['access_token'])
                if decoded_access:
                    access_token_info = {
                        "username": decoded_access.get('preferred_username'),
                        "name": decoded_access.get('name'),
                        "entidad": decoded_access.get('entidad'),
                        "unidadejecutora": decoded_access.get('unidadejecutora'),
                        "roles": decoded_access.get('realm_access', {}).get('roles', []),
                        "exp": decoded_access.get('exp'),
                        "iat": decoded_access.get('iat'),
                        "expires_in_seconds": decoded_access.get('exp', 0) - current_time if decoded_access.get('exp') else 0
                    }
            
            # Información del refresh token
            refresh_token_info = {}
            if 'refresh_token' in tokens:
                decoded_refresh = decode_jwt_token(tokens['refresh_token'])
                if decoded_refresh:
                    refresh_token_info = {
                        "exp": decoded_refresh.get('exp'),
                        "iat": decoded_refresh.get('iat'),
                        "expires_in_seconds": decoded_refresh.get('exp', 0) - current_time if decoded_refresh.get('exp') else 0
                    }
            
            return {
                "access_token_info": access_token_info,
                "refresh_token_info": refresh_token_info,
                "stored_expires_at": {
                    "access": tokens.get('access_token_expires_at'),
                    "refresh": tokens.get('refresh_token_expires_at')
                },
                "current_time": current_time
            }
            
        except Exception as e:
            logger.error(f"Error al obtener información del token: {e}")
            return {"error": str(e)}

# Instancia global del token manager
siaf_token_manager = SIAFTokenManager()

def require_siaf_auth(func):
    """
    Decorador para endpoints que requieren autenticación SIAF
    Automáticamente obtiene o refresca tokens según sea necesario
    """
    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        try:
            # Obtener tokens válidos
            tokens = get_valid_siaf_tokens()
            if not tokens:
                return JsonResponse({
                    "error": "No se pudieron obtener tokens de autenticación SIAF",
                    "detail": "Verifique las credenciales y la conectividad"
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            # Agregar tokens al request para uso en la función
            request.siaf_tokens = tokens
            return func(self, request, *args, **kwargs)
            
        except Exception as e:
            logger.error(f"Error en decorador require_siaf_auth: {e}")
            return JsonResponse({
                "error": "Error interno del servidor",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return wrapper

def get_valid_siaf_tokens() -> Optional[Dict[str, Any]]:
    """
    Obtiene tokens válidos de SIAF, refrescándolos si es necesario
    """
    try:
        # Intentar obtener tokens existentes
        tokens = siaf_token_manager.get_tokens()
        
        if tokens and siaf_token_manager._is_token_valid(tokens):
            logger.info("Usando tokens existentes válidos")
            return tokens
        
        # Si hay tokens pero el access token expiró, intentar refrescar
        if tokens and siaf_token_manager._is_refresh_token_valid(tokens):
            logger.info("Refrescando tokens expirados")
            refreshed_tokens = refresh_siaf_tokens(tokens.get('refresh_token'))
            if refreshed_tokens:
                return refreshed_tokens
        
        # Si no hay tokens válidos, hacer login
        logger.info("Realizando nuevo login a SIAF")
        return login_siaf_backend()
        
    except Exception as e:
        logger.error(f"Error al obtener tokens válidos: {e}")
        return None

def refresh_siaf_tokens(refresh_token: str) -> Optional[Dict[str, Any]]:
    """
    Refresca los tokens usando el refresh token
    """
    try:
        # URL del endpoint de refresh de Keycloak
        url = "https://authorize.mef.gob.pe/auth/realms/mef/protocol/openid-connect/token"
        
        # Headers requeridos
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Datos del body para refresh token
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': 'jwtClient'  # Basado en el token JWT que mostraste
        }
        
        # Hacer la petición
        response = requests.post(url, headers=headers, data=data, timeout=30)
        
        if response.status_code == 200:
            token_data = response.json()
            
            # Extraer información de los tokens
            access_token = token_data.get('access_token')
            new_refresh_token = token_data.get('refresh_token')
            expires_in = token_data.get('expires_in')
            refresh_expires_in = token_data.get('refresh_expires_in')
            
            if access_token and new_refresh_token:
                # Obtener tiempos de expiración reales de los tokens JWT
                access_exp = get_token_expiration_time(access_token)
                refresh_exp = get_token_expiration_time(new_refresh_token)
                
                current_time = time.time()
                
                tokens = {
                    "access_token": access_token,
                    "refresh_token": new_refresh_token,
                    "access_token_expires_at": access_exp or (current_time + expires_in),
                    "refresh_token_expires_at": refresh_exp or (current_time + refresh_expires_in),
                    "expires_in": expires_in,
                    "refresh_expires_in": refresh_expires_in,
                    "created_at": current_time,
                    "token_type": "Bearer"
                }
                
                # Almacenar los nuevos tokens
                siaf_token_manager.store_tokens(tokens)
                logger.info("Tokens refrescados exitosamente")
                return tokens
            else:
                logger.error("Respuesta de refresh no contiene tokens válidos")
                return None
        else:
            logger.error(f"Error al refrescar tokens. Status: {response.status_code}, Response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error al refrescar tokens: {e}")
        return None

def login_siaf_backend() -> Optional[Dict[str, Any]]:
    """
    Realiza el login a SIAF y obtiene los tokens
    Esta función debe ser llamada desde views.py
    """
    try:
        # Verificar si ya hay un login en proceso
        if not siaf_token_manager.acquire_login_lock():
            logger.warning("Ya hay un login en proceso, esperando...")
            # Esperar un poco y verificar si ya se completó
            time.sleep(2)
            tokens = siaf_token_manager.get_tokens()
            if tokens:
                return tokens
            return None
        
        try:
            # Esta función será implementada en views.py
            # Retorna None para indicar que necesita ser implementada
            logger.info("Función login_siaf_backend necesita ser implementada en views.py")
            return None
                    
        finally:
            siaf_token_manager.release_login_lock()
            
    except Exception as e:
        logger.error(f"Error en login_siaf_backend: {e}")
        siaf_token_manager.release_login_lock()
        return None

def get_siaf_status() -> Dict[str, Any]:
    """
    Obtiene el estado actual de los tokens SIAF
    """
    try:
        tokens = siaf_token_manager.get_tokens()
        
        if tokens:
            current_time = time.time()
            access_valid = siaf_token_manager._is_token_valid(tokens)
            refresh_valid = siaf_token_manager._is_refresh_token_valid(tokens)
            
            return {
                "tokens_exist": True,
                "access_token_valid": access_valid,
                "refresh_token_valid": refresh_valid,
                "access_token_expires_at": datetime.fromtimestamp(tokens['access_token_expires_at']).isoformat(),
                "refresh_token_expires_at": datetime.fromtimestamp(tokens['refresh_token_expires_at']).isoformat(),
                "time_until_access_expires": int(tokens['access_token_expires_at'] - current_time),
                "time_until_refresh_expires": int(tokens['refresh_token_expires_at'] - current_time),
            }
        else:
            return {
                "tokens_exist": False,
                "message": "No hay tokens almacenados"
            }
                
    except Exception as e:
        logger.error(f"Error en get_siaf_status: {e}")
        return {
            "error": "Error interno del servidor",
            "detail": str(e)
        } 
    

def login_siaf_backend(self):
    
    try:
        if not siaf_token_manager.acquire_login_lock():
            return JsonResponse({
                "message": "Ya hay un login en proceso, intente nuevamente en unos segundos",
                "content": "Por Mario Medina"
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        

        try:
            tokens = None
            
            with sync_playwright() as playwright:        
                browser = playwright.chromium.launch()   
                context = browser.new_context()         
                page = context.new_page()

                # Función para interceptar las respuestas
                def handle_response(response):
                    nonlocal tokens
                    if "authorize.mef.gob.pe/auth/realms/mef/protocol/openid-connect/token" in response.url:
                        try:
                            data = response.json()                        
                            refresh_token = data.get('refresh_token')
                            access_token = data.get('access_token')
                            expires_in = data.get('expires_in', SIAF_ACCESS_TOKEN_EXPIRY)
                            refresh_expires_in = data.get('refresh_expires_in', SIAF_REFRESH_TOKEN_EXPIRY)
                            
                            if refresh_token and access_token:
                                current_time = time.time()
                                tokens = {
                                    "access_token": access_token,
                                    "refresh_token": refresh_token,
                                    "access_token_expires_at": current_time + expires_in,
                                    "refresh_token_expires_at": current_time + refresh_expires_in,
                                    "expires_in": expires_in,
                                    "refresh_expires_in": refresh_expires_in,
                                    "created_at": current_time,
                                    "token_type": "Bearer"
                                }
                                print("Tokens obtenidos exitosamente")
                                print(f"Access token expira en: {expires_in} segundos")
                                print(f"Refresh token expira en: {refresh_expires_in} segundos")
                                
                        except Exception as e:
                            print("Error al procesar la respuesta:", e)

                # Escucha las respuestas
                page.on("response", handle_response)

                page.goto(URL_LOGIN)      
                time.sleep(3)
                page.click("text='SIAF'")

                page.wait_for_load_state('networkidle') 
                page.fill("#username", "02897041")
                page.fill("#password", "Yvjv971p@")
                time.sleep(7)
                page.click("#kc-login")
                page.wait_for_load_state('networkidle') 
                title = page.title()
                
                # Captura la pantalla
                page.screenshot(path="screenshot.png")

                # Cierra el navegador
                browser.close()
            
            # Almacenar tokens en caché si se obtuvieron
            if tokens:
                siaf_token_manager.store_tokens(tokens)
                return JsonResponse({
                    "message": "Login exitoso a SIAF",
                    "tokens_obtained": True,
                    "access_token_expires_at": tokens['access_token_expires_at'],
                    "refresh_token_expires_at": tokens['refresh_token_expires_at'],
                    "content": "Por Mario Medina"
                })
            else:
                return JsonResponse({
                    "message": "Error al obtener tokens de SIAF",
                    "tokens_obtained": False,
                    "content": "Por Mario Medina"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        finally:
            siaf_token_manager.release_login_lock()
                    
        
    except Exception as e:
        logger.error(f"Error en login_siaf_backend: {e}")
        return None
