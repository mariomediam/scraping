import re 
import time
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
import requests
from rest_framework import status
from django.http import JsonResponse
from datetime import datetime
from playwright.sync_api import sync_playwright
from django.core.cache import cache

# Importar el sistema de gestión de tokens SIAF
from .siaf_token_manager import (
    siaf_token_manager, 
    get_valid_siaf_tokens, 
    require_siaf_auth, 
    get_siaf_status,
    SIAF_ACCESS_TOKEN_EXPIRY,
    SIAF_REFRESH_TOKEN_EXPIRY
)

from .siaf_token_manager2 import (SIAFTokenManager2)

# Guardar los tokens
# tokens = {"access": "tu_access_token", "refresh": "tu_refresh_token"}
cache.set("is_login", False, None)  # timeout=None para que no expire
tokens = {}
cache.set("tokens", tokens, timeout=60)  # timeout=None para que no expire

URL_SIAF_DEVENGADOS = "https://apps.mef.gob.pe/v1/siaf-services/devengado/devengados"


# mi_numero = 0
# Clases base que puedes reutilizar
class BaseAPIView(APIView):
    """Clase base para todas las vistas API"""
    pass

class HomeView(APIView):  
    permission_classes = [AllowAny]
    def get(self, request, format=None):
        return JsonResponse({
            "message": 'HOLA MUNDO DESDE DJANGO Y DOCKER',
            "content": 'Por Mario Medina'
        })
    
class test_scraping(APIView):
    permission_classes = [AllowAny]
    def get(self, request, format=None):

        # url = "http://tramitevirtual.munipiura.gob.pe/Account/Login?ReturnUrl=%2FHome%2FDashboard"
        url = "http://sistemasmpp/login"
        # url = "http://192.168.100.59/login"

        if not url:
            return JsonResponse({
                "message": 'No se proporcionó una URL',
                "content": 'Por Mario Medina'
            }, status=status.HTTP_400_BAD_REQUEST)
        

        with sync_playwright() as playwright:        
            browser = playwright.chromium.launch()   
            context = browser.new_context()         
            page = context.new_page()

            # Variable para almacenar el token            
            refresh_token = None
            access_token = None

            # Función para interceptar las respuestas
            def handle_response(response):
                nonlocal refresh_token, access_token
                if "api/seguridad/login" in response.url:  # Verifica si es la URL de la API de login
                    try:
                        data = response.json()  # Obtiene el cuerpo de la respuesta en formato JSON
                        refresh_token = data.get('refresh')
                        access_token = data.get('access')
                    except Exception as e:
                        print("Error al procesar la respuesta:", e)

            # Escucha las respuestas
            page.on("response", handle_response)

            page.goto(url)      
            
            
            page.locator("#formBasicEmail").fill("mmedina")
            page.locator('#formBasicPassword').fill("aaaaa")  
            page.click("button[type='submit']")

            page.on("console", lambda msg: print(msg.text))
            
                     
            title = page.title()
            page.wait_for_load_state('networkidle', timeout=60000) 
            
            # Imprime los tokens si se encontraron
            if refresh_token and access_token:
                print("Refresh Token:", refresh_token)
                print("Access Token:", access_token)
            else:
                print("No se encontraron tokens.")

            # Captura la pantalla
            page.screenshot(path="screenshot.png")

            # Cierra el navegador
            browser.close()
            return JsonResponse({
                "message": f"El título de la página es: {title}",
                "content": 'Por Mario Medina'
            })


class login_siaf(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, format=None):
        """
        Endpoint para realizar login a SIAF y obtener tokens
        """
        try:
            url = "https://apps.mef.gob.pe/weblanding/#/landing"

            if not url:
                return JsonResponse({
                    "message": 'No se proporcionó una URL',
                    "content": 'Por Mario Medina'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Verificar si ya hay un login en proceso
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

                    page.goto(url)      
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
            siaf_token_manager.release_login_lock()
            return JsonResponse({
                "error": "Error interno del servidor",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class incrementar_numero(APIView):
    permission_classes = [AllowAny]
    CACHE_KEY = "tokens"  # Class constant for cache key
    
    def get(self, request, format=None):
        try:
            # Get current number from cache with default value
            current_tokens = cache.get(self.CACHE_KEY, {"mi_numero": 0})
            
            # Increment number
            mi_numero = current_tokens["mi_numero"] + 1
            
            # Update cache
            cache.set(
                self.CACHE_KEY, 
                {"mi_numero": mi_numero}, 
                timeout=60
            )
            
            return JsonResponse({
                "message": f"El Número es: {mi_numero}",
                "content": "Por Mario"
            }, status=200)
            
        except Exception as e:
            return JsonResponse({
                "error": "Error al incrementar el número",
                "detail": str(e)
            }, status=500)
        

# def login_remote_backend(username, password):

#     try:
    
#         url = "http://sistemasmpp/login"
#         tokens = None

#         is_login = cache.get("is_login", False)
#         if is_login:
#             return tokens
                
#         with sync_playwright() as playwright:   
#             cache.set("is_login", True, timeout=60)     
#             browser = playwright.chromium.launch()   
#             context = browser.new_context()         
#             page = context.new_page()

#             # Función para interceptar las respuestas
#             def handle_response(response):            
#                 nonlocal tokens
#                 if "api/seguridad/login" in response.url:  # Verifica si es la URL de la API de login
                    
#                     data = response.json()  # Obtiene el cuerpo de la respuesta en formato JSON
#                     refresh_token = data.get('refresh')
#                     access_token = data.get('access')
#                     expires_in = data.get('expires_in', 3600)
#                     refresh_expires_in = data.get('refresh_expires_in', 1800)
#                     # obtener fecha y hora en que expirará el token
#                     time_expiration = time.time() + expires_in 
#                     tokens = {
#                         "username": username,
#                         "access": access_token,
#                         "refresh": refresh_token,
#                         "expires_in": expires_in,
#                         "refresh_expires_in": refresh_expires_in,
#                         "time_expiration": time_expiration
#                     }
#                     store_tokens_in_cache(tokens)  # Almacena los tokens en caché
                    
#             # Escucha las respuestas
#             page.on("response", handle_response)

#             page.goto(url)      
            
#             # Use the provided username and password
#             page.locator("#formBasicEmail").fill(username)
#             page.locator('#formBasicPassword').fill(password)  
#             page.click("button[type='submit']")
                    
#             page.wait_for_load_state('networkidle') 
            
#             # Cierra el navegador
#             browser.close()

#         return tokens
#     except Exception as e:
#         print("Error en la función login_remote_backend:", e)
#         return None
#     finally:
#         cache.set("is_login", False, None) 



def store_tokens_in_cache(tokens):
    timeout = tokens.get("expires_in", 3600)  # Default timeout if not provided
    cache.set("tokens", tokens, timeout=timeout)  # timeout=None para que no expire
    print("Tokens almacenados en caché:", tokens)

class siaf_status(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, format=None):
        """
        Endpoint para verificar el estado de los tokens SIAF
        """
        try:
            status_info = get_siaf_status()
            return JsonResponse({
                **status_info,
                "content": "Por Mario Medina"
            })
                
        except Exception as e:
            return JsonResponse({
                "error": "Error interno del servidor",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class siaf_endpoint_example(APIView):
    permission_classes = [AllowAny]
    
    @require_siaf_auth
    def get(self, request, format=None):
        """
        Ejemplo de endpoint que requiere autenticación SIAF
        Los tokens están disponibles en request.siaf_tokens
        """
        try:
            # Los tokens están disponibles en request.siaf_tokens
            tokens = getattr(request, 'siaf_tokens', None)
            
            # Aquí harías la llamada al endpoint de SIAF usando los tokens
            # Por ejemplo:
            # headers = {
            #     'Authorization': f'Bearer {tokens["access_token"]}',
            #     'Content-Type': 'application/json'
            # }
            # response = requests.get('https://api.siaf.gob.pe/endpoint', headers=headers)
            
            return JsonResponse({
                "message": "Endpoint protegido accedido exitosamente",
                "tokens_available": tokens is not None,
                "access_token_preview": tokens["access_token"][:20] + "..." if tokens else None,
                "content": "Por Mario Medina"
            })
            
        except Exception as e:
            return JsonResponse({
                "error": "Error interno del servidor",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class siaf_clear_tokens(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, format=None):
        """
        Endpoint para limpiar los tokens almacenados
        """
        try:
            success = siaf_token_manager.clear_tokens()
            if success:
                return JsonResponse({
                    "message": "Tokens eliminados exitosamente",
                    "content": "Por Mario Medina"
                })
            else:
                return JsonResponse({
                    "error": "Error al eliminar tokens",
                    "content": "Por Mario Medina"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return JsonResponse({
                "error": "Error interno del servidor",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class siaf_token_info(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, format=None):
        """
        Endpoint para obtener información detallada de los tokens SIAF
        """
        try:
            tokens = siaf_token_manager.get_tokens()
            
            if tokens:
                token_info = siaf_token_manager.get_token_info(tokens)
                return JsonResponse({
                    **token_info,
                    "content": "Por Mario Medina"
                })
            else:
                return JsonResponse({
                    "error": "No hay tokens almacenados",
                    "content": "Por Mario Medina"
                }, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return JsonResponse({
                "error": "Error interno del servidor",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class siaf_leer_devengado(RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = None
    serializer_class = None

    def get(self, request):
        print("*********** 1 ***********")
        ano_eje = request.query_params.get('ano_eje', None)
        expediente = request.query_params.get('expediente', None)
        secuencia = request.query_params.get('secuencia', None)

        if not ano_eje or not expediente or not secuencia:
            return JsonResponse({
                "error": "Faltan parámetros requeridos",
                "content": "Por Mario Medina"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Obtener los tokens SIAF
        siaf_manager = SIAFTokenManager2()
        access_token = siaf_manager.get_access_token()

        print("*********** access_token ***********", access_token)

#         curl --location 'https://apps.mef.gob.pe/v1/siaf-services/devengado/devengados/2025/3318/2' \
# --header 'Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJBeGxPdUtBVjBMN0xCa2k5VHhTcmxCaE92QUZzdzNCQjF3RWRfQmlXaGdJIn0.eyJleHAiOjE3NTEwNTAzNDMsImlhdCI6MTc1MTA0Njc0MywiYXV0aF90aW1lIjoxNzUxMDQ2NzQxLCJqdGkiOiI5MTM5OWEyMC05MDQxLTRkOWItYTI1MS0zNDYxNGRiN2YxODgiLCJpc3MiOiJodHRwczovL2F1dGhvcml6ZS5tZWYuZ29iLnBlL2F1dGgvcmVhbG1zL21lZiIsImF1ZCI6ImFjY291bnQiLCJzdWIiOiJmOjM2MGVjNWEwLTBlMjctNDM2OS04NzgxLTAwYzg4ZjMzMzc1MzowMjg5NzA0MSIsInR5cCI6IkJlYXJlciIsImF6cCI6Imp3dENsaWVudCIsInNlc3Npb25fc3RhdGUiOiJkZmNlMWZlNC02OWU0LTQzNjUtODFiMi1mZmE4Zjc3NTc0MjciLCJhY3IiOiIxIiwiYWxsb3dlZC1vcmlnaW5zIjpbIioiXSwicmVhbG1fYWNjZXNzIjp7InJvbGVzIjpbIm9mZmxpbmVfYWNjZXNzIiwidW1hX2F1dGhvcml6YXRpb24iXX0sInJlc291cmNlX2FjY2VzcyI6eyJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6ImVtYWlsIHJlYWQgd3JpdGUgcHJvZmlsZSIsInNpZCI6ImRmY2UxZmU0LTY5ZTQtNDM2NS04MWIyLWZmYThmNzc1NzQyNyIsImVtYWlsX3ZlcmlmaWVkIjpmYWxzZSwiYXBlbGxpZG9wYXRlcm5vIjoiTUVESU5BIiwicHJlZmVycmVkX3VzZXJuYW1lIjoiMDI4OTcwNDEiLCJnaXZlbl9uYW1lIjoiTUFSSU8gQUxFWEFOREVSIiwibm9tYnJlIjoiTUFSSU8gQUxFWEFOREVSIiwibm9tYnJldXN1YXJpbyI6Ik1BUklPIEFMRVhBTkRFUiBNRURJTkEgTUFSUVVFWiIsInVuaWRhZGVqZWN1dG9yYSI6IjMwMTUyOSIsImVudGlkYWQiOiJNVU5JQ0lQQUxJREFEIFBST1ZJTkNJQUwgREUgUElVUkEiLCJhcGVsbGlkb21hdGVybm8iOiJNQVJRVUVaIiwibmFtZSI6Ik1BUklPIEFMRVhBTkRFUiBNRURJTkEgTUFSUVVFWiIsImZhbWlseV9uYW1lIjoiTUVESU5BIE1BUlFVRVoiLCJ0aXBvdW5pZGFkIjoiTSIsInVzZXJuYW1lIjoiMDI4OTcwNDEifQ.DAw6jdEiv3i0S74fvxNzKz3De_rI_P7qRa4-KsCH6CWrmq55FtFWBdII2eVQQTj-QyLxPW-NHIujaBoHHLeJSYxuUyeepn2zZnEGw8W91CYlhQHrgMq1uXv8UM6HqgIgbG9aATCOdNLGCgN1_ChXauL1VYA5bNBG7tNnfQYX7h_FWEAoiZsncaxswhInD1jjlANexy8OPo0MHsJS_gfybWbV4f7H8nzfy1lUM55PtwXRRJcssR6m99_QVbVdMabsPJexCbw_0Lrl_9I_3MHxdfTu8v04E8mU8nj073Q3FDgri7TpEYdKQ3Y9LHFnrFgRos0SgiHt3RxMu2OHscKXyQ' \
# --header 'Cookie: incap_ses_8221_3160769=jclrZoFu8g+DRMr5SdwWchfdXmgAAAAAI7iMQDUt5WbFT1VCrzRCdw==; visid_incap_3160769=a4l3QqtbQQWe2KXk0ZyOiOyT2WcAAAAAQUIPAAAAAADAibZD6YD3So1rQbWfeR15; visid_incap_3160770=pEBgpNY5SpCb0QVwfLp6AT5X7WcAAAAAQUIPAAAAAABmHIqs7P2d5TqLB0zytyhB'
        
        if not access_token:
            return JsonResponse({
                "error": "No hay tokens almacenados",
                "content": "Por Mario Medina"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # url = f"https://apps.mef.gob.pe/v1/siaf-services/devengado/devengados/{ano_eje}/{expediente}/{secuencia}"
        url = f"https://apps.mef.gob.pe/v1/siaf-services/devengado/devengados/{ano_eje}/{expediente}/{secuencia}"
        headers = {
            "Authorization": f"Bearer {access_token}",            
        }
        # "Cookie": "incap_ses_8221_3160769=jclrZoFu8g+DRMr5SdwWchfdXmgAAAAAI7iMQDUt5WbFT1VCrzRCdw==; visid_incap_3160769=a4l3QqtbQQWe2KXk0ZyOiOyT2WcAAAAAQUIPAAAAAADAibZD6YD3So1rQbWfeR15; visid_incap_3160770=pEBgpNY5SpCb0QVwfLp6AT5X7WcAAAAAQUIPAAAAAABmHIqs7P2d5TqLB0zytyhB"
        # response = requests.get(url, headers=headers)
        # response_json = response.json()
        response_json = {
            "message": "Tokens obtenidos exitosamente",
            "content": "Por Mario Medina"
        }
        
        
        
        
        
        # # print("*********** access_token ***********", access_token)
        tokens_siaf = cache.get("tokens_siaf", None)
        # # print("*********** tokens_siaf ***********", tokens_siaf)
        # 'refresh_token_expires_at': 1751307677.9027617
        # #  convertir a datetime
        refresh_token_expires_at = datetime.fromtimestamp(tokens_siaf.get("refresh_token_expires_at", 0))
        print("*********** refresh_token_expires_at ***********", refresh_token_expires_at)
        # # imprime hora actual
        print("*********** hora actual ***********", datetime.now())
        # # imprime la diferencia en segundos
        print("*********** diferencia en segundos ***********", (refresh_token_expires_at - datetime.now()).total_seconds())
        # access_token = tokens_siaf.get("access_token", None)
        # print("*********** access_token ***********", access_token)

        return JsonResponse({
            "message": "Tokens obtenidos exitosamente",
            "content": response_json
        })
    

def siaf_buscar_devengados(ano_eje, expediente, secuencia=None):
    try:
        siaf_manager = SIAFTokenManager2()
        access_token = siaf_manager.get_access_token()

        if not access_token:
            raise Exception("No hay tokens almacenados")
        
        url = f"{URL_SIAF_DEVENGADOS}/{ano_eje}/{expediente}"

        if secuencia:
            url = f"{url}/{secuencia}"

        headers = {
            "Authorization": f"Bearer {access_token}",            
        }
        response = requests.get(url, headers=headers)
        response_json = response.json()
        return response_json
    except Exception as e:
        raise Exception(f"Error al buscar devengados: {e}")
    