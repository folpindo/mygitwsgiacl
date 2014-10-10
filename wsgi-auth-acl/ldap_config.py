#! /usr/bin/env python
#coding=utf-8

#ldap(or active directory) server uri
server_uri='ldap://localhost:389'

#use this username to login ldap server,to authentication other user
bind_dn='myldapuser'

#password of "bind_dn"
bind_pw='myldapuserpwd'

#ldap base dn
base_dn='OU=MyAccounts,dc=mygroup,dc=local'
