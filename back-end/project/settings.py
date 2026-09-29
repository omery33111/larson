from datetime import timedelta
from pathlib import Path
import os
import sys
from dotenv import load_dotenv



load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
#
# It defaults to OFF, and that direction matters: a deployment that forgets to set anything
# gets the safe value, while a developer who wants tracebacks has to ask for them in .env.
# The other way round, one missing variable serves a full traceback - settings, paths and
# fragments of the environment - to anyone who can make a request fail.
DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'

# `manage.py test`. Used in exactly one place - to switch the rate limits off - and named so
# that the one place is obvious.
TESTING = 'test' in sys.argv

# '*' accepts any Host header, which is what makes cache poisoning and password-reset links
# pointed at somebody else's domain possible - the reset mail builds its URL from a request
# in many projects, and a wildcard is what lets that be forged.
ALLOWED_HOSTS = [h.strip() for h in os.environ.get(
    'DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',') if h.strip()]



# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    'authentication',
    'trades',
    'analytics',
    'chat',
    'mentor',
    'usage',
]



REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (

        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),

    # ~~~~~~~~~~ RATE LIMITS
    # The three endpoints that call Claude cost real money per request and are the only ones
    # that can be looped into a bill: a single answer is allowed up to 64k output tokens.
    # Nothing here protects against an attacker in particular - it protects against a retry
    # loop in the client, which is the way this actually happens.
    #
    # Two windows on the AI scope rather than one: an hourly cap that still allows a heavy
    # session, and a daily cap that stops a slow loop from running all night under it.
    # Off while the suite runs. The counters live in a cache that outlives a single test, so
    # left on, the eleventh test to register a user would fail on a limit rather than on what
    # it was checking - and the failure would move around as tests are added. The limits
    # themselves are tested deliberately, in ThrottleTests, by turning them back on.
    'DEFAULT_THROTTLE_RATES': {scope: None for scope in (
        'ai', 'ai-day', 'email', 'login', 'register', 'user', 'anon')} if TESTING else {
        'ai': '40/hour',
        'ai-day': '150/day',

        # Anything that sends mail. Without this, "forgot my password" is a way to have our
        # server deliver mail to an address of the sender's choosing, over and over.
        'email': '5/hour',

        # Credential stuffing, and account creation in bulk.
        'login': '20/hour',
        'register': '10/hour',

        # A floor under everything else, so no endpoint is completely unbounded.
        'user': '1200/hour',
        'anon': '120/hour',
    },

    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ),
}


# ~~~~~~~~~~ HOW MUCH OF THE MODEL ONE TRADER MAY SPEND
# **The rate limits above count requests; this counts what they cost.** One request is not
# one price - and a cap that cannot tell a short question from a long debrief on a large
# resume is a cap that still empties an account.
#
# The unit is `input + 5 x output`, which is the price ratio of the model ($5 vs $25 per
# million), so a unit is a straight stand-in for cost. See usage/budget.py.
#
# **Where the default comes from, measured rather than guessed.** On a 400-trade resume the
# system prompt and statistics document come to about 12,700 characters, which is roughly
# 4,200 input tokens; an ordinary answer runs a few hundred out. That is about 7,200 units,
# or a little under four US cents.
#
#   400,000 units  ~  56 substantial answers  ~  $2.00 per trader per day
#
# **Deliberately more than a heavy day needs.** The most engaged tester - a debrief plus a
# long conversation about it, twice - lands somewhere near twenty answers, and a budget that
# a keen user can reach is a budget that teaches him to hold back. That is the exact
# behaviour this product cannot afford: the mentor only works if he is told everything.
#
# The ceiling that actually bounds the money is the site-wide one below, not this. This one
# only decides how it is shared out.
AI_DAILY_UNITS = int(os.environ.get('AI_DAILY_UNITS', '400000'))

# Rolling, not a reset at midnight: a window with an edge can be spent twice across it, which
# is exactly the shape a runaway loop produces.
AI_BUDGET_WINDOW_HOURS = int(os.environ.get('AI_BUDGET_WINDOW_HOURS', '24'))

# **And a ceiling on the whole site, because the per-trader budget does not bound anything by
# itself.** One trader's dollar a day multiplied by however many people sign up tomorrow is a
# rate, not a limit - and the entire point of having a budget is being able to say the worst
# case out loud.
#
#   4,000,000 units  ~  $20 a day for everybody put together
#
# **This is the number to look at, not the per-trader one.** Whatever ten testers do, and
# however keen any one of them is, the whole site cannot spend more than this in a day. Raise
# it as the number of real users grows; set it to 0 to lift it entirely.
AI_GLOBAL_DAILY_UNITS = int(os.environ.get('AI_GLOBAL_DAILY_UNITS', '4000000'))

# When to say anything at all. **Late on purpose**: the point of the notice is that the wall
# is not a surprise, not that the trader can budget around it - and somebody who ends the day
# at 80% never needed to know a limit existed. See UsageNotice.tsx.
AI_WARN_AT = float(os.environ.get('AI_WARN_AT', '0.90'))

# What the model costs, so the usage report is arithmetic rather than a guess. Per million
# tokens, in US dollars - `claude-opus-5` as of September 2026.
AI_INPUT_PRICE = float(os.environ.get('AI_INPUT_PRICE', '5'))
AI_OUTPUT_PRICE = float(os.environ.get('AI_OUTPUT_PRICE', '25'))


# ~~~~~~~~~~ WHERE THE THROTTLE COUNTERS LIVE
# In memory by default, which is per process: with several workers the effective limit is
# multiplied by the worker count. That is honest for a single-process run and it still stops
# the runaway-loop case, which is what this is for. Setting REDIS_URL makes the counters
# shared and the limits exact; the redis package is only needed if you do.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ['REDIS_URL'],
    } if os.environ.get('REDIS_URL') else {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'larson-throttle',
    }
}



SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(days = 1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days = 90),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 0,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),
}



MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # Back on, and it costs the API nothing: DRF wraps every APIView in `csrf_exempt`, and
    # CSRF is only re-applied by SessionAuthentication - which this project does not use. It
    # is here for the one thing that DOES authenticate with a cookie, **the Django admin at
    # /admin/**, which was reachable in production with no CSRF protection at all.
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, "templates")],
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


# Where the links in outgoing mail point. It is a setting and never built from the incoming
# request: a Host header is attacker-controlled, and a password-reset link built from one is
# how a reset token ends up being delivered to somebody else's server.
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173').rstrip('/')


# ~~~~~~~~~~ CLAUDE API
# Read once at startup, like every other secret. A change to .env only takes effect after
# the server is restarted - runserver keeps the value it loaded.
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')


WSGI_APPLICATION = 'project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))

# SQLite by default, and PostgreSQL the moment POSTGRES_DB is set - a change of environment
# rather than a change of code.
#
# **This is not cosmetic once there is more than one user.** SQLite locks the whole database
# for a write, and this product holds connections open for the length of an answer; two
# people finishing a debrief at the same moment is enough to produce "database is locked".
# The timeout below buys patience, and WAL (see authentication/apps.py) lets reads continue
# during a write, but neither of them makes SQLite a multi-user database.
if os.environ.get('POSTGRES_DB'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['POSTGRES_DB'],
            'USER': os.environ.get('POSTGRES_USER', ''),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': 60,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(PROJECT_DIR, 'mydatabase.db'),
            # Wait for a writer to finish instead of failing immediately.
            'OPTIONS': {'timeout': 20},
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
MEDIA_URL = '/media/'


STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]


MEDIA_ROOT = BASE_DIR / 'static/files'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ------------------------- CORS -------------------------
# Wide open in development, and an explicit list everywhere else. `CORS_ALLOW_ALL_ORIGINS`
# in production lets any site on the internet make credentialed calls to this API with a
# token it has managed to read.
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
        'CORS_ALLOWED_ORIGINS', FRONTEND_URL).split(',') if o.strip()]


# ------------------------- MAIL -------------------------
# Two things need it and both are account safety: verifying an address at sign-up, and
# resetting a forgotten password.
#
# With no host configured the console backend prints the message to the terminal, so the
# whole flow can be developed and tested without an account anywhere. Set EMAIL_HOST and it
# switches to real delivery - nothing else changes.
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')

if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
    EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Larson <no-reply@larson.local>')

# How long a password-reset link and a verification link stay good. Long enough to survive a
# mail client that delays delivery, short enough that a link sitting in an old inbox is not a
# standing key to the account.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24


# ------------------------- HTTPS, ONCE IT IS NOT DEBUG -------------------------
# All of these are no-ops behind plain HTTP in development, which is why they are switched on
# by the same flag rather than by a second one somebody has to remember.
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'


# ------------------------- SIGNING IN WITH GOOGLE -------------------------
# Inert until this is set, exactly like the mail server and the error monitor: the button does
# not render and the endpoint says so plainly, rather than half-working.
#
# It is a public value - it travels to the browser and is meant to - and it is the `aud` every
# incoming Google token is checked against. **That check is the whole point of it being here:**
# a token minted for somebody else's site is a perfectly valid Google token, and without the
# audience check their login would be ours.
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')


# ------------------------- ERROR MONITORING -------------------------
# Off unless SENTRY_DSN is set, exactly like the mail server: the code is wired and inert
# until somebody supplies the one value that turns it on.
#
# **Why it is not optional once real people are using this.** A failure inside a streaming
# answer is invisible without it: the response headers have already gone out, the browser
# gets a truncated body with no explanation, and the trader has no idea what to report. The
# console log below is only read by whoever happens to be looking at the console.
#
# **`send_default_pii` is off, and that is a decision rather than a default.** This product
# holds somebody's trading record; an error report that quietly carried a request body would
# ship exactly the thing the privacy policy promises stays here. Cookies, headers and bodies
# are all withheld - what goes is the traceback and where it happened.
#
# **The DSN does not have to be Sentry's.** What is wired here is the Sentry SDK, and its
# protocol is spoken by other servers too - GlitchTip hosts it free, Bugsink runs it in one
# container - so switching vendor is this one value and no code. On a small free quota set
# SENTRY_TRACES_RATE=0: performance samples are counted as events there, and they would eat
# the allowance that the errors need.
#
# NOTE: switching this on means a third party processes technical error reports, and the
# privacy policy should say so before it is used in production.
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')

# **Never under `manage.py test`.** The suite stages failures on purpose - a stream that dies
# mid-answer, a file the parser cannot read - and every one of them is logged, which the SDK
# turns into an event. Left on, a single test run spends the monthly allowance on failures
# that were scripted, and mails about them.
if SENTRY_DSN and not TESTING:
    import sentry_sdk

    sentry_sdk.init(
        dsn = SENTRY_DSN,
        environment = os.environ.get('SENTRY_ENVIRONMENT', 'production'),

        send_default_pii = False,
        max_request_body_size = 'never',

        # A sample of traffic rather than all of it, because performance data is a nice to
        # have and the free tier is not large.
        traces_sample_rate = float(os.environ.get('SENTRY_TRACES_RATE', '0.05')),
    )


# ------------------------- LOGGING -------------------------
# Without this, a failure inside a streaming response is invisible: the headers are already
# out, the client sees a truncated body, and nothing is written down anywhere. Errors go to
# the console at WARNING and above, which is what a host collects.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'larson': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
