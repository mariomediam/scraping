# Usamos una imagen oficial de Python (ajusta la versión según tus necesidades)
FROM python:3.13.2

# Evitar que Python genere archivos .pyc y asegurar salida sin buffering
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Definir el directorio de trabajo en el contenedor
WORKDIR /app

# Copiar el archivo de dependencias al contenedor
COPY requirements.txt /app/

# Actualizar pip e instalar las dependencias
RUN pip install --upgrade pip && pip install -r requirements.txt

RUN playwright install
RUN playwright install-deps

RUN echo "192.168.100.59 sistemasmpp" >> /etc/hosts

# Copiar el resto del código de la aplicación
COPY . /app/

# Exponer el puerto 8000 para acceder a Django
EXPOSE 8000

# Comando por defecto para iniciar el servidor de desarrollo de Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
