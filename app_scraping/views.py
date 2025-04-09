import re 
import time
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse

from playwright.sync_api import sync_playwright


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


          