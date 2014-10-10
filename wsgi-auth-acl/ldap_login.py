#! /usr/bin/env python
#coding=utf-8

"""
    MoinMoin - LDAP / Active Directory authentication

    This code only creates a user object, the session will be established by
    moin automatically.

    python-ldap needs to be at least 2.0.0pre06 (available since mid 2002) for
    ldaps support - some older debian installations (woody and older?) require
    libldap2-tls and python2.x-ldap-tls, otherwise you get ldap.SERVER_DOWN:
    "Can't contact LDAP server" - more recent debian installations have tls
    support in libldap2 (see dependency on gnutls) and also in python-ldap.

    TODO: allow more configuration (alias name, ...) by using callables as parameters

    @copyright: 2006-2008 MoinMoin:ThomasWaldmann,
                2006 Nick Phillips
    @license: GNU GPL, see COPYING for details.
"""

try:
    import ldap
except ImportError, err:
    print("You need to have python-ldap installed (%s)." % str(err))
    raise

DEBUG = False

if DEBUG:
    def log(s):
        print s
else:
    def log(s):
        pass

class LDAPAuth():
    """ get authentication data from form, authenticate against LDAP (or Active
        Directory), fetch some user infos from LDAP and create a user object
        for that user. The session is kept by moin automatically.
    """

    login_inputs = ['username', 'password']
    logout_possible = True
    name = 'ldap'

    def __init__(self,
        server_uri='ldap://localhost',
        bind_dn='',
        bind_pw='',
        base_dn='',
        scope=ldap.SCOPE_SUBTREE,
        referrals=0,
        search_filter='(uid=%(username)s)',
        givenname_attribute=None,
        surname_attribute=None,
        aliasname_attribute=None,
        email_attribute=None,
        email_callback=None,
        coding='utf-8',
        timeout=10,
        start_tls=0,
        tls_cacertdir='',
        tls_cacertfile='',
        tls_certfile='',
        tls_keyfile='',
        tls_require_cert=0,
        bind_once=False,
        ):
        self.server_uri = server_uri
        self.bind_dn = bind_dn
        self.bind_pw = bind_pw
        self.base_dn = base_dn
        self.scope = scope
        self.referrals = referrals
        self.search_filter = search_filter

        self.givenname_attribute = givenname_attribute
        self.surname_attribute = surname_attribute
        self.aliasname_attribute = aliasname_attribute
        self.email_attribute = email_attribute
        self.email_callback = email_callback

        self.coding = coding
        self.timeout = timeout

        self.start_tls = start_tls
        self.tls_cacertdir = tls_cacertdir
        self.tls_cacertfile = tls_cacertfile
        self.tls_certfile = tls_certfile
        self.tls_keyfile = tls_keyfile
        self.tls_require_cert = tls_require_cert

        self.bind_once = bind_once

    def login(self, username, password):

        if not password:
            return False

        try:
            try:
                u = None
                dn = None
                coding = self.coding
                ldap.set_option(ldap.OPT_PROTOCOL_VERSION, ldap.VERSION3)
                ldap.set_option(ldap.OPT_REFERRALS, self.referrals)
                ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, self.timeout)

                if hasattr(ldap, 'TLS_AVAIL') and ldap.TLS_AVAIL:
                    for option, value in (
                        (ldap.OPT_X_TLS_CACERTDIR, self.tls_cacertdir),
                        (ldap.OPT_X_TLS_CACERTFILE, self.tls_cacertfile),
                        (ldap.OPT_X_TLS_CERTFILE, self.tls_certfile),
                        (ldap.OPT_X_TLS_KEYFILE, self.tls_keyfile),
                        (ldap.OPT_X_TLS_REQUIRE_CERT, self.tls_require_cert),
                        (ldap.OPT_X_TLS, self.start_tls),
                        #(ldap.OPT_X_TLS_ALLOW, 1),
                    ):
                        if value is not None:
                            ldap.set_option(option, value)

                server = self.server_uri
                log("Trying to initialize %r." % server)
                l = ldap.initialize(server)
                log("Connected to LDAP server %r." % server)

                if self.start_tls and server.startswith('ldap:'):
                    log("Trying to start TLS to %r." % server)
                    try:
                        l.start_tls_s()
                        log("Using TLS to %r." % server)
                    except (ldap.SERVER_DOWN, ldap.CONNECT_ERROR), err:
                        log("Couldn't establish TLS to %r (err: %s)." % (server, str(err)))
                        raise

                binddn = self.bind_dn % locals()
                bindpw = self.bind_pw % locals()
                l.simple_bind_s(binddn.encode(coding), bindpw.encode(coding))

                filterstr = self.search_filter % locals()

                attrs = [getattr(self, attr) for attr in [
                                         'email_attribute',
                                         'aliasname_attribute',
                                         'surname_attribute',
                                         'givenname_attribute',
                                         ] if getattr(self, attr) is not None]
                lusers = l.search_st(self.base_dn, self.scope, filterstr.encode(coding),
                                     attrlist=attrs, timeout=self.timeout)

                lusers = [(dn, ldap_dict) for dn, ldap_dict in lusers if dn is not None]
                for dn, ldap_dict in lusers:
                    log("dn:%r" % dn)
                    for key, val in ldap_dict.items():
                        log("    %r: %r" % (key, val))

                result_length = len(lusers)
                if result_length != 1:
                    if result_length > 1:
                        log("Search found more than one (%d) matches for %r." % (result_length, filterstr))
                    if result_length == 0:
                        log("Search found no matches for %r." % (filterstr, ))

                    log("Invalid username or password.")
                    return False

                dn, ldap_dict = lusers[0]
                if not self.bind_once:
                    log("DN found is %r, trying to bind with pw" % dn)
                    l.simple_bind_s(dn, password.encode(coding))
                    log("Bound with dn %r (username: %r)" % (dn, username))
                '''
                if self.email_callback is None:
                    if self.email_attribute:
                        email = ldap_dict.get(self.email_attribute, [''])[0].decode(coding)
                    else:
                        email = None
                else:
                    email = self.email_callback(ldap_dict)

                aliasname = ''
                try:
                    aliasname = ldap_dict[self.aliasname_attribute][0]
                except (KeyError, IndexError):
                    pass
                if not aliasname:
                    sn = ldap_dict.get(self.surname_attribute, [''])[0]
                    gn = ldap_dict.get(self.givenname_attribute, [''])[0]
                    if sn and gn:
                        aliasname = "%s, %s" % (sn, gn)
                    elif sn:
                        aliasname = sn
                aliasname = aliasname.decode(coding)
                '''
                log("ok")
                return True


            except ldap.INVALID_CREDENTIALS, err:
                log("invalid credentials (wrong password?) for dn %r (username: %r)" % (dn, username))
                #return CancelLogin(_("Invalid username or password."))
                log("Invalid username or password.")
                return False

            #return ContinueLogin(u)
            return False

        except ldap.SERVER_DOWN, err:

            log("LDAP server %s failed (%s). "
                          "Trying to authenticate with next auth list entry." % (server, str(err)))
            #return ContinueLogin(user_obj, _("LDAP server %(server)s failed.") % {'server': server})
            return False

        except:
            log("caught an exception, traceback follows...")
            #return ContinueLogin(user_obj)
            return False

if __name__ == '__main__':
    pass
