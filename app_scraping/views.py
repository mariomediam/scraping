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

URL_SIAF_API = "https://apps.mef.gob.pe/v1/siaf-services"


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
        ano_eje = request.query_params.get('ano_eje', None)
        expediente = request.query_params.get('expediente', None)        

        if not ano_eje or not expediente:
            return JsonResponse({
                "message": "Faltan parámetros requeridos",
                "content": None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        response_json = siaf_buscar_devengado(ano_eje, expediente)
        
        if not response_json:
            return JsonResponse({
                "message": "No se encontraron devengados",
                "content": []
            }, status=status.HTTP_200_OK)
        
        devengados_list = []
        for item in response_json:
            secuencia = item.get("secuencia")
            devengado = siaf_buscar_devengado_by_secuencia(ano_eje, expediente, secuencia)            
            devengado["detalle"]["expediente"] = expediente
            devengado["detalle"]["secuencia"] = secuencia
            formatted_devengado = aplicar_formato_devengado(devengado)
            devengados_list.append(formatted_devengado)

        

        return JsonResponse({
            "message": "",
            "content": devengados_list
        })
    

def siaf_buscar_devengado(ano_eje, expediente, secuencia=None):
    try:
        siaf_manager = SIAFTokenManager2()
        access_token = siaf_manager.get_access_token()
        print("*********** access_token ***********", access_token)

        if not access_token:
            raise Exception("No hay tokens almacenados")
        
        
        
        url = f"{URL_SIAF_API}/devengado/devengados?anio={ano_eje}&expediente={expediente}&page=0&page_size=10&sort=-"


        headers = {
            "Authorization": f"Bearer {access_token}",            
        }
        response = requests.get(url, headers=headers)
        response_json = response.json()        
        content_list = response_json.get("content", [])
        
        if content_list and len(content_list) > 0:
            # Tomar el primer elemento de la lista content
            first_item = content_list[0]
            
            # Obtener la lista de contenido del primer item
            contenido_list = first_item.get("contenido", [])
            
            # solo los que fase sea D
            filtered_content = [item for item in contenido_list if item.get("fase") == "D"]
            return filtered_content
        return []






    except Exception as e:
        raise Exception(f"Error al buscar devengados: {e}")
    


def siaf_buscar_devengado_by_secuencia(ano_eje, expediente, secuencia):
    try:
        siaf_manager = SIAFTokenManager2()
        access_token = siaf_manager.get_access_token()

        if not access_token:
            raise Exception("No hay tokens almacenados")
        
        url = f"{URL_SIAF_API}/devengado/devengados/{ano_eje}/{expediente}/{secuencia}"

        headers = {
            "Authorization": f"Bearer {access_token}",            
        }
        response = requests.get(url, headers=headers)
        response_json = response.json()
        return response_json
    except Exception as e:
        raise Exception(f"Error al buscar devengado por secuencia: {e}")
    

def aplicar_formato_devengado(devengado):
    try:

        # este es el formato de entrada
        # {
#     "detalle": {
#         "anio": 2025,
#         "entidad": 301529,
#         "entidadRuc": 20154477374,
#         "correlativo": 1,
#         "entidadDestino": 5000,
#         "entidadDestinoNombre": "MEF - TESORO PÚBLICO",
#         "area": 0,
#         "areaNombre": "MUNICIPALIDAD PROVINCIAL DE PIURA",
#         "tipoOperacion": "N",
#         "tipoOperacionDescripcion": "GASTO - ADQUISICION DE BIENES Y SERVICIOS",
#         "expedienteFinanciamiento": 0,
#         "modalidadCompra": "CA",
#         "modalidadCompraDescripcion": "LEY DE CONTRATACIONES DEL ESTADO",
#         "faseContractual": "P",
#         "faseContractualDescripcion": "PAGO_TOTAL O PAGO A CUENTA",
#         "tipoProcesoSeleccion": "18",
#         "tipoProcesoSeleccionDescripcion": "ADJUDICACION SIN PROCESO",
#         "idContrato": null,
#         "idProceso": null,
#         "ceamOceDetId": null,
#         "ciclo": "G",
#         "cicloDescripcion": "Gasto",
#         "fase": "D",
#         "faseDescripcion": "DEVENGADO",
#         "certificado": 931,
#         "certificadoSecuencia": 2,
#         "proveedorTipoId": "1",
#         "proveedorTipoIdDescripcion": "RUC",
#         "proveedorNumeroDocumento": 10731443853,
#         "proveedorNombre": "VALLADOLID GUTIERREZ DELIA GABRIELA",
#         "entidadReciproca": null,
#         "entidadReciprocaNombre": null,
#         "fuenteFinanc": "1",
#         "rubro": "00",
#         "rubroNombre": "RECURSOS ORDINARIOS",
#         "convenioProyecto": "0",
#         "convenioProyectoDescripcion": "Sin Proyecto",
#         "moneda": "S/.",
#         "monedaDescripcion": "Nuevo Sol",
#         "tipoCambio": 1,
#         "monto": 21000,
#         "montoNacional": 21000,
#         "codDoc": "027",
#         "codDocNombre": "RECIBO POR HONORARIOS PROFESIONALES",
#         "numDoc": "13",
#         "serie": "E001",
#         "fechaDoc": "2025-04-30",
#         "tipoPago": "E",
#         "tipoPagoDescripcion": "EFECTIVO",
#         "tipoRecurso": "0",
#         "tipoRecursoDescripcion": "RECURSOS ORDINARIOS",
#         "viajaBanco": "S",
#         "tipoCompromiso": "11",
#         "tipoCompromisoDescripcion": "MES VIGENTE",
#         "estadoRegistro": "A",
#         "estadoRegistroDescripcion": "APROBADO",
#         "notas": "DEVENGADO O/S Nro 0000485 - SERVICIOS DE UN ASISTENTE TÉCNICO EN MONITOREO DE OBRA PARA LA OBRA  REHABILITACIÓN DE REDES DE AGUA POTABLE Y ALCANTARILLADO EN EL AH ALMIRANTE MIGUEL GRAU I Y II ETAPA- PRIMER ENTREGABLE  DEL DISTRITO DE PIURA POR 180 DÍAS S/ 21,000.00 SEIS ENTREGABLES -CONFORMIDAD CON INFORME N° 900-2025-SGO-GDTYGI/MPP",
#         "tipoRegistro": "N",
#         "codMensa": "0000",
#         "codMensaDescripcion": "NORMAL",
#         "usuario": "02892329",
#         "fecha": "2025-04-30",
#         "totalFase": 21000,
#         "totalFaseSiguiente": 3500,
#         "totalModificaciones": -17500,
#         "totalModificacionesAprobadas": -17500,
#         "saldo": 0,
#         "saldoAprobado": 0,
#         "codDocConformidad": "001",
#         "codDocConformidadDescripcion": "ACTA DE CONFORMIDAD",
#         "numDocConformidad": "730-2025",
#         "fechaDocConformidad": "2025-04-23",
#         "tipoCambioPs": null,
#         "clasificadores": [
#             {
#                 "idClasificador": "ACbcxSj",
#                 "clasificador": "2.6.8 1.4 3",
#                 "clasificadorDescripcion": "GASTO POR LA CONTRATACION DE SERVICIOS",
#                 "monto": 21000,
#                 "montoNacional": 21000,
#                 "secuencia": 0,
#                 "metas": [
#                     {
#                         "secFunc": 23,
#                         "metaNombre": "MEJORAMIENTO DE SISTEMAS DE AGUA POTABLE Y ALCANTARILLADO",
#                         "monto": 21000,
#                         "montoNacional": 21000
#                     }
#                 ]
#             }
#         ]
#     },
#     "modificaciones": [
#         {
#             "correlativo": 2,
#             "tipoRegistro": "C",
#             "tipoRegistroDescripcion": "'REBAJA (T.C. FAVORABLE')",
#             "estadoRegistro": "A",
#             "estadoRegistroDescripcion": "APROBADO",
#             "codDoc": "027",
#             "codDocNombre": "RECIBO POR HONORARIOS PROFESIONALES",
#             "numDoc": "13",
#             "fechaDoc": "2025-04-30",
#             "serie": "E001",
#             "moneda": "S/.",
#             "monedaDescripcion": "Nuevo Sol",
#             "tipoCambio": 1,
#             "monto": -17500,
#             "notas": "POR REBAJA SEGUN RECIBO POR HONORARIO E001-13 POR EL IMPORTE DE S/.3,500.00",
#             "usuario": "02892329",
#             "fecha": "2025-05-05",
#             "hora": "09:38:26",
#             "codMensa": "0000",
#             "codMensaDescripcion": "NORMAL",
#             "clasificadores": [
#                 {
#                     "idClasificador": "ACbcxSj",
#                     "clasificador": "2.6.8 1.4 3",
#                     "clasificadorDescripcion": "GASTO POR LA CONTRATACION DE SERVICIOS",
#                     "monto": -17500,
#                     "montoNacional": -17500,
#                     "secuencia": 0,
#                     "metas": [
#                         {
#                             "secFunc": 23,
#                             "metaNombre": "MEJORAMIENTO DE SISTEMAS DE AGUA POTABLE Y ALCANTARILLADO",
#                             "monto": -17500,
#                             "montoNacional": -17500
#                         }
#                     ]
#                 }
#             ]
#         }
#     ],
#     "saldos": [
#         {
#             "idClasificador": "ACbcxSj",
#             "clasificador": "2.6.8 1.4 3",
#             "clasificadorDescripcion": "GASTO POR LA CONTRATACION DE SERVICIOS",
#             "secuencia": 0,
#             "monto": 7000.00,
#             "montoNacional": 7000.00,
#             "saldo": 0.00,
#             "saldoAprobado": 0.00,
#             "metas": []
#         }
#     ],
#     "acciones": {
#         "anular": false,
#         "ampliar": true,
#         "rebajar": false,
#         "devolver": true,
#         "insertar": false,
#         "rebajaTc": false
#     }
# }

        # este es el formato de salida
        # {
        #     "ANO_EJE": "2025",
        #     "EXPEDIENTE": "0000001854",
        #     "CICLO": "G",
        #     "FASE": "D",
        #     "SECUENCIA": "0002",
        #     "CORRELATIVO": "0001",
        #     "COD_DOC": "027",
        #     "ABREVIATURA": "RECIB. HON. PROF.   ",
        #     "SERIE_DOC": "E001",
        #     "NUM_DOC": "13",
        #     "FECHA_DOC": "2025-04-30",
        #     "FUENTE_FINANC": "00",
        #     "TIPO_RECURSO": "0 ",
        #     "RUC": "10731443853",
        #     "NOMBRE": "VALLADOLID GUTIERREZ DELIA GABRIELA",
        #     "MONTO_NACIONAL": 3500.0,
        #     "GLOSA": "DEVENGADO O/S Nro 0000485 - SERVICIOS DE UN ASISTENTE T+CNICO EN MONITOREO DE OBRA PARA LA OBRA  REHABILITACIËN DE REDESDE AGUA POTABLE Y ALCANTARILLADO EN EL AH ALMIRANTE MIGUELGRAU I Y II ETAPA- PRIMER ENTREGABLE  DEL DISTRITO DE PIURAPOR 180 D-AS S/ 21,000.00 SEIS ENTREGABLES -CONFORMIDAD CONINFORME N¦ 900-2025-SGO-GDTYGI/MPP"
        # }

        detalle = devengado.get("detalle")
        formatted_devengado = {
            "ANO_EJE": detalle.get("anio"),
            "EXPEDIENTE": detalle.get("expediente"),
            "CICLO": detalle.get("ciclo"),
            "FASE": detalle.get("fase"),
            "SECUENCIA": detalle.get("secuencia"),
            "CORRELATIVO": detalle.get("correlativo"),
            "COD_DOC": detalle.get("codDoc"),
            "ABREVIATURA": detalle.get("codDocNombre"),
            "SERIE_DOC": detalle.get("serie"),
            "NUM_DOC": detalle.get("numDoc"),
            "FECHA_DOC": detalle.get("fechaDoc"),
            "FUENTE_FINANC": detalle.get("rubro"),
            "TIPO_RECURSO": detalle.get("tipoRecurso"),
            "RUC": detalle.get("proveedorNumeroDocumento"),        
            "NOMBRE": detalle.get("proveedorNombre"),
            "MONTO_NACIONAL": detalle.get("totalFaseSiguiente"),
            "GLOSA": detalle.get("notas")
        }

        return formatted_devengado
    except Exception as e:
        raise Exception(f"Error al aplicar formato a devengado: {e}")