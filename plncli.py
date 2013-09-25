import twisted.web.client
import json
import urllib

# getPage Method
cookies = {}

def parseResult(data):
    data = json.loads(data)
    return data

def getPbxPage(page, postdata):
    postdata = urllib.urlencode(postdata)
    d = twisted.web.client.getPage('https://pbx.lorea.org/' + page,
                                   cookies = cookies,
                                   method  = 'POST',
                                   headers = {'Content-Type': 'application/x-www-form-urlencoded', 'Host': 'pbx.lorea.org'},
                                   postdata = postdata,
                                   followRedirect = 0)
    d.addCallback(parseResult)
    return d

def getCredit(user, password):
    d = getPbxPage('login', {'login': user, 'password': password, 'action': 'login_agent'})
    return d

def transferCredit(user_ext, amount):
    d = getPbxPage('credit/transfer', {'user': user_ext, 'credit': amount})
    return d
   
def createCredit(user_ext, amount):
    d = getPbxPage('credit/add', {'user': user_ext, 'credit': amount})
    return d
 
