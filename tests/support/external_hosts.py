"""Which outside hosts a page of the portal may name, and which it may not.

The rule lives apart from the check that applies it. The smoke check runs against
the deployed portal and is kept out of the ordinary suite, because a test that
fails on somebody else's network stops being read; a rule that only ever runs
there is a rule nobody exercises. So the deciding is here, where the fast suite
can break it on purpose and see that it complains.

**The rule.** The portal renders itself. Its fonts and styles are built in
deliberately: reaching an external one makes the portal hostage to another
platform's availability and reports the reader to a third party.

**The one exception, and its grounds.** A visit counter is loaded from
`mc.yandex.ru`. It was added deliberately, in the commit "Count the visits,
including the ones that load no document", because the portal has no server of
its own to count from: it is static files, and a reader who opens a data file
directly leaves no other trace. The exception is written down here rather than
left as a failing check, because a check that is known to fail teaches everyone
to ignore it, and the next genuine breach would go unread with it.

What the exception does not license: any other host, and any other name that
merely begins with this one. The comparison is by host and not by the prefix of
an address, so `mc.yandex.ru.example.com` is a stranger like any other.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

#: The portal's own host. The same address stands in render.yaml.
PORTAL_HOST = "ragworld.org"

#: The visit counter, the one outside host the page may name. See the grounds in
#: the module's own description.
COUNTER_HOST = "mc.yandex.ru"

ALLOWED_HOSTS: tuple[str, ...] = (PORTAL_HOST, COUNTER_HOST)

#: Addresses are taken from the two attributes that make a browser fetch
#: something while it renders.
_ADDRESS = re.compile(r'(?:src|href)="(https?://[^"]+)"')


def stray_hosts(html: str, allowed: tuple[str, ...] = ALLOWED_HOSTS) -> list[str]:
    """The addresses in the markup that point at a host outside the allowed set.

    Returns the addresses rather than the hosts: a reader of the failure needs to
    see what exactly the page would fetch.
    """
    permitted = {host.lower() for host in allowed}
    stray: list[str] = []
    for address in _ADDRESS.findall(html):
        # By host, not by the prefix of the address. A prefix comparison lets
        # `https://mc.yandex.ru.example.com/x` through, and a rule that can be
        # walked around by adding a dot is not a rule.
        host = (urlsplit(address).hostname or "").lower()
        if host not in permitted:
            stray.append(address)
    return stray
