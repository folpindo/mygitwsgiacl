#! /usr/bin/env python
#coding=utf-8

import os

GIT_AUTH_DIR_PATH = os.path.dirname(__file__)
GIT_ACL_INI_FILE_PATH = "%s/gitldapacl.ini" % GIT_AUTH_DIR_PATH

import urlparse
import sys; sys.path.insert(0, GIT_AUTH_DIR_PATH)
import ldap_config,ldap_login

def __init_ldap():
  if not globals().has_key('__authen_ldap_authenticator'):
    global __authen_ldap_authenticator
    __authen_ldap_authenticator = ldap_login.LDAPAuth(
        server_uri= ldap_config.server_uri,
        bind_dn= ldap_config.bind_dn,
        bind_pw= ldap_config.bind_pw,
        base_dn= ldap_config.base_dn,
        scope=2,
        referrals=0,
        search_filter='(sAMAccountName=%(username)s)',
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
    )

def ini2acl_dict(fp):
    import dict4ini
    ini = dict4ini.DictIni(fp)
    acldict = {}
    groups = ini.groups
    for config_name, value in ini.ordereditems(ini):
        if config_name[-1:]==":":
            repo_name = config_name[:-1]
            for role in value:
                if role[0]=="@":
                    groupname = role[1:]
                    if groups.has_key(groupname):
                        for user in groups[groupname]:
                            if not acldict.has_key(repo_name):
                                acldict[repo_name] = {}
                            acldict[repo_name][user]=value[role]
                else:
                    if not acldict.has_key(repo_name):
                        acldict[repo_name] = {}
                    acldict[repo_name][role]=value[role]
                    
    return acldict,ini

def __init_acl():
    global __acldict,__configini
    __acldict,__configini = ini2acl_dict(GIT_ACL_INI_FILE_PATH)

def uri_can_access_by_user(uri,user):
    uri_prefix = __configini.common.uri_prefix
    uri_prefix_len = len(uri_prefix)
    
    uri_prefix_gitweb = __configini.common.uri_prefix_gitweb
    uri_prefix_gitweb_len = len(uri_prefix_gitweb)
    
    if uri[0:uri_prefix_len]==uri_prefix:
        uri_strip = uri[uri_prefix_len:]
        repo_name = uri_strip.split("/")[0]
        need_write_access = (uri_strip.find("git-receive-pack")!=-1)
    elif uri[0:uri_prefix_gitweb_len]==uri_prefix_gitweb:
        uresult = urlparse.urlparse(uri)
        qresult = urlparse.parse_qs(uresult.query)
        if qresult.has_key("p"):
            repo_name = qresult["p"][0]
            need_write_access = False
        else:
            return True
    else:
        return False
    
    if need_write_access:
        try:
            have_w_permission = __acldict[repo_name][user].find("w")!=-1
            #if not have_w_permission:
            #    print("%s have no write permission with %s"%(user,uri))
            return have_w_permission
        except KeyError,e:
            print("%s have no write permission with %s"%(user,uri))
            return False
    else:
        try:
            have_r_permission =  __acldict[repo_name][user].find("r")!=-1
            #if not have_r_permission:
            #    print("%s have no read permission with %s"%(user,uri))
            return have_r_permission
        except KeyError,e:
            print("%s have no read permission with %s"%(user,uri))
            return False
        
    print("should not be here!")
    return False


def check_password(environ, user, password):
    from passlib.apache import HtpasswdFile
    import ConfigParser
    
    pathdir = os.path.dirname(os.path.realpath(__file__))
    gitaclfile = "%s/gitldapacl.ini" % pathdir
    #print gitaclfile
    config = ConfigParser.ConfigParser()
    config.read(gitaclfile)

    users_str = config.get("local_users","users")
    htpwdfile = config.get("local_users","passwd_file")

    users_lst = users_str.split(',')
    ht = HtpasswdFile(htpwdfile)
    users = []

    for u in users_lst:
      u = u.strip()
      users.append(u)

    if user in users:
        if ht.verify(user,password):
            allowed = False
            __init_acl()
            #print "Verified user account %s." % user
            allowed = uri_can_access_by_user(environ['REQUEST_URI'],user)
            #if allowed:
            #    print "Can access by user."
            return allowed
        else:
	    return False

    __init_ldap()
    __init_acl()

    if __authen_ldap_authenticator.login(user,password):
        return uri_can_access_by_user(environ['REQUEST_URI'],user)
    return False
