from datetime import timedelta
from pathlib import Path
import os
import sys

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv



load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

# **Refused at startup rather than at the first request that needs it.** Without this the
# process comes up perfectly happily and fails later, somewhere inside signing - which is to
# say inside password reset links, session tokens and the mail they are sent in.
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is not set. Every signature this product makes depends on it: "
        "session tokens, password-reset links and email verification links.")

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

# Behind a load balancer, one caller does not use the site's name: the balancer's own health
# check is addressed to the instance's private address, because that is what it is talking to.
# Without that address on the list Django answers 400, the balancer reads 400 as a dead
# instance, and it replaces a server that was working perfectly - **the failure looks like a
# crash and is a configuration line.** The address is assigned at boot and is different on
# every instance, so it cannot be written into a variable by hand.
#
# Read only when `RUNNING_ON_EB` says to. The metadata address is not routable off AWS, and an
# unguarded attempt would spend its timeout on every local start and every test run.
if os.environ.get('RUNNING_ON_EB') == '1':
    try:
        import urllib.request

        # IMDSv2: a short-lived token first, then the question. The older unauthenticated form
        # is what made instance metadata reachable through a server-side request forgery.
        token = urllib.request.urlopen(urllib.request.Request(
            'http://169.254.169.254/latest/api/token',
            headers = {'X-aws-ec2-metadata-token-ttl-seconds': '60'},
            method = 'PUT'), timeout = 2).read().decode()

        ALLOWED_HOSTS.append(urllib.request.urlopen(urllib.request.Request(
            'http://169.254.169.254/latest/meta-data/local-ipv4',
            headers = {'X-aws-ec2-metadata-token': token}), timeout = 2).read().decode())

    except Exception:
        # A site that refuses to start is worse than one whose health check complains, and the
        # health check complaining is exactly how this failure announces itself.
        pass



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

    # ~~~~~~~~~~ WHO MAY CALL A VIEW THAT DID NOT SAY
    # DRF's own default is `AllowAny`, which means **a view that forgets its decorator is
    # public** - and every screen in this product is somebody's private trading record. Every
    # view today declares its own and nothing changes for them; what changes is the direction
    # the next one fails in. The handful that are deliberately open say `AllowAny` out loud.
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),

    # ~~~~~~~~~~ WHICH ADDRESS A RATE LIMIT COUNTS AGAINST
    # **Left unset, DRF takes the whole `X-Forwarded-For` header as the caller's identity -
    # and that header is written by the caller.** Sending a different one on every request
    # buys a fresh bucket each time, which walks straight past the login, registration and
    # mail limits. Measured before this line existed: eight wrong passwords in a row, none of
    # them blocked.
    #
    # The number is how many proxies sit in front of this server, so DRF can count back past
    # them to the address that is actually the client's. **0 is the honest default** - it
    # ignores the header entirely and uses the socket address, which is right with no proxy
    # and merely strict behind one. On a host that terminates TLS for you this must be set to
    # 1, or every visitor shares the proxy's address and therefore one bucket.
    'NUM_PROXIES': int(os.environ.get('TRUSTED_PROXY_COUNT', '0')),

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
# **600,000 and not 400,000, because the first number was sized against the wrong prompt.**
# It assumed around 56 answers a day; measured on a real 231-trade resume it bought 13 to 35,
# and the difference is almost entirely thinking. Output is priced at five times input and
# `effort: high` spends it before a word reaches the screen - so an answer that reads as 200
# tokens can bill ten times that. 600,000 is roughly 35 turns in a window, which covers a
# session with room to be curious in it.
AI_DAILY_UNITS = int(os.environ.get('AI_DAILY_UNITS', '600000'))

# Rolling, not a reset at midnight: a window with an edge can be spent twice across it, which
# is exactly the shape a runaway loop produces.
#
# **Six hours and not twenty-four.** A trader who runs out should wait for the next session,
# not for tomorrow - and the per-trader budget was never what bounds the money anyway. Its
# job is to stop one runaway loop, and a loop is stopped just as well by a six-hour ceiling
# as by a daily one. **What a shorter window must not do is quietly multiply the site's
# ceiling**, which is why that one now has a window of its own below.
AI_BUDGET_WINDOW_HOURS = int(os.environ.get('AI_BUDGET_WINDOW_HOURS', '6'))

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

# **A day, always, and deliberately not the trader's window.** The two numbers answer
# different questions: his window decides how long a cap is allowed to punish him, and this
# one is the money. They shared a window until the first was shortened, and sharing it would
# have turned "$20 a day" into "$20 every six hours" - the same $80, with nothing anywhere
# saying it had changed. That is the kind of mistake a budget exists to prevent.
AI_GLOBAL_WINDOW_HOURS = int(os.environ.get('AI_GLOBAL_WINDOW_HOURS', '24'))

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



# **Fifteen minutes, and the number is the security of "log out everywhere".**
#
# Blacklisting reaches refresh tokens only. An access token is a signed bearer with nothing to
# check it against - no database lookup, by design, which is what makes it fast - so from the
# moment it is issued it is good until it expires and there is no way to take it back. At a day
# that meant: the trader presses "disconnect all other sessions", the product tells him it is
# done, and the session on the machine he was worried about keeps working for another 23 hours.
# Measured: the refresh was refused with 401 and the old access token still answered 200.
#
# The same applies to a password reset, which is the moment somebody most believes another
# person is inside the account.
#
# It costs nothing to shorten now: `app/session.ts` renews on its own, and did not exist when
# this was set. It does mean a rotation every fifteen minutes for an active tab, so the
# blacklist table grows faster - `flushexpiredtokens` on a schedule is what keeps that in hand.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes = 15),
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
    # First, so a caller who is not allowed near the admin never reaches a session, a form or
    # a database query. Inert until DJANGO_ADMIN_ALLOWED_IPS is set.
    'project.admin_gate.AdminAllowlist',

    'django.middleware.security.SecurityMiddleware',

    # **The only thing that serves the admin's own CSS once DEBUG is off.** Django stops
    # serving static files itself in production and expects a web server to do it; on a host
    # that gives you one process and no nginx, this is that web server. Directly after the
    # security middleware, which is where it has to be to see every response.
    'whitenoise.middleware.WhiteNoiseMiddleware',

    # **Above CommonMiddleware, which is the only placement that works.** Common answers some
    # requests by itself - a missing trailing slash becomes a redirect - and a response that
    # leaves before this middleware runs carries no CORS headers at all. The browser then
    # reports a CORS failure for a request the server actually handled, which is the most
    # misleading error in the stack to debug.
    'corsheaders.middleware.CorsMiddleware',

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


# **No project-level static directory.** The only static files this backend has are the
# admin's own, and those come from the app that ships them. `back-end/static` existed to hold
# the uploaded files, which now live in `media/` - and a STATICFILES_DIRS entry pointing at a
# folder that is not there makes `collectstatic` warn on every deploy.


# **Outside anything called `static`, and that is the whole point of the name.** These are
# the traders' own exports - the raw record the product promises to keep - and they used to
# sit in `static/files`. Nothing here served them, but the folder was one careless static
# configuration away from handing every uploaded file to anyone who could guess a name, and
# the names are the ones the traders' own computers gave them.
MEDIA_ROOT = BASE_DIR / 'media'

# **The suite writes real files, and the test database is the only thing thrown away.**
# Django isolates the database for a test run and nothing else, so every upload a test made
# landed in the real media directory and stayed there after the rows that pointed at it were
# gone. Found by counting: 265 files on disk against one row in the database.
#
# They are copies of trade exports with nothing pointing at them, which also means neither
# "delete my resume" nor "delete my account" would ever have reached them - those walk the
# rows.
if TESTING:
    import tempfile
    MEDIA_ROOT = Path(tempfile.mkdtemp(prefix = "larson-test-media-"))
STATIC_ROOT = BASE_DIR / 'staticfiles'


# ------------------------- WHERE FILES LIVE -------------------------
# **The uploaded files are the half that matters.** On every host worth using, the disk is
# thrown away on each deploy - so a trader's original export, which this product promises to
# keep as the thing it can re-ingest from, would vanish on the next push. The resume in the
# database would survive and the file behind it would not.
#
# Wired and inert, like the mail server and the error monitor: with no bucket name it stays
# on the local disk and nothing changes. `collectstatic` has to run at deploy either way -
# the manifest backend below refuses to serve a file it has no hash for, which is the point
# of it: a missing asset fails loudly at deploy rather than silently in a browser.
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME', '')

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

if AWS_STORAGE_BUCKET_NAME:
    STORAGES['default'] = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'bucket_name': AWS_STORAGE_BUCKET_NAME,
            'region_name': os.environ.get('AWS_S3_REGION_NAME', ''),
            # **No ACL is sent, and that is the private setting, not the absence of one.**
            # This used to say `'default_acl': 'private'`, which reads like the safer line and
            # is in fact the broken one: a bucket created today defaults to
            # `BucketOwnerEnforced`, where object ACLs are turned off entirely and S3 answers
            # any request carrying an ACL header with `AccessControlListNotSupported`. Every
            # upload would have failed - the first time a trader handed us a file, not in a
            # test.
            #
            # What actually keeps the record private is the bucket: public access is blocked at
            # the account and bucket level, and nothing may grant it per object. That is a
            # stronger guarantee than a per-object ACL, because it cannot be undone one file at
            # a time.
            'querystring_auth': True,
            'file_overwrite': False,
        },
    }

# The suite must not reach for a bucket, whatever the environment says.
if TESTING:
    STORAGES['default'] = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
    STORAGES['staticfiles'] = {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}

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

    # The health check is the one thing that may answer over plain HTTP, and it has to be.
    #
    # A load balancer probes the instance directly, over HTTP and without the
    # `X-Forwarded-Proto` header that tells Django the outside connection was encrypted. With
    # the redirect applying to it, every probe would come back 301 - and a 301 says only that
    # the middleware is alive, not that the application behind it can serve anything. Either
    # the balancer is taught to accept a redirect as health, which makes the check almost
    # meaningless, or the check is allowed to reach the view. This is the second.
    #
    # It gives nothing away: the view touches no database, no model and no authentication, and
    # answers the same three characters to everyone.
    SECURE_REDIRECT_EXEMPT = [r'^healthz/$']
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
    from django.core.exceptions import DisallowedHost

    sentry_sdk.init(
        dsn = SENTRY_DSN,
        environment = os.environ.get('SENTRY_ENVIRONMENT', 'production'),

        send_default_pii = False,
        max_request_body_size = 'never',

        # A sample of traffic rather than all of it, because performance data is a nice to
        # have and the free tier is not large.
        traces_sample_rate = float(os.environ.get('SENTRY_TRACES_RATE', '0.05')),

        # **`DisallowedHost` is not a fault, it is the defence working.** Every scanner on the
        # internet eventually asks the load balancer's bare IP address for a page, Django
        # refuses because that address is not on `ALLOWED_HOSTS`, and the refusal is logged at
        # error level - which mails an alert and spends one of the month's allowance. The
        # answer is never to add the address: it is to stop reporting a rejection that is the
        # intended outcome. A genuine misconfiguration announces itself differently, as the
        # site's own name being refused on every request rather than a stranger's IP once.
        # The class and not its dotted name: string matching here depends on how the SDK
        # spells a type, and a rule that silently stops matching is worse than no rule.
        ignore_errors = [DisallowedHost],
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
