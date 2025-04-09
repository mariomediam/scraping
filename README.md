## Inicia un contenedor vacio para que luego se pueda ingresar en el e instalar lo que se desee

'''
docker compose up --build
'''

### Construye la imagen:
'''
docker-compose build
'''

### Crea el proyecto dentro del contenedor:
'''
docker-compose run web django-admin startproject scraping .
'''

### Levanta el contenedor para ejecutar el proyecto:
'''
docker-compose up
'''

### Ejecutar dentro del contenerdor:
'''
pip install djangorestframework
pip install pytest-playwright
playwright install
playwright install-deps
pip freeze > requirements.txt
'''
