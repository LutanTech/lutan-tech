import re

KNOWN_BOTS = {
    'Googlebot': r'googlebot',
    'Bingbot': r'bingbot',
    'Yahoo Slurp': r'slurp',
    'DuckDuckBot': r'duckduckbot',
    'Baiduspider': r'baiduspider',
    'YandexBot': r'yandexbot',
    'Applebot': r'applebot',
    'Twitterbot': r'twitterbot',
    'FacebookExternalHit': r'facebookexternalhit',
    'LinkedInBot': r'linkedinbot',
    'Pinterestbot': r'pinterestbot',
    'AhrefsBot': r'ahrefsbot',
    'SEMrushBot': r'semrushbot',
    'MJ12bot': r'mj12bot',
    'DotBot': r'dotbot',
    'Generic Crawler': r'bot|crawler|spider|curl|wget|python-requests|headless',
}


def detect_bot(user_agent_string):
  if not user_agent_string:
    return False, None

  ua_lower = user_agent_string.lower()

  for bot_label, pattern in KNOWN_BOTS.items():
    if re.search(pattern, ua_lower):
      return True, bot_label

  return False, None