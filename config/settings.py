# config/settings.py
from pathlib import Path
import os
import sys
from dotenv import load_dotenv

# --- Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# --- .env
load_dotenv(BASE_DIR / '.env')

# Quando empacotado com PyInstaller, os arquivos adicionados via --add-data
# são extraídos em runtime para sys._MEIPASS. Detectamos isso e expomos
# um caminho BUNDLED_DATA para apontar para os templates/static empacotados.
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BUNDLED_DATA = Path(sys._MEIPASS)
else:
    BUNDLED_DATA = BASE_DIR

# --- Básico
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-insecure-change-me')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = [
    "*",
    "localhost",
    "127.0.0.1",
]

# --- Apps
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',

    'core',
    'estoque',
    'web',
]

# --- Middleware (CORS no topo)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',     # <- antes de CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.AllowAny",),
}

# Apenas DEV. Em produção restrinja.
CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = 'config.urls'

# --- Templates: incluí caminhos para dev e para o bundle (sys._MEIPASS)
# prioridade: BUNDLED_DATA/templates (quando empacotado) -> BASE_DIR/templates -> BASE_DIR/web/templates
_templates_candidates = [
    BUNDLED_DATA / "templates",            # -> sys._MEIPASS/templates (onefile extraction)
    BASE_DIR / "templates",                # -> projeto raiz/templates/
    BASE_DIR / "web" / "templates",        # -> projeto/web/templates/
]

# transforma em strings e remove duplicatas mantendo ordem
_TEMPLATES_DIRS = []
for p in _templates_candidates:
    sp = str(p)
    if p.exists() and sp not in _TEMPLATES_DIRS:
        _TEMPLATES_DIRS.append(sp)
# se nenhum existir fisicamente, ainda adicionamos os caminhos (útil no exe onde extraction ocorre em runtime)
if not _TEMPLATES_DIRS:
    _TEMPLATES_DIRS = [str(p) for p in _templates_candidates]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': _TEMPLATES_DIRS,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# --- DB (dev)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# --- Passwords
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- I18N
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --- Static
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Pontos adicionais onde o Django procura por arquivos estáticos (dev + bundle)
_static_candidates = [
    BUNDLED_DATA / "static",           # quando empacotado -> sys._MEIPASS/static
    BASE_DIR / "static",               # projeto raiz/static
    BASE_DIR / "web" / "static",       # web/static
]

STATICFILES_DIRS = []
for p in _static_candidates:
    sp = str(p)
    if sp not in STATICFILES_DIRS:
        STATICFILES_DIRS.append(sp)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
