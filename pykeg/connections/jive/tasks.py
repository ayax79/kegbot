"""Celery tasks for Jive."""

from pykeg.connections import common
from pykeg.core import models as core_models
from kegbot.util import kbjson
from celery.task import task
from django.contrib.sites.models import Site
import urllib2

logger = common.get_logger(__name__)

DEFAULT_SYSTEM_SESSION_JOINED_TEMPLATE = "%(name)s is having a drink on %(kb_name)s! %(kb_url)s"
DEFAULT_SYSTEM_DRINK_POURED_TEMPLATE = "%(name)s just poured %(drink_size)s of %(beer_name)s on %(kb_name)s! %(drink_url)s"
PLACE_HOLDER_IMAGE = "http://www.beer100.com/images/beermug.jpg"
JIVE_USERNAME = "admin"
JIVE_PASSWORD = "admin"

@task
def post_activity(event):
    if common.is_stale(event.time):
        logger.info('Event is stale, ignoring: %s' % str(event))
        return
    if event.kind not in ('session_joined', 'drink_poured'):
        logger.info('Event is not tweetable: %s' % event.kind)
        return
    kb_vars = _get_vars(event)
    do_post(event, kb_vars)


def do_post(event, kb_vars):
    """Sends the activity to the jive instance"""
    user = event.user
    if not user:
        logger.info('No user for this event no jive activity post is possible')
        return

    kind = event.kind
    post = None
    if kind == 'session_joined':
        post = DEFAULT_SYSTEM_SESSION_JOINED_TEMPLATE % kb_vars
    elif kind == 'drink_poured':
        post = DEFAULT_SYSTEM_DRINK_POURED_TEMPLATE % kb_vars

    json = kbjson.dumps(build_model(user, post, kb_vars))


    url = build_url()
    password_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
    password_mgr.add_password(None, url, JIVE_USERNAME, JIVE_PASSWORD)
    auth_handler = urllib2.HTTPBasicAuthHandler(password_mgr)
    opener = urllib2.build_opener(auth_handler)
    urllib2.install_opener(opener)
    f = urllib2.urlopen(url, json)
    response = f.read()
    logger.info("jive response %s" % str(response))


def build_model(user, desc, kb_vars):
    action = {'name': 'posted', 'description': 'kegbot update'}
    actor = {'name': user.username, 'email': user.email}
    object = {'type': 'website',
              'url': kb_vars['drink_url'],
              'image': PLACE_HOLDER_IMAGE,
              'title': desc,
              'description': desc}
    return {'activity': {'action': action, 'actor': actor, 'object': object}}


def _get_vars(event):
    base_url = 'http://%s/%s' % (Site.objects.get_current().domain, event.site.url())
    name = ''
    if event.user:
        name = event.user.username
    session_url = ''
    drink_url = ''

    if event.drink:
        session_url = '%s/%s' % (base_url, event.drink.session.get_absolute_url())
        drink_url = event.drink.ShortUrl()

    beer_name = ''
    if event.drink.keg and event.drink.keg.type:
        beer_name = event.drink.keg.type.name

    drink_size = ''
    if event.drink:
        drink_size = '%.1foz' % event.drink.Volume().InOunces()

    kbvars = {
        'kb_name': event.site.settings.title,
        'name': name,
        'kb_url': base_url,
        'drink_url': drink_url,
        'session_url': session_url,
        'drink_size': drink_size,
        'beer_name': beer_name,
    }
    return kbvars

def build_url():
    jive_url = "http://d4nim4l.pdx.jiveland.com:8080"
    external_stream_id = 1027
    params = {"jive_url": jive_url, "external_stream_id": external_stream_id}
    api_url = "%(jive_url)/api/jivelinks/v1/extstreams/%(external_stream_id)/activities"
    return api_url % params
