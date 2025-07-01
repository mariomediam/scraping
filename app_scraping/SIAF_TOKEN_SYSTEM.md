# Sistema de Gestión de Tokens SIAF

## Descripción

Este sistema implementa las mejores prácticas para el manejo de tokens de autenticación de SIAF, incluyendo:

- Almacenamiento seguro en caché
- Refresco automático de tokens
- Prevención de múltiples logins simultáneos
- Validación de expiración de tokens
- Decoradores para endpoints protegidos
- Decodificación de tokens JWT para información detallada

## Características Principales

### 1. Gestión Automática de Tokens
- **Token de Acceso**: Caduca a los 60 minutos (3600 segundos)
- **Token de Refresco**: Caduca a los 30 minutos (1800 segundos)
- **Refresco Automático**: Se refresca 5 minutos antes de expirar
- **Decodificación JWT**: Extrae información real de expiración de los tokens

### 2. Almacenamiento en Memoria
- Los tokens se almacenan en el caché de Django
- Timeout automático basado en la expiración del refresh token
- Limpieza automática cuando expiran

### 3. Prevención de Race Conditions
- Lock de login para evitar múltiples autenticaciones simultáneas
- Timeout de 60 segundos para el lock

### 4. Información Detallada de Tokens
- Decodificación automática de tokens JWT
- Información del usuario (nombre, entidad, roles)
- Tiempos de expiración precisos
- Información de la sesión

## Endpoints Disponibles

### 1. Login SIAF
```
GET /login-siaf
```
Realiza el login a SIAF y obtiene los tokens de acceso y refresco.

**Respuesta exitosa:**
```json
{
    "message": "Login exitoso a SIAF",
    "tokens_obtained": true,
    "access_token_expires_at": 1751037476,
    "refresh_token_expires_at": 1751035676,
    "content": "Por Mario Medina"
}
```

### 2. Estado de Tokens
```
GET /siaf-status
```
Verifica el estado actual de los tokens almacenados.

**Respuesta:**
```json
{
    "tokens_exist": true,
    "access_token_valid": true,
    "refresh_token_valid": true,
    "access_token_expires_at": "2024-01-01T12:00:00",
    "refresh_token_expires_at": "2024-01-01T11:30:00",
    "time_until_access_expires": 3600,
    "time_until_refresh_expires": 1800,
    "content": "Por Mario Medina"
}
```

### 3. Información Detallada de Tokens
```
GET /siaf-token-info
```
Obtiene información detallada decodificada de los tokens JWT.

**Respuesta:**
```json
{
    "access_token_info": {
        "username": "02897041",
        "name": "MARIO ALEXANDER MEDINA MARQUEZ",
        "entidad": "MUNICIPALIDAD PROVINCIAL DE PIURA",
        "unidadejecutora": "301529",
        "roles": ["offline_access", "uma_authorization"],
        "exp": 1751037476,
        "iat": 1751033876,
        "expires_in_seconds": 3600
    },
    "refresh_token_info": {
        "exp": 1751035676,
        "iat": 1751033876,
        "expires_in_seconds": 1800
    },
    "stored_expires_at": {
        "access": 1751037476,
        "refresh": 1751035676
    },
    "current_time": 1751033876,
    "content": "Por Mario Medina"
}
```

### 4. Endpoint Protegido (Ejemplo)
```
GET /siaf-endpoint-example
```
Ejemplo de endpoint que requiere autenticación SIAF. Los tokens se obtienen automáticamente.

**Respuesta:**
```json
{
    "message": "Endpoint protegido accedido exitosamente",
    "tokens_available": true,
    "access_token_preview": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "content": "Por Mario Medina"
}
```

### 5. Limpiar Tokens
```
POST /siaf-clear-tokens
```
Elimina los tokens almacenados del caché.

**Respuesta:**
```json
{
    "message": "Tokens eliminados exitosamente",
    "content": "Por Mario Medina"
}
```

## Uso en Código

### 1. Crear un Endpoint Protegido

```python
from .siaf_token_manager import require_siaf_auth

class MiEndpointSIAF(APIView):
    permission_classes = [AllowAny]
    
    @require_siaf_auth
    def get(self, request, format=None):
        # Los tokens están disponibles en request.siaf_tokens
        tokens = getattr(request, 'siaf_tokens', None)
        
        # Usar el token para hacer llamadas a SIAF
        headers = {
            'Authorization': f'Bearer {tokens["access_token"]}',
            'Content-Type': 'application/json'
        }
        
        # Hacer la llamada al API de SIAF
        # response = requests.get('https://api.siaf.gob.pe/endpoint', headers=headers)
        
        return JsonResponse({
            "message": "Operación exitosa",
            "content": "Por Mario Medina"
        })
```

### 2. Obtener Tokens Manualmente

```python
from .siaf_token_manager import get_valid_siaf_tokens

def mi_funcion():
    tokens = get_valid_siaf_tokens()
    if tokens:
        # Usar los tokens
        access_token = tokens["access_token"]
        # ...
    else:
        # Manejar error
        pass
```

### 3. Verificar Estado de Tokens

```python
from .siaf_token_manager import get_siaf_status

def verificar_tokens():
    status = get_siaf_status()
    if status["tokens_exist"] and status["access_token_valid"]:
        print("Tokens válidos disponibles")
    else:
        print("Necesita hacer login")
```

### 4. Obtener Información del Usuario

```python
from .siaf_token_manager import siaf_token_manager

def obtener_info_usuario():
    tokens = siaf_token_manager.get_tokens()
    if tokens:
        token_info = siaf_token_manager.get_token_info(tokens)
        user_info = token_info["access_token_info"]
        print(f"Usuario: {user_info['name']}")
        print(f"Entidad: {user_info['entidad']}")
        print(f"Roles: {user_info['roles']}")
```

## Configuración

### Constantes Configurables

En `siaf_token_manager.py`:

```python
SIAF_ACCESS_TOKEN_EXPIRY = 60 * 60  # 60 minutos
SIAF_REFRESH_TOKEN_EXPIRY = 30 * 60  # 30 minutos
TOKEN_REFRESH_THRESHOLD = 5 * 60  # 5 minutos antes de expirar
```

### Credenciales

Las credenciales están hardcodeadas en `views.py`. Para producción, se recomienda usar variables de entorno:

```python
import os

username = os.getenv('SIAF_USERNAME', '02897041')
password = os.getenv('SIAF_PASSWORD', 'Yvjv971p@')
```

## Implementación del Refresh de Tokens

El sistema ahora incluye una implementación completa del refresh de tokens:

### Endpoint de Refresh
- **URL**: `https://authorize.mef.gob.pe/auth/realms/mef/protocol/openid-connect/token`
- **Método**: POST
- **Content-Type**: `application/x-www-form-urlencoded`

### Parámetros de Refresh
```python
data = {
    'grant_type': 'refresh_token',
    'refresh_token': refresh_token,
    'client_id': 'jwtClient'
}
```

### Proceso Automático
1. El sistema verifica si el access token está próximo a expirar (5 minutos antes)
2. Si el refresh token es válido, intenta refrescar automáticamente
3. Si el refresh falla, fuerza un nuevo login
4. Los nuevos tokens se almacenan automáticamente en caché

## Mejores Prácticas Implementadas

1. **Separación de Responsabilidades**: La lógica de tokens está separada en su propio módulo
2. **Manejo de Errores**: Logging detallado y manejo de excepciones
3. **Thread Safety**: Lock para evitar múltiples logins simultáneos
4. **Validación de Tokens**: Verificación automática de expiración usando JWT
5. **Decoradores**: Fácil aplicación de autenticación a endpoints
6. **Documentación**: Código bien documentado y ejemplos de uso
7. **Decodificación JWT**: Información precisa de expiración y datos del usuario
8. **Refresh Automático**: Renovación automática de tokens sin intervención manual

## Logging

El sistema incluye logging detallado para debugging:

```python
import logging
logger = logging.getLogger(__name__)

# Los logs incluyen:
# - Obtención de tokens
# - Almacenamiento en caché
# - Validación de tokens
# - Errores de autenticación
# - Refresco de tokens
# - Decodificación JWT
```

## Próximos Pasos

1. **Variables de Entorno**: Mover credenciales a variables de entorno
2. **Tests Unitarios**: Agregar tests para el sistema de tokens
3. **Métricas**: Agregar métricas de uso y rendimiento
4. **Rate Limiting**: Implementar rate limiting para los endpoints
5. **Seguridad**: Implementar validación de firma JWT (opcional) 